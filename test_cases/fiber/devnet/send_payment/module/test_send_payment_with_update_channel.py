"""
Test send_payment with update_channel (e.g. tlc_fee_proportional_millionths) in between.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, TLCFeeRate


class TestSendPaymentWithUpdateChannel(FiberTest):
    """
    Test sending payments while updating channel params (e.g. tlc_fee) between rounds.
    """

    def test_01(self):
        """
        Linear topology 0->1->2->3; send payments; update tlc_fee on channel 1-2; repeat; wait all payments.
        Step 1: Start fiber3, open channels 0-1, 1-2, 2-3.
        Step 2: For 3 rounds: send payments 0->3, update channel 1-2 tlc_fee, send more payments; wait all.
        Step 3: Send one final payment and assert success.
        """
        # Step 1: Build linear topology
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[3],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )

        payment_hashes = []

        # Step 2: Rounds of payments and update_channel
        for j in range(3):
            for _ in range(30):
                try:
                    payment_hash = self.send_payment(
                        self.fibers[0],
                        self.fibers[3],
                        Amount.ckb(1),
                        False,
                        None,
                        0,
                    )
                    payment_hashes.append(payment_hash)
                except Exception:
                    pass

            channels = (
                self.fibers[1]
                .get_client()
                .list_channels({"peer_id": self.fibers[2].get_peer_id()})
            )
            self.fibers[1].get_client().update_channel(
                {
                    "channel_id": channels["channels"][0]["channel_id"],
                    "tlc_fee_proportional_millionths": hex(
                        TLCFeeRate.MEDIUM + (1 + j) * 10000
                    ),
                }
            )

            for _ in range(30):
                try:
                    payment_hash = self.send_payment(
                        self.fibers[0],
                        self.fibers[3],
                        Amount.ckb(1),
                        False,
                        None,
                        0,
                    )
                    payment_hashes.append(payment_hash)
                except Exception:
                    pass

            for payment_hash in payment_hashes:
                self.wait_payment_finished(
                    self.fibers[0], payment_hash, timeout=1200
                )

        # Step 3: Final payment
        self.send_payment(self.fibers[0], self.fibers[3], 1)
