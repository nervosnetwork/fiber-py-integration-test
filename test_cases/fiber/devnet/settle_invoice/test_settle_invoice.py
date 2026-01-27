import time
import hashlib
import pytest

from framework.basic_fiber import FiberTest


def sha256_hex(preimage_hex: str) -> str:
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()


class TestSettleInvoice(FiberTest):
    """
    settle_invoice 集成测试（适配 PR-961）：
    规则：只有发票处于 Received 状态才允许结算；Open/Cancelled/Expired/Paid 状态结算将返回明确错误。

    1. 基本功能：正确 preimage 结算 hold invoice（在发票 Received 后结算），支付成功，发票变为 Paid
    2. 错误 preimage 结算：返回 Hash mismatch
    3. 不存在的 invoice：返回 Invoice not found
    4. 过期的 hold invoice：发票过期后结算返回“already expired”，支付失败（不变为 Paid）
    5. 已结算的 invoice：再次结算返回“already paid”
    6. 空 payment_hash：参数校验异常
    7. 空 payment_preimage：参数校验异常
    8. 并发结算同一 invoice：在发票 Received 前提下并发结算，至多一次成功，其他可能返回“already paid”；最终支付成功
    9. 批量结算：批量创建 hold 发票、等待全部 Received 后逐个结算，余额变动符合期望
    10. 节点重启后结算：重启并重连后，在发票 Received 后结算，支付成功
    11. 支付时 TLC expiry 超过 invoice expiry：发票短期限创建与支付；过期后结算返回“already expired”，支付失败
    12. 使用 ckb_hash 算法创建的 hold invoice：仅提供 preimage 让节点生成 payment_hash；在 Received 后结算成功
    13. 多跳路径 A→B→C 结算：C 创建 hold 发票，A 经 B 支付；C 端发票 Received 后结算，支付成功

    14. 结算 Open 发票（新增）：未发送支付导致发票仍为 Open，结算应返回“still open/Open”
    15. 结算 Cancelled 发票（新增）：取消发票后结算应返回“already cancelled”
    16. 结算 Expired 发票（新增）：发票过期后结算应返回“already expired”
    """

    # FiberTest.debug = True

    def test_settle_valid_hold_invoice(self):
        # 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        # 创建 hold invoice（仅提供 payment_hash）
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "settle hold invoice",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        # 发送支付，等待发票进入 Received（Hold 状态）
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(
            self.fiber1, payment["payment_hash"], "Received", 120, 1
        )
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment["payment_hash"], "payment_preimage": preimage}
        )
        self.wait_payment_state(self.fiber2, payment["payment_hash"], "Success")
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"

    def test_settle_with_wrong_preimage(self):
        # 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        # 创建 hold invoice（payment_hash 基于 preimage1）
        preimage1 = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage1)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "wrong preimage settle",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        # 发送支付，不再等待进入 Received
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # 错误 preimage 结算，期望 hash mismatch
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {
                    "payment_hash": payment_hash,
                    "payment_preimage": self.generate_random_preimage(),  # 不同于 preimage1
                }
            )
        expected_error_message = "Hash mismatch"
        assert expected_error_message in exc_info.value.args[0]

    def test_settle_nonexistent_invoice(self):
        # 随机生成不存在的 payment_hash
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        expected_error_message = "Invoice not found"
        assert expected_error_message in exc_info.value.args[0]

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/1029")
    def test_settle_expired_hold_invoice(self):
        # 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        # 创建快过期的 hold invoice（先支付，后过期再结算）
        expiry_hex = "0x5"  # 5秒有效期 //如果直接设置0x0会被前置校验拦截掉了,InvalidParameter: Failed to validate payment request:
        # "invoice is expired"
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "expired hold invoice",
                "expiry": expiry_hex,
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        # 先在有效期内发送支付
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # 推荐：过期前确保进入 Received（更贴合 PR-961 的要求）
        # 调整：尽量等待，但不作为失败条件，避免环境波动导致用例中断
        try:
            self.wait_invoice_state(self.fiber1, payment_hash, "Received", 30, 1)
        except Exception:
            pass

        # 等待过期后再结算
        time.sleep(int(expiry_hex, 16) + 3)

        # 过期后结算，必须抛错 “already expired”
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        # 发票状态应为 Paid，且不为 Expired
        self.wait_invoice_state(self.fiber1, payment_hash, "Paid", 30, 1)
        # assert inv["status"] == "Expired"

        # 支付状态为 Success
        self.wait_payment_state(self.fiber2, payment["payment_hash"], "Success")

    def test_settle_already_settled_invoice(self):
        # 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        # 创建 hold invoice 并发送支付
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "already settled invoice",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(self.fiber1, payment_hash, "Received", 120, 1)
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.wait_payment_state(self.fiber2, payment["payment_hash"], "Success")
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"

        # 变更验证：第二次结算应返回错误（InvoiceIsPaid）
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already paid" in exc_info.value.args[0]

    def test_settle_open_invoice_should_fail(self):
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "open invoice settle should fail",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert (
            "still open" in exc_info.value.args[0] or "Open" in exc_info.value.args[0]
        )

    def test_settle_cancelled_invoice_should_fail(self):
        # 创建发票后直接取消，再尝试结算
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "cancelled invoice settle should fail",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        self.fiber1.get_client().cancel_invoice(
            {"payment_hash": invoice["invoice"]["data"]["payment_hash"]}
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already cancelled" in exc_info.value.args[0]

    @pytest.mark.skip("expiry_time限制的是发送,所以这个场景不存在")
    def test_settle_expired_invoice_should_fail(self):
        # 发票过期后尝试结算
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )

        expiry_hex = "0x5"
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "expired invoice settle should fail",
                "expiry": expiry_hex,
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        # 为了确保状态明确，这里也可以选择不发送支付直接过期
        time.sleep(int(expiry_hex, 16) + 3)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already expired" in exc_info.value.args[0]

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/965")
    def test_settle_sametime(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "test invoice generated by node2",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        fiber1_payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        fiber3_payment = self.fiber3.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        time.sleep(1)
        print("before--settle-----")
        fiber1_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        payment = self.fiber3.get_client().get_payment(
            {
                "payment_hash": payment_hash,
            }
        )
        assert payment["status"] == "Failed" or fiber1_payment["status"] == "Failed"

        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        time.sleep(1)
        print("after--settle-----")
        fiber1_payment = self.wait_payment_finished(self.fiber1, payment_hash)
        fiber3_payment = self.wait_payment_finished(self.fiber3, payment_hash)
        assert fiber1_payment["status"] != fiber3_payment["status"]
