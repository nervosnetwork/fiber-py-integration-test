import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliMultiHop(FiberTest):
    """Test multi-hop payment routing via fnn-cli (3-node topology).

    Topology: fiber1 <-> fiber2 <-> fiber3
    Payments: fiber1 -> fiber3 (routed through fiber2)
    """

    def setup_three_node_topology(self):
        """Set up a 3-node linear topology with channels: f1-f2 and f2-f3."""
        account3 = self.generate_account(10000)
        self.fiber3 = self.start_new_fiber(account3)
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(1)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)

        self.wait_graph_channels_sync(self.fiber1, 2)

    # ───────────────────────────────────────────────
    # Keysend multi-hop
    # ───────────────────────────────────────────────

    def test_keysend_multi_hop_via_cli(self):
        """Send keysend from fiber1 to fiber3 (routed through fiber2) via CLI."""
        self.setup_three_node_topology()

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=10 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

        payment = cli1.get_payment(result["payment_hash"])
        assert payment["status"] == "Success"

    # ───────────────────────────────────────────────
    # Invoice multi-hop
    # ───────────────────────────────────────────────

    def test_invoice_payment_multi_hop_via_cli(self):
        """Create invoice on fiber3, pay from fiber1 via CLI (routed through fiber2)."""
        self.setup_three_node_topology()

        cli3 = FnnCli(f"http://127.0.0.1:{self.fiber3.rpc_port}")
        preimage = self.generate_random_preimage()
        invoice_result = cli3.new_invoice(
            amount=5 * 100000000,
            currency="Fibd",
            description="multi-hop invoice test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice_result

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment(invoice=invoice_result["invoice_address"])
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    # ───────────────────────────────────────────────
    # build_router multi-hop
    # ───────────────────────────────────────────────

    def test_build_router_multi_hop_via_cli(self):
        """Build a 2-hop router via CLI: fiber1 -> fiber2 -> fiber3."""
        self.setup_three_node_topology()

        graph_channels = self.fiber1.get_client().graph_channels({})
        assert len(graph_channels["channels"]) >= 2

        fiber2_pubkey = self.fiber2.get_client().node_info()["pubkey"]
        fiber3_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        ch_f1_f2 = None
        ch_f2_f3 = None
        for ch in graph_channels["channels"]:
            nodes = {ch["node1"], ch["node2"]}
            if fiber2_pubkey in nodes and fiber3_pubkey in nodes:
                ch_f2_f3 = ch["channel_outpoint"]
            elif fiber2_pubkey in nodes:
                ch_f1_f2 = ch["channel_outpoint"]

        assert ch_f1_f2 is not None, "Channel f1-f2 not found in graph"
        assert ch_f2_f3 is not None, "Channel f2-f3 not found in graph"

        hops_info = [
            {"pubkey": fiber2_pubkey, "channel_outpoint": ch_f1_f2},
            {"pubkey": fiber3_pubkey, "channel_outpoint": ch_f2_f3},
        ]

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.build_router(hops_info=hops_info, amount=5 * 100000000)
        assert result is not None

    # ───────────────────────────────────────────────
    # send_payment_with_router multi-hop
    # ───────────────────────────────────────────────

    def test_send_payment_with_router_multi_hop_keysend(self):
        """Build router for 2-hop path, send keysend via CLI."""
        self.setup_three_node_topology()

        graph_channels = self.fiber1.get_client().graph_channels({})
        fiber2_pubkey = self.fiber2.get_client().node_info()["pubkey"]
        fiber3_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        ch_f1_f2 = None
        ch_f2_f3 = None
        for ch in graph_channels["channels"]:
            nodes = {ch["node1"], ch["node2"]}
            if fiber2_pubkey in nodes and fiber3_pubkey in nodes:
                ch_f2_f3 = ch["channel_outpoint"]
            elif fiber2_pubkey in nodes:
                ch_f1_f2 = ch["channel_outpoint"]

        hops_info = [
            {"pubkey": fiber2_pubkey, "channel_outpoint": ch_f1_f2},
            {"pubkey": fiber3_pubkey, "channel_outpoint": ch_f2_f3},
        ]

        router = self.fiber1.get_client().build_router(
            {"hops_info": hops_info, "amount": hex(5 * 100000000)}
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment_with_router(router=router, keysend=True)
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    def test_send_payment_with_router_multi_hop_invoice(self):
        """Build router for 2-hop path, pay invoice on fiber3 via CLI."""
        self.setup_three_node_topology()

        preimage = self.generate_random_preimage()
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(3 * 100000000),
                "currency": "Fibd",
                "description": "multi-hop router invoice",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
            }
        )

        graph_channels = self.fiber1.get_client().graph_channels({})
        fiber2_pubkey = self.fiber2.get_client().node_info()["pubkey"]
        fiber3_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        ch_f1_f2 = None
        ch_f2_f3 = None
        for ch in graph_channels["channels"]:
            nodes = {ch["node1"], ch["node2"]}
            if fiber2_pubkey in nodes and fiber3_pubkey in nodes:
                ch_f2_f3 = ch["channel_outpoint"]
            elif fiber2_pubkey in nodes:
                ch_f1_f2 = ch["channel_outpoint"]

        hops_info = [
            {"pubkey": fiber2_pubkey, "channel_outpoint": ch_f1_f2},
            {"pubkey": fiber3_pubkey, "channel_outpoint": ch_f2_f3},
        ]

        router = self.fiber1.get_client().build_router(
            {"hops_info": hops_info, "amount": hex(3 * 100000000)}
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment_with_router(
            router=router, invoice=invoice["invoice_address"]
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    # ───────────────────────────────────────────────
    # Multi-hop balance verification
    # ───────────────────────────────────────────────

    def test_multi_hop_balance_after_payment(self):
        """After a multi-hop payment, verify channel balances shifted correctly."""
        self.setup_three_node_topology()

        channels_f1_before = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_f1_before = int(channels_f1_before["channels"][0]["local_balance"], 16)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber3.get_client().node_info()["pubkey"]
        payment_amount = 10 * 100000000

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=payment_amount,
            keysend=True,
            allow_self_payment=True,
        )
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

        channels_f1_after = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_f1_after = int(channels_f1_after["channels"][0]["local_balance"], 16)

        assert local_f1_after < local_f1_before
        payment = cli1.get_payment(result["payment_hash"])
        fee = int(payment["fee"], 16)
        assert local_f1_before - local_f1_after == payment_amount + fee

    # ───────────────────────────────────────────────
    # Multi-hop with max_fee_amount
    # ───────────────────────────────────────────────

    def test_multi_hop_with_max_fee_amount(self):
        """Send multi-hop payment with max_fee_amount constraint via CLI."""
        self.setup_three_node_topology()

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=5 * 100000000,
            keysend=True,
            allow_self_payment=True,
            max_fee_amount=1 * 100000000,
        )
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")
        payment = cli1.get_payment(result["payment_hash"])
        assert int(payment["fee"], 16) <= 1 * 100000000

    # ───────────────────────────────────────────────
    # Dry-run multi-hop
    # ───────────────────────────────────────────────

    def test_multi_hop_dry_run(self):
        """Dry-run payment over multi-hop should not change balances."""
        self.setup_three_node_topology()

        channels_before = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_before = int(channels_before["channels"][0]["local_balance"], 16)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=5 * 100000000,
            keysend=True,
            allow_self_payment=True,
            dry_run=True,
        )
        assert result is not None

        channels_after = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_after = int(channels_after["channels"][0]["local_balance"], 16)
        assert local_after == local_before

    # ───────────────────────────────────────────────
    # CLI vs RPC consistency for multi-hop
    # ───────────────────────────────────────────────

    def test_multi_hop_get_payment_cli_vs_rpc(self):
        """get_payment via CLI and RPC should return identical data for multi-hop payment."""
        self.setup_three_node_topology()

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber3.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=5 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

        cli_payment = cli1.get_payment(result["payment_hash"])
        rpc_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": result["payment_hash"]}
        )

        assert cli_payment["status"] == rpc_payment["status"]
        assert cli_payment["payment_hash"] == rpc_payment["payment_hash"]
        assert cli_payment["fee"] == rpc_payment["fee"]
        assert cli_payment["created_at"] == rpc_payment["created_at"]
