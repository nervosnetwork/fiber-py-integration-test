"""
Test cases for MPP self-payment bench: multi-channel topology and self-payment stress.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, FeeRate, Timeout, TLCFeeRate


class TestMppBench(FiberTest):
    """
    MPP self-payment benchmark: build ring topology (fiber1-fiber2-fiber3-fiber1),
    run many self-payments, then shutdown channels with close_script and assert output cells.
    """

    @pytest.mark.skip(reason="todo: benchmark test to be stabilized")
    def test_bench_self(self):
        """
        Build ring topology; run 100 rounds of self-payment (3 nodes); wait all finished;
        then send final invoice payments and shutdown each channel with close_script.
        Step 1: Start fiber3 and open 6 channels (1-2 x2, 2-3 x2, 3-1 x2).
        Step 2: Run 100 rounds of send_invoice_payment self-payment (try_count=0).
        Step 3: Wait all payment finished; get_fiber_graph_balance; send final invoice payments.
        Step 4: For each channel shutdown with close_script; assert output_cells.
        """
        # Step 1: Start fiber3 and open 6 channels
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.ckb(1000))
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )

        time.sleep(10)
        payments = [[], [], []]
        # Step 2: Run 100 rounds of self-payment (try_count=0)
        for _ in range(100):
            for i in range(3):
                try:
                    payment_hash = self.send_invoice_payment(
                        self.fibers[i],
                        self.fibers[i],
                        Amount.ckb(1001),
                        wait=False,
                        try_count=0,
                    )
                    payments[i].append(payment_hash)
                except Exception:
                    pass

        # Step 3: Wait all payment finished; get_fiber_graph_balance; send final invoice payments
        for i in range(len(payments)):
            for payment_hash in payments[i]:
                self.wait_payment_finished(
                    self.fibers[i], payment_hash, timeout=Timeout.VERY_LONG
                )
        time.sleep(200)
        self.get_fiber_graph_balance()
        for i in range(3):
            self.send_invoice_payment(
                self.fibers[i], self.fibers[i], Amount.ckb(100), wait=True
            )

        # Step 4: For each channel shutdown with close_script; assert output_cells
        for fiber in self.fibers:
            fiber1_channels = fiber.get_client().list_channels({})
            for channel in fiber1_channels["channels"]:
                fiber.get_client().shutdown_channel(
                    {
                        "channel_id": channel["channel_id"],
                        "close_script": self.get_account_script(fiber.account_private),
                        "fee_rate": FeeRate.to_hex(1020),  # 0x3FC
                    }
                )
                shutdown_tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.MIN, False)
                self.Miner.miner_until_tx_committed(self.node, shutdown_tx_hash)
                shutdown_tx = self.get_tx_message(shutdown_tx_hash)
                assert {
                    "args": self.get_account_script(fiber.account_private)["args"],
                    "capacity": int(channel["local_balance"], 16)
                    + DEFAULT_MIN_DEPOSIT_CKB
                    - shutdown_tx["fee"],
                } in shutdown_tx["output_cells"]

    @pytest.mark.skip(reason="not stable: stop cause mutilSig Err")
    def test_bench_self_with_stop(self):
        """
        Same topology as test_bench_self; run self-payments; stop fiber3; send payments
        and restart; assert offered/received TLC zero and final self-payments succeed.
        Step 1: Build ring topology and run 100 rounds of self-payment.
        Step 2: Stop fiber3; send payments 1-2 and 2-1; restart fiber3; send again; get balance.
        Step 3: Reconnect; wait; send self-payments; assert all TLC balances zero.
        """
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.ckb(1000))
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )

        time.sleep(10)
        payments = [[], [], []]
        for _ in range(100):
            for i in range(3):
                try:
                    payment_hash = self.send_invoice_payment(
                        self.fibers[i],
                        self.fibers[i],
                        Amount.ckb(1001),
                        wait=False,
                        try_count=0,
                    )
                    payments[i].append(payment_hash)
                except Exception:
                    pass
        self.fibers[2].stop()
        time.sleep(100)
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))
        time.sleep(100)
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))
        self.fibers[2].start()
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))
        self.get_fiber_graph_balance()
        self.fiber1.connect_peer(self.fibers[2])
        self.fiber2.connect_peer(self.fibers[2])
        time.sleep(200)
        for fiber in self.fibers:
            balance = self.get_fiber_balance(fiber)
            assert balance["ckb"]["offered_tlc_balance"] == 0
            assert balance["ckb"]["received_tlc_balance"] == 0
        for i in range(3):
            for _ in range(3):
                self.send_payment(
                    self.fibers[i], self.fibers[i], Amount.ckb(1), wait=True, try_count=3
                )
        for fiber in self.fibers:
            balance = self.get_fiber_balance(fiber)
            assert balance["ckb"]["offered_tlc_balance"] == 0
            assert balance["ckb"]["received_tlc_balance"] == 0
