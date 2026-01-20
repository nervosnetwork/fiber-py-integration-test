import time

from framework.basic_fiber import FiberTest


class TestAllowTrampolineRouting(FiberTest):
    def test_send_payment_with_allow_trampoline_routing(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )

        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), "CHANNEL_READY"
        )
        time.sleep(1)

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "allow_trampoline_routing": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "allow_trampoline_routing": False,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
