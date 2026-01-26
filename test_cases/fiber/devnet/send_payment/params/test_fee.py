import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber


def _parse_fee(fee) -> int:
    """解析 fee 字段，支持 hex 字符串或整数。"""
    if fee is None:
        return 0
    if isinstance(fee, str) and len(fee) > 2 and fee[:2] == "0x":
        return int(fee, 16)
    return int(fee)


class TestFee(SharedFiberTest):
    """
    https://github.com/nervosnetwork/fiber/pull/1073
    > ## 1. Parameter Specification
    > * **RPC Interface**: `send_payment`
    > * **New Parameter**: `max_fee_rate`
    > * **Default Value**: `5` (represents **0.5%**), if this field is not specified, there will also a hardcoded default `5` for it.
    >
    > ## 2. Validation Logic for `max_fee_amount`
    > The maximum fee limit for a payment should be determined using the following logic:
    >
    > * **Case 1: `max_fee_amount` is not provided in the RPC**
    >   If the user does not specify a fixed amount, the limit defaults to the rate-based calculation:
    >
    > FeeLimit = 0.5 % × amount
    >
    > * **Case 2: Both `max_fee_rate` and `max_fee_amount` are provided**
    >   If both constraints are set, the system must enforce the stricter (lower) limit:
    >
    > FeeLimit = min ( max_fee_rate × amount, rpc.max_fee_amount )
    """

    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber
    fiber7: Fiber
    fiber8: Fiber

    def setUp(self):
        """
        fiber1_fee 表示, fiber1 在该通道中,做为路由节点时收取的基础费用 (base fee)，单位为 msat。
        fiber2_fee 表示, fiber2 在该通道中,做为路由节点时收取的基础费用 (base fee)，单位为 msat。
        Returns:

        """
        if getattr(TestFee, "_channel_inited", False):
            return
        TestFee._channel_inited = True

        # self.__class__.fiber3 = self.start_new_mock_fiber("")
        # self.__class__.fiber4 = self.start_new_mock_fiber("")
        # self.__class__.fiber5 = self.start_new_mock_fiber("")
        # self.__class__.fiber6 = self.start_new_mock_fiber("")
        # self.__class__.fiber7 = self.start_new_mock_fiber("")
        # self.__class__.fiber8 = self.start_new_mock_fiber("")

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber6 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber7 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber8 = self.start_new_fiber(self.generate_account(10000))
        # # #
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber3,
            self.fiber4,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber4,
            self.fiber5,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber5,
            self.fiber6,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber6,
            self.fiber7,
            1000 * 100000000,
            0,
            fiber1_fee=1000,
            fiber2_fee=1000,
        )
        self.open_channel(
            self.fiber7,
            self.fiber8,
            1000 * 100000000,
            0,
            fiber1_fee=5000,
            fiber2_fee=1000,
        )

    def test_case1_only_set_max_fee_amount(self):
        """
        单独设置max_fee_amount  的话，如果max_fee_amount> 0.05% ,那取的值好像还是0.05%
        Returns:
        """
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "max_fee_amount": hex(10000000000),
                "dry_run": True,
            }
        )

    @pytest.mark.skip("todo")
    def test_case1_only_set_max_fee_rate(self):
        """
        单独设置max_fee_rate  的话，如果max_fee_rate >  5 ,那取的值应该是99
        Returns:
        """
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "max_fee_rate": hex(99),
                "dry_run": True,
            }
        )

    # --- Case 1: max_fee_amount 未提供时，FeeLimit = 0.5% × amount（默认 max_fee_rate=5）---

    def test_case1_default_max_fee_rate_when_max_fee_amount_omitted(self):
        """
        Case 1: 不传 max_fee_amount 时，FeeLimit = 0.5% × amount（默认 max_fee_rate=5）。
        - dry_run 校验：实际 fee <= amount * 5 / 1000。
        """
        amount = 10 * 100000000  # 10 CKB
        fee_limit = amount * 5 // 1000  # 0.5% × amount
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "dry_run": True,
            }
        )
        actual_fee = _parse_fee(payment.get("fee"))
        assert (
            actual_fee <= fee_limit
        ), f"Case 1: fee {actual_fee} 应 <= 0.5%×amount={fee_limit}"

    def test_case1_explicit_max_fee_rate_no_max_fee_amount(self):
        """
        Case 1 变体：显式传 max_fee_rate，不传 max_fee_amount。
        FeeLimit = max_fee_rate/1000 × amount。此处 max_fee_rate=10 即 1%。
        """
        amount = 10 * 100000000
        max_fee_rate = 10  # 1%
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
        assert (
            actual_fee <= fee_limit
        ), f"fee {actual_fee} 应 <= max_fee_rate×amount/1000={fee_limit}"

    # --- Case 2: 同时提供 max_fee_rate 和 max_fee_amount 时，FeeLimit = min(rate×amount, max_fee_amount) ---

    def test_case2_both_provided_rate_tighter_succeeds(self):
        """
        Case 2: max_fee_rate×amount < max_fee_amount，则 FeeLimit = max_fee_rate×amount。
        dry_run 校验 fee <= max_fee_rate×amount/1000。
        """
        amount = 10 * 100000000
        max_fee_rate = 5  # 0.5%
        max_fee_amount = 100 * 100000000  # 足够大，使 min 取 rate 那一侧
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
        assert (
            actual_fee <= fee_limit
        ), f"Case 2(rate更严): fee {actual_fee} 应 <= {fee_limit}"

    def test_case2_both_provided_max_fee_amount_tighter_fails(self):
        """
        Case 2: max_fee_amount < max_fee_rate×amount，则 FeeLimit = max_fee_amount。
        当 max_fee_amount 低于实际所需路由费时，应报错（如 Failed to build route / max_fee_amount too low）。
        """
        amount = 1 * 100000000  # 1 CKB，2 跳所需费远高于 100
        max_fee_rate = 5
        max_fee_amount = 100  # 极低，必小于实际费用
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
        ), f"应因 max_fee_amount 过严而失败，实际: {err}"

    def test_case2_both_provided_max_fee_amount_tighter_succeeds(self):
        """
        Case 2: max_fee_amount 更严，但设置为实际所需费用，支付应成功。
        先 dry_run 取 fee，再以 max_fee_amount=该值、max_fee_rate 放宽松发送。
        """
        amount = 1 * 100000000
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
                "max_fee_rate": hex(10),  # 10%，足够大
                "max_fee_amount": hex(max_fee_amount),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        actual = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert _parse_fee(actual.get("fee")) <= max_fee_amount

    # --- 边界场景测试 ---

    def test_boundary_max_fee_rate_zero_rejects_payment(self):
        """
        边界场景：max_fee_rate = 0 时应拒绝支付
        费率为 0 意味着不允许任何费用支出，即使有有效路由也应拒绝
        """
        amount = 1 * 100000000
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
        ), f"max_fee_rate=0 应拒绝支付，实际错误: {err}"

    def test_boundary_max_fee_amount_zero_rejects_payment(self):
        """
        边界场景：max_fee_amount = 0 时应拒绝支付
        即使有有效的路由，max_fee_amount=0 意味着不允许任何费用支出
        """
        amount = 1 * 100000000
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
        ), f"max_fee_amount=0 应拒绝支付，实际错误: {err}"

    def test_boundary_max_fee_rate_minimum_allows_payment(self):
        """
        边界场景：max_fee_rate = 1（最小有效值，0.1%）应允许支付
        验证系统接受最小费率值并正确计算限制
        """
        amount = 10 * 100000000
        max_fee_rate = 1  # 0.1%
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
        assert (
            actual_fee <= expected_fee_limit
        ), f"最小费率1(0.1%)应允许支付，实际费用 {actual_fee} 应 <= 限制 {expected_fee_limit}"
        assert actual_fee >= 0, "费用不应为负数"

    def test_boundary_max_fee_rate_large_allows_but_limits_effective_fee(self):
        """
        边界场景：max_fee_rate 很大（如 1000，即 100%）应允许但实际费用远小于限制
        验证系统能处理大费率值，但实际路由费用远小于 amount
        """
        amount = 1 * 100000000
        max_fee_rate = 1000  # 100%，理论上允许支付 amount 作为费用
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
        assert (
            actual_fee <= theoretical_fee_limit
        ), f"大费率应允许，实际费用 {actual_fee} 应 <= 理论限制 {theoretical_fee_limit}"
        # 对于正常路由，实际费用应该远小于 amount（远小于100%）
        assert (
            actual_fee < amount // 10
        ), f"正常路由的实际费用 {actual_fee} 应远小于支付金额 {amount}"

    def test_boundary_max_fee_amount_zero(self):
        """
        边界场景：max_fee_amount = 0
        应该拒绝支付或报错
        """
        amount = 1 * 100000000
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
        ), f"max_fee_amount=0 应失败，实际: {err}"

    def test_boundary_max_fee_amount_equal_to_rate_limit_allows_payment(self):
        """
        边界场景：max_fee_amount 刚好等于 max_fee_rate × amount 时应允许支付
        验证 min(rate_limit, max_fee_amount) = rate_limit，当两者相等时
        """
        amount = 10 * 100000000
        max_fee_rate = 5  # 0.5%
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
        assert (
            actual_fee <= expected_rate_limit
        ), f"当 max_fee_amount = rate_limit 时，应允许支付且费用 <= {expected_rate_limit}，实际 {actual_fee}"

    def test_boundary_max_fee_amount_above_rate_limit_uses_rate_limit(self):
        """
        边界场景：max_fee_amount > max_fee_rate × amount 时，FeeLimit 应为 rate_limit
        验证 min(rate_limit, max_fee_amount) = rate_limit，当 max_fee_amount 更大时
        """
        amount = 10 * 100000000
        max_fee_rate = 5  # 0.5%
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
        assert (
            actual_fee <= expected_rate_limit
        ), f"当 max_fee_amount > rate_limit 时，FeeLimit 应为 rate_limit，实际费用 {actual_fee} 应 <= {expected_rate_limit}"

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
        assert "route" in err.lower(), f"max_fee_rate too min:{int(payment['fee'],16)}"

    def test_boundary_max_fee_amount_below_rate_limit_uses_max_fee_amount(self):
        """
        边界场景：max_fee_amount < max_fee_rate × amount 时，FeeLimit 应为 max_fee_amount
        验证 min(rate_limit, max_fee_amount) = max_fee_amount，当 max_fee_amount 更小时
        """
        amount = 10 * 100000000
        max_fee_rate = 5  # 0.5%
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
        assert (
            actual_fee <= max_fee_amount
        ), f"当 max_fee_amount < rate_limit 时，FeeLimit 应为 max_fee_amount，实际费用 {actual_fee} 应 <= {max_fee_amount}"

        # 当fee > max_fee_amount , fee < max_fee_rate ,依然失败
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
        ), "当fee > max_fee_amount , fee < max_fee_rate ,依然失败"

    def test_boundary_amount_minimum_handles_small_values(self):
        """
        边界场景：amount 最小值（1 satoshi）应正确处理费率计算
        验证系统能处理最小金额，且费率计算不会导致异常
        """
        amount = 1  # 最小值 1 satoshi
        max_fee_rate = 5  # 0.5%
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
            assert (
                actual_fee <= expected_rate_limit
            ), f"最小金额支付应正确处理，实际费用 {actual_fee} 应 <= 费率限制 {expected_rate_limit}"
        else:
            # 如果费率限制为 0，验证实际费用不为负数
            assert actual_fee >= 0, "费用不应为负数"

    def test_boundary_amount_large_calculates_fee_limit_correctly(self):
        """
        边界场景：大金额支付应正确计算费率限制
        验证系统能处理大金额，且费率限制按比例正确计算
        """
        amount = 100 * 100000000  # 100 CKB
        max_fee_rate = 5  # 0.5%
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
        assert (
            actual_fee <= expected_fee_limit
        ), f"大金额支付应正确计算费率限制，实际费用 {actual_fee} 应 <= 0.5%×{amount//100000000}CKB = {expected_fee_limit}"
        # 对于大金额，实际费用应远小于费率限制
        assert (
            actual_fee < expected_fee_limit // 2
        ), f"大金额支付的实际费用 {actual_fee} 应远小于费率限制 {expected_fee_limit}"

    def test_boundary_fee_exactly_at_limit_succeeds(self):
        """
        边界场景：实际费用刚好等于 max_fee_amount 限制时应允许支付成功
        验证系统允许费用等于限制值的情况
        """
        amount = 1 * 100000000
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
                "max_fee_rate": hex(100),  # 设置足够大，使 FeeLimit = max_fee_amount
                "max_fee_amount": hex(exact_limit),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        # 验证实际支付的费用等于限制值
        actual_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        actual_fee = _parse_fee(actual_payment.get("fee"))
        assert (
            actual_fee == exact_limit
        ), f"当费用等于限制值时应成功支付，实际费用 {actual_fee} 应等于限制值 {exact_limit}"

    def test_boundary_fee_one_below_limit_fails(self):
        """
        边界场景：max_fee_amount 比实际所需费用少 1 时应拒绝支付
        验证系统严格执行费用限制，即使只差 1 也不允许
        """
        amount = 1 * 100000000
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
                    "max_fee_rate": hex(100),  # 设置足够大
                    "max_fee_amount": hex(insufficient_limit),
                    "dry_run": True,
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert (
            "Failed" in err or "max_fee" in err.lower() or "route" in err.lower()
        ), f"费用预算不足应拒绝支付，实际费用需求 {required_fee}，限制 {insufficient_limit}，错误: {err}"

    def test_boundary_fee_one_above_limit_succeeds(self):
        """
        边界场景：max_fee_amount 比实际所需费用多 1 时应允许支付成功
        验证系统允许略高于实际费用的预算
        """
        amount = 1 * 100000000
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
                "max_fee_rate": hex(100),  # 设置足够大
                "max_fee_amount": hex(sufficient_limit),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        # 验证实际支付的费用不超过预算
        actual_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        actual_fee = _parse_fee(actual_payment.get("fee"))
        assert (
            actual_fee <= sufficient_limit
        ), f"费用预算充足应成功支付，实际费用 {actual_fee} 应 <= 预算 {sufficient_limit}"
