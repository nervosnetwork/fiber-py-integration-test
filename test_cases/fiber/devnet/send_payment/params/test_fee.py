"""
Test cases for send_payment max_fee_rate / max_fee_amount.
Requirement: https://github.com/nervosnetwork/fiber/pull/1073
"""
import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.constants import (
    Amount,
    ChannelState,
    PaymentFeeRate,
    PaymentStatus,
    TLCFeeRate,
    Timeout,
)
from framework.test_fiber import Fiber


def _parse_fee(fee) -> int:
    """Parse fee field, support hex string or integer."""
    if fee is None:
        return 0
    if isinstance(fee, str) and len(fee) > 2 and fee[:2] == "0x":
        return int(fee, 16)
    return int(fee)


class TestFee(SharedFiberTest):
    """
    Test max_fee_rate / max_fee_amount validation and default behavior for send_payment.
    Requirement: https://github.com/nervosnetwork/fiber/pull/1073
    Topology: fiber1->2->3->4->5->6->7->8, for multi-hop payment and fee validation.
    """

    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber
    fiber7: Fiber
    fiber8: Fiber

    def setUp(self):
        """Initialize multi-hop topology once to avoid rebuilding for each test case."""
        if getattr(TestFee, "_channel_inited", False):
            return
        TestFee._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber6 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber7 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber8 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber3,
            self.fiber4,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber4,
            self.fiber5,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber5,
            self.fiber6,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber6,
            self.fiber7,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fiber7,
            self.fiber8,
            Amount.ckb(1000),
            0,
            fiber1_fee=TLCFeeRate.MEDIUM,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

    @pytest.mark.skip("When only max_fee_amount is set, the value seems to still be 0.05%")
    def test_case1_only_set_max_fee_amount(self):
        """
        When only max_fee_amount is set and > 0.05%, the value seems to still be 0.05%.
        """
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "max_fee_amount": hex(Amount.ckb(100)),
                "dry_run": True,
            }
        )

    @pytest.mark.skip("todo")
    def test_case1_only_set_max_fee_rate(self):
        """
        When only max_fee_rate is set and > 5, the value should be 99.
        """
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "max_fee_rate": hex(99),
                "dry_run": True,
            }
        )

    def test_case1_default_max_fee_rate_when_max_fee_amount_omitted(self):
        """
        Case 1: When max_fee_amount is omitted, FeeLimit = 0.5% × amount (default max_fee_rate=5).
        Step 1: Send dry_run payment without max_fee_amount.
        Step 2: Assert actual fee <= amount * 5 / 1000.
        """
        amount = Amount.ckb(10)
        fee_limit = amount * PaymentFeeRate.DEFAULT // 1000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= fee_limit, (
            f"Case 1: fee {actual_fee} should <= 0.5%×amount={fee_limit}"
        )

    def test_case1_explicit_max_fee_rate_no_max_fee_amount(self):
        """
        Case 1 variant: Explicit max_fee_rate, no max_fee_amount.
        FeeLimit = max_fee_rate/1000 × amount. max_fee_rate=10 means 1%.
        Step 1: Send dry_run payment with max_fee_rate=10.
        Step 2: Assert actual fee <= fee_limit.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.MEDIUM  # 1%
        fee_limit = amount * max_fee_rate // 1000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= fee_limit, (
            f"fee {actual_fee} should <= max_fee_rate×amount/1000={fee_limit}"
        )

    def test_case2_both_provided_rate_tighter_succeeds(self):
        """
        Case 2: When max_fee_rate×amount < max_fee_amount, FeeLimit = max_fee_rate×amount.
        Step 1: Send dry_run with both params; rate is tighter.
        Step 2: Assert fee <= max_fee_rate×amount/1000.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.DEFAULT  # 0.5%
        max_fee_amount = Amount.ckb(100)
        fee_limit = amount * max_fee_rate // 1000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "max_fee_amount": hex(max_fee_amount),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= fee_limit, (
            f"Case 2 (rate tighter): fee {actual_fee} should <= {fee_limit}"
        )

    def test_case2_both_provided_max_fee_amount_tighter_fails(self):
        """
        Case 2: When max_fee_amount < max_fee_rate×amount, FeeLimit = max_fee_amount.
        When max_fee_amount is below actual required fee, should raise error.
        Step 1: Send dry_run with very low max_fee_amount.
        Step 2: Assert error related to fee/route.
        """
        amount = Amount.ckb(1)
        max_fee_rate = PaymentFeeRate.DEFAULT
        max_fee_amount = 100
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_rate": hex(max_fee_rate),
                    "max_fee_amount": hex(max_fee_amount),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed to build route" in err or "max_fee_amount" in err or "Failed" in err
        ), f"Should fail due to max_fee_amount too strict, actual: {err}"

    def test_case2_both_provided_max_fee_amount_tighter_succeeds(self):
        """
        Case 2: max_fee_amount tighter but set to actual required fee; payment should succeed.
        Step 1: Get required fee via dry_run.
        Step 2: Send real payment with max_fee_amount and relaxed max_fee_rate.
        Step 3: Wait for payment success.
        Step 4: Assert actual fee <= max_fee_amount.
        """
        amount = Amount.ckb(1)
        dry = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        required_fee = _parse_fee(dry.get("fee"))
        # 使用略大于 required_fee 的 max_fee_amount，max_fee_rate 设大，使 min 取 max_fee_amount
        max_fee_amount = required_fee + 10000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(PaymentFeeRate.HIGH),
                "max_fee_amount": hex(max_fee_amount),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )
        actual = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert _parse_fee(actual.get("fee")) <= max_fee_amount

    def test_boundary_max_fee_rate_zero_rejects_payment(self):
        """
        Boundary: max_fee_rate=0 should reject payment.
        Step 1: Call send_payment with max_fee_rate=0 (dry_run).
        Step 2: Assert error related to fee/routing.
        """
        amount = Amount.ckb(1)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_rate": hex(0),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), f"max_fee_rate=0 should reject payment, actual: {err}"

    def test_boundary_max_fee_amount_zero_rejects_payment(self):
        """
        Boundary: max_fee_amount=0 should reject payment.
        Step 1: Call send_payment with max_fee_amount=0 (dry_run).
        Step 2: Assert error related to fee/routing.
        """
        amount = Amount.ckb(1)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_amount": hex(0),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), f"max_fee_amount=0 should reject payment, actual: {err}"

    def test_boundary_max_fee_rate_minimum_allows_payment(self):
        """
        Boundary: max_fee_rate=1 (min valid, 0.1%) should allow payment.
        Step 1: Send dry_run with max_fee_rate=1.
        Step 2: Assert fee <= expected limit and >= 0.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.LOW  # 0.1%
        expected_fee_limit = amount * max_fee_rate // 1000  # 10000000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= expected_fee_limit, (
            f"Min rate 1 (0.1%) should allow payment, fee {actual_fee} <= {expected_fee_limit}"
        )
        assert actual_fee >= 0, "Fee should not be negative"

    def test_boundary_max_fee_rate_large_allows_but_limits_effective_fee(self):
        """
        Boundary: Large max_fee_rate (e.g. 1000 = 100%) should allow but actual fee << limit.
        Step 1: Send dry_run with max_fee_rate=1000.
        Step 2: Assert fee <= theoretical limit and << amount.
        """
        amount = Amount.ckb(1)
        max_fee_rate = 1000
        theoretical_fee_limit = amount * max_fee_rate // 1000  # = amount
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= theoretical_fee_limit, (
            f"Large rate should allow, fee {actual_fee} <= {theoretical_fee_limit}"
        )
        assert actual_fee < amount // 10, (
            f"Actual fee {actual_fee} should be << amount {amount}"
        )

    def test_boundary_max_fee_amount_zero(self):
        """
        Boundary: max_fee_amount=0 should reject payment.
        Step 1: Call send_payment with max_fee_amount=0 (dry_run).
        Step 2: Assert error.
        """
        amount = Amount.ckb(1)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_amount": hex(0),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), f"max_fee_amount=0 should fail, actual: {err}"

    def test_boundary_max_fee_amount_equal_to_rate_limit_allows_payment(self):
        """
        Boundary: When max_fee_amount equals max_fee_rate×amount, payment should succeed.
        Step 1: Send dry_run with max_fee_amount = rate_limit.
        Step 2: Assert fee <= expected_rate_limit.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.DEFAULT
        expected_rate_limit = amount * max_fee_rate // 1000
        max_fee_amount = expected_rate_limit  # 刚好等于 rate_limit

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "max_fee_amount": hex(max_fee_amount),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        # 当 max_fee_amount == rate_limit 时，FeeLimit = rate_limit
        assert actual_fee <= expected_rate_limit, (
            f"When max_fee_amount=rate_limit, fee {actual_fee} should <= {expected_rate_limit}"
        )

    def test_boundary_max_fee_amount_above_rate_limit_uses_rate_limit(self):
        """
        Boundary: When max_fee_amount > rate_limit, FeeLimit = rate_limit.
        Step 1: Send dry_run with max_fee_amount > rate_limit.
        Step 2: Assert fee <= rate_limit.
        Step 3: Verify fiber4->fiber7 with max_fee_rate=2 fails.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.DEFAULT
        expected_rate_limit = amount * max_fee_rate // 1000
        max_fee_amount = expected_rate_limit + 10000  # 明显大于 rate_limit

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "max_fee_amount": hex(max_fee_amount),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        # 当 max_fee_amount > rate_limit 时，FeeLimit = rate_limit（更严格的限制）
        assert actual_fee <= expected_rate_limit, (
            f"When max_fee_amount > rate_limit, fee {actual_fee} should <= {expected_rate_limit}"
        )

        payment = self.fiber4.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                # "max_fee_rate": hex(1),
                # "max_fee_amount": hex(max_fee_amount),
                "dry_run": True,
            }
        )
        assert int(payment["fee"], 16) > 1000000

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber4.get_client().send_payment(
                {
                    "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_rate": hex(2),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "route" in err.lower(), f"max_fee_rate too low: {int(payment['fee'], 16)}"

    def test_boundary_max_fee_amount_below_rate_limit_uses_max_fee_amount(self):
        """
        Boundary: When max_fee_amount < rate_limit, FeeLimit = max_fee_amount.
        Step 1: Send dry_run with max_fee_amount < rate_limit.
        Step 2: Assert fee <= max_fee_amount.
        Step 3: Assert max_fee_amount=fee-1 fails.
        """
        amount = Amount.ckb(10)
        max_fee_rate = PaymentFeeRate.DEFAULT
        rate_limit = amount * max_fee_rate // 1000
        max_fee_amount = rate_limit - 10000  # 明显小于 rate_limit，但仍足够支付

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "max_fee_amount": hex(max_fee_amount),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        # 当 max_fee_amount < rate_limit 时，FeeLimit = max_fee_amount（更严格的限制）
        assert actual_fee <= max_fee_amount, (
            f"When max_fee_amount < rate_limit, fee {actual_fee} should <= {max_fee_amount}"
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_rate": hex(max_fee_rate),
                    "max_fee_amount": hex(int(payment["fee"], 16) - 1),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), "When fee > max_fee_amount and fee < max_fee_rate, should still fail"

    def test_boundary_amount_minimum_handles_small_values(self):
        """
        Boundary: amount=1 (min) should handle fee calculation correctly.
        Step 1: Send dry_run with amount=1, max_fee_rate=5.
        Step 2: Assert fee handling (rate_limit may be 0).
        """
        amount = 1
        max_fee_rate = PaymentFeeRate.DEFAULT
        expected_rate_limit = (
            amount * max_fee_rate // 1000
        )  # 对于 amount=1，rate_limit = 0

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        # 对于极小金额，费率限制可能为 0，但实际路由可能仍需基础费用
        # 重要的是系统不应崩溃，且费用不应超过理论限制（如果限制 > 0）
        if expected_rate_limit > 0:
            assert actual_fee <= expected_rate_limit, (
                f"Min amount payment: fee {actual_fee} should <= {expected_rate_limit}"
            )
        else:
            assert actual_fee >= 0, "Fee should not be negative"

    def test_boundary_amount_large_calculates_fee_limit_correctly(self):
        """
        Boundary: Large amount payment should calculate fee limit correctly.
        Step 1: Send dry_run with 100 CKB, max_fee_rate=5.
        Step 2: Assert fee <= 0.5%×amount and << limit.
        """
        amount = Amount.ckb(100)
        max_fee_rate = PaymentFeeRate.DEFAULT
        expected_fee_limit = amount * max_fee_rate // 1000  # 0.5% × 100 CKB = 0.5 CKB

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(max_fee_rate),
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert actual_fee <= expected_fee_limit, (
            f"Large amount: fee {actual_fee} should <= 0.5%×amount={expected_fee_limit}"
        )
        assert actual_fee < expected_fee_limit // 2, (
            f"Large amount: actual fee {actual_fee} should << limit {expected_fee_limit}"
        )

    def test_boundary_fee_exactly_at_limit_succeeds(self):
        """
        Boundary: When actual fee equals max_fee_amount limit, payment should succeed.
        Step 1: Get required fee via dry_run.
        Step 2: Send payment with max_fee_amount = required_fee.
        Step 3: Assert actual fee == exact_limit.
        """
        amount = Amount.ckb(1)
        # 先获取实际需要的费用
        dry_run = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        required_fee = _parse_fee(dry_run.get("fee"))

        # 设置 max_fee_amount 刚好等于实际需要的费用
        exact_limit = required_fee
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(PaymentFeeRate.HIGH),
                "max_fee_amount": hex(exact_limit),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # 验证实际支付的费用等于限制值
        actual_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        actual_fee = _parse_fee(actual_payment.get("fee"))
        assert actual_fee == exact_limit, (
            f"When fee equals limit, actual {actual_fee} should == {exact_limit}"
        )

    def test_boundary_fee_one_below_limit_fails(self):
        """
        Boundary: max_fee_amount = required_fee - 1 should reject payment.
        Step 1: Get required fee via dry_run.
        Step 2: Send with max_fee_amount = required_fee - 1; assert error.
        """
        amount = Amount.ckb(1)
        # 先获取实际需要的费用
        dry_run = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        required_fee = _parse_fee(dry_run.get("fee"))

        # 设置 max_fee_amount 比实际费用少 1
        insufficient_limit = required_fee - 1

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(amount),
                    "keysend": True,
                    "max_fee_rate": hex(PaymentFeeRate.HIGH),
                    "max_fee_amount": hex(insufficient_limit),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), f"Insufficient fee budget should reject, required {required_fee}, limit {insufficient_limit}: {err}"

    def test_boundary_fee_one_above_limit_succeeds(self):
        """
        Boundary: max_fee_amount = required_fee + 1 should allow payment success.
        Step 1: Get required fee via dry_run.
        Step 2: Send with max_fee_amount = required_fee + 1.
        Step 3: Assert payment success and actual fee <= limit.
        """
        amount = Amount.ckb(1)
        # 先获取实际需要的费用
        dry_run = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        required_fee = _parse_fee(dry_run.get("fee"))

        # 设置 max_fee_amount 比实际费用多 1
        sufficient_limit = required_fee + 1

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(PaymentFeeRate.HIGH),
                "max_fee_amount": hex(sufficient_limit),
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # 验证实际支付的费用不超过预算
        actual_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        actual_fee = _parse_fee(actual_payment.get("fee"))
        assert actual_fee <= sufficient_limit, (
            f"Sufficient fee budget should succeed, actual {actual_fee} <= {sufficient_limit}"
        )
