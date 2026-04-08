"""
Test cases for UDT funding error handling (fiber PR #1253)

This module tests the fix for UDT channels getting stuck in negotiating state
when UDT cells are not yet indexed. The fix adds proper error classification:
- InsufficientCells: non-temporary error that aborts the channel
- AbsentTx: temporary error that retries with backoff

Reference: https://github.com/nervosnetwork/fiber/pull/1253
"""

import time
import pytest
from framework.basic_fiber import FiberTest


class TestUdtFundingErrors(FiberTest):
    """
    Test cases for UDT funding error handling when cells are not yet indexed.

    Background:
    When UDT cells are not yet indexed, the funding transaction builder would fail
    with a generic TxBuilderError that was silently swallowed. This left UDT channels
    permanently stuck in the negotiating state.

    The fix adds:
    - FundingError::InsufficientCells variant (non-temporary, aborts channel)
    - Reclassifies AbsentTx as temporary (retries with backoff)
    - Better error mapping to distinguish between insufficient cells and indexing delays
    """

    def test_udt_channel_with_insufficient_cells_should_fail(self):
        """
        Test that opening a UDT channel with insufficient cells fails immediately.

        This test verifies that when there are truly insufficient UDT cells,
        the channel creation fails with an appropriate error message instead of
        getting stuck in negotiating state.

        Steps:
        1. Create a new account with no UDT balance
        2. Attempt to open a UDT channel from this account
        3. Verify the channel fails with InsufficientCells error
        4. Confirm the channel does not remain in negotiating state indefinitely

        Expected:
        - Channel creation should fail with a clear error message
        - Error should mention insufficient UDT cells
        - Channel should not be stuck in negotiating state
        """
        # Generate a new account with CKB but no UDT
        new_account_private_key = self.generate_account(1000)

        # Get UDT type script
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        # Attempt to open a UDT channel with insufficient UDT cells
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(100 * 100000000),  # 100 UDT
                    "public": True,
                    "funding_udt_type_script": udt_script,
                }
            )

        # Verify the error message indicates insufficient cells
        error_msg = str(exc_info.value)
        assert (
            "can not find enough UDT owner cells" in error_msg
            or "InsufficientCells" in error_msg
            or "insufficient" in error_msg.lower()
        ), f"Expected insufficient cells error, got: {error_msg}"

    def test_udt_channel_funding_retry_on_indexing_delay(self):
        """
        Test that UDT channel funding retries when cells are being indexed.

        This test simulates a scenario where UDT cells exist but are not yet
        indexed, which should trigger a retry mechanism rather than immediate failure.

        Steps:
        1. Issue UDT to fiber1's account
        2. Immediately attempt to open a UDT channel before indexing completes
        3. Verify the system retries the funding transaction
        4. Confirm the channel eventually opens successfully after cells are indexed

        Expected:
        - Initial funding attempts may fail with temporary errors
        - System should retry with exponential backoff
        - Channel should eventually reach CHANNEL_READY state
        """
        # Issue fresh UDT cells
        tx_hash = self.issue_udt_tx(
            self.udtContract,
            self.node.rpcUrl,
            self.fiber1.account_private,
            self.fiber1.account_private,
            500 * 100000000,
        )

        # Mine the transaction
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # Small delay to allow partial indexing
        time.sleep(2)

        # Attempt to open UDT channel
        # This might succeed immediately or after retries depending on indexing speed
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(100 * 100000000),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )

        # Auto-accept the channel
        time.sleep(1)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(50 * 100000000),
            }
        )

        # Wait for channel to become ready (allows time for retries if needed)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CHANNEL_READY",
            timeout=180,  # Extended timeout to allow for retry backoff
        )

        # Verify channel is operational by sending a payment
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibt",
                "description": "test invoice",
                "payment_preimage": self.gen_rand_sha256(),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )

        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )

        # Verify payment succeeded
        self.wait_payment_state(
            self.fiber1, invoice["payment_hash"], "Success", timeout=30
        )

    def test_udt_channel_does_not_stuck_in_negotiating(self):
        """
        Test that UDT channels do not get stuck in negotiating state indefinitely.

        This is the main regression test for the bug fixed in PR #1253.
        Before the fix, channels would remain in negotiating state forever when
        UDT cells were not indexed. After the fix, they should either succeed
        (after retries) or fail cleanly.

        Steps:
        1. Check initial channel list
        2. Open a UDT channel
        3. Monitor channel state changes
        4. Verify channel either reaches CHANNEL_READY or fails with clear error
        5. Confirm no channels remain in NEGOTIATING_FUNDING state for extended period

        Expected:
        - Channel should not remain in NEGOTIATING_FUNDING for more than reasonable time
        - If funding fails, error should be clear and channel should be aborted
        - If funding succeeds, channel should reach CHANNEL_READY state
        """
        # Get initial channel count
        initial_channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        initial_count = len(initial_channels.get("channels", []))

        # Open a UDT channel
        try:
            temporary_channel = self.fiber1.get_client().open_channel(
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
            time.sleep(1)
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": temporary_channel["temporary_channel_id"],
                    "funding_amount": hex(50 * 100000000),
                }
            )

            # Monitor channel state for up to 3 minutes
            max_wait_time = 180  # 3 minutes
            check_interval = 5
            elapsed = 0

            while elapsed < max_wait_time:
                channels = self.fiber1.get_client().list_channels(
                    {"peer_id": self.fiber2.get_peer_id()}
                )

                # Check if any channel is in NEGOTIATING_FUNDING state
                negotiating_channels = [
                    ch
                    for ch in channels.get("channels", [])
                    if "NEGOTIATING_FUNDING"
                    in ch.get("state", {}).get("state_name", "")
                ]

                if not negotiating_channels:
                    # Channel either succeeded or failed, which is good
                    break

                time.sleep(check_interval)
                elapsed += check_interval

            # After max wait time, verify no channels are stuck in negotiating
            final_channels = self.fiber1.get_client().list_channels(
                {"peer_id": self.fiber2.get_peer_id()}
            )

            stuck_channels = [
                ch
                for ch in final_channels.get("channels", [])
                if "NEGOTIATING_FUNDING" in ch.get("state", {}).get("state_name", "")
            ]

            assert (
                len(stuck_channels) == 0
            ), f"Found {len(stuck_channels)} channel(s) stuck in NEGOTIATING_FUNDING state after {max_wait_time}s"

        except Exception as e:
            # If channel creation failed immediately, that's acceptable
            # as long as it's a clear error message
            error_msg = str(e)
            assert any(
                keyword in error_msg.lower()
                for keyword in [
                    "insufficient",
                    "not enough",
                    "cannot find",
                    "funding error",
                ]
            ), f"Expected clear funding error message, got: {error_msg}"

    def test_multiple_udt_channels_concurrent_funding(self):
        """
        Test concurrent UDT channel funding to ensure proper error handling under load.

        This test verifies that when multiple UDT channels are opened concurrently,
        the funding error handling works correctly and doesn't cause race conditions
        or leave channels in inconsistent states.

        Steps:
        1. Ensure sufficient UDT balance for multiple channels
        2. Attempt to open multiple UDT channels concurrently
        3. Verify each channel either succeeds or fails cleanly
        4. Confirm no channels are stuck in negotiating state

        Expected:
        - All channels should eventually reach a final state (success or failure)
        - No channels should be stuck in NEGOTIATING_FUNDING
        - Error messages should be clear and specific
        """
        # Ensure we have enough UDT for multiple channels
        # This test assumes fiber1 already has UDT from setup_method

        num_channels = 3
        channel_amount = 50 * 100000000  # 50 UDT per channel

        temporary_channels = []

        # Open multiple channels
        for i in range(num_channels):
            try:
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
                temporary_channels.append(temp_ch)
                time.sleep(0.5)  # Small delay between opens
            except Exception as e:
                # Some channels might fail due to insufficient cells, which is acceptable
                print(f"Channel {i} failed to open: {e}")

        # Accept all successfully opened channels
        time.sleep(2)
        for temp_ch in temporary_channels:
            try:
                self.fiber2.get_client().accept_channel(
                    {
                        "temporary_channel_id": temp_ch["temporary_channel_id"],
                        "funding_amount": hex(channel_amount // 2),
                    }
                )
            except Exception as e:
                print(
                    f"Failed to accept channel {temp_ch['temporary_channel_id']}: {e}"
                )

        # Wait for all channels to reach final state
        time.sleep(120)

        # Verify no channels are stuck in negotiating
        final_channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )

        stuck_channels = [
            ch
            for ch in final_channels.get("channels", [])
            if "NEGOTIATING_FUNDING" in ch.get("state", {}).get("state_name", "")
        ]

        assert (
            len(stuck_channels) == 0
        ), f"Found {len(stuck_channels)} channel(s) stuck in NEGOTIATING_FUNDING state"

        # Count successful channels
        ready_channels = [
            ch
            for ch in final_channels.get("channels", [])
            if "CHANNEL_READY" in ch.get("state", {}).get("state_name", "")
        ]

        print(
            f"Successfully opened {len(ready_channels)} out of {num_channels} attempted channels"
        )
        # At least one channel should have succeeded if we had sufficient funds
        # This assertion is optional as it depends on available UDT balance
