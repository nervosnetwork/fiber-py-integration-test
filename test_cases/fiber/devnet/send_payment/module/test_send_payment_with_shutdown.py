"""
Test send_payment while or after shutdown_channel.
See https://github.com/nervosnetwork/fiber/issues/503 for force shutdown skip.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate, Timeout


class TestSendPaymentWithShutdown(FiberTest):
    """
    Test payments in flight when a channel is shut down; wait for payments to finish.
    """

    def test_shutdown_in_send_payment(self):
        """
        Linear topology fiber0->1->2->3; send payments both ways; shutdown channel on fiber3;
        wait for shutdown tx; wait for all payments to finish.
        Step 1: Start fiber3, open channels 0-1, 1-2, 2-3; send 10 payments 0->3 and 3->0.
        Step 2: Shutdown fiber3's channel (to fiber2); wait for tx in pool and payments to finish.
        """
        # Step 1: Build linear topology and send payments
        self.start_new_fiber(self.generate_account(Amount.ckb(10000)))
        self.start_new_fiber(self.generate_account(Amount.ckb(10000)))
        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[3],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        payment_node1_hashes = []
        payment_node3_hashes = []
        for _ in range(10):
            payment_hash = self.send_payment(
                self.fibers[0], self.fibers[3], 1, False
            )
            payment_node1_hashes.append(payment_hash)
            payment_hash = self.send_payment(
                self.fibers[3], self.fibers[0], 1, False
            )
            payment_node3_hashes.append(payment_hash)

        N3N4_CHANNEL_ID = (
            self.fibers[3].get_client().list_channels({})["channels"][0]["channel_id"]
        )

        # Step 2: Shutdown channel and wait for payments to finish
        for _ in range(10):
            try:
                self.fibers[3].get_client().shutdown_channel(
                    {
                        "channel_id": N3N4_CHANNEL_ID,
                        "close_script": {
                            "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                            "hash_type": "type",
                            "args": self.fibers[3].get_account()["lock_arg"],
                        },
                        "fee_rate": hex(FeeRate.DEFAULT),
                    }
                )
                break
            except Exception:
                time.sleep(1)

        self.wait_and_check_tx_pool_fee(1000, False, Timeout.CHANNEL_READY)
        for payment_hash in payment_node1_hashes:
            self.wait_payment_finished(self.fibers[0], payment_hash, Timeout.VERY_LONG)
        for payment_hash in payment_node3_hashes:
            self.wait_payment_finished(self.fibers[3], payment_hash, Timeout.VERY_LONG)

    @pytest.mark.skip(reason="https://github.com/nervosnetwork/fiber/issues/503")
    def test_force_shutdown_in_send_payment(self):
        """
        Force shutdown during in-flight payments; skip per issue 503.
        Step 1: Build topology and send payments; force shutdown channel.
        Step 2: Wait for shutdown tx and all payments to finish.
        """
        self.start_new_fiber(self.generate_account(Amount.ckb(10000)))
        self.start_new_fiber(self.generate_account(Amount.ckb(10000)))
        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[3],
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        payment_hashes = []
        for _ in range(10):
            payment_hash = self.send_payment(
                self.fibers[0], self.fibers[3], 1, False
            )
            payment_hashes.append(payment_hash)
        N3N4_CHANNEL_ID = (
            self.fibers[3].get_client().list_channels({})["channels"][0]["channel_id"]
        )

        self.fibers[3].get_client().shutdown_channel(
            {
                "channel_id": N3N4_CHANNEL_ID,
                "force": True,
            }
        )
        self.wait_and_check_tx_pool_fee(1000, False, Timeout.CHANNEL_READY)
        for payment_hash in payment_hashes:
            self.wait_payment_finished(
                self.fibers[0], payment_hash, Timeout.VERY_LONG
            )
