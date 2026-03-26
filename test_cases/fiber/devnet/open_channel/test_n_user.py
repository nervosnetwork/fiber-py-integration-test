import time

import pytest

from framework.basic_fiber import FiberTest


class TestNUser(FiberTest):

    @pytest.mark.skip("skip")
    def test_n_user(self):
        n_user = 5
        for i in range(n_user):
            self.start_new_fiber(self.generate_account(10000))
        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].connect_peer(self.fibers[-1])
        time.sleep(1)
        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].get_client().open_channel(
                {
                    "pubkey": self.fibers[-1].get_pubkey(),
                    "funding_amount": hex(1000 * 100000000),
                    "public": True,
                }
            )
        for i in range(0, len(self.fibers) - 1):
            self.wait_for_channel_state(
                self.fibers[i].get_client(),
                self.fibers[-1].get_pubkey(),
                "ChannelReady",
                120,
            )

        for i in range(0, len(self.fibers) - 1):
            self.send_payment(self.fibers[i], self.fibers[-1])

        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].get_client().shutdown_channel(
                {
                    "channel_id": self.fibers[i]
                    .get_client()
                    .list_channels({"pubkey": self.fibers[-1].get_pubkey()})[
                        "channels"
                    ][0]["channel_id"],
                    "close_script": self.get_account_script(
                        self.fibers[i].account_private
                    ),
                    "fee_rate": "0x3FC",
                }
            )
        for i in range(0, len(self.fibers) - 1):
            self.wait_for_channel_state(
                self.fibers[i], self.fibers[-1].get_pubkey(), "Closed"
            )
