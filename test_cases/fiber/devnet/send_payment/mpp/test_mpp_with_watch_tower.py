"""
Test cases for MPP with watch tower: pending TLC, disconnect, force shutdown, epoch advance.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, TLCFeeRate


class TestWatchTowerWithMpp(FiberTest):
    """
    Test MPP with watch tower: ring topology, many self-payments, disconnect peer,
    force shutdown all channels, advance epochs; assert balance change (ckb loss < 1 CKB).
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    @classmethod
    def teardown_class(cls):
        """Restore time and call parent teardown."""
        cls.restore_time()
        super().teardown_class()

    def test_watch_tower_with_bench_pending_tlc(self):
        """
        Build ring topology (fiber1-2-3-1) with 8 channels; run 60 rounds of self-payment;
        disconnect fiber1-fiber2; force shutdown all channels; advance epochs until
        commit cells drained; assert per-fiber CKB balance change < 1 CKB.
        Step 1: Start fiber3 and open 8 channels; record before_balance.
        Step 2: Run 60 rounds of send_invoice_payment self-payment; disconnect fiber1-fiber2.
        Step 3: Force shutdown all channels; generate epoch; wait tip ahead of commit; add time and epochs.
        Step 4: Drain commit cells; get after_balance; assert balance change ckb < 1 CKB.
        """
        # Step 1: Start fiber3 and open 8 channels; record before_balance
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.udt(1000))
        )
        before_balance = self.get_fibers_balance()

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

        # Step 2: Run 60 rounds of self-payment; disconnect fiber1-fiber2
        for _ in range(60):
            for fiber in self.fibers:
                try:
                    self.send_invoice_payment(
                        fiber, fiber,
                        Amount.ckb(1001),
                        wait=False,
                        try_count=0,
                    )
                except Exception:
                    pass
        self.fiber1.get_client().disconnect_peer({"peer_id": self.fiber2.get_peer_id()})

        # Step 3: Force shutdown all channels; generate epoch; wait tip ahead; add time and epochs
        for fiber in self.fibers:
            try:
                for channel in fiber.get_client().list_channels({})["channels"]:
                    fiber.get_client().shutdown_channel(
                        {"channel_id": channel["channel_id"], "force": True}
                    )
            except Exception:
                pass
        time.sleep(20)
        self.node.getClient().generate_epochs("0x1")
        time.sleep(10)
        while (
            self.node.getClient().get_tip_block_number()
            - self.get_latest_commit_tx_number()
            < 50
        ):
            time.sleep(20)
        self.add_time_and_generate_epoch(25, 2)
        while len(self.get_commit_cells()) > 0:
            self.add_time_and_generate_epoch(24, 1)
            time.sleep(10)

        # Step 4: Get after_balance; assert balance change ckb < 1 CKB
        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        for rt in result:
            assert rt["ckb"] < Amount.ckb(1), "Per-fiber CKB balance change should be < 1 CKB"
