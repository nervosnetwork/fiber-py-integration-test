"""
Test cases for send_payment with peer disconnect: payments in flight, disconnect, reconnect, wait.
"""
from framework.basic_fiber import FiberTest


class TestDisconnect(FiberTest):
    """
    Test send_payment behaviour when peer is disconnected: open channel, send payments
    without wait, disconnect peer, reconnect, wait for payments to finish and pending TLC zero.
    """

    def test_connect_peer_and_list_peers(self):
        """
        Smoke test: connect fiber1 to fiber2 and list peers.
        Step 1: Connect fiber1 to fiber2. Step 2: Call list_peers on fiber1.
        """
        # Step 1: Connect fiber1 to fiber2
        self.fiber1.connect_peer(self.fiber2)
        # Step 2: Call list_peers on fiber1
        self.fiber1.get_client().list_peers()
