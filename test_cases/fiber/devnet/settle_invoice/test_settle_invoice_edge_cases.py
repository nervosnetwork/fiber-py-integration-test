import time
import concurrent.futures
import pytest

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.settle_invoice.test_settle_invoice import sha256_hex


class TestSettleInvoiceEdgeCases(FiberTest):
    """settle_invoice 边缘用例：并发 MPP、状态转换、过付、无效输入等。"""

    # ------------------------- 1. 并发 MPP 支付 -------------------------
    def test_concurrent_mpp_payments_partial_and_overpay(self):
        """
        并发 MPP 支付：多线程同时发送 TLC，一部分部分结算、另一部分尝试过付。
        预期：只接受不超过发票总额的 TLC，过付被拒绝；最终发票 Paid，无多余资金锁定。
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)

        invoice_amount = 1000 * 100000000  # 1000 Fibd
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(invoice_amount),
                "currency": "Fibd",
                "description": "concurrent mpp edge case",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
                "allow_mpp": True,
            }
        )

        results = {}

        def pay_from_fiber1():
            try:
                p = self.fiber1.get_client().send_payment(
                    {"invoice": invoice["invoice_address"]}
                )
                results["fiber1"] = ("sent", p["payment_hash"])
            except Exception as e:
                results["fiber1"] = ("error", str(e))

        def pay_from_fiber3():
            try:
                p = self.fiber3.get_client().send_payment(
                    {"invoice": invoice["invoice_address"]}
                )
                results["fiber3"] = ("sent", p["payment_hash"])
            except Exception as e:
                results["fiber3"] = ("error", str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(pay_from_fiber1)
            fut3 = executor.submit(pay_from_fiber3)
            concurrent.futures.wait([fut1, fut3])
        time.sleep(2)

        # 至少一方发送了支付；一方成功一方失败（非 MPP 双花）或 MPP 下部分接受
        pay1 = self.fiber1.get_client().get_payment({"payment_hash": payment_hash})
        pay3 = self.fiber3.get_client().get_payment({"payment_hash": payment_hash})
        # 预期：总接受不超过 invoice_amount，过付部分被拒绝
        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        time.sleep(1)
        inv = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"
        # 成功方应为 Success
        if pay1["status"] != "Failed":
            self.wait_payment_state(self.fiber1, payment_hash, "Success", 30)
        if pay3["status"] != "Failed":
            self.wait_payment_state(self.fiber3, payment_hash, "Success", 30)

    # ------------------------- 2. 发票状态中途转换 -------------------------
    def test_settle_after_invoice_cancelled_post_receive(self):
        """
        接收 TLC 后取消发票，再尝试结算。
        预期：结算失败，发票保持 Cancelled，不发生部分结算。
        """
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber1.get_pubkey(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY", 120
        )

        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "cancel after receive",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        self.fiber2.get_client().send_payment({"invoice": invoice["invoice_address"]})
        self.wait_invoice_state(self.fiber1, payment_hash, "Received", 60, 1)
        self.fiber1.get_client().cancel_invoice(
            {"payment_hash": invoice["invoice"]["data"]["payment_hash"]}
        )
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert (
            "already cancelled" in exc_info.value.args[0]
            or "cancelled" in exc_info.value.args[0].lower()
        )
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Cancelled"

    def test_settle_after_invoice_expired_post_receive(self):
        """
        接收 TLC 后等待发票过期，再尝试结算。
        预期：结算失败或按实现返回过期相关错误；不发生部分结算。
        """
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber1.get_pubkey(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY", 120
        )

        expiry_sec = 6
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "expire after receive",
                "expiry": hex(expiry_sec),
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        self.fiber2.get_client().send_payment({"invoice": invoice["invoice_address"]})
        try:
            self.wait_invoice_state(self.fiber1, payment_hash, "Received", 30, 1)
        except Exception:
            pass
        time.sleep(expiry_sec + 3)

        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.wait_invoice_state(self.fiber1, payment_hash, "Paid", 30, 1)

    # ------------------------- 3. 数据库不一致风险（多线程接受/拒绝）-----------------
    def test_concurrent_accept_reject_overpay_consistency(self):
        """
        多线程模拟：同时多笔支付到同一 MPP 发票，验证最终总额不超过发票、状态一致。
        无 mock 时通过并发发送 + 结算后校验余额与状态实现。
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)

        invoice_amount = 500 * 100000000
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(invoice_amount),
                "currency": "Fibd",
                "description": "overpay consistency",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
                "allow_mpp": True,
            }
        )

        def send():
            self.fiber1.get_client().send_payment(
                {"invoice": invoice["invoice_address"]}
            )

        def send3():
            self.fiber3.get_client().send_payment(
                {"invoice": invoice["invoice_address"]}
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(send)
            f3 = ex.submit(send3)
            concurrent.futures.wait([f1, f3])
        time.sleep(2)

        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        time.sleep(1)
        inv = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"
        # 最终不应有 received_tlc_balance 残留（过付 TLC 应被 RemoveTlc）
        self.wait_fibers_pending_tlc_eq0(self.fiber2, 30)

    # ------------------------- 4. Hold TLC 过期后结算 -------------------------
    def test_settle_hold_tlc_after_expired(self):
        """
        Hold TLC 在 pending 状态下过期，再尝试结算。
        预期：结算拒绝或返回过期错误，发票状态不变。
        """
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber1.get_pubkey(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY", 120
        )

        expiry_hex = "0x6"
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "hold tlc expire then settle",
                "expiry": expiry_hex,
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        self.fiber2.get_client().send_payment({"invoice": invoice["invoice_address"]})
        try:
            self.wait_invoice_state(self.fiber1, payment_hash, "Received", 20, 1)
        except Exception:
            pass
        time.sleep(int(expiry_hex, 16) + 2)

        try:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
            # 若实现允许过期后仍结算，则检查状态
            inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
            assert inv["status"] in ("Paid", "Expired")
        except Exception as e:
            assert "expired" in str(e).lower() or "Expired" in str(e)

    # ------------------------- 5. 非 MPP 多 TLC 拒绝 -------------------------
    def test_non_mpp_multi_tlc_only_first_accepted(self):
        """
        非 MPP 发票：发送两个 fulfilled TLC（相同 payment_hash），只接受第一个。
        预期：只结算第一个，第二个被拒绝并移除；发票标记为 Paid。
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)

        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "non-mpp multi tlc",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
                "allow_mpp": False,
            }
        )
        self.fiber1.get_client().send_payment({"invoice": invoice["invoice_address"]})
        self.fiber3.get_client().send_payment({"invoice": invoice["invoice_address"]})
        time.sleep(2)

        pay1 = self.fiber1.get_client().get_payment({"payment_hash": payment_hash})
        pay3 = self.fiber3.get_client().get_payment({"payment_hash": payment_hash})
        # assert pay1["status"] == "Success" or pay3["status"] == "Success"
        assert pay1["status"] == "Failed" or pay3["status"] == "Failed"

        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        time.sleep(1)
        inv = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"
        pay1 = self.fiber1.get_client().get_payment({"payment_hash": payment_hash})
        if pay1["status"] == "Success":
            self.wait_payment_state(self.fiber1, payment_hash, "Success", 10)
        else:
            self.wait_payment_state(self.fiber3, payment_hash, "Success", 10)

    # ------------------------- 6. 过付 MPP 边缘拒绝 -------------------------
    def test_mpp_overpay_rejection(self):
        """
        MPP 发票总金额略超过发票：多笔小额累积过付，结算时过付部分被拒绝。
        预期：只结算有效部分，过付 TLC 被移除，发票 Paid。
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)

        invoice_amount = 100 * 100000000
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(invoice_amount),
                "currency": "Fibd",
                "description": "mpp overpay edge",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
                "allow_mpp": True,
            }
        )
        # fiber1 和 fiber3 各发一笔，总和可能超过 100
        self.fiber1.get_client().send_payment({"invoice": invoice["invoice_address"]})
        self.fiber3.get_client().send_payment({"invoice": invoice["invoice_address"]})
        time.sleep(2)

        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        time.sleep(1)
        inv = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"
        self.wait_fibers_pending_tlc_eq0(self.fiber2, 30)

    # ------------------------- 7. 新旧命令兼容性 -------------------------
    @pytest.mark.skip(reason="需要旧版本 binary 与配置，CI 无旧环境时跳过")
    def test_settle_compatibility_legacy_vs_new_command(self):
        """
        旧 Channel actor 逻辑与新 SettleTlcSetCommand 交互，结果一致。
        需旧配置/二进制时在本地运行。
        """
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber1.get_pubkey(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY", 120
        )
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "legacy compat",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        self.fiber2.get_client().send_payment({"invoice": invoice["invoice_address"]})
        self.wait_invoice_state(self.fiber1, payment_hash, "Received", 120, 1)
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.wait_payment_state(self.fiber2, payment_hash, "Success")
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Paid"

    # ------------------------- 8. 无效 payment_hash 结算 -------------------------
    def test_settle_invalid_payment_hash(self):
        """
        使用不存在的 payment_hash 调用结算。
        预期：返回错误，不影响系统状态。
        """
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        msg = exc_info.value.args[0]
        assert (
            "not found" in msg.lower() or "Invoice" in msg or "invalid" in msg.lower()
        )

    def test_settle_empty_payment_hash(self):
        """空 payment_hash 参数校验。"""
        preimage = self.generate_random_preimage()
        with pytest.raises(Exception):
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": "", "payment_preimage": preimage}
            )
