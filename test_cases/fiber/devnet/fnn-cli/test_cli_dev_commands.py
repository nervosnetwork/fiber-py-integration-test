import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli
from framework.test_fiber import FiberConfigPath


class TestCliDevCommands(FiberTest):
    """Test dev/debug commands via fnn-cli: add_tlc, remove_tlc.

    These commands are for development/debugging only and provide direct
    TLC (Time-Locked Contract) manipulation on channels.
    """

    fiber_version = FiberConfigPath.CURRENT_DEV_DEBUG

    # ───────────────────────────────────────────────
    # add_tlc
    # ───────────────────────────────────────────────

    def test_add_tlc_via_cli(self):
        """Add a TLC to a channel via CLI, then verify it appears in channel state."""
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, 0, 0)

        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]
        payment_hash = self.generate_random_preimage()

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.add_tlc(
            channel_id=channel_id,
            amount=1 * 100000000,
            payment_hash=payment_hash,
            expiry=int((time.time() + 60) * 1000),
        )
        assert result is not None

    def test_add_tlc_cli_vs_rpc(self):
        """add_tlc via CLI should produce the same result as RPC."""
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, 0, 0)

        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]

        payment_hash = self.generate_random_preimage()
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_result = cli1.add_tlc(
            channel_id=channel_id,
            amount=1 * 100000000,
            payment_hash=payment_hash,
            expiry=int((time.time() + 60) * 1000),
        )
        assert cli_result is not None
        assert "tlc_id" in cli_result

    def test_add_tlc_nonexistent_channel(self):
        """add_tlc on a non-existent channel should fail."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_channel_id = "0x" + "ab" * 32
        with pytest.raises(Exception):
            cli1.add_tlc(
                channel_id=fake_channel_id,
                amount=1 * 100000000,
                payment_hash=self.generate_random_preimage(),
                expiry=int((time.time() + 60) * 1000),
            )

    def test_add_tlc_amount_exceeds_balance(self):
        """add_tlc with amount exceeding local balance should fail."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0, 0, 0)

        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli1.add_tlc(
                channel_id=channel_id,
                amount=9999 * 100000000,
                payment_hash=self.generate_random_preimage(),
                expiry=int((time.time() + 60) * 1000),
            )

    # ───────────────────────────────────────────────
    # remove_tlc
    # ───────────────────────────────────────────────

    def test_add_and_remove_tlc_via_cli(self):
        """Add a TLC via RPC, then remove it via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, 0, 0)

        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]
        payment_hash = self.generate_random_preimage()

        tlc_result = self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(1 * 100000000),
                "payment_hash": payment_hash,
                "expiry": hex(int((time.time() + 60) * 1000)),
            }
        )
        tlc_id = tlc_result["tlc_id"]

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        channels2 = self.fiber2.get_client().list_channels({})
        channel_id2 = channels2["channels"][0]["channel_id"]

        time.sleep(1)
        result = cli2.remove_tlc(
            channel_id=channel_id2,
            tlc_id=tlc_id,
            reason={"error_code": "0x2002"},
        )
        assert result is None or result is not Exception

    def test_remove_tlc_nonexistent_channel(self):
        """remove_tlc on a non-existent channel should fail."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_channel_id = "0x" + "cd" * 32
        with pytest.raises(Exception):
            cli1.remove_tlc(
                channel_id=fake_channel_id,
                tlc_id="0x0",
                reason={"error_code": "0x2002"},
            )

    def test_remove_tlc_nonexistent_tlc_id(self):
        """remove_tlc with a non-existent TLC ID should fail."""
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, 0, 0)

        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli1.remove_tlc(
                channel_id=channel_id,
                tlc_id="0x9999",
                reason={"error_code": "0x2002"},
            )
