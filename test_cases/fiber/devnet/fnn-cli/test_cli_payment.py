from framework.basic_share_fiber import SharedFiberTest
from framework.fnn_cli import FnnCli


class TestCliPayment(SharedFiberTest):
    """Test payment and list_payments commands via fnn-cli."""

    def setUp(self):
        """One-time channel setup, guarded by _channel_inited flag."""
        if getattr(TestCliPayment, "_channel_inited", False):
            return
        TestCliPayment._channel_inited = True

        # Open channel between fiber1 and fiber2
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

    def test_send_keysend_payment_via_cli(self):
        """Open channel, send keysend payment via CLI, verify success."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["pubkey"]

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

    def test_send_invoice_payment_via_cli(self):
        """Create invoice via RPC on fiber2, pay it via CLI on fiber1."""
        preimage = self.generate_random_preimage()
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(5 * 100000000),
                "currency": "Fibd",
                "description": "pay via cli",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
            }
        )

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.send_payment(invoice=invoice["invoice_address"])
        assert "payment_hash" in result

        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")

    def test_get_payment_via_cli(self):
        """Send payment via RPC, retrieve status via CLI."""
        payment_hash = self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        payment = cli1.get_payment(payment_hash)
        assert payment["status"] == "Success"
        assert payment["payment_hash"] == payment_hash

    def test_list_payments_basic(self):
        """Send multiple payments, then list them via CLI."""
        hashes = []
        for _ in range(3):
            h = self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)
            hashes.append(h)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        payments = cli1.list_payments()
        assert "payments" in payments
        assert len(payments["payments"]) >= 3

        listed_hashes = [p["payment_hash"] for p in payments["payments"]]
        for h in hashes:
            assert h in listed_hashes

    def test_list_payments_with_status_filter(self):
        """Filter list_payments by Success status."""
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        success_payments = cli1.list_payments(status="Success")
        assert "payments" in success_payments
        for p in success_payments["payments"]:
            assert p["status"] == "Success"

    def test_list_payments_with_limit(self):
        """Verify limit parameter restricts result count."""
        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        limited = cli1.list_payments(limit=2)
        assert "payments" in limited
        assert len(limited["payments"]) <= 2

    def test_list_payments_pagination(self):
        """Test pagination via the after cursor."""
        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        page1 = cli1.list_payments(limit=2)
        assert len(page1["payments"]) == 2

        last_hash = page1["payments"][-1]["payment_hash"]
        page2 = cli1.list_payments(limit=2, after=last_hash)
        assert "payments" in page2
        if len(page2["payments"]) > 0:
            assert (
                page2["payments"][0]["payment_hash"]
                != page1["payments"][0]["payment_hash"]
            )

    def test_list_payments_rpc_vs_cli(self):
        """CLI list_payments should return same data as RPC list_payments."""
        self.send_payment(self.fiber1, self.fiber2, 2 * 100000000)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_result = cli1.list_payments()
        rpc_result = self.fiber1.get_client().list_payments({})

        assert len(cli_result["payments"]) == len(rpc_result["payments"])
        for i in range(len(cli_result["payments"])):
            assert (
                cli_result["payments"][i]["payment_hash"]
                == rpc_result["payments"][i]["payment_hash"]
            )
            assert (
                cli_result["payments"][i]["status"]
                == rpc_result["payments"][i]["status"]
            )

    def test_send_payment_dry_run_via_cli(self):
        """Dry-run payment should not actually transfer funds."""
        # Record balance before dry_run
        channels_before = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_balance_before = int(channels_before["channels"][0]["local_balance"], 16)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        target_pubkey = self.fiber2.get_client().node_info()["pubkey"]

        result = cli1.send_payment(
            target_pubkey=target_pubkey,
            amount=10 * 100000000,
            keysend=True,
            allow_self_payment=True,
            dry_run=True,
        )
        assert result is not None
        assert "payment_hash" in result

        # Verify balance unchanged after dry_run
        channels_after = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        local_balance_after = int(channels_after["channels"][0]["local_balance"], 16)
        assert local_balance_after == local_balance_before
