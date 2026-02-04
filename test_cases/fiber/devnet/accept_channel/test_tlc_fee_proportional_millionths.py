"""
Test cases for accept_channel tlc_fee_proportional_millionths parameter.
Verifies: channel acceptance with TLC fee proportional rate and payment fee calculation.
"""
import time

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestTlcFeeProportionalMillionths(FiberTest):
    """
    Test accept_channel with tlc_fee_proportional_millionths parameter.
    Verifies: channel can be accepted with custom TLC fee rate, and payment fees are calculated correctly.
    """

    def test_tlc_fee_proportional_millionths(self):
        """
        Test that tlc_fee_proportional_millionths sets the TLC forwarding fee rate.
        Step 1: Open a new channel with fiber1 as the client and fiber2 as the peer.
        Step 2: Accept the channel with fiber2, setting tlc_fee_proportional_millionths to 100% (1 * 100000000).
        Step 3: Wait for the channel state to be CHANNEL_READY.
        Step 4: Open channel fiber3->fiber2 and send payment through fiber3->fiber2->fiber1.
        Step 5: Verify payment fee matches expected calculation.
        """
        # Step 1: Open a new channel with fiber1 as the client and fiber2 as the peer
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Accept the channel with fiber2, setting tlc_fee_proportional_millionths to 100% (1e8 millionths)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(Amount.ckb(1000)),
                "tlc_fee_proportional_millionths": hex(100_000_000),  # 100%
            }
        )

        # Step 3: Wait for the channel state to be CHANNEL_READY
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 4: Open channel fiber3->fiber2 and send payment through fiber3->fiber2->fiber1
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber3, self.fiber2, Amount.ckb(1000), Amount.ckb(1))
        payment_hash = self.send_payment(self.fiber3, self.fiber1, Amount.ckb(0.1))

        # Step 5: Verify payment fee matches expected calculation (100% fee on 0.1 CKB)
        payment = self.fiber3.get_client().get_payment(
            {
                "payment_hash": payment_hash,
            }
        )
        fee = self.calculate_tx_fee(Amount.ckb(0.1), [100_000_000])
        assert int(payment["fee"], 16) == fee
