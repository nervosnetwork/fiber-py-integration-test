import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliAdvancedChannel(FiberTest):
    """Test advanced channel CLI commands: open with extra params,
    force close, only-pending filter, accept_channel, and update enabled."""

    start_fiber_config = {"fiber_auto_accept_amount": "0"}

    # ───────────────────────────────────────────────
    # open_channel with advanced parameters
    # ───────────────────────────────────────────────

    def test_open_channel_with_tlc_params(self):
        """Open channel via CLI with TLC fee and expiry delta."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=1000 * 100000000,
            public=True,
            tlc_fee_proportional_millionths=5000,
            tlc_expiry_delta=86400000,
        )
        assert "temporary_channel_id" in result

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=0,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

        channels = self.fiber2.get_client().list_channels(
            {"pubkey": self.fiber1.get_pubkey()}
        )
        assert len(channels["channels"]) >= 1
        ch = channels["channels"][0]
        assert ch["tlc_fee_proportional_millionths"] == hex(5000)

    def test_open_channel_with_max_tlc_limits(self):
        """Open channel via CLI with max_tlc_value_in_flight and max_tlc_number_in_flight."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=1000 * 100000000,
            public=True,
            max_tlc_value_in_flight=500 * 100000000,
            max_tlc_number_in_flight=10,
        )
        assert "temporary_channel_id" in result

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=0,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

    # ───────────────────────────────────────────────
    # accept_channel via CLI
    # ───────────────────────────────────────────────

    def test_accept_channel_via_cli(self):
        """Open channel with auto-accept disabled, accept via CLI."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        temp_id = result["temporary_channel_id"]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        accept_result = cli1.accept_channel(
            temporary_channel_id=temp_id,
            funding_amount=200 * 100000000,
        )
        assert accept_result is not None

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

        channels = cli2.list_channels()
        assert len(channels["channels"]) >= 1
        ch = channels["channels"][0]
        assert ch["state"]["state_name"] == "CHANNEL_READY"

    def test_accept_channel_with_tlc_params(self):
        """Accept channel via CLI with custom TLC parameters."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        temp_id = result["temporary_channel_id"]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=temp_id,
            funding_amount=100 * 100000000,
            tlc_fee_proportional_millionths=3000,
            max_tlc_number_in_flight=20,
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY"
        )

    # ───────────────────────────────────────────────
    # list_channels --only-pending
    # ───────────────────────────────────────────────

    def test_list_channels_only_pending(self):
        """only-pending filter should show channels not yet CHANNEL_READY."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        assert "temporary_channel_id" in result

        pending = cli2.list_channels(only_pending=True)
        assert "channels" in pending

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=0,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

        pending_after = cli2.list_channels(only_pending=True)
        assert len(pending_after["channels"]) == 0

    # ───────────────────────────────────────────────
    # update_channel --enabled false
    # ───────────────────────────────────────────────

    def test_update_channel_disable_and_enable(self):
        """Disable and re-enable a channel via CLI update_channel."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=100 * 100000000,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

        channels = cli2.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        cli2.update_channel(channel_id, enabled=False)
        time.sleep(1)

        cli2.update_channel(channel_id, enabled=True)
        time.sleep(1)

    # ───────────────────────────────────────────────
    # shutdown_channel --force
    # ───────────────────────────────────────────────

    def test_force_close_channel_via_cli(self):
        """Force close a channel via CLI shutdown_channel --force."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=100 * 100000000,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )

        channels = cli2.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        close_script = self.get_account_script(self.fiber2.account_private)
        cli2.shutdown_channel(
            channel_id=channel_id,
            close_script=close_script,
            fee_rate=1020,
            force=True,
        )
        time.sleep(20)

        channels_after = cli2.list_channels(include_closed=True)
        found = False
        for ch in channels_after["channels"]:
            if ch["channel_id"] == channel_id:
                found = True
                assert ch["state"]["state_name"] in [
                    "SHUTTING_DOWN",
                    "CLOSED",
                ]
        assert found

    # ───────────────────────────────────────────────
    # open_channel with one-way flag
    # ───────────────────────────────────────────────

    def test_open_one_way_channel_via_cli(self):
        """Open a one-way channel via CLI."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        result = cli2.open_channel(
            pubkey=self.fiber1.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
            one_way=True,
        )
        assert "temporary_channel_id" in result

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli1.accept_channel(
            temporary_channel_id=result["temporary_channel_id"],
            funding_amount=0,
        )

        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_pubkey(), "CHANNEL_READY"
        )
