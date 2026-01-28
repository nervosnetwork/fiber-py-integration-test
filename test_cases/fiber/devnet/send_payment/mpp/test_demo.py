"""
Test cases for MPP (Multi-Path Payment) demo: open multiple channels and send invoice payments.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount


class TestMppDemo(FiberTest):
    """
    Test MPP demo: open multiple channels between fiber1 and fiber2, then send invoice payments
    back and forth; assert fiber1 local balance after rounds.
    """

    def test_mpp_demo(self):
        """
        Open three channels with MPP between fiber1 and fiber2; send 10 rounds of invoice
        payments in both directions; assert fiber1 local balance equals total channel capacity.
        Step 1: Open three channels fiber1->fiber2 with semantic amounts.
        Step 2: Send 10 rounds of invoice payment fiber1->fiber2 and fiber2->fiber1.
        Step 3: Assert fiber1 CKB local balance equals 3000 CKB.
        """
        # Step 1: Open three channels fiber1->fiber2 with semantic amounts
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Send 10 rounds of invoice payment fiber1->fiber2 and fiber2->fiber1
        for i in range(10):
            self.send_invoice_payment(
                self.fiber1, self.fiber2,
                Amount.ckb(2100),
            )
            self.send_invoice_payment(
                self.fiber2, self.fiber1,
                Amount.ckb(2100),
            )

        # Step 3: Assert fiber1 CKB local balance equals 3000 CKB
        fiber_balance = self.get_fiber_balance(self.fiber1)
        assert fiber_balance["ckb"]["local_balance"] == Amount.ckb(3000), (
            "fiber1 local balance should be 3000 CKB"
        )
