"""
Test cases for send_payment tlc_expiry_limit parameter.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, PaymentStatus, Timeout


class TestTlcExpiryLimit(FiberTest):
    """
    Test tlc_expiry_limit parameter: 0x0 rejected (too small);
    >1209600000 rejected (too large); valid values succeed.
    """

    def test_tlc_expiry_limit(self):
        """
        Test tlc_expiry_limit validation and valid values.
        Step 1: Build fiber1->fiber2->fiber3 topology.
        Step 2: Assert tlc_expiry_limit=0x0 rejected (too small).
        Step 3: Assert tlc_expiry_limit=1209600001 rejected (too large).
        Step 4: Send payment with tlc_expiry_limit=86400000*2; assert success.
        Step 5: Send payment with tlc_expiry_limit=1209600000; assert success.
        Step 6: Assert channel balances.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(500)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(500)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Assert tlc_expiry_limit=0x0 rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "dry_run": True,
                    "tlc_expiry_limit": "0x0",
                }
            )
        expected_error_message = "tlc_expiry_limit is too small"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Assert tlc_expiry_limit=1209600001 rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "dry_run": True,
                    "tlc_expiry_limit": hex(1209600001),
                }
            )
        expected_error_message = "tlc_expiry_limit is too large"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 4: Send payment with tlc_expiry_limit=86400000*2
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "tlc_expiry_limit": hex(86400000 * 2),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # Step 5: Send payment with tlc_expiry_limit=1209600000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "tlc_expiry_limit": hex(1209600000),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # Step 6: Assert channel balances
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(int(380.98 * 10**8))
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(20))
