"""
Test cases for add_tlc (other TLC) on channels.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, TLCFeeRate


class OtherTlcTest(FiberTest):
    """
    Test add_tlc RPC: open multiple channels between same pair, add TLC to channel.
    """

    def test_other_tlc(self):
        """
        Open multiple channels between fiber1 and fiber2, add TLC to first channel.
        Step 1: Start fiber3 and open 4 channels between fiber1 and fiber2.
        Step 2: Get first channel_id from list_channels.
        Step 3: Call add_tlc on the channel with amount and expiry.
        """
        # Step 1: Start fiber3 and open 4 channels between fiber1 and fiber2
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0,
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0,
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0,
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0,
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )

        # Step 2: Get first channel_id from list_channels
        channel_id = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]

        # Step 3: Call add_tlc on the channel with amount and expiry
        self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(Amount.ckb(1) + 1),
                "payment_hash": self.generate_random_preimage(),
                "expiry": hex((int(time.time()) + 10) * 1000),
            }
        )
