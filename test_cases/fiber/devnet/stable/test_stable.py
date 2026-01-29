"""
Test cases for stable stress: long-running concurrent payments on ring topology (a->b->c->a).
Covers: CKB and UDT self-payments across three nodes over extended run.
"""
import time
import concurrent.futures

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, TLCFeeRate


class TestStableStress(FiberTest):
    """
    Stable stress: ring topology fiber1->fiber2->fiber3->fiber1; long-running CKB and UDT self-payments.
    """

    fnn_log_level = "info"

    def test_stable_stress(self):
        """
        Ring a->b->c->a; submit many batches of self-payments (CKB and UDT) over long run; assert final balances.
        Step 1: Start fiber3, faucet, open CKB and UDT channels for 1-2, 2-3, 3-1.
        Step 2: Submit 5*60*60*2 batches of 6 payments via thread pool (each node: 1 CKB + 1 UDT self-payment).
        Step 3: Assert each node CKB local_balance 2000 CKB, UDT local_balance 2000 CKB + min deposit.
        """
        # Step 1: Build ring topology and open channels
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.udt(10000))
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
            self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
            self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(
            self.fiber3,
            self.fiber1,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3,
            self.fiber1,
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.ZERO,
            TLCFeeRate.ZERO,
            self.get_account_udt_script(self.fiber1.account_private),
        )

        time.sleep(10)
        udt = self.get_account_udt_script(self.fiber1.account_private)
        send_tx_size = 5 * 60 * 60 * 2
        tasks_submitted = 0
        start_time = time.time()
        times = []
        completed_counts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(send_tx_size):
                futures.append(
                    executor.submit(self.send_payment, self.fiber1, self.fiber1, 1)
                )
                futures.append(
                    executor.submit(
                        self.send_payment, self.fiber1, self.fiber1, 1, True, udt
                    )
                )
                futures.append(
                    executor.submit(self.send_payment, self.fiber2, self.fiber2, 1)
                )
                futures.append(
                    executor.submit(
                        self.send_payment, self.fiber2, self.fiber2, 1, True, udt
                    )
                )
                futures.append(
                    executor.submit(self.send_payment, self.fiber3, self.fiber3, 1)
                )
                futures.append(
                    executor.submit(
                        self.send_payment, self.fiber3, self.fiber3, 1, True, udt
                    )
                )
                tasks_submitted += 6

            completed_tasks = 0
            for future in concurrent.futures.as_completed(futures):
                completed_tasks += 1
                try:
                    future.result()
                    self.logger.debug(
                        f"Task {completed_tasks}/{tasks_submitted} completed"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Task {completed_tasks}/{tasks_submitted} failed: {e}"
                    )
                elapsed_time = time.time() - start_time
                times.append(elapsed_time)
                completed_counts.append(completed_tasks)
                if completed_tasks % 100 == 0:
                    speed = completed_tasks / elapsed_time if elapsed_time > 0 else 0
                    self.logger.info(
                        f"Completed {completed_tasks}/{tasks_submitted} tasks in {elapsed_time:.2f} s. "
                        f"Speed: {speed:.2f} tasks/s"
                    )

            total_time = time.time() - start_time
            speed = completed_tasks / total_time if total_time > 0 else 0
            self.logger.info(
                f"Completed {completed_tasks}/{tasks_submitted} tasks in {total_time:.2f} s. "
                f"Final speed: {speed:.2f} tasks/s"
            )
            self.logger.info(f"finished: {send_tx_size}")

        # Step 3: Assert final balances
        self.get_fibers_balance_message()
        expected_ckb_local = Amount.ckb(2000)
        expected_udt_local = Amount.ckb(2000) + DEFAULT_MIN_DEPOSIT_CKB
        for fiber in self.fibers:
            message = self.get_fiber_balance(fiber)
            assert message["ckb"] == {
                "local_balance": expected_ckb_local,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            }, f"CKB balance mismatch for fiber: {message['ckb']}"
            assert message[udt["args"]] == {
                "local_balance": expected_udt_local,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            }, f"UDT balance mismatch for fiber: {message[udt['args']]}"
