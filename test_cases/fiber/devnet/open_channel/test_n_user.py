"""
Test open_channel with N users: multiple fibers open channels to one hub, pay, then shutdown.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Timeout


class TestNUser(FiberTest):
    """
    Test N-user topology: one hub fiber, N-1 fibers open channel to hub, send payment, shutdown.
    """

    @pytest.mark.skip("skip")
    def test_n_user(self):
        """
        N users: start N fibers, each (except last) connects and opens channel to last; pay; shutdown.
        Step 1: Start n_user fibers; connect each to the last (hub).
        Step 2: Each opener opens channel to hub; wait CHANNEL_READY for all.
        Step 3: Each opener send_payment to hub.
        Step 4: Each opener shutdown_channel; wait CLOSED for all.
        """
        n_user = 5
        # Step 1: Start fibers and connect to hub (last fiber)
        for i in range(n_user):
            self.start_new_fiber(self.generate_account(10000))
        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].connect_peer(self.fibers[-1])
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Open channels to hub; wait CHANNEL_READY
        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].get_client().open_channel(
                {
                    "peer_id": self.fibers[-1].get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
        for i in range(0, len(self.fibers) - 1):
            self.wait_for_channel_state(
                self.fibers[i].get_client(),
                self.fibers[-1].get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        # Step 3: Send payment from each opener to hub
        for i in range(0, len(self.fibers) - 1):
            self.send_payment(self.fibers[i], self.fibers[-1])

        # Step 4: Shutdown channels; wait CLOSED
        for i in range(0, len(self.fibers) - 1):
            self.fibers[i].get_client().shutdown_channel(
                {
                    "channel_id": self.fibers[i]
                    .get_client()
                    .list_channels({"peer_id": self.fibers[-1].get_peer_id()})[
                        "channels"
                    ][0]["channel_id"],
                    "close_script": self.get_account_script(
                        self.fibers[i].account_private
                    ),
                    "fee_rate": hex(1020),  # 0x3FC
                }
            )
        for i in range(0, len(self.fibers) - 1):
            self.wait_for_channel_state(
                self.fibers[i].get_client(),
                self.fibers[-1].get_peer_id(),
                ChannelState.CLOSED,
                timeout=Timeout.CHANNEL_READY,
                include_closed=True,
            )
