import time

import pytest

from framework.basic_fiber import FiberTest
from framework.basic_share_fiber import SharedFiberTest
from framework.fnn_cli import FnnCli


class TestCliChannelShared(SharedFiberTest):
    """Tests that can share a common channel environment."""

    def setUp(self):
        """One-time channel setup, guarded by _channel_inited flag."""
        if getattr(TestCliChannelShared, "_channel_inited", False):
            return
        TestCliChannelShared._channel_inited = True

        # Open channel between fiber1 and fiber2
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

    def test_list_channels_with_peer_filter(self):
        """Open channel, then list channels filtering by pubkey via CLI."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels(pubkey=self.fiber2.get_pubkey())
        assert len(channels["channels"]) >= 1

        channels_self = cli1.list_channels(pubkey=self.fiber1.get_pubkey())
        assert len(channels_self["channels"]) == 0

    def test_update_channel_via_cli(self):
        """Open a channel, update its TLC fee via CLI, then verify."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        cli1.update_channel(
            channel_id,
            tlc_fee_proportional_millionths=2000,
        )
        time.sleep(1)

        channels_updated = self.fiber1.get_client().list_channels({})
        for ch in channels_updated["channels"]:
            if ch["channel_id"] == channel_id:
                assert ch["tlc_fee_proportional_millionths"] == hex(2000)

    def test_open_channel_cli_vs_rpc_consistency(self):
        """Ensure CLI list_channels returns same data as RPC list_channels."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_channels = cli1.list_channels()
        rpc_channels = self.fiber1.get_client().list_channels({})

        assert len(cli_channels["channels"]) == len(rpc_channels["channels"])
        for i in range(len(cli_channels["channels"])):
            assert (
                cli_channels["channels"][i]["channel_id"]
                == rpc_channels["channels"][i]["channel_id"]
            )
            assert (
                cli_channels["channels"][i]["local_balance"]
                == rpc_channels["channels"][i]["local_balance"]
            )
            assert (
                cli_channels["channels"][i]["remote_balance"]
                == rpc_channels["channels"][i]["remote_balance"]
            )

    def test_abandon_channel_via_cli(self):
        """Open a channel that gets auto-accepted, then verify abandon is rejected
        once signatures are exchanged — this is expected Fiber behavior."""

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        with pytest.raises(Exception) as exc_info:
            cli1.abandon_channel(channel_id)
        assert "cannot be abandoned" in str(
            exc_info.value
        ).lower() or "ChannelReady" in str(exc_info.value)
