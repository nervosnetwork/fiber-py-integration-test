"""
Test cases for remove_tlc RPC.
Verifies that remove_tlc clears offered/received TLC balance after removing a TLC.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout
from framework.test_fiber import FiberConfigPath


class TestRemoveTlc(FiberTest):
    """
    Test remove_tlc RPC: add TLC then remove with reason, assert balances zero.
    """
    fiber_version = FiberConfigPath.CURRENT_DEV_DEBUG

    def test_remove_tlc_clears_balance(self):
        """
        Add TLC then remove_tlc with reason; offered/received TLC balance should be zero.
        Step 1: Open channel and add TLC on node1.
        Step 2: Remove TLC from node2 with IncorrectOrUnknownPaymentDetails.
        Step 3: Assert offered_tlc_balance and received_tlc_balance are 0x0.
        """
        # Step 1: Open channel and add TLC on node1
        self.open_channel(self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1))

        channel_id = self.fiber1.get_client().list_channels({})["channels"][0]["channel_id"]
        tlc = self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x266cec97cbede2cfbce73666f08deed9560bdf7841a7a5a51b3a3f09da249e21",
                "expiry": hex((int(time.time()) + 3600) * 1000),
            }
        )

        # Step 2: Remove TLC from node2 with reason
        time.sleep(2)
        self.fiber2.get_client().remove_tlc(
            {
                "channel_id": channel_id,
                "tlc_id": tlc["tlc_id"],
                "reason": {"error_code": "IncorrectOrUnknownPaymentDetails"},
            }
        )

        # Step 3: Assert offered/received TLC balance are zero
        time.sleep(2)
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["offered_tlc_balance"] == "0x0"
        assert channels["channels"][0]["received_tlc_balance"] == "0x0"
