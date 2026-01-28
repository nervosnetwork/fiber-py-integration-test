"""
Trampoline routing fee-rate tests: dry_run fee, trampoline fee, insufficient fee.
"""

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.constants import Amount, Currency, PaymentFeeRate, PaymentStatus, Timeout
from framework.test_fiber import Fiber


class TestFeeRate(SharedFiberTest):
    """
    Trampoline fee-rate: dry_run returns fee; max_fee_amount caps fee;
    insufficient fee yields route build failure or payment failure.
    Topology: f1->f2->f3->f4, f1->f5->f6 (plus one-way variants).
    """

    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber

    def setUp(self):
        """Initialize topology once: chain f1->2->3->4, branch f1->5->6."""
        if getattr(TestFeeRate, "_channel_inited", False):
            return
        TestFeeRate._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber6 = self.start_new_fiber(self.generate_account(10000))

        for i in range(3):
            self.open_channel(
                self.fibers[i], self.fibers[i + 1],
                fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(1000),
            )
            self.open_channel(
                self.fibers[i], self.fibers[i + 1],
                fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(1000),
                other_config={"public": False, "one_way": True},
            )
        self.open_channel(
            self.fiber1, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            fiber1_fee=6000, fiber2_fee=9000,
        )
        self.open_channel(
            self.fiber5, self.fiber6,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            fiber1_fee=5001, fiber2_fee=7000,
        )

    def test_dry_run(self):
        """
        dry_run returns fee; max_fee_amount caps returned fee.
        Step 1: dry_run without max_fee_amount; assert fee == 500000.
        Step 2: dry_run with max_fee_amount=400000; assert fee == 400000.
        """
        # Step 1: dry_run without max_fee_amount; assert fee
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "dry_run": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        assert payment["fee"] == hex(500000)

        # Step 2: dry_run with max_fee_amount; assert fee
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "dry_run": True,
                "max_fee_amount": hex(400000),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        assert payment["fee"] == hex(400000)

    def test_trampoline_1_path_2(self):
        """
        One trampoline hop, two paths; pay and assert balance change.
        Step 1: send_payment f2->f4 to prepare balances.
        Step 2: Keysend f1->f4 via trampoline; wait success; assert balance deltas.
        """
        # Step 1: send_payment f2->f4
        self.send_payment(self.fiber2, self.fiber4, Amount.ckb(1))
        before_balance = self.get_fibers_balance()

        # Step 2: Keysend f1->f4 via trampoline; wait success; assert balance deltas
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        self.fiber1.get_client().get_payment({"payment_hash": payment["payment_hash"]})
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        assert result[:4] == [
            {"local_balance": 100500000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -400000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -100000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -Amount.CKB, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]

    def test_fee_rate_check_enough(self):
        """
        Insufficient fee: dry_run without max yields route failure; with trampoline dry_run
        returns fee; pay without enough fee fails; pay with max_fee_rate and sufficient
        max_fee_amount succeeds; assert balance change. Second payment same path succeeds.
        Step 1: dry_run to f6 without max_fee; expect route failure.
        Step 2: dry_run with trampoline_hops; assert fee; pay without max_fee; wait Failed.
        Step 3: dry_run with max_fee_rate=10; pay with that fee; wait success; assert result.
        Step 4: Pay again with max_fee_rate and max_fee_amount; wait success; assert result2.
        """
        before_balance = self.get_fibers_balance()

        # Step 1: dry_run to f6 without max_fee; expect route failure
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        assert "Failed to build route" in (exc_info.value.args[0] if exc_info.value.args else ""), (
            "Expected 'Failed to build route' in error."
        )

        # Step 2: dry_run with trampoline_hops; pay without max_fee; wait Failed
        dry = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "dry_run": True,
                "trampoline_hops": [self.fiber5.get_client().node_info()["node_id"]],
            }
        )
        assert dry["fee"] == hex(500000)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber5.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.FAILED,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 3: dry_run with max_fee_rate=10; pay with that fee; wait success; assert result
        dry2 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "dry_run": True,
                "max_fee_rate": hex(PaymentFeeRate.MEDIUM),
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "max_fee_amount": dry2["fee"],
                "max_fee_rate": hex(PaymentFeeRate.MEDIUM),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        assert result == [
            {"local_balance": 100500100, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -500100, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -Amount.CKB, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]

        # Step 4: Pay again with max_fee_rate and max_fee_amount; wait success; assert result2
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "max_fee_rate": hex(PaymentFeeRate.MEDIUM),
                "max_fee_amount": dry2["fee"],
                "trampoline_hops": [self.fiber5.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        after2_balance = self.get_fibers_balance()
        result2 = self.get_channel_balance_change(after_balance, after2_balance)
        assert result2 == [
            {"local_balance": 100500100, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -500100, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -Amount.CKB, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]
