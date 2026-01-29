"""
Test cases for send_payment through private channels.
Verifies payment routing a-private-b-c-d-private-a topology.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, TLCFeeRate, Timeout


class TestPrivateChannel(FiberTest):
    """
    Test send_payment through private channel topology: a-private-b-c-d-private-a.
    Verifies payments can route through private channels.
    """

    def test_private_channel(self):
        """
        Test payment through private channel topology a-private-b-c-d-private-a.
        Step 1: Open private channel fiber1-fiber2 and fiber3-fiber0.
        Step 2: Open public channels fiber1-fiber2, fiber2-fiber3, fiber3-fiber0.
        Step 3: Send payments from fiber0 to fiber1, fiber2, fiber3.
        Step 4: Send self-payment from fiber0 to fiber0 (through the loop).
        """
        # Step 1: Start two additional fibers
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        # Open private channel fiber1-fiber2
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Open public channels fiber1-fiber2, fiber2-fiber3, fiber3-fiber0
        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3],
            Amount.ckb(1000), Amount.ckb(1)
        )

        # Open private channel fiber3-fiber0
        self.fibers[3].connect_peer(self.fibers[0])
        time.sleep(Timeout.POLL_INTERVAL)
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: Send payments from fiber0 to fiber1, fiber2, fiber3
        time.sleep(Timeout.POLL_INTERVAL)
        for i in range(1, len(self.fibers)):
            self.send_payment(
                self.fibers[0], self.fibers[i],
                Amount.ckb(1)
            )

        # Step 4: Send self-payment from fiber0 to fiber0 (through the loop)
        self.send_payment(
            self.fibers[0], self.fibers[0],
            Amount.ckb(1)
        )
