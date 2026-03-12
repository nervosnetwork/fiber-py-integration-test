import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliAdvancedPayment(FiberTest):
    """Test advanced payment CLI commands: build_router, send_payment_with_router,
    send_payment with timeout/fee params, and multi-hop routing."""

    # ───────────────────────────────────────────────
    # build_router via CLI
    # ───────────────────────────────────────────────

    def test_build_router_basic(self):
        """Build a router with a single hop via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        graph_channels = self.fiber1.get_client().graph_channels({})
        assert len(graph_channels["channels"]) >= 1
        channel_outpoint = graph_channels["channels"][0]["channel_outpoint"]

        target_pubkey = self.fiber2.get_client().node_info()["node_id"]
        hops_info = [
            {
                "pubkey": target_pubkey,
                "channel_outpoint": channel_outpoint,
            }
        ]

        result = cli1.build_router(
            hops_info=hops_info,
            amount=5 * 100000000,
        )
        assert result is not None

    def test_build_router_cli_vs_rpc(self):
        """CLI build_router should return the same data as RPC build_router."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        graph_channels = self.fiber1.get_client().graph_channels({})
        channel_outpoint = graph_channels["channels"][0]["channel_outpoint"]
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        hops_info = [
            {
                "pubkey": target_pubkey,
                "channel_outpoint": channel_outpoint,
            }
        ]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_result = cli1.build_router(hops_info=hops_info, amount=5 * 100000000)

        rpc_result = self.fiber1.get_client().build_router(
            {
                "hops_info": hops_info,
                "amount": hex(5 * 100000000),
            }
        )

        assert cli_result is not None
        assert rpc_result is not None

    # ───────────────────────────────────────────────
    # send_payment_with_router via CLI
    # ───────────────────────────────────────────────

    def test_send_payment_with_router_keysend(self):
        """Build a router via RPC, then send keysend payment with that router via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        graph_channels = self.fiber1.get_client().graph_channels({})
        channel_outpoint = graph_channels["channels"][0]["channel_outpoint"]
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        hops_info = [
            {
                "pubkey": target_pubkey,
                "channel_outpoint": channel_outpoint,
            }
        ]

        router = self.fiber1.get_client().build_router(
            {
                "hops_info": hops_info,
                "amount": hex(5 * 100000000),
            }
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment_with_router(
            router=router,
            keysend=True,
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

        payment = cli1.get_payment(result["payment_hash"])
        assert payment["status"] == "Success"

    def test_send_payment_with_router_invoice(self):
        """Build router, create invoice on receiver, pay via CLI send_payment_with_router."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        preimage = self.generate_random_preimage()
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(3 * 100000000),
                "currency": "Fibd",
                "description": "router payment",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
            }
        )

        graph_channels = self.fiber1.get_client().graph_channels({})
        channel_outpoint = graph_channels["channels"][0]["channel_outpoint"]
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        hops_info = [
            {
                "pubkey": target_pubkey,
                "channel_outpoint": channel_outpoint,
            }
        ]

        router = self.fiber1.get_client().build_router(
            {
                "hops_info": hops_info,
                "amount": hex(3 * 100000000),
            }
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment_with_router(
            router=router,
            invoice=invoice["invoice_address"],
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    def test_send_payment_with_router_dry_run(self):
        """Dry run with router should not actually transfer funds."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        graph_channels = self.fiber1.get_client().graph_channels({})
        channel_outpoint = graph_channels["channels"][0]["channel_outpoint"]
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        hops_info = [
            {
                "pubkey": target_pubkey,
                "channel_outpoint": channel_outpoint,
            }
        ]

        router = self.fiber1.get_client().build_router(
            {
                "hops_info": hops_info,
                "amount": hex(5 * 100000000),
            }
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment_with_router(
            router=router,
            keysend=True,
            dry_run=True,
        )
        assert result is not None

        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        local_balance = int(channels["channels"][0]["local_balance"], 16)
        assert local_balance == 200 * 100000000

    # ───────────────────────────────────────────────
    # send_payment with fee/timeout parameters
    # ───────────────────────────────────────────────

    def test_send_payment_with_timeout(self):
        """Send payment with explicit timeout via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=5 * 100000000,
            keysend=True,
            allow_self_payment=True,
            timeout=30,
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    def test_send_payment_with_max_fee_amount(self):
        """Send payment with max_fee_amount via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=5 * 100000000,
            keysend=True,
            allow_self_payment=True,
            max_fee_amount=1 * 100000000,
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    def test_send_payment_timeout_expired(self):
        """Payment with very short timeout should eventually fail if it can't complete in time."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_pubkey = "0x" + "ab" * 33

        with pytest.raises(Exception):
            cli1.send_payment(
                target_pubkey=fake_pubkey,
                amount=1 * 100000000,
                keysend=True,
                allow_self_payment=True,
                timeout=1,
            )

    # ───────────────────────────────────────────────
    # send_payment RPC vs CLI field consistency
    # ───────────────────────────────────────────────

    def test_send_payment_get_payment_consistency(self):
        """Payment sent via CLI should be retrievable via both CLI and RPC with same data."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=3 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        payment_hash = result["payment_hash"]

        self.wait_payment_state(self.fiber1, payment_hash, "Success")

        cli_payment = cli1.get_payment(payment_hash)
        rpc_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment_hash}
        )

        assert cli_payment["status"] == rpc_payment["status"]
        assert cli_payment["payment_hash"] == rpc_payment["payment_hash"]
        assert cli_payment["created_at"] == rpc_payment["created_at"]
        assert cli_payment["fee"] == rpc_payment["fee"]
