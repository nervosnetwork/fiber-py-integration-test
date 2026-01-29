"""
Watch tower tests for multiple channels shutdown (CKB + UDT).
Verifies balance consistency after force shutdown of several CKB and UDT channels.
"""

import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Timeout


class TestMutilShutdown(FiberTest):
    """
    Test watch tower behavior when shutting down multiple CKB and UDT channels.
    Opens several CKB and UDT channels, force shutdown in order, mine commits and splits,
    then asserts CKB/UDT balance deltas.
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_mutil_shutdown(self):
        """
        Shutdown multiple CKB and UDT channels; assert total CKB delta near zero and UDT unchanged.
        Step 1: Open multiple CKB channels between fiber1 and fiber2.
        Step 2: Open multiple UDT channels.
        Step 3: Force shutdown all channels in order (alternating initiator).
        Step 4: Wait for shutdown commits, mine until commit cells cleared.
        Step 5: Assert CKB balance change (sum across nodes) within tolerance; UDT unchanged.
        """
        ckb_channel_size = 4
        udt_channel_size = 4

        before_udt_balances = self.get_fibers_balance()

        # Step 1: Open CKB channels
        for i in range(ckb_channel_size):
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                self.fiber1.get_client(),
                self.fiber2.get_peer_id(),
                ChannelState.CHANNEL_READY,
            )
            time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Open UDT channels
        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        for i in range(udt_channel_size):
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(200)),
                    "public": True,
                    "funding_udt_type_script": udt_script,
                }
            )
            time.sleep(Timeout.POLL_INTERVAL)
            self.wait_for_channel_state(
                self.fiber1.get_client(),
                self.fiber2.get_peer_id(),
                ChannelState.CHANNEL_READY,
            )

        # Step 3: Shutdown channels in order (alternate fiber1 / fiber2 as initiator)
        channels = self.fiber1.get_client().list_channels({})
        is_node1 = True
        for channel in channels["channels"]:
            if is_node1:
                self.fiber1.get_client().shutdown_channel(
                    {"channel_id": channel["channel_id"], "force": True}
                )
            else:
                self.fiber2.get_client().shutdown_channel(
                    {"channel_id": channel["channel_id"], "force": True}
                )
            is_node1 = not is_node1

        # Step 4: Wait for shutdown commits, mine until commit cells cleared
        self.wait_tx_pool(1, 1000)
        time.sleep(5)
        for _ in range(10):
            self.Miner.miner_with_version(self.node, "0x0")
        time.sleep(5)
        while len(self.get_commit_cells()) > 0:
            self.node.getClient().generate_epochs("0x1", 0)
            time.sleep(10)

        # Step 5: Assert CKB and UDT balance changes
        after_udt_balances = self.get_fibers_balance()
        results = self.get_balance_change(before_udt_balances, after_udt_balances)
        ckb_tolerance = 50000
        assert abs(results[0]["ckb"] + results[1]["ckb"]) < ckb_tolerance
        assert results[0]["udt"] == 0
        assert results[1]["udt"] == 0
