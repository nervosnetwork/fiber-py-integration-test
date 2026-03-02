import time

import pytest

from framework.basic_fiber import FiberTest


class TestConnectPeer(FiberTest):

    def test_connect_peer_via_pubkey_success(self):
        """
        Test connecting to a peer via pubkey (success case).

        Prerequisites: The target node's address must be known locally (saved via
        connect_peer with address + save: true). See upgradeGuide.md.

        Steps:
        1. Connect to fiber2 via address with save=True to persist the peer address.
        2. Disconnect from fiber2.
        3. Connect to fiber2 via pubkey (address resolved from saved data).
        4. Verify the connection is established.
        """
        # Step 1: Disconnect first (setup connected via address without save), then
        # connect via address with save=True to persist the peer address
        self.fiber1.get_client().disconnect_peer({"pubkey": self.fiber2.get_pubkey()})
        time.sleep(1)

        addr = self.fiber2.get_client().node_info()["addresses"][0].replace(
            "0.0.0.0", "127.0.0.1"
        ).replace("0。0.0.0", "127.0.0.1")  # full-width period in some configs
        self.fiber1.get_client().connect_peer({"address": addr, "save": True})

        # Step 2: Disconnect
        self.fiber1.get_client().disconnect_peer({"pubkey": self.fiber2.get_pubkey()})
        time.sleep(3)
        node_info = self.fiber1.get_client().list_peers()
        assert len(node_info["peers"]) == 0

        # Step 3: Connect via pubkey (address is resolved from saved data)
        self.fiber1.get_client().connect_peer({"pubkey": self.fiber2.get_pubkey()})

        # Step 4: Verify connection
        time.sleep(1)
        node_info = self.fiber1.get_client().node_info()
        assert node_info["peers_count"] == "0x1"

        peers = self.fiber1.get_client().list_peers()
        assert len(peers["peers"]) == 1
        assert peers["peers"][0]["pubkey"] == self.fiber2.get_pubkey()


    def test_connect_peer_via_pubkey_failure(self):
        """
        Test connecting to a peer via pubkey (failure case).

        When the target node's address is NOT in the local graph (no NodeAnnouncement
        synced, never saved), connect_peer with pubkey returns an address resolution error.
        See upgradeGuide.md.

        Steps:
        1. Use a pubkey that is not in fiber1's graph (unknown node).
        2. Attempt to connect via pubkey.
        3. Verify that the call fails with an error.
        """
        unknown_pubkey = "02192d74d0cb94344c9569c2e77901507e6d9cafd1cd71d2342635e11eeb0b4aaf"

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().connect_peer({"pubkey": unknown_pubkey})

        # Expect error related to address resolution
        error_msg = str(exc_info.value).lower()
        assert "address" in error_msg or "resolve" in error_msg or "not found" in error_msg or "error" in error_msg

    def test_connect_peer(self):
        """
        Test connecting to a peer.

        Steps:
        1. Connect to an existing node.
        2. Attempt to connect to a non-existing node.
        3. Wait for 2 seconds to ensure the connection is established.
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

        # Step 3: Wait for 2 seconds to ensure the connection is established
        time.sleep(2)

        # Step 4: Retrieve node information
        node_info = self.fiber1.get_client().node_info()

        # Step 5: Assert that the peer count is 1
        assert node_info["peers_count"] == "0x1"

    @pytest.mark.skip("restart ,list_peer will empty ,not stable")
    def test_restart(self):
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        for i in range(5):
            self.fiber1.stop()
            self.fiber1.start()
            peers = self.fiber1.get_client().list_peers()
        time.sleep(2)
        self.fiber1.get_client().list_channels({})
        peers = self.fiber1.get_client().list_peers()
        assert len(peers["peers"]) == 1
