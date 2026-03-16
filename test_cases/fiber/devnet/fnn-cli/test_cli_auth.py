import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli

AUTH_TOKEN = (
    "EsQCCtkBCghjaGFubmVscwoIbWVzc2FnZXMKBWNoYWluCgVncmFwaAoIaW52b2ljZXMK"
    "CHBheW1lbnRzCgVwZWVycwoKd2F0Y2h0b3dlchgDIgkKBwgBEgMYgAgiCQoHCAASAxiA"
    "CCIJCgcIARIDGIEIIgkKBwgBEgMYgggiCQoHCAASAxiDCCIICgYIABICGBgiCQoHCAES"
    "AxiECCIJCgcIABIDGIQIIgkKBwgBEgMYhQgiCQoHCAASAxiFCCIJCgcIARIDGIYIIgkK"
    "BwgAEgMYhggiCQoHCAESAxiHCBIkCAASINfXW27Y4O0VbCYm7ZmQdwAnTsHUzMX1vKt2"
    "ntZAm0knGkAEipd0kOQyxA9h6oq8OC_267N-V9ukmJsSKAPWbvsjtAwsqWftJq1DbM_j"
    "ZUOte00x_jqIrKsPwkKjo_Aaq14AIiIKIFbhKm3u63rug1IRE7jtW6uSHaZyrIS-6kiK"
    "olenfKHm"
)

REMOTE_RPC_URL = "http://16.162.99.28:8129/"
REMOTE_CURRENCY = "Fibt"


