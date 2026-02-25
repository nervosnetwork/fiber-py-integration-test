import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliChannel(FiberTest):
    """Test channel lifecycle commands via fnn-cli."""

    def test_open_channel_and_list(self):
        """Open a channel via CLI on fiber2 -> fiber1, then verify with list_channels."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            peer_id=self.fiber1.get_peer_id(),
            funding_amount=1000 * 100000000,
            public=True,
        )
        assert result is not None
        assert "temporary_channel_id" in result

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY"
        )

        channels = cli2.list_channels()
        assert "channels" in channels
        assert len(channels["channels"]) >= 1
        ready_channels = [
            ch
            for ch in channels["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert len(ready_channels) >= 1

    def test_list_channels_with_peer_filter(self):
        """Open channel, then list channels filtering by peer_id via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels(peer_id=self.fiber2.get_peer_id())
        assert len(channels["channels"]) >= 1

        channels_self = cli1.list_channels(peer_id=self.fiber1.get_peer_id())
        assert len(channels_self["channels"]) == 0

    def test_shutdown_channel_via_cli(self):
        """Open a channel via RPC, then shutdown via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        close_script = self.get_account_script(self.fiber1.account_private)
        cli1.shutdown_channel(
            channel_id=channel_id,
            close_script=close_script,
            fee_rate=1020,
        )
        time.sleep(20)

        channels_after = cli1.list_channels(include_closed=True)
        found = False
        for ch in channels_after["channels"]:
            if ch["channel_id"] == channel_id:
                found = True
                assert "CLOSED" in ch["state"]["state_name"] or ch["state"][
                    "state_name"
                ] in ["SHUTTING_DOWN", "CLOSED"]
        assert found, "Closed channel should still be visible with include_closed=True"

    def test_update_channel_via_cli(self):
        """Open a channel, update its TLC fee via CLI, then verify."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

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
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

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
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        with pytest.raises(Exception) as exc_info:
            cli1.abandon_channel(channel_id)
        assert "cannot be abandoned" in str(
            exc_info.value
        ).lower() or "CHANNEL_READY" in str(exc_info.value)
