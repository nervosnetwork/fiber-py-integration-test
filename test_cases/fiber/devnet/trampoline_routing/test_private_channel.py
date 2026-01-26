import time

import pytest

from framework.basic_fiber import FiberTest


class TestPrivateChannel(FiberTest):

    def test_private_channel(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 1000 * 100000000)

        channel = self.fiber2.get_client().list_channels(
            {
                "peer_id": self.fiber3.get_peer_id(),
            }
        )
        self.fiber2.get_client().update_channel(
            {"channel_id": channel["channels"][0]["channel_id"], "enabled": False}
        )
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Failed")

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        # 应该因为余额不足而失败
        assert "no path found" in exc_info.value.args[0] or "Failed" in str(
            exc_info.value
        )
