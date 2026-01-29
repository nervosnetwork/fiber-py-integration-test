"""
Test watch tower discard behavior when mid-node disconnects with pending TLCs.
Verifies UDT and CKB balance changes after force shutdown with abandoned TLCs.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate


class TestDiscard(FiberTest):
    """
    Test that when mid-node disconnects and force shuts down with pending TLCs,
    UDT balance is preserved (no loss) and CKB fee is within expected range.
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
        Test UDT balance preservation when mid-node force shuts down with pending TLCs.
        Step 1: Faucet UDT to fiber1 and fiber2.
        Step 2: Start fiber3 and open UDT channels.
        Step 3: Send payments (some may fail due to disconnect).
        Step 4: Disconnect mid-node and force shutdown channels.
        Step 5: Wait for commitment cells to clear.
        Step 6: Assert UDT balance unchanged and CKB fee within range.
        """
        udt = self.get_account_udt_script(self.fiber1.account_private)
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 1000000000,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 1000000000,
        )
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        before_udt_balances = self.get_fibers_balance()

        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0, udt=udt
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            Amount.ckb(1000), 0, udt=udt
        )

        for i in range(10):
            try:
                self.send_payment(
                    self.fiber1, self.fiber3, Amount.ckb(1), False, udt=udt, try_count=0
                )
                # self.send_payment(self.fiber3, self.fiber1,  10000000, False, udt=udt, try_count=0)
            except Exception as e:
                pass
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber3.get_peer_id()})
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber1.get_peer_id()})
        list_channels = self.fiber2.get_client().list_channels({})
        for channel in list_channels["channels"]:
            self.fiber2.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)

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

        after_udt_balances = self.get_fibers_balance()
        result = self.get_balance_change(before_udt_balances, after_udt_balances)
        udt_change_balance = 0
        for i in range(len(result)):
            udt_change_balance += result[i]["udt"]
        assert udt_change_balance == 0
        ckb_change_balance = 0
        for i in range(len(result)):
            ckb_change_balance += result[i]["ckb"]
        assert ckb_change_balance < 20000  # CKB fee tolerance (shannon)
        assert ckb_change_balance > 0

    def test_ckb(self):
        """
        Test CKB balance change when mid-node force shuts down with pending TLCs.
        Step 1: Start fiber3 and open CKB channels.
        Step 2: Send payments (some may fail).
        Step 3: Disconnect mid-node and force shutdown channels.
        Step 4: Wait for commitment cells to clear.
        Step 5: Assert CKB fee within expected range.
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        before_udt_balances = []
        for fiber in self.fibers:
            before_udt_balances.append(self.get_fiber_balance(fiber))

        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), 0
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            Amount.ckb(1000), 0
        )

        for i in range(10):
            try:
                self.send_payment(
                    self.fiber1, self.fiber3, Amount.ckb(1), False, try_count=0
                )
                # self.send_payment(self.fiber3, self.fiber1,  10000000, False, udt=udt, try_count=0)
            except Exception as e:
                pass
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber3.get_peer_id()})
        self.fiber2.get_client().disconnect_peer({"peer_id": self.fiber1.get_peer_id()})
        time.sleep(1)
        list_channels = self.fiber2.get_client().list_channels({})
        for channel in list_channels["channels"]:
            self.fiber2.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)

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

        after_udt_balances = []
        for fiber in self.fibers:
            after_udt_balances.append(self.get_fiber_balance(fiber))

        results = []
        for i in range(len(before_udt_balances)):
            print(
                f"ckb:{before_udt_balances[i]['chain']['ckb']} - {after_udt_balances[i]['chain']['ckb']} = {before_udt_balances[i]['chain']['ckb'] - after_udt_balances[i]['chain']['ckb']}"
            )
            results.append(
                {
                    "ckb": before_udt_balances[i]["chain"]["ckb"]
                    - after_udt_balances[i]["chain"]["ckb"]
                }
            )
        ckb_change_balance = 0
        for i in range(len(results)):
            ckb_change_balance += results[i]["ckb"]
        assert ckb_change_balance < 20000  # CKB fee tolerance (shannon)
        assert ckb_change_balance > 0
