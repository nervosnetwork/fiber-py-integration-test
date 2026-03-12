import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliPeer(FiberTest):
    """Test peer management commands via fnn-cli."""

    def test_list_peers(self):
        """fiber1 should see fiber2 in its peer list (connected in setup)."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        peers = cli.list_peers()
        rpc_peers = self.fiber1.get_client().list_peers()
        cli_peer_list = peers["peers"] if isinstance(peers, dict) else peers
        rpc_peer_list = rpc_peers["peers"] if isinstance(rpc_peers, dict) else rpc_peers
        assert len(cli_peer_list) == len(rpc_peer_list)
        assert len(cli_peer_list) >= 1

    def test_connect_and_disconnect_peer(self):
        """Start a third fiber node, connect and disconnect via CLI."""
        account3 = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        fiber3_address = fiber3.get_client().node_info()["addresses"][0]
        cli1.connect_peer(address=fiber3_address)
        time.sleep(2)

        peers = cli1.list_peers()
        peer_list = peers["peers"] if isinstance(peers, dict) else peers
        pubkeys = [p["pubkey"] for p in peer_list]
        fiber3_pubkey = fiber3.get_client().node_info()["pubkey"]
        assert fiber3_pubkey in pubkeys

        cli1.disconnect_peer(fiber3_pubkey)
        time.sleep(2)

        peers_after = cli1.list_peers()
        peer_list_after = (
            peers_after["peers"] if isinstance(peers_after, dict) else peers_after
        )
        pubkeys_after = [p["pubkey"] for p in peer_list_after]
        assert fiber3_pubkey not in pubkeys_after

    def test_connect_peer_invalid_address(self):
        """Connecting to an invalid multi-address should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.connect_peer(address="/ip4/127.0.0.1/tcp/99999/p2p/invalid_peer_id")

    def test_disconnect_peer_invalid_pubkey(self):
        """Disconnecting a non-existent peer should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.disconnect_peer("02" + "00" * 32)
