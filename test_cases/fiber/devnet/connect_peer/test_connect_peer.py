"""
Test cases for connect_peer RPC: connect to peer and optional restart behavior.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout


class TestConnectPeer(FiberTest):
    """
    Test connect_peer RPC: connecting to existing/non-existing node and peer count.
    """

    def test_connect_peer(self):
        """
        Test connecting to a peer.

        Steps:
        1. Connect to an existing node.
        2. Attempt to connect to a non-existing node.
        3. Wait briefly to ensure the connection is established.
        4. Retrieve node information.
        5. Assert that the peer count is 1.
        """
        # Step 1: Connect to an existing node
        self.fiber1.connect_peer(self.fiber2)

        # Step 2: Attempt to connect to a non-existing node
        self.fiber1.get_client().connect_peer(
            {
                "address": "/ip4/127.0.0.1/tcp/8231/p2p/QmNoDjLNbJujKpBorKHWPHPKoLrzND1fYtmmEVxkq35Hgp"
            }
        )

        # Step 3: Wait briefly to ensure the connection is established
        time.sleep(Timeout.POLL_INTERVAL * 2)

        # Step 4: Retrieve node information
        node_info = self.fiber1.get_client().node_info()

        # Step 5: Assert that the peer count is 1
        assert node_info["peers_count"] == "0x1"

    @pytest.mark.skip(reason="restart后 list_peer 可能为空，不稳定")
    def test_restart(self):
        """
        Restart node and check list_peers; skipped due to instability.
        Step 1: Open channel. Step 2: Restart fiber1 multiple times. Step 3: Assert peer count.
        """
        # Step 1: Open channel
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        # Step 2: Restart fiber1 multiple times
        for _ in range(5):
            self.fiber1.stop()
            self.fiber1.start()
            self.fiber1.get_client().list_peers()
        time.sleep(Timeout.POLL_INTERVAL * 2)
        self.fiber1.get_client().list_channels({})
        # Step 3: Assert peer count is 1
        peers = self.fiber1.get_client().list_peers()
        assert len(peers["peers"]) == 1
