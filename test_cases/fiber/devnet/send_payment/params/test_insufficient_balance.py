import time

import pytest

from framework.basic_fiber import FiberTest


class TestInsufficientBalance(FiberTest):
    """
    Tests for the early-fail InsufficientBalance check introduced in:
    https://github.com/nervosnetwork/fiber/pull/1133

    When a payment's amount exceeds the source node's outbound liquidity,
    build_route now returns an InsufficientBalance error immediately
    (before running the routing algorithm).

    - Non-MPP: max(outbound_liquidity across all source channels) < amount
    - MPP: sum(outbound_liquidity across all source channels) < amount
    """

    def test_non_mpp_amount_exceeds_single_channel_outbound(self):
        """
        Non-MPP: source has one channel with outbound liquidity X.
        Sending amount > X should fail early with InsufficientBalance.
        """
        self.open_channel(self.fiber1, self.fiber2, 1200 * 100000000, 120 * 100000000)

        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(2000 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = "max outbound liquidity 120000000000 is insufficient, required amount: 200000000000"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(2000 * 100000000),
                    "keysend": True,
                    "udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )
        expected_error_message = (
            "max outbound liquidity 0 is insufficient, required amount: 200000000000"
        )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_non_mpp_amount_within_capacity_succeeds(self):
        """
        Non-MPP: source has one channel with capacity X.
        Sending amount < X should succeed (no InsufficientBalance).
        """
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        time.sleep(1)

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                "amount": hex(100 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_non_mpp_multiple_channels_amount_exceeds_max(self):
        """
        Non-MPP: source has two channels each with capacity 500.
        Sending 800 (> max single channel 500, but < total 1000) should fail
        early with InsufficientBalance because non-MPP needs the full amount
        to flow through a single channel.
        """
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0)
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0)
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(800 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = "Insufficient balance"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_non_mpp_amount_exceeds_all_channels(self):
        """
        Non-MPP: source has two channels each with capacity 500.
        Sending 1500 (> total 1000) should also fail with InsufficientBalance.
        """
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0)
        self.open_channel(self.fiber1, self.fiber2, 600 * 100000000, 0)
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(1500 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = "max outbound liquidity 60000000000 is insufficient, required amount: 150000000000"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_mpp_total_outbound_insufficient(self):
        """
        MPP: source has two channels each with capacity 500 (total 1000).
        Sending 1500 via MPP should fail with InsufficientBalance because
        the total outbound liquidity (1000) < amount (1500).
        """
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.send_invoice_payment(self.fiber1, self.fiber2, 1500 * 100000000)
        expected_error_message = "total outbound liquidity 100000000000 is insufficient, required amount: 150000000000"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_mpp_individual_channels_insufficient_but_total_enough(self):
        """
        MPP: source has two channels each with capacity 500 (total 1000).
        Sending 800 via MPP should NOT get InsufficientBalance because total
        outbound (1000) >= amount (800), even though no single channel can
        cover the full amount.
        """
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        time.sleep(1)

        # This should not fail with InsufficientBalance
        # (it may succeed or fail for other routing reasons, but not InsufficientBalance)
        self.send_invoice_payment(self.fiber1, self.fiber2, 800 * 100000000)

    def test_non_mpp_dry_run_amount_exceeds_outbound(self):
        """
        Non-MPP with dry_run: amount exceeds outbound liquidity should fail
        with InsufficientBalance even in dry_run mode.
        """
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(2000 * 100000000),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        expected_error_message = "Insufficient balance"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_non_mpp_multi_hop_amount_exceeds_source_outbound(self):
        """
        Non-MPP multi-hop: A -> B -> C
        Source A has one channel to B with capacity 1000.
        Sending 2000 to C should fail with InsufficientBalance at A's outbound
        check, not with "no path found".
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                    "amount": hex(2000 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = "Insufficient balance"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_non_mpp_peer_stopped_returns_insufficient_balance(self):
        """
        When the peer node stops, the channel becomes disabled.
        Outbound liquidity effectively becomes 0.
        Sending any amount should fail with InsufficientBalance.
        """
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        time.sleep(1)

        # Verify payment works before stopping
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                "amount": hex(1 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        # Stop the peer node
        target_pubkey = self.fiber2.get_client().node_info()["pubkey"]
        self.fiber2.stop()
        time.sleep(5)

        # Now sending should fail with InsufficientBalance since channel is disabled
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": target_pubkey,
                    "amount": hex(100 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = (
            "max outbound liquidity 0 is insufficient, required amount: 10000000000"
        )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_mpp_after_spending_outbound_liquidity(self):
        """
        MPP: After spending most of the outbound liquidity through payments,
        trying to send more than remaining total outbound should fail with
        InsufficientBalance.

        Setup: A has two channels to B, each 500 CKB.
        Step 1: Send 400 CKB from A to B (uses one channel).
        Step 2: Send 400 CKB from A to B (uses the other channel).
        Step 3: Try to send 300 CKB via MPP. Total remaining outbound is ~200,
                so it should fail with InsufficientBalance.
        """
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0, 0, 0)
        time.sleep(1)

        # Spend most of the outbound liquidity
        self.send_invoice_payment(self.fiber1, self.fiber2, 800 * 100000000)
        time.sleep(1)

        # Now try sending more than what's remaining via MPP
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                    "amount": hex(300 * 100000000),
                    "keysend": True,
                    "allow_self_payment": True,
                    "max_fee_rate": hex(1000000000000000),
                }
            )
        expected_error_message = "Insufficient balance"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
