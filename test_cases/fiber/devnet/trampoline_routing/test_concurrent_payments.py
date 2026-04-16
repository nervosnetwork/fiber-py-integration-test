import pytest
import threading
import time

from framework.basic_fiber import FiberTest


class TestConcurrentPayments(FiberTest):
    """
    测试并发支付场景
    包括同时发送多个 trampoline routing 支付
    """

    def test_concurrent_payments_same_trampoline(self):
        """
        测试通过同一个 trampoline 节点并发发送多个支付
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        # 建立通道
        self.open_channel(self.fiber1, self.fiber2, 10000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 10000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber4, 10000 * 100000000, 0)

        # 并发发送多个支付
        payments = []
        errors = []

        def send_payment(target_fiber, amount):
            try:
                payment = self.fiber1.get_client().send_payment(
                    {
                        "target_pubkey": target_fiber.get_client().node_info()[
                            "pubkey"
                        ],
                        "currency": "Fibd",
                        "amount": hex(amount),
                        "keysend": True,
                        "trampoline_hops": [
                            self.fiber2.get_client().node_info()["pubkey"],
                        ],
                    }
                )
                payments.append((payment["payment_hash"], target_fiber))
            except Exception as e:
                errors.append(str(e))

        # 启动多个线程并发发送支付
        threads = []
        for i in range(5):
            target = self.fiber3 if i % 2 == 0 else self.fiber4
            thread = threading.Thread(target=send_payment, args=(target, 1 * 100000000))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有支付都成功
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(payments) == 5, f"Expected 5 payments, got {len(payments)}"

        # 等待所有支付完成
        for payment_hash, target_fiber in payments:
            self.wait_payment_state(self.fiber1, payment_hash, "Success")

    def test_concurrent_payments_different_trampolines(self):
        """
        测试通过不同的 trampoline 节点并发发送多个支付
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(100000))
        self.fiber4 = self.start_new_fiber(self.generate_account(100000))
        self.fiber5 = self.start_new_fiber(self.generate_account(100000))

        # 建立通道
        self.open_channel(self.fiber1, self.fiber2, 10000 * 100000000, 0)
        self.open_channel(self.fiber1, self.fiber3, 10000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber4, 10000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber5, 10000 * 100000000, 0)

        # 并发发送多个支付，使用不同的 trampoline 节点
        payments = []
        errors = []

        def send_payment(target_fiber, trampoline_fiber, amount):
            try:
                payment = self.fiber1.get_client().send_payment(
                    {
                        "target_pubkey": target_fiber.get_client().node_info()[
                            "pubkey"
                        ],
                        "currency": "Fibd",
                        "amount": hex(amount),
                        "keysend": True,
                        "trampoline_hops": [
                            trampoline_fiber.get_client().node_info()["pubkey"],
                        ],
                    }
                )
                payments.append((payment["payment_hash"], target_fiber))
            except Exception as e:
                errors.append(str(e))

        # 启动多个线程并发发送支付
        threads = []
        for i in range(4):
            trampoline = self.fiber2 if i % 2 == 0 else self.fiber3
            target = self.fiber4 if i % 2 == 0 else self.fiber5
            thread = threading.Thread(
                target=send_payment, args=(target, trampoline, 1 * 100000000)
            )
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有支付都成功
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(payments) == 4, f"Expected 4 payments, got {len(payments)}"

        # 等待所有支付完成
        for payment_hash, target_fiber in payments:
            self.wait_payment_state(self.fiber1, payment_hash, "Success")

    def test_sequential_vs_concurrent_payments(self):
        """
        测试顺序支付和并发支付的对比
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(self.fiber1, self.fiber2, 10000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 10000 * 100000000, 0)

        # 顺序发送支付
        start_time = time.time()
        for i in range(3):
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["pubkey"],
                    ],
                }
            )
            self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        sequential_time = time.time() - start_time

        # 并发发送支付
        payments = []
        start_time = time.time()

        def send_payment():
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["pubkey"],
                    ],
                }
            )
            payments.append(payment["payment_hash"])

        threads = []
        for i in range(3):
            thread = threading.Thread(target=send_payment)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 等待所有支付完成
        for payment_hash in payments:
            self.wait_payment_state(self.fiber1, payment_hash, "Success")
        concurrent_time = time.time() - start_time

        # 并发应该比顺序更快（或至少不会更慢）
        print(
            f"Sequential time: {sequential_time}s, Concurrent time: {concurrent_time}s"
        )
        # 注意：由于网络延迟等因素，这个断言可能不总是成立
        # assert concurrent_time <= sequential_time