class TestCliAuth(FiberTest):
    """Test complete Fiber transaction lifecycle via CLI with Biscuit auth token."""

    def _make_cli(self, fiber, auth_token=AUTH_TOKEN):
        return FnnCli(
            f"http://127.0.0.1:{fiber.rpc_port}",
            auth_token=auth_token,
        )

    def test_full_transaction_lifecycle_with_auth(self):
        """End-to-end flow via CLI with auth token:
        node_info -> open_channel -> keysend -> invoice payment ->
        get_payment -> list_payments -> shutdown_channel
        """
        cli1 = self._make_cli(self.fiber1)
        cli2 = self._make_cli(self.fiber2)

        # 1. node_info
        info1 = cli1.node_info()
        assert "pubkey" in info1
        info2 = cli2.node_info()
        assert "pubkey" in info2

        # 2. list_peers
        peers = cli1.list_peers()
        assert "peers" in peers

        # 3. open_channel
        open_result = cli1.open_channel(
            pubkey=info2["pubkey"],
            funding_amount=1000 * 100000000,
            public=True,
        )
        assert "temporary_channel_id" in open_result

        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

        channels = cli1.list_channels()
        assert len(channels["channels"]) >= 1
        channel_id = channels["channels"][0]["channel_id"]

        # 4. keysend payment
        keysend_result = cli1.send_payment(
            target_pubkey=info2["pubkey"],
            amount=10 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        assert "payment_hash" in keysend_result
        self.wait_payment_state(self.fiber1, keysend_result["payment_hash"], "Success")

        keysend_detail = cli1.get_payment(keysend_result["payment_hash"])
        assert keysend_detail["status"] == "Success"

        # 5. invoice payment
        preimage = self.generate_random_preimage()
        invoice = cli2.new_invoice(
            amount=5 * 100000000,
            currency="Fibd",
            description="auth token test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice

        inv_result = cli1.send_payment(invoice=invoice["invoice_address"])
        assert "payment_hash" in inv_result
        self.wait_payment_state(self.fiber1, inv_result["payment_hash"], "Success")

        inv_detail = cli1.get_payment(inv_result["payment_hash"])
        assert inv_detail["status"] == "Success"

        # 6. list_payments — should contain both payments
        payments = cli1.list_payments()
        assert len(payments["payments"]) >= 2
        listed_hashes = {p["payment_hash"] for p in payments["payments"]}
        assert keysend_result["payment_hash"] in listed_hashes
        assert inv_result["payment_hash"] in listed_hashes

        # 7. shutdown_channel
        close_script = self.get_account_script(self.fiber1.account_private)
        cli1.shutdown_channel(
            channel_id=channel_id,
            close_script=close_script,
            fee_rate=1020,
        )
        time.sleep(20)

        channels_after = cli1.list_channels(include_closed=True)
        closed = [
            ch for ch in channels_after["channels"] if ch["channel_id"] == channel_id
        ]
        assert len(closed) == 1
        assert closed[0]["state"]["state_name"] in [
            "ShuttingDown",
            "Closed",
        ]

    def test_node_info_with_auth(self):
        """Verify node_info succeeds when auth token is provided."""
        cli = self._make_cli(self.fiber1)
        info = cli.node_info()
        assert "pubkey" in info
        assert "node_name" in info
        assert "addresses" in info

    def test_open_channel_and_keysend_with_auth(self):
        """Open channel and send keysend payment, all via CLI with auth token."""
        cli1 = self._make_cli(self.fiber1)
        cli2 = self._make_cli(self.fiber2)
        target_pubkey = cli2.node_info()["pubkey"]

        cli1.open_channel(
            pubkey=target_pubkey,
            funding_amount=1000 * 100000000,
            public=True,
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady"
        )

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

    def test_invoice_flow_with_auth(self):
        """Create invoice on node2, pay from node1 — all via CLI with auth token."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = self._make_cli(self.fiber1)
        cli2 = self._make_cli(self.fiber2)

        preimage = self.generate_random_preimage()
        invoice = cli2.new_invoice(
            amount=5 * 100000000,
            currency="Fibd",
            description="invoice auth test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice

        parsed = cli1.parse_invoice(invoice["invoice_address"])
        assert parsed is not None

        result = cli1.send_payment(invoice=invoice["invoice_address"])
        assert "payment_hash" in result
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

        inv_status = cli2.get_invoice(result["payment_hash"])
        assert inv_status["status"] == "Paid"

    def test_list_channels_with_auth(self):
        """List channels via CLI with auth token and verify consistency with RPC."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = self._make_cli(self.fiber1)
        cli_channels = cli1.list_channels()
        rpc_channels = self.fiber1.get_client().list_channels({})

        assert len(cli_channels["channels"]) == len(rpc_channels["channels"])
        for cli_ch, rpc_ch in zip(cli_channels["channels"], rpc_channels["channels"]):
            assert cli_ch["channel_id"] == rpc_ch["channel_id"]

    def test_list_payments_with_auth(self):
        """Send multiple payments, list them via CLI with auth token."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        cli1 = self._make_cli(self.fiber1)
        target_pubkey = self.fiber2.get_client().node_info()["pubkey"]

        hashes = []
        for _ in range(3):
            r = cli1.send_payment(
                target_pubkey=target_pubkey,
                amount=1 * 100000000,
                keysend=True,
                allow_self_payment=True,
            )
            self.wait_payment_state(self.fiber1, r["payment_hash"], "Success")
            hashes.append(r["payment_hash"])

        payments = cli1.list_payments()
        assert len(payments["payments"]) >= 3
        listed_hashes = {p["payment_hash"] for p in payments["payments"]}
        for h in hashes:
            assert h in listed_hashes

    def test_auth_via_env_variable(self):
        """Verify that FNN_AUTH_TOKEN env variable is picked up by fnn-cli."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        info = cli.run_raw(
            ["info", "node_info"],
            env_override={"FNN_AUTH_TOKEN": AUTH_TOKEN},
        )
        assert "pubkey" in info


class TestCliAuthRemote:
    """Tests against the remote authenticated Fiber node at REMOTE_RPC_URL.

    These tests require network access to the remote node and are
    skipped by default.  Run with:
        pytest ... -k TestCliAuthRemote --run-remote
    """

    @pytest.fixture(autouse=True)
    def _skip_unless_remote(self, request):
        if not request.config.getoption("--run-remote", default=False):
            pytest.skip("need --run-remote to execute remote auth tests")

    @staticmethod
    def _remote_cli():
        return FnnCli(REMOTE_RPC_URL, auth_token=AUTH_TOKEN)

    @staticmethod
    def _wait_for_channel_state(cli, expected_state, timeout=300):
        last_logged = ""
        for i in range(timeout):
            channels = cli.list_channels()
            ch_list = channels.get("channels", [])
            for ch in ch_list:
                state = ch["state"]["state_name"]
                if state == expected_state:
                    print(
                        f"  [channel] reached {expected_state} after {i}s, "
                        f"id={ch['channel_id']}"
                    )
                    return ch["channel_id"]
            summary = (
                ", ".join(
                    f"{ch['channel_id'][:18]}..={ch['state']['state_name']}"
                    for ch in ch_list
                )
                if ch_list
                else "(no channels)"
            )
            if summary != last_logged or i % 15 == 0:
                print(f"  [wait {i}s] channels: {summary}")
                last_logged = summary
            time.sleep(1)
        raise TimeoutError(
            f"No channel reached state {expected_state} within {timeout}s. "
            f"Last seen: {last_logged}"
        )

    @staticmethod
    def _wait_payment_state(cli, payment_hash, expected, timeout=300):
        for i in range(timeout):
            payment = cli.get_payment(payment_hash)
            status = payment["status"]
            if i % 10 == 0:
                print(
                    f"  [wait {i}s] payment {payment_hash[:18]}.. " f"status={status}"
                )
            if status == expected:
                return payment
            if status in ("Failed", "Success"):
                print(
                    f"  [payment] terminal state={status}, "
                    f"error={payment.get('failed_error')}"
                )
                return payment
            time.sleep(1)
        raise TimeoutError(
            f"Payment {payment_hash} did not reach {expected} within {timeout}s"
        )

    # ── smoke tests ────────────────────────────────────────────────

    def test_remote_node_info(self):
        """Fetch node_info from the remote authenticated node."""
        cli = self._remote_cli()
        info = cli.node_info()
        assert "pubkey" in info
        assert "addresses" in info

    def test_remote_list_channels(self):
        """List channels on the remote authenticated node."""
        cli = self._remote_cli()
        channels = cli.list_channels()
        assert "channels" in channels

    def test_remote_list_peers(self):
        """List peers on the remote authenticated node."""
        cli = self._remote_cli()
        peers = cli.list_peers()
        assert "peers" in peers

    def test_remote_list_payments(self):
        """List payments on the remote authenticated node."""
        cli = self._remote_cli()
        payments = cli.list_payments()
        assert "payments" in payments

    def test_remote_graph_nodes(self):
        """Query graph nodes on the remote authenticated node."""
        cli = self._remote_cli()
        nodes = cli.graph_nodes(limit=5)
        assert "nodes" in nodes

    def test_remote_graph_channels(self):
        """Query graph channels on the remote authenticated node."""
        cli = self._remote_cli()
        channels = cli.graph_channels(limit=5)
        assert "channels" in channels

    # ── full lifecycle on remote node ──────────────────────────────

    def test_remote_full_lifecycle(self):
        """End-to-end on the REMOTE node:
        node_info -> pick peer -> open_channel -> keysend -> list_payments
        -> shutdown_channel

        Requires: remote node has >=1 connected peer with auto-accept
        enabled and sufficient CKB balance for funding.
        """
        cli = self._remote_cli()

        # 1. node_info
        info = cli.node_info()
        assert "pubkey" in info
        print(f"\n[step 1] node_info OK  pubkey={info['pubkey'][:20]}...")

        # 2. pick a peer and query its auto-accept minimum via graph_nodes
        peers = cli.list_peers()
        peer_list = peers["peers"] if isinstance(peers, dict) else peers
        assert len(peer_list) >= 1, "Remote node has no peers to open channel with"
        peer_pubkey = peer_list[0]["pubkey"]
        print(f"[step 2] peers={len(peer_list)}, " f"target peer={peer_pubkey[:20]}...")

        min_ckb_funding = 500 * 100000000
        graph = cli.graph_nodes(limit=100)
        for node in graph.get("nodes", []):
            if node.get("node_id") == peer_pubkey:
                raw = node.get("auto_accept_min_ckb_funding_amount", "0x0")
                if raw and raw != "0x0":
                    min_ckb_funding = int(raw, 16)
                print(
                    f"  peer auto_accept_min_ckb = {min_ckb_funding} "
                    f"({min_ckb_funding // 100000000} CKB)"
                )
                break

        funding_amount = max(min_ckb_funding + 100 * 100000000, 500 * 100000000)
        print(
            f"  using funding_amount = {funding_amount} "
            f"({funding_amount // 100000000} CKB)"
        )

        # 3. open_channel
        open_result = cli.open_channel(
            pubkey=peer_pubkey,
            funding_amount=funding_amount,
            public=True,
        )
        assert "temporary_channel_id" in open_result
        print(
            f"[step 3] open_channel OK  "
            f"temp_id={open_result['temporary_channel_id'][:20]}..."
        )

        # check initial channel state immediately
        time.sleep(2)
        initial_channels = cli.list_channels()
        for ch in initial_channels.get("channels", []):
            print(
                f"  [diag] channel {ch['channel_id'][:18]}.. "
                f"state={ch['state']['state_name']}"
            )
        pending = cli.list_channels(only_pending=True)
        for ch in pending.get("channels", []):
            print(
                f"  [diag-pending] channel {ch['channel_id'][:18]}.. "
                f"state={ch['state']['state_name']}"
            )

        # 4. wait for ChannelReady (up to 5 min for on-chain confirmation)
        print("[step 4] waiting for ChannelReady ...")
        channel_id = self._wait_for_channel_state(cli, "ChannelReady", timeout=300)
        assert channel_id is not None
        print(f"[step 4] ChannelReady!  channel_id={channel_id[:20]}...")

        # 5. keysend payment
        print("[step 5] sending keysend payment ...")
        keysend_result = cli.send_payment(
            target_pubkey=peer_pubkey,
            amount=1 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        assert "payment_hash" in keysend_result
        print(f"  payment_hash={keysend_result['payment_hash'][:20]}...")

        payment = self._wait_payment_state(
            cli, keysend_result["payment_hash"], "Success", timeout=300
        )
        assert payment["status"] == "Success"
        print("[step 5] keysend Success!")

        # 6. create invoice (visible in TUI Invoices tab as Open)
        print("[step 6] creating invoice ...")
        import random

        preimage = "0x" + "".join(hex(random.randint(0, 15))[2:] for _ in range(64))
        invoice = cli.new_invoice(
            amount=1 * 100000000,
            currency=REMOTE_CURRENCY,
            description="auth lifecycle invoice",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice
        print(f"  invoice created: {invoice['invoice_address'][:30]}...")

        parsed = cli.parse_invoice(invoice["invoice_address"])
        payment_hash = parsed["invoice"]["data"]["payment_hash"]
        print(f"  payment_hash={payment_hash[:20]}...")

        inv_status = cli.get_invoice(payment_hash)
        assert inv_status["status"] == "Open"
        print(f"  invoice status: {inv_status['status']}")

        # 6b. pay the peer's invoice from our node (invoice payment via channel)
        #     settle_invoice requires Received status (someone must pay first),
        #     so we demo invoice payment by sending to peer instead.
        preimage2 = "0x" + "".join(hex(random.randint(0, 15))[2:] for _ in range(64))
        peer_invoice = cli.new_invoice(
            amount=1 * 100000000,
            currency=REMOTE_CURRENCY,
            description="lifecycle peer invoice",
            payment_preimage=preimage2,
            hash_algorithm="sha256",
        )
        print(f"  second invoice: {peer_invoice['invoice_address'][:30]}...")

        # cancel the second invoice to show Cancelled status in TUI
        parsed2 = cli.parse_invoice(peer_invoice["invoice_address"])
        payment_hash2 = parsed2["invoice"]["data"]["payment_hash"]
        cli.cancel_invoice(payment_hash2)
        inv_cancelled = cli.get_invoice(payment_hash2)
        assert inv_cancelled["status"] == "Cancelled"
        print(f"  second invoice cancelled: {inv_cancelled['status']}")

        # 7. list_payments — keysend should appear
        payments = cli.list_payments()
        listed_hashes = {p["payment_hash"] for p in payments["payments"]}
        assert keysend_result["payment_hash"] in listed_hashes
        print(f"[step 7] list_payments OK  count={len(payments['payments'])}")

        # 8. shutdown_channel
        print(f"[step 8] shutdown_channel {channel_id[:20]}...")
        cli.shutdown_channel(channel_id=channel_id, fee_rate=1020)
        time.sleep(30)

        channels_after = cli.list_channels(include_closed=True)
        closed = [
            ch for ch in channels_after["channels"] if ch["channel_id"] == channel_id
        ]
        assert len(closed) == 1
        final_state = closed[0]["state"]["state_name"]
        assert final_state in ["ShuttingDown", "Closed"]
        print(f"[step 8] channel final state={final_state}  DONE!")

    def test_remote_open_channel_and_keysend(self):
        """Open channel on remote node and send keysend payment."""
        cli = self._remote_cli()

        peers = cli.list_peers()
        peer_list = peers["peers"] if isinstance(peers, dict) else peers
        assert len(peer_list) >= 1, "No peers available"
        peer_pubkey = peer_list[0]["pubkey"]
        print(f"\ntarget peer={peer_pubkey[:20]}...")

        min_ckb_funding = 500 * 100000000
        graph = cli.graph_nodes(limit=100)
        for node in graph.get("nodes", []):
            if node.get("node_id") == peer_pubkey:
                raw = node.get("auto_accept_min_ckb_funding_amount", "0x0")
                if raw and raw != "0x0":
                    min_ckb_funding = int(raw, 16)
                break
        funding_amount = max(min_ckb_funding + 100 * 100000000, 500 * 100000000)

        cli.open_channel(
            pubkey=peer_pubkey,
            funding_amount=funding_amount,
            public=True,
        )
        channel_id = self._wait_for_channel_state(cli, "ChannelReady", timeout=300)
        print(f"channel ready: {channel_id[:20]}...")

        result = cli.send_payment(
            target_pubkey=peer_pubkey,
            amount=1 * 100000000,
            keysend=True,
            allow_self_payment=True,
        )
        assert "payment_hash" in result

        payment = self._wait_payment_state(
            cli, result["payment_hash"], "Success", timeout=300
        )
        assert payment["status"] == "Success"
        print("keysend payment Success!")

    def test_remote_invoice_create_and_parse(self):
        """Create an invoice on the remote node, parse and verify it."""
        cli = self._remote_cli()

        import random

        preimage = "0x" + "".join(hex(random.randint(0, 15))[2:] for _ in range(64))
        invoice = cli.new_invoice(
            amount=1 * 100000000,
            currency=REMOTE_CURRENCY,
            description="remote create test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice
        print(f"\ninvoice: {invoice['invoice_address'][:30]}...")

        parsed = cli.parse_invoice(invoice["invoice_address"])
        payment_hash = parsed["invoice"]["data"]["payment_hash"]
        assert payment_hash is not None

        inv_detail = cli.get_invoice(payment_hash)
        assert inv_detail["status"] == "Open"
        print(f"status: {inv_detail['status']}")

    def test_remote_invoice_cancel(self):
        """Create an invoice on the remote node and cancel it."""
        cli = self._remote_cli()

        import random

        preimage = "0x" + "".join(hex(random.randint(0, 15))[2:] for _ in range(64))
        invoice = cli.new_invoice(
            amount=1 * 100000000,
            currency=REMOTE_CURRENCY,
            description="remote cancel test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice

        parsed = cli.parse_invoice(invoice["invoice_address"])
        payment_hash = parsed["invoice"]["data"]["payment_hash"]

        cli.cancel_invoice(payment_hash)
        inv_cancelled = cli.get_invoice(payment_hash)
        assert inv_cancelled["status"] == "Cancelled"
