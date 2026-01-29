"""
Test cases for Fiber issue #484: concurrent payments and balance contention.
Requirement: https://github.com/nervosnetwork/fiber/pull/484
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, PaymentStatus, TLCFeeRate, Timeout


class Test484(FiberTest):
    """
    Test issue #484: concurrent payments when total amount exceeds balance.
    One payment should succeed, the other may fail; then a third payment succeeds.
    """

    def test_484(self):
        """
        Concurrent payments: first and third succeed; second may fail due to balance.
        Step 1: Open channel with equal balances.
        Step 2: Send first payment (no wait).
        Step 3: Send second payment with try_count=0 (expected to possibly fail).
        Step 4: Send third payment (no wait).
        Step 5: Wait for first payment success.
        Step 6: If second payment exists, wait for it to fail.
        Step 7: Wait for third payment success.
        Step 8: Send payment back from fiber2 to fiber1 to rebalance.
        """
        # Step 1: Open channel with equal balances
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1000),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

        # Step 2: Send first payment (no wait)
        payment1 = self.send_payment(
            self.fiber1, self.fiber2, Amount.ckb(600), wait=False
        )

        # Step 3: Send second payment with try_count=0 (expected to possibly fail)
        try:
            payment2 = self.send_payment(
                self.fiber1, self.fiber2, Amount.ckb(600), wait=False, try_count=0
            )
        except Exception as e:
            payment2 = None

        # Step 4: Send third payment (no wait)
        payment3 = self.send_payment(
            self.fiber1, self.fiber2, Amount.ckb(300), wait=False
        )

        # Step 5: Wait for first payment success
        self.wait_payment_state(
            self.fiber1, payment1, PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

        # Step 6: If second payment exists, wait for it to fail
        if payment2 is not None:
            self.wait_payment_state(
                self.fiber1, payment2, PaymentStatus.FAILED, timeout=Timeout.SHORT
            )

        # Step 7: Wait for third payment success
        self.wait_payment_state(
            self.fiber1, payment3, PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

        # Step 8: Send payment back from fiber2 to fiber1 to rebalance
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(300))
