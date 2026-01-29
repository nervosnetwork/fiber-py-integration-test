"""
Test cases for disconnect_peer RPC: disconnect from peer and peer count.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Timeout


class TestDisconnectPeer(FiberTest):
    """
    Test disconnect_peer RPC: disconnect from peer, verify peers_count, and non-existing peer.
    """

    def test_disconnect_peer(self):
        """
        Test disconnecting from a peer.

        Steps:
        1. Retrieve initial node information and assert the peer count is 1.
        2. Disconnect from the peer.
        3. Wait briefly to ensure the disconnection is processed.
        4. Retrieve node information and assert the peer count is 0.
        5. Attempt to disconnect from a non-existing peer.
        """
        # Step 1: Retrieve initial node information and assert the peer count is 1
        before_node_info = self.fiber1.get_client().node_info()
        assert before_node_info["peers_count"] == "0x1"

        # Step 2: Disconnect from the peer
        self.fiber1.get_client().disconnect_peer({"peer_id": self.fiber2.get_peer_id()})

        # Step 3: Wait briefly to ensure the disconnection is processed
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: Retrieve node information and assert the peer count is 0
        after_node_info = self.fiber1.get_client().node_info()
        assert after_node_info["peers_count"] == "0x0"

        # Step 5: Attempt to disconnect from a non-existing peer
        self.fiber1.get_client().disconnect_peer(
            {"peer_id": "QmNoDjLNbJujKpBorKHWPHPKoLrzND1fYtmmEVxkq35Hgp"}
        )
