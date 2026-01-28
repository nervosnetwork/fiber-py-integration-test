"""
Test cases for CKB tx pool and remove_tx behavior: open_channel funding tx in pool,
clear pool or resend tx, verify node state.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount


class TestCkbRemoveTx(FiberTest):
    """
    Test CKB node tx pool and remove_tx: open_channel funding tx stuck in pool,
    clear pool then resend tx or open again; verify fiber node_info and list_channels.
    """

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/515")
    def test_remove_open_tx_stuck_node1(self):
        """
        Open channel then clear tx pool and resend funding tx; verify node1 recovers.
        Step 1: fiber1 opens channel (funding tx enters pool).
        Step 2: Wait for tx in pool, get tx and clear pool.
        Step 3: Resend tx and mine until committed.
        Step 4: Wait for channel processing.
        """
        # Step 1: fiber1 opens channel (funding tx enters pool)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(2000)),
                "public": True,
            }
        )
        # Step 2: Wait for tx in pool, get tx and clear pool
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        tx = self.node.getClient().get_transaction(tx_hash)
        self.node.client.clear_tx_pool()
        time.sleep(5)
        del tx["transaction"]["hash"]
        tx_hash = self.node.getClient().send_transaction(tx["transaction"])
        # Step 3: Mine until committed
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        # Step 4: Wait for channel processing
        time.sleep(10)

    def test_0001(self):
        """List channels (include closed) on both fiber1 and fiber2."""
        self.fiber1.get_client().list_channels({"include_closed": True})
        self.fiber2.get_client().list_channels({"include_closed": True})

    def test_bbabb(self):
        """List peers on fiber1 and fiber2."""
        self.fiber1.get_client().list_peers()
        self.fiber2.get_client().list_peers()

    def test_0002(self):
        """
        Stress open_channel: send many open_channel requests in a short time.
        Step 1: Loop open_channel with increasing funding amount.
        """
        # Step 1: Loop open_channel with increasing funding amount
        for i in range(100):
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000) + i),
                    "public": True,
                }
            )
            time.sleep(0.1)

    def test_balala(self):
        """List channels on fiber1 and fiber2."""
        self.fiber1.get_client().list_channels({})
        self.fiber2.get_client().list_channels({})

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/515")
    def test_remove_open_tx_stuck_node2(self):
        """
        Open channel, clear tx pool before commit, then open again; verify node2 recovers.
        Step 1: fiber1 opens channel (funding tx in pool).
        Step 2: Wait for tx in pool then clear pool.
        Step 3: fiber1 opens channel again.
        Step 4: Wait and call node_info; start fiber3 and open channel with fiber2.
        """
        # Step 1: fiber1 opens channel (funding tx in pool)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        # Step 2: Wait for tx in pool then clear pool
        self.wait_tx_pool(pending_size=1, try_size=100)
        self.node.client.clear_tx_pool()
        time.sleep(3)
        # Step 3: fiber1 opens channel again
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        time.sleep(5)
        # Step 4: Verify node_info and open channel fiber3-fiber2
        self.fiber2.get_client().node_info()
        fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(fiber3, self.fiber2, Amount.ckb(1000), Amount.ckb(1))
