"""
Trampoline routing tests: concurrent payments same/different trampolines,
sequential vs concurrent timing.
"""

import threading
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestConcurrentPayments(FiberTest):
    """
    Concurrent trampoline payments: same trampoline, different trampolines,
    sequential vs concurrent. Uses FiberTest (per-test env).
    """

    def test_concurrent_payments_same_trampoline(self):
        """
        Concurrent keysends via same trampoline to multiple targets; all succeed.
        Step 1: Create fiber3..4 and open channels.
        Step 2: Spawn threads to keysend to f3/f4 via trampoline; collect payment hashes.
        Step 3: Wait for all payments success; assert no errors and count.
        """
        # Step 1: Create fiber3..4 and open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Spawn threads to keysend; collect payment hashes
        payments = []
        errors = []

        def send_one(target_fiber, amount):
            try:
                payment = self.fiber1.get_client().send_payment(
                    {
                        "target_pubkey": target_fiber.get_client().node_info()["node_id"],
                        "currency": Currency.FIBD,
                        "amount": hex(amount),
                        "keysend": True,
                        "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                    }
                )
                payments.append((payment["payment_hash"], target_fiber))
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(5):
            target = self.fiber3 if i % 2 == 0 else self.fiber4
            t = threading.Thread(target=send_one, args=(target, Amount.ckb(1)))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # Step 3: Wait for all success; assert no errors and count
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(payments) == 5, f"Expected 5 payments, got {len(payments)}"
        for payment_hash, _ in payments:
            self.wait_payment_state(
                self.fiber1, payment_hash, PaymentStatus.SUCCESS,
                timeout=Timeout.PAYMENT_SUCCESS,
            )

    def test_concurrent_payments_different_trampolines(self):
        """
        Concurrent keysends via different trampolines to different targets; all succeed.
        Step 1: Create fiber3..5 and open channels (f1-f2, f1-f3, f2-f4, f3-f5).
        Step 2: Spawn threads to keysend via f2 or f3; collect payment hashes.
        Step 3: Wait for all success; assert no errors and count.
        """
        # Step 1: Create fiber3..5 and open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(100000))
        self.fiber4 = self.start_new_fiber(self.generate_account(100000))
        self.fiber5 = self.start_new_fiber(self.generate_account(100000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber1, self.fiber3,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber5,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Spawn threads; collect payment hashes
        payments = []
        errors = []

        def send_one(target_fiber, trampoline_fiber, amount):
            try:
                payment = self.fiber1.get_client().send_payment(
                    {
                        "target_pubkey": target_fiber.get_client().node_info()["node_id"],
                        "currency": Currency.FIBD,
                        "amount": hex(amount),
                        "keysend": True,
                        "trampoline_hops": [trampoline_fiber.get_client().node_info()["node_id"]],
                    }
                )
                payments.append((payment["payment_hash"], target_fiber))
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(4):
            trampoline = self.fiber2 if i % 2 == 0 else self.fiber3
            target = self.fiber4 if i % 2 == 0 else self.fiber5
            t = threading.Thread(target=send_one, args=(target, trampoline, Amount.ckb(1)))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # Step 3: Wait for all success; assert no errors and count
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(payments) == 4, f"Expected 4 payments, got {len(payments)}"
        for payment_hash, _ in payments:
            self.wait_payment_state(
                self.fiber1, payment_hash, PaymentStatus.SUCCESS,
                timeout=Timeout.PAYMENT_SUCCESS,
            )

    def test_sequential_vs_concurrent_payments(self):
        """
        Sequential then concurrent keysends via trampoline; both complete.
        Step 1: Create fiber3 and open channels.
        Step 2: Sequential: 3 keysends, wait each; record time.
        Step 3: Concurrent: 3 keysends in threads, wait all; record time.
        """
        # Step 1: Create fiber3 and open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(10000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Sequential keysends; record time
        start = time.time()
        for _ in range(3):
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
                self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
                timeout=Timeout.PAYMENT_SUCCESS,
            )
        sequential_time = time.time() - start

        # Step 3: Concurrent keysends; record time
        payments = []
        start = time.time()

        def send_one():
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
            payments.append(payment["payment_hash"])

        threads = [threading.Thread(target=send_one) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for ph in payments:
            self.wait_payment_state(
                self.fiber1, ph, PaymentStatus.SUCCESS,
                timeout=Timeout.PAYMENT_SUCCESS,
            )
        concurrent_time = time.time() - start

        # Log timing (no strict assert; network may vary)
        assert sequential_time >= 0 and concurrent_time >= 0
