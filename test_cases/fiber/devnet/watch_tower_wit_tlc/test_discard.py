"""
Test watch tower discard behavior when mid-node force shutdown with pending TLC.
When mid-node disconnects and force shutdowns, discarded TLC should not cause UDT/CKB loss.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate


class TestDiscard(FiberTest):
    """
    Test watch tower discard behavior when mid-node force shutdowns with pending TLC.
    Verifies UDT and CKB balance consistency after discard scenario.
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def teardown_method(self, method):
        super().teardown_method(method)

    @classmethod
    def teardown_class(cls):
        cls.restore_time()
        super().teardown_class()

    def test_udt(self):
        """
        Test UDT discard: mid-node force shutdown should not cause UDT loss.
        Step 1: Setup UDT faucet and build fiber1->fiber2->fiber3 topology.
        Step 2: Send payments and disconnect mid-node, force shutdown channels.
        Step 3: Wait for commitment tx and epoch progression.
        Step 4: Assert UDT balance change is zero and CKB fee is within expected range.
        """
        # Step 1: Setup UDT faucet and build fiber1->fiber2->fiber3 topology
        udt = self.get_account_udt_script(self.fiber1.account_private)
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            Amount.udt(10000),
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.udt(10000),
        )
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        before_udt_balances = self.get_fibers_balance()

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
            udt=udt,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
            udt=udt,
        )

        # Step 2: Send payments and disconnect mid-node, force shutdown channels
        for i in range(10):
            try:
                self.send_payment(
                    self.fiber1, self.fiber3,
                    Amount.ckb(1),
                    wait=False,
                    udt=udt,
                    try_count=0,
                )
            except Exception:
                pass
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber3.get_peer_id()})
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber1.get_peer_id()})
        list_channels = self.fiber2.get_client().list_channels({})
        for channel in list_channels["channels"]:
            self.fiber2.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)

        # Step 3: Wait for commitment tx and epoch progression
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        for i in range(5):
            self.Miner.miner_with_version(self.node, "0x0")
        self.node.getClient().generate_epochs("0x1", 0)
        while (
            self.node.getClient().get_tip_block_number()
            - self.get_latest_commit_tx_number()
            < 20
        ):
            time.sleep(5)
        while len(self.get_commit_cells()) > 0:
            self.add_time_and_generate_epoch(24, 1)
            time.sleep(10)

        # Step 4: Assert UDT balance change is zero and CKB fee is within expected range
        after_udt_balances = self.get_fibers_balance()
        result = self.get_balance_change(before_udt_balances, after_udt_balances)
        udt_change_balance = sum(r["udt"] for r in result)
        assert udt_change_balance == 0
        ckb_change_balance = sum(r["ckb"] for r in result)
        assert ckb_change_balance < Amount.ckb(0.0002)
        assert ckb_change_balance > 0

    def test_ckb(self):
        """
        Test CKB discard: mid-node force shutdown should not cause CKB loss beyond fees.
        Step 1: Build fiber1->fiber2->fiber3 topology and send payments.
        Step 2: Disconnect mid-node and force shutdown channels.
        Step 3: Wait for commitment tx and epoch progression.
        Step 4: Assert CKB fee is within expected range.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology and send payments
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        before_udt_balances = []
        for fiber in self.fibers:
            before_udt_balances.append(self.get_fiber_balance(fiber))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )

        for i in range(10):
            try:
                self.send_payment(
                    self.fiber1, self.fiber3,
                    Amount.ckb(1),
                    wait=False,
                    try_count=0,
                )
            except Exception:
                pass

        # Step 2: Disconnect mid-node and force shutdown channels
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber3.get_peer_id()})
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber1.get_peer_id()})
        time.sleep(1)
        list_channels = self.fiber2.get_client().list_channels({})
        for channel in list_channels["channels"]:
            self.fiber2.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)

        # Step 3: Wait for commitment tx and epoch progression
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        for i in range(5):
            self.Miner.miner_with_version(self.node, "0x0")
        self.node.getClient().generate_epochs("0x1", 0)
        while (
            self.node.getClient().get_tip_block_number()
            - self.get_latest_commit_tx_number()
            < 20
        ):
            time.sleep(5)
        while len(self.get_commit_cells()) > 0:
            self.add_time_and_generate_epoch(24, 1)
            time.sleep(10)

        # Step 4: Assert CKB fee is within expected range
        after_udt_balances = []
        for fiber in self.fibers:
            after_udt_balances.append(self.get_fiber_balance(fiber))
        results = []
        for i in range(len(before_udt_balances)):
            print(
                f"ckb:{before_udt_balances[i]['chain']['ckb']} - "
                f"{after_udt_balances[i]['chain']['ckb']} = "
                f"{before_udt_balances[i]['chain']['ckb'] - after_udt_balances[i]['chain']['ckb']}"
            )
            results.append(
                {
                    "ckb": before_udt_balances[i]["chain"]["ckb"]
                    - after_udt_balances[i]["chain"]["ckb"]
                }
            )
        ckb_change_balance = sum(r["ckb"] for r in results)
        assert ckb_change_balance < Amount.ckb(0.0002)
        assert ckb_change_balance > 0
