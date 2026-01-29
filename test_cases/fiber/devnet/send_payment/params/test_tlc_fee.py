"""
Test cases for send_payment tlc_fee (routing fee) validation.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, PaymentStatus, TLCFeeRate, Timeout


class TestTlcFee(FiberTest):
    """
    Test TLC routing fee: multi-hop payment fee equals sum of channel fees.
    Topology: fiber0->1->2->3 with tlc_fee_proportional_millionths 1000, 1500, 2000.
    """

    def test_01(self):
        """
        Multi-hop payment fee equals calculate_tx_fee(amount, [1500, 2000]).
        Step 1: Build fiber0->1->2->3 topology with different TLC fees.
        Step 2: Send payment fiber0->fiber3; assert success.
        Step 3: Dry_run and assert fee == calculate_tx_fee(amount, [1500, 2000]).
        Step 4: Send payment with max_fee_amount=fee; assert success.
        """
        # Step 1: Build fiber0->1->2->3 topology with different TLC fees
        for i in range(2):
            self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
            fiber1_fee=1500,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[3],
            Amount.ckb(1000),
            Amount.ckb(1000),
            fiber1_fee=2000,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

        # Step 2: Send payment fiber0->fiber3
        amount = Amount.ckb(1)
        payment_hash = self.send_payment(self.fibers[0], self.fibers[3], amount)
        payment = self.fibers[0].get_client().get_payment({"payment_hash": payment_hash})

        # Step 3: Dry_run and assert fee == calculate_tx_fee
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": self.fibers[3].get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "allow_self_payment": True,
                "udt_type_script": None,
                "dry_run": True,
            }
        )
        expected_fee = self.calculate_tx_fee(amount, [1500, 2000])
        assert int(payment["fee"], 16) == expected_fee

        # Step 4: Send payment with max_fee_amount=fee
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": self.fibers[3].get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "allow_self_payment": True,
                "udt_type_script": None,
                "max_fee_amount": payment["fee"],
            }
        )
        self.wait_payment_state(
            self.fibers[0], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.VERY_LONG
        )
        assert int(payment["fee"], 16) == expected_fee
