"""Regression coverage for fiber PR #1466.

Payments with pending TLCs must still finish after rapid reconnect/reestablish.
"""

import time

from framework.basic_fiber import FiberTest


class TestPR1466ReestablishRetry(FiberTest):
    def test_pending_payments_finish_after_rapid_reconnects(self):
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 100 * 100000000)

        payment_hashes = []
        for _ in range(5):
            payment_hashes.append(
                self.send_payment(self.fiber1, self.fiber2, 1 * 100000000, False)
            )

        self.fiber1.get_client().disconnect_peer({"pubkey": self.fiber2.get_pubkey()})
        time.sleep(1)
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(1)
        self.fiber1.get_client().disconnect_peer({"pubkey": self.fiber2.get_pubkey()})
        time.sleep(1)
        self.fiber1.connect_peer(self.fiber2)

        for payment_hash in payment_hashes:
            self.wait_payment_state(self.fiber1, payment_hash, "Success", 120)

        channels = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )["channels"]
        assert channels[0].get("pending_tlcs", []) == []
