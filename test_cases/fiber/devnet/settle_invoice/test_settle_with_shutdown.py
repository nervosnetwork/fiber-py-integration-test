import time
import hashlib

import pytest

from framework.basic_fiber import FiberTest


def sha256_hex(preimage_hex: str) -> str:
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()


class TestSettleWithShutdown(FiberTest):
    """
    invoice 用 payment_hash 支付，但未进行 settle，然后正常 shutdown。
    验证：hold invoice 在 Received 状态下未 settle，直接正常关闭通道的行为。
    """
    debug = True

    def test_0000(self):
        self.fiber1.get_client().list_channels({})
    def test_shutdown_without_settle(self):
        """
        场景：
        1. fiber2 向 fiber1 打开通道
        2. fiber1 创建 hold invoice（仅提供 payment_hash，不提供 preimage）
        3. fiber2 使用 invoice 发送支付，等待 invoice 进入 Received 状态
        4. 不进行 settle_invoice
        5. 发起正常 shutdown（非 force），验证 shutdown 行为
        """
        # 1. 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "ChannelReady", 120
        )

        # 2. 创建 hold invoice（仅提供 payment_hash）
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "hold invoice without settle then shutdown",
                "expiry": "0xe10",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        # 3. fiber2 发送支付，等待 invoice 进入 Received（Hold 状态）
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(
            self.fiber1, payment["payment_hash"], "Received", 120, 1
        )

        # 4. 不进行 settle_invoice，确认 invoice 仍为 Received
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Received"

        # 5. 正常 shutdown 通道（非 force）
        channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(
                    self.Config.ACCOUNT_PRIVATE_1
                ),
                "fee_rate": "0x3FC",
            }
        )

        # 6. 等待关闭交易上链
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # 7. 验证通道已关闭
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            "CLOSED",
            120,
            include_closed=True,
        )

    def test_shutdown_without_settle_multi_invoice(self):
        """
        场景：
        1. 打开通道
        2. 创建多个 hold invoice，全部发送支付并进入 Received 状态
        3. 全部都不 settle
        4. 正常 shutdown，验证行为
        """
        # 1. 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "ChannelReady", 120
        )

        # 2. 创建多个 hold invoice 并发送支付
        N = 3
        preimages = []
        payment_hashes = []
        for i in range(N):
            preimage = self.generate_random_preimage()
            payment_hash = sha256_hex(preimage)
            preimages.append(preimage)
            payment_hashes.append(payment_hash)

            invoice = self.fiber1.get_client().new_invoice(
                {
                    "amount": hex(1 * 100000000),
                    "currency": "Fibd",
                    "description": f"hold invoice {i} without settle",
                    "expiry": "0xe10",
                    "final_cltv": "0x28",
                    "payment_hash": payment_hash,
                    "hash_algorithm": "sha256",
                }
            )
            payment = self.fiber2.get_client().send_payment(
                {"invoice": invoice["invoice_address"]}
            )
            self.wait_invoice_state(
                self.fiber1, payment["payment_hash"], "Received", 120, 1
            )
            time.sleep(1)

        # 3. 确认所有 invoice 均为 Received，不进行 settle
        for ph in payment_hashes:
            inv = self.fiber1.get_client().get_invoice({"payment_hash": ph})
            assert inv["status"] == "Received"

        # 4. 正常 shutdown 通道
        channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]

        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(
                    self.Config.ACCOUNT_PRIVATE_2
                ),
                "fee_rate": "0x3FC",
            }
        )

        # 5. 等待关闭交易上链
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # 6. 验证通道已关闭
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            "CLOSED",
            120,
            include_closed=True,
        )

    def test_shutdown_without_settle_check_balance(self):
        """
        场景：
        1. 打开通道，记录初始余额
        2. 创建 hold invoice 并发送支付，进入 Received
        3. 不进行 settle
        4. 正常 shutdown
        5. 验证链上余额变化：因为未 settle，支付金额应退回给发送方
        """
        before_balance = self.get_fibers_balance()

        # 1. 打开通道
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "ChannelReady", 120
        )

        # 2. 创建 hold invoice 并发送支付
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibd",
                "description": "hold invoice balance check",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(
            self.fiber1, payment["payment_hash"], "Received", 120, 1
        )

        # 3. 不进行 settle，确认 invoice 为 Received
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == "Received"

        # 4. 正常 shutdown 通道
        channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]

        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(
                    self.Config.ACCOUNT_PRIVATE_2
                ),
                "fee_rate": "0x3FC",
            }
        )

        # 5. 等待关闭交易上链
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # 6. 验证通道已关闭
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            "CLOSED",
            120,
            include_closed=True,
        )

        # 7. 验证链上余额：未 settle 的 hold invoice，支付金额应退回
        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        print("balance change:", result)
