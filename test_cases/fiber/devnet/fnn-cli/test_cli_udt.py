import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliUdt(FiberTest):
    """Test UDT (User Defined Token) channel and payment operations via fnn-cli.

    Validates that the CLI correctly handles UDT type scripts when opening
    channels, creating invoices, and sending payments.
    """

    def get_udt_type_script(self):
        return self.get_account_udt_script(self.fiber1.account_private)

    def fund_accounts_for_udt(self):
        """Faucet UDT tokens to both fiber nodes."""
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        time.sleep(10)

    # ───────────────────────────────────────────────
    # Open UDT channel via CLI
    # ───────────────────────────────────────────────

    def test_open_udt_channel_via_cli(self):
        """Open a UDT channel via CLI with funding_udt_type_script."""
        self.fund_accounts_for_udt()

        udt_script = self.get_udt_type_script()
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=2000 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = cli1.list_channels()
        assert len(channels["channels"]) >= 1
        ch = channels["channels"][0]
        assert ch["funding_udt_type_script"] is not None

    # ───────────────────────────────────────────────
    # UDT keysend payment via CLI
    # ───────────────────────────────────────────────

    def test_udt_keysend_payment_via_cli(self):
        """Send UDT keysend payment via CLI after opening UDT channel."""
        self.fund_accounts_for_udt()

        udt_script = self.get_udt_type_script()
        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(2000 * 100000000),
                "public": True,
                "funding_udt_type_script": udt_script,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=10 * 100000000,
            keysend=True,
            allow_self_payment=True,
            udt_type_script=udt_script,
        )
        assert "payment_hash" in result
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    # ───────────────────────────────────────────────
    # UDT invoice via CLI
    # ───────────────────────────────────────────────

    def test_new_udt_invoice_via_cli(self):
        """Create a UDT invoice via CLI and verify it contains UDT type script."""
        udt_script = self.get_udt_type_script()

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        preimage = self.generate_random_preimage()

        invoice_result = cli2.new_invoice(
            amount=5 * 100000000,
            currency="Fibd",
            description="UDT invoice test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
            udt_type_script=udt_script,
        )
        assert "invoice_address" in invoice_result

        parsed = cli2.parse_invoice(invoice_result["invoice_address"])
        assert "invoice" in parsed

        attrs = parsed["invoice"]["data"]["attrs"]
        udt_found = False
        for attr in attrs:
            if isinstance(attr, dict) and "udt_script" in attr:
                udt_found = True
                break
        assert udt_found, f"UDT script should be present in invoice attrs: {attrs}"

    # ───────────────────────────────────────────────
    # UDT invoice payment via CLI
    # ───────────────────────────────────────────────

    def test_udt_invoice_payment_via_cli(self):
        """Create UDT invoice on fiber2, pay it from fiber1 via CLI."""
        self.fund_accounts_for_udt()
        udt_script = self.get_udt_type_script()

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(2000 * 100000000),
                "public": True,
                "funding_udt_type_script": udt_script,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )
        self.send_payment(self.fiber1, self.fiber2, 1000 * 100000000, True, udt_script)

        preimage = self.generate_random_preimage()
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(5 * 100000000),
                "currency": "Fibd",
                "description": "UDT CLI invoice payment",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
                "udt_type_script": udt_script,
            }
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment(invoice=invoice["invoice_address"])
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    # ───────────────────────────────────────────────
    # UDT channel list and verify via CLI
    # ───────────────────────────────────────────────

    def test_udt_channel_list_cli_vs_rpc(self):
        """Verify UDT channel shown via CLI matches RPC."""
        self.fund_accounts_for_udt()
        udt_script = self.get_udt_type_script()

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(2000 * 100000000),
                "public": True,
                "funding_udt_type_script": udt_script,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_channels = cli1.list_channels()
        rpc_channels = self.fiber1.get_client().list_channels({})

        assert len(cli_channels["channels"]) == len(rpc_channels["channels"])

        for cli_ch, rpc_ch in zip(cli_channels["channels"], rpc_channels["channels"]):
            assert cli_ch["channel_id"] == rpc_ch["channel_id"]
            assert (
                cli_ch["funding_udt_type_script"] == rpc_ch["funding_udt_type_script"]
            )
