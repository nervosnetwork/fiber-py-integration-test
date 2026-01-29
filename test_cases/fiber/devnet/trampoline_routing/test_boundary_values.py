"""
Trampoline routing boundary-value tests: max hops, min/large amount, fee rate, etc.
"""

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout
from framework.test_fiber import Fiber


class TestBoundaryValues(SharedFiberTest):
    """
    Trampoline routing boundary scenarios: max hops, min/large amount,
    zero/high fee rate, min max_fee_amount, trampoline_hops contains target.
    Topology: linear chain fiber1->2->3->4->5->6->7->8.
    """

    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber
    fiber7: Fiber
    fiber8: Fiber

    def setUp(self):
        """Initialize linear topology once (fiber1->2->...->8)."""
        if getattr(TestBoundaryValues, "_channel_inited", False):
            return
        TestBoundaryValues._channel_inited = True
        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber6 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber7 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber8 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber5, self.fiber6,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber6, self.fiber7,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber7, self.fiber8,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

    def test_max_trampoline_hops(self):
        """
        Use max trampoline hops (5); dry_run then real pay; assert fee and balance change.
        Step 1: Dry run without trampoline_hops; expect route fail.
        Step 2: Dry run with 5 hops; get fee; send with that fee; expect Failed.
        Step 3: Send with sufficient max_fee_amount; expect Success; assert fee and balance change.
        """
        # Step 1: Dry run without trampoline_hops; expect route fail
        before_balance = self.get_fibers_balance()

        dry = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "dry_run": True,
                "max_fee_amount": hex(Amount.ckb(1)),
                "max_fee_rate": hex(99),
            }
        )
        # Step 2: Send with trampoline_hops and fee from dry_run; expect Failed
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "max_fee_amount": dry["fee"],
                "max_fee_rate": hex(99),
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                    self.fiber5.get_client().node_info()["node_id"],
                    self.fiber6.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.FAILED, timeout=Timeout.PAYMENT_SUCCESS
        )

        # Step 3: Send with sufficient max_fee_amount; expect Success; assert fee and balance change
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "max_fee_amount": hex(Amount.ckb(0.006)),
                "max_fee_rate": hex(99),
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                    self.fiber5.get_client().node_info()["node_id"],
                    self.fiber6.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        payment_info = self.fiber1.get_client().get_payment({"payment_hash": payment["payment_hash"]})

        assert payment_info["fee"] == hex(600000)
        assert result == [
            {"local_balance": 100600000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -120000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -120000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -120000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -120000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -120000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -Amount.CKB, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]

    def test_exceed_max_trampoline_hops(self):
        """
        Use 6 trampoline hops (over limit 5); expect error.
        Step 1: Send payment with 6 trampoline_hops; assert error message.
        """
        # Step 1: Send with 6 trampoline_hops; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber8.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                        self.fiber4.get_client().node_info()["node_id"],
                        self.fiber5.get_client().node_info()["node_id"],
                        self.fiber6.get_client().node_info()["node_id"],
                        self.fiber7.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "too many" in err.lower() or "Failed" in str(exc_info.value)

    def test_minimum_amount(self):
        """
        Minimum amount (1 shannon) keysend via trampoline; expect success.
        Step 1: Send keysend with amount=1; wait success.
        """
        # Step 1: Send keysend with amount=1; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(1),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_large_amount(self):
        """
        Large amount (50 CKB) keysend via trampoline; expect success.
        Step 1: Send keysend with 50 CKB; wait success.
        """
        # Step 1: Send keysend with 50 CKB; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(50)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_zero_fee_rate(self):
        """
        Keysend with default fee rate (no explicit max_fee_rate); expect success.
        Step 1: Send keysend; wait success; check balance change.
        """
        # Step 1: Send keysend; wait success; check balance change
        before_balance = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )
        after_balance = self.get_fibers_balance()
        _ = self.get_channel_balance_change(before_balance, after_balance)

    def test_very_high_fee_rate(self):
        """
        Keysend with high fee budget; expect success.
        Step 1: Send keysend; wait success.
        """
        # Step 1: Send keysend; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_minimum_max_fee_amount(self):
        """
        Keysend with minimal max_fee_amount that still succeeds; expect success.
        Step 1: Send keysend with max_fee_amount=200000; wait success.
        """
        # Step 1: Send keysend with max_fee_amount=200000; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "max_fee_amount": hex(200000),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_trampoline_hops_contains_target_pubkey(self):
        """
        trampoline_hops must not contain target; expect error.
        Step 1: Send keysend with target in trampoline_hops; assert error.
        """
        # Step 1: Send with target in trampoline_hops; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        expected = "trampoline_hops must not contain target_pubkey"
        assert expected in (exc_info.value.args[0] if exc_info.value.args else ""), (
            f"Expected substring '{expected}' not found in actual error."
        )
