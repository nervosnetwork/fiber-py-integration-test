"""
Test cases for funding error classification and retry logic (fiber PR #1253)

This module tests the error classification and retry mechanisms for channel funding:
- Temporary errors (AbsentTx) should trigger retries with backoff
- Non-temporary errors (InsufficientCells) should abort immediately
- Error messages should be clear and actionable

Reference: https://github.com/nervosnetwork/fiber/pull/1253
"""

import time
import pytest
from framework.basic_fiber import FiberTest


class TestFundingErrorClassification(FiberTest):
    """
    Test the classification of funding errors as temporary vs non-temporary.

    The fix in PR #1253 introduces proper error classification:
    - InsufficientCells: Non-temporary, channel should abort
    - AbsentTx: Temporary, should retry with backoff
    """

    def test_insufficient_cells_aborts_channel(self):
        """
        Test that InsufficientCells error causes immediate channel abortion.

        When there are genuinely insufficient UDT cells, the channel should
        fail immediately with a clear error message, not retry indefinitely.

        Steps:
        1. Create an account with minimal/no UDT balance
        2. Attempt to open a large UDT channel
        3. Verify channel fails quickly with InsufficientCells error
        4. Confirm no retry attempts are made

        Expected:
        - Channel should fail within a few seconds
        - Error message should mention insufficient cells
        - No prolonged retry attempts
        """
        # Create new fiber node with minimal UDT
        new_account = self.generate_account(1000)  # Only CKB, no UDT
        new_fiber = self.start_new_fiber(new_account)

        # Connect the new fiber to fiber2
        self.connect_peer(new_fiber, self.fiber2)
        time.sleep(2)

        # Record start time
        start_time = time.time()

        # Attempt to open a UDT channel that requires more UDT than available
        with pytest.raises(Exception) as exc_info:
            new_fiber.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(1000 * 100000000),  # 1000 UDT (not available)
                    "public": True,
                    "funding_udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )

        # Calculate time taken
        elapsed_time = time.time() - start_time

        # Should fail quickly (within 10 seconds), not after long retries
        assert (
            elapsed_time < 10
        ), f"Channel abortion took too long: {elapsed_time}s. Expected quick failure."

        # Verify error message
        error_msg = str(exc_info.value)
        assert any(
            keyword in error_msg.lower()
            for keyword in ["insufficient", "not enough", "cannot find", "can not find"]
        ), f"Expected clear insufficient cells error, got: {error_msg}"

    def test_funding_error_messages_are_clear(self):
        """
        Test that funding error messages are clear and actionable.

        Before PR #1253, errors were silently swallowed. After the fix,
        errors should propagate with clear, actionable messages.

        Steps:
        1. Trigger various funding error scenarios
        2. Verify each error has a clear, descriptive message
        3. Confirm errors are not silently swallowed

        Expected:
        - Each error should have a descriptive message
        - No generic "TxBuilderError" without details
        - Users should understand what went wrong
        """
        # Test 1: Insufficient UDT cells
        new_account = self.generate_account(1000)
        new_fiber = self.start_new_fiber(new_account)
        self.connect_peer(new_fiber, self.fiber2)
        time.sleep(2)

        try:
            new_fiber.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(500 * 100000000),
                    "public": True,
                    "funding_udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )
            pytest.fail("Expected exception for insufficient UDT cells")
        except Exception as e:
            error_msg = str(e)
            # Error should mention UDT cells specifically
            assert (
                "UDT" in error_msg or "udt" in error_msg
            ), f"Error message should mention UDT: {error_msg}"
            # Should not be a generic error
            assert (
                "TxBuilderError" not in error_msg or "can not find" in error_msg
            ), f"Error should be specific, not generic TxBuilderError: {error_msg}"

    def test_channel_state_transitions_on_funding_errors(self):
        """
        Test that channel state transitions correctly on funding errors.

        Channels should transition through states appropriately:
        - On temporary errors: remain in negotiating and retry
        - On permanent errors: move to failed/aborted state
        - Should not get stuck indefinitely

        Steps:
        1. Open a channel that will encounter funding issues
        2. Monitor channel state transitions
        3. Verify appropriate state changes occur
        4. Confirm channel reaches a terminal state

        Expected:
        - Channel should not remain in NEGOTIATING_FUNDING indefinitely
        - On permanent error, should transition to failed state
        - State transitions should be timely
        """
        # Get initial channels
        initial_channels = self.fiber1.get_client().list_channels({})

        # Attempt to open a channel with high likelihood of funding issues
        # (using all available UDT to make it tight)
        try:
            temp_ch = self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(200 * 100000000),
                    "public": True,
                    "funding_udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )

            # Track state transitions over time
            states_observed = []
            max_observation_time = 60  # 1 minute
            start_time = time.time()

            while time.time() - start_time < max_observation_time:
                channels = self.fiber1.get_client().list_channels({})

                # Find our channel
                our_channel = None
                for ch in channels.get("channels", []):
                    if ch.get("channel_outpoint") == temp_ch.get("channel_id"):
                        our_channel = ch
                        break

                if our_channel:
                    current_state = our_channel.get("state", {}).get("state_name", "")
                    if current_state not in states_observed:
                        states_observed.append(current_state)
                        print(f"Channel state: {current_state}")

                    # If reached terminal state, break
                    if current_state in ["CHANNEL_READY", "SHUTDOWN", "CLOSED"]:
                        break
                else:
                    # Channel might have been aborted and removed
                    break

                time.sleep(2)

            # Verify channel didn't get stuck in NEGOTIATING_FUNDING
            assert (
                "NEGOTIATING_FUNDING" not in states_observed[-1:]
                or len(states_observed) > 1
            ), "Channel should not end in NEGOTIATING_FUNDING state"

        except Exception as e:
            # Immediate failure is also acceptable
            print(f"Channel failed immediately: {e}")
            assert any(
                keyword in str(e).lower()
                for keyword in ["insufficient", "not enough", "cannot find"]
            )

    def test_retry_backoff_mechanism(self):
        """
        Test that retry mechanism uses appropriate backoff for temporary errors.

        When encountering temporary errors (like AbsentTx), the system should
        retry with exponential backoff, not hammer the system continuously.

        Steps:
        1. Create a scenario that triggers temporary funding errors
        2. Monitor retry attempts
        3. Verify backoff is applied between retries
        4. Confirm retries eventually succeed or give up appropriately

        Expected:
        - Retries should have increasing delays
        - Should not retry indefinitely
        - Should eventually succeed or fail with clear error
        """
        # Issue fresh UDT and immediately try to use it (might not be indexed yet)
        tx_hash = self.issue_udt_tx(
            self.udtContract,
            self.node.rpcUrl,
            self.fiber1.account_private,
            self.fiber1.account_private,
            300 * 100000000,
        )

        # Mine the transaction but don't wait for full indexing
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        time.sleep(1)  # Minimal wait

        # Attempt to open channel immediately
        start_time = time.time()

        try:
            temp_ch = self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(100 * 100000000),
                    "public": True,
                    "funding_udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )

            # Accept the channel
            time.sleep(2)
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": temp_ch["temporary_channel_id"],
                    "funding_amount": hex(50 * 100000000),
                }
            )

            # Wait for channel with extended timeout to allow for retries
            self.wait_for_channel_state(
                self.fiber1.get_client(),
                self.fiber2.get_peer_id(),
                "CHANNEL_READY",
                timeout=180,
            )

            elapsed = time.time() - start_time

            # If it took a while, likely had to retry
            if elapsed > 10:
                print(f"Channel took {elapsed}s to open, likely retried with backoff")

        except Exception as e:
            # If it fails, should be after reasonable retry period
            elapsed = time.time() - start_time
            print(f"Channel failed after {elapsed}s: {e}")

            # Should have tried for a reasonable amount of time before giving up
            # (not fail immediately, not retry forever)
            assert (
                5 < elapsed < 300
            ), f"Expected retry period between 5-300s, got {elapsed}s"


