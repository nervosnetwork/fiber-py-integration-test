"""
Test cases for list_peers RPC: verify peer list matches connected node info.
"""
import pytest

from framework.basic_fiber import FiberTest


class TestListPeers(FiberTest):
    """
    Test list_peers RPC: peer pubkey, address, peer_id match node_info of connected peer.
    """

    def test_01(self):
        """
        list_peers returns peer matching fiber2 node_info (pubkey, address, peer_id).
        Step 1: Get list_peers from fiber1 (fiber2 is connected by setup).
        Step 2: Assert first peer pubkey equals fiber2 node_id.
        Step 3: Assert peer address is in fiber2 addresses.
        Step 4: Assert peer peer_id equals fiber2 addresses[0] suffix.
        Step 5: Get list_peers from fiber2; assert peers list has at least one peer with address.
        """
        # Step 1: Get list_peers from fiber1
        peer = self.fiber1.get_client().list_peers()

        # Step 2: Assert first peer pubkey equals fiber2 node_id
        assert (
            peer["peers"][0]["pubkey"]
            == self.fiber2.get_client().node_info()["node_id"]
        )

        # Step 3: Assert peer address is in fiber2 addresses
        assert (
            peer["peers"][0]["address"]
            in self.fiber2.get_client().node_info()["addresses"]
        )

        # Step 4: Assert peer peer_id equals fiber2 addresses[0] suffix
        assert (
            peer["peers"][0]["peer_id"]
            == self.fiber2.get_client().node_info()["addresses"][0].split("/")[-1]
        )

        # Step 5: Get list_peers from fiber2; assert peers list has at least one peer with address
        peers = self.fiber2.get_client().list_peers()
        assert len(peers["peers"]) >= 1
        assert peers["peers"][0]["address"] is not None
        assert len(peers["peers"][0]["address"]) > 0
