import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliErrorHandling(FiberTest):
    """Systematic error-handling tests for fnn-cli commands.

    Validates that invalid inputs, missing required arguments, and operations
    on non-existent resources produce proper error messages via the CLI.
    """

    # ───────────────────────────────────────────────
    # info
    # ───────────────────────────────────────────────

    def test_info_unreachable_node(self):
        """CLI should fail clearly when the node is unreachable."""
        cli = FnnCli("http://127.0.0.1:19999")
        with pytest.raises(Exception) as exc_info:
            cli.node_info()
        assert exc_info.value

    # ───────────────────────────────────────────────
    # peer
    # ───────────────────────────────────────────────

    def test_connect_peer_malformed_multiaddr(self):
        """Malformed multiaddr should produce an error."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.connect_peer("not-a-valid-multiaddr")

    def test_connect_peer_empty_address(self):
        """Empty address string should produce an error."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.connect_peer("")

    def test_disconnect_nonexistent_peer(self):
        """Disconnecting a peer that was never connected should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.disconnect_peer("QmNonExistentPeerIdXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

    # ───────────────────────────────────────────────
    # channel - open
    # ───────────────────────────────────────────────

    def test_open_channel_zero_funding(self):
        """Opening a channel with zero funding should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception) as exc_info:
            cli.open_channel(
                peer_id=self.fiber2.get_peer_id(),
                funding_amount=0,
                public=True,
            )
        assert "greater than" in str(exc_info.value).lower() or "invalid" in str(
            exc_info.value
        ).lower() or "error" in str(exc_info.value).lower()

    def test_open_channel_nonexistent_peer(self):
        """Opening a channel with a non-connected peer should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.open_channel(
                peer_id="QmNonExistentPeerIdXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                funding_amount=1000 * 100000000,
                public=True,
            )

    # ───────────────────────────────────────────────
    # channel - list
    # ───────────────────────────────────────────────

    def test_list_channels_no_channels(self):
        """list_channels on a fresh node should return empty list."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli.list_channels()
        assert "channels" in result
        assert len(result["channels"]) == 0

    # ───────────────────────────────────────────────
    # channel - shutdown
    # ───────────────────────────────────────────────

    def test_shutdown_nonexistent_channel(self):
        """Shutting down a non-existent channel_id should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_channel_id = "0x" + "ab" * 32
        with pytest.raises(Exception):
            cli.shutdown_channel(channel_id=fake_channel_id)

    # ───────────────────────────────────────────────
    # channel - update
    # ───────────────────────────────────────────────

    def test_update_nonexistent_channel(self):
        """Updating a non-existent channel_id should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_channel_id = "0x" + "cd" * 32
        with pytest.raises(Exception):
            cli.update_channel(
                fake_channel_id,
                tlc_fee_proportional_millionths=5000,
            )

    # ───────────────────────────────────────────────
    # channel - abandon
    # ───────────────────────────────────────────────

    def test_abandon_nonexistent_channel(self):
        """Abandoning a non-existent channel should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_channel_id = "0x" + "ef" * 32
        with pytest.raises(Exception):
            cli.abandon_channel(fake_channel_id)

    def test_abandon_ready_channel(self):
        """Abandoning a CHANNEL_READY channel should fail (already funded)."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli.list_channels()
        channel_id = channels["channels"][0]["channel_id"]
        with pytest.raises(Exception):
            cli.abandon_channel(channel_id)

    # ───────────────────────────────────────────────
    # invoice
    # ───────────────────────────────────────────────

    def test_get_invoice_nonexistent_hash(self):
        """Getting an invoice with a non-existent payment_hash should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_hash = "0x" + "11" * 32
        with pytest.raises(Exception):
            cli.get_invoice(fake_hash)

    def test_cancel_invoice_nonexistent_hash(self):
        """Cancelling a non-existent invoice should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_hash = "0x" + "22" * 32
        with pytest.raises(Exception):
            cli.cancel_invoice(fake_hash)

    def test_cancel_already_cancelled_invoice(self):
        """Cancelling an already cancelled invoice should fail or be idempotent."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        preimage = self.generate_random_preimage()
        invoice = cli.new_invoice(
            amount=1 * 100000000,
            currency="Fibd",
            description="double cancel test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        parsed = cli._run_json(
            ["invoice", "parse_invoice", "--invoice", invoice["invoice_address"]]
        )
        payment_hash = parsed["invoice"]["data"]["payment_hash"]

        cli.cancel_invoice(payment_hash)
        got = cli.get_invoice(payment_hash)
        assert got["status"] == "Cancelled"

        with pytest.raises(Exception):
            cli.cancel_invoice(payment_hash)

    def test_parse_invoice_invalid_string(self):
        """Parsing a garbage invoice string should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.parse_invoice("not_a_valid_invoice_string")

    # ───────────────────────────────────────────────
    # payment
    # ───────────────────────────────────────────────

    def test_get_payment_nonexistent_hash(self):
        """Getting a non-existent payment should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        fake_hash = "0x" + "33" * 32
        with pytest.raises(Exception):
            cli.get_payment(fake_hash)

    def test_send_payment_no_channel(self):
        """Sending a payment without any open channel should fail."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]
        with pytest.raises(Exception):
            cli.send_payment(
                target_pubkey=target_pubkey,
                amount=1 * 100000000,
                keysend=True,
                allow_self_payment=True,
                timeout=5,
            )

    def test_send_payment_amount_exceeds_balance(self):
        """Payment amount larger than channel balance should fail."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["node_id"]
        with pytest.raises(Exception):
            cli.send_payment(
                target_pubkey=target_pubkey,
                amount=999 * 100000000,
                keysend=True,
                allow_self_payment=True,
                timeout=5,
            )

    def test_send_payment_to_self_without_flag(self):
        """Sending to self without allow_self_payment should fail."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber1.get_client().node_info()["node_id"]
        with pytest.raises(Exception):
            cli.send_payment(
                target_pubkey=target_pubkey,
                amount=1 * 100000000,
                keysend=True,
                timeout=5,
            )

    # ───────────────────────────────────────────────
    # graph
    # ───────────────────────────────────────────────

    def test_graph_nodes_empty_before_channel(self):
        """Before any channels, graph_nodes may have 0 or very few nodes."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli.graph_nodes()
        assert "nodes" in result

    def test_graph_channels_empty_before_channel(self):
        """Before any channels, graph_channels should be empty."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli.graph_channels()
        assert "channels" in result
        assert len(result["channels"]) == 0

    def test_graph_nodes_limit_zero(self):
        """Limit=0 should return empty or be handled gracefully."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli.graph_nodes(limit=0)
        assert "nodes" in result
        assert len(result["nodes"]) == 0

    # ───────────────────────────────────────────────
    # list_payments edge cases
    # ───────────────────────────────────────────────

    def test_list_payments_empty(self):
        """Before any payments, list_payments should return empty."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli.list_payments()
        assert "payments" in result
        assert len(result["payments"]) == 0

    def test_list_payments_invalid_status(self):
        """Filtering by an invalid status should fail or return empty."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        with pytest.raises(Exception):
            cli.list_payments(status="InvalidStatus")

    # ───────────────────────────────────────────────
    # output format edge cases
    # ───────────────────────────────────────────────

    def test_raw_data_json_output(self):
        """--raw-data with json format should produce valid JSON."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        import json
        raw = cli._run(["info", "node_info"], output_format="json", raw_data=True)
        parsed = json.loads(raw)
        assert parsed is not None

    def test_raw_data_yaml_output(self):
        """--raw-data with yaml format should produce valid YAML."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        import yaml
        raw = cli._run(["info", "node_info"], output_format="yaml", raw_data=True)
        parsed = yaml.safe_load(raw)
        assert parsed is not None