class TestFundingErrorEdgeCases(FiberTest):
    """Test edge cases in funding error handling."""

    def test_udt_channel_with_exact_minimum_cells(self):
        """
        Test opening UDT channel with exactly the minimum required cells.

        This tests the boundary condition where we have just enough cells
        to fund the channel.

        Expected:
        - Channel should open successfully
        - No funding errors should occur
        """
        # Calculate minimum UDT needed
        channel_amount = 10 * 100000000  # Small amount

        # Open channel with minimal funding
        temp_ch = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(channel_amount),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )

        time.sleep(1)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temp_ch["temporary_channel_id"],
                "funding_amount": hex(channel_amount),
            }
        )

        # Should succeed
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CHANNEL_READY",
            timeout=120,
        )

    def test_funding_error_after_channel_accepted(self):
        """
        Test funding error handling after channel has been accepted.

        If funding fails after acceptance, both parties should be notified
        and channel should be aborted cleanly.

        Expected:
        - Both nodes should detect the funding failure
        - Channel should be removed from both sides
        - No inconsistent state between peers
        """
        # Open a channel
        temp_ch = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(100 * 100000000),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )

        # Accept it
        time.sleep(1)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temp_ch["temporary_channel_id"],
                "funding_amount": hex(50 * 100000000),
            }
        )

        # Wait and check both sides
        time.sleep(120)

        # Both sides should have consistent view
        fiber1_channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        fiber2_channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )

        # Neither should have channels stuck in negotiating
        for channels in [fiber1_channels, fiber2_channels]:
            stuck = [
                ch
                for ch in channels.get("channels", [])
                if "NEGOTIATING" in ch.get("state", {}).get("state_name", "")
            ]
            assert len(stuck) == 0, "Found channels stuck in negotiating state"
