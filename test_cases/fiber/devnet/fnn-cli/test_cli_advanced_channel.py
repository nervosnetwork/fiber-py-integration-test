import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.fnn_cli import FnnCli


class TestCliAdvancedChannel(FiberTest):
    """Test advanced channel CLI commands: open with extra params,
    force close, only-pending filter, accept_channel, and update enabled."""

    start_fiber_config = {
        "fiber_auto_accept_channel_ckb_funding_amount": 0,
    }

    # Open/accept direction matches accept_channel/test_max_tlc_number_in_flight_debug.py:
    # fiber1 initiates open_channel, fiber2 accept_channel. The reverse (fiber2 open,
    # fiber1 accept) consistently hits "No channel with temp id ... found" on the
    # acceptor in practice, so all tests below use cli1 open -> cli2 accept.

    def _accept_channel_when_ready(
        self, cli_acceptor, temporary_channel_id, funding_amount, **kwargs
    ):
        """Call accept_channel after the acceptor has registered the pending open.

        First polls the acceptor's RPC list_channels until the pending channel
        appears (NegotiatingFunding state), then retries accept_channel via CLI.
        This is more reliable than blind retries in CI where P2P delivery may
        take longer than expected.
        """
        from framework.fiber_rpc import FiberRPCClient

        time.sleep(3)  # increased from 1s: give P2P message more time to propagate

        # Poll acceptor's RPC until the pending channel appears
        rpc_client = FiberRPCClient(cli_acceptor.rpc_url)
        for _ in range(120):  # up to 60s
            try:
                channels = rpc_client.list_channels({"include_closed": False})
                pending = [
                    ch
                    for ch in channels.get("channels", [])
                    if ch.get("state", {}).get("state_name") == "NegotiatingFunding"
                ]
                if pending:
                    break
            except Exception:
                pass
            time.sleep(0.5)

        # Now attempt accept_channel via CLI with retries
        last_exc = None
        for _ in range(120):  # increased from 60 to 120 (~63s total)
            try:
                return cli_acceptor.accept_channel(
                    temporary_channel_id=temporary_channel_id,
                    funding_amount=funding_amount,
                    **kwargs,
                )
            except Exception as e:
                last_exc = e
                err = str(e).lower()
                if "no channel with temp id" not in err and "temp id" not in err:
                    raise
                time.sleep(0.5)
        if last_exc:
            raise last_exc
        raise RuntimeError("accept_channel retry exhausted")

    # ───────────────────────────────────────────────
    # open_channel with advanced parameters
    # ───────────────────────────────────────────────

    def test_open_channel_with_tlc_params(self):
        """Open channel via CLI with TLC fee and expiry delta."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=1000 * 100000000,
            public=True,
            tlc_fee_proportional_millionths=5000,
            tlc_expiry_delta=86400000,
        )
        assert "temporary_channel_id" in result

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], DEFAULT_MIN_DEPOSIT_CKB
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        assert len(channels["channels"]) >= 1
        ch = channels["channels"][0]
        assert ch["tlc_fee_proportional_millionths"] == hex(5000)

    def test_open_channel_with_max_tlc_limits(self):
        """Open channel via CLI with max_tlc_value_in_flight and max_tlc_number_in_flight."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=1000 * 100000000,
            public=True,
            max_tlc_value_in_flight=500 * 100000000,
            max_tlc_number_in_flight=10,
        )
        assert "temporary_channel_id" in result

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], DEFAULT_MIN_DEPOSIT_CKB
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

    # ───────────────────────────────────────────────
    # accept_channel via CLI
    # ───────────────────────────────────────────────

    def test_accept_channel_via_cli(self):
        """Open channel with auto-accept disabled, accept via CLI."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        temp_id = result["temporary_channel_id"]

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        accept_result = self._accept_channel_when_ready(cli2, temp_id, 200 * 100000000)
        assert accept_result is not None

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = cli1.list_channels()
        assert len(channels["channels"]) >= 1
        ch = channels["channels"][0]
        assert ch["state"]["state_name"] == "ChannelReady"

    def test_accept_channel_with_tlc_params(self):
        """Accept channel via CLI with custom TLC parameters."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        temp_id = result["temporary_channel_id"]

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2,
            temp_id,
            100 * 100000000,
            tlc_fee_proportional_millionths=3000,
            max_tlc_number_in_flight=20,
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

    # ───────────────────────────────────────────────
    # list_channels --only-pending
    # ───────────────────────────────────────────────

    def test_list_channels_only_pending(self):
        """only-pending filter should show channels not yet CHANNEL_READY."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )
        assert "temporary_channel_id" in result

        pending = cli1.list_channels(only_pending=True)
        assert "channels" in pending

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], DEFAULT_MIN_DEPOSIT_CKB
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        pending_after = cli1.list_channels(only_pending=True)
        assert len(pending_after["channels"]) == 0

    # ───────────────────────────────────────────────
    # update_channel --enabled false
    # ───────────────────────────────────────────────

    def test_update_channel_disable_and_enable(self):
        """Disable and re-enable a channel via CLI update_channel."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], 100 * 100000000
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        cli1.update_channel(channel_id, enabled=False)
        time.sleep(1)

        cli1.update_channel(channel_id, enabled=True)
        time.sleep(1)

    # ───────────────────────────────────────────────
    # shutdown_channel --force
    # ───────────────────────────────────────────────

    def test_force_close_channel_via_cli(self):
        """Force close a channel via CLI shutdown_channel --force."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=True,
        )

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], 100 * 100000000
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = cli1.list_channels()
        channel_id = channels["channels"][0]["channel_id"]

        cli1.shutdown_channel(
            channel_id=channel_id,
            force=True,
        )
        time.sleep(20)

        channels_after = cli1.list_channels(include_closed=True)
        found = False
        for ch in channels_after["channels"]:
            if ch["channel_id"] == channel_id:
                found = True
                assert ch["state"]["state_name"] in [
                    "ShuttingDown",
                    "Closed",
                ]
        assert found

    # ───────────────────────────────────────────────
    # open_channel with one-way flag
    # ───────────────────────────────────────────────

    def test_open_one_way_channel_via_cli(self):
        """Open a one-way channel via CLI."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=500 * 100000000,
            public=False,
            one_way=True,
        )
        assert "temporary_channel_id" in result

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        self._accept_channel_when_ready(
            cli2, result["temporary_channel_id"], DEFAULT_MIN_DEPOSIT_CKB
        )

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )
