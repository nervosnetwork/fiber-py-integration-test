import time

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.fnn_cli import FnnCli


class TestCliInvoice(SharedFiberTest):
    """Test invoice commands via fnn-cli."""

    def test_new_invoice_and_parse(self):
        """Create invoice via CLI, then parse it back."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        preimage = self.generate_random_preimage()
        amount = 10 * 100000000

        invoice_result = cli2.new_invoice(
            amount=amount,
            currency="Fibd",
            description="cli test invoice",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )
        assert "invoice_address" in invoice_result
        invoice_addr = invoice_result["invoice_address"]

        parsed = cli2.parse_invoice(invoice_addr)
        assert "invoice" in parsed
        assert parsed["invoice"]["currency"] == "Fibd"
        assert parsed["invoice"]["amount"] == hex(amount)

    def test_new_invoice_cli_vs_rpc(self):
        """Invoice created via CLI should be retrievable via RPC."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        preimage = self.generate_random_preimage()

        invoice_result = cli2.new_invoice(
            amount=5 * 100000000,
            currency="Fibd",
            description="cli-rpc cross test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
        )

        parsed = self.fiber2.get_client().parse_invoice(
            {"invoice": invoice_result["invoice_address"]}
        )
        assert parsed is not None
        assert "invoice" in parsed

        payment_hash = parsed["invoice"]["data"]["payment_hash"]
        got_invoice = self.fiber2.get_client().get_invoice(
            {"payment_hash": payment_hash}
        )
        assert got_invoice["status"] == "Open"

    def test_get_invoice_via_cli(self):
        """Create invoice via RPC, retrieve it via CLI."""
        preimage = self.generate_random_preimage()
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(8 * 100000000),
                "currency": "Fibd",
                "description": "rpc created, cli retrieved",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
            }
        )
        parsed = self.fiber2.get_client().parse_invoice(
            {"invoice": invoice["invoice_address"]}
        )
        payment_hash = parsed["invoice"]["data"]["payment_hash"]

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        cli_invoice = cli2.get_invoice(payment_hash)
        assert cli_invoice["status"] == "Open"

    def test_cancel_invoice_via_cli(self):
        """Create invoice via RPC, cancel it via CLI."""
        preimage = self.generate_random_preimage()
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(3 * 100000000),
                "currency": "Fibd",
                "description": "to be cancelled",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
            }
        )
        parsed = self.fiber2.get_client().parse_invoice(
            {"invoice": invoice["invoice_address"]}
        )
        payment_hash = parsed["invoice"]["data"]["payment_hash"]

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        cli2.cancel_invoice(payment_hash)

        cli_invoice = cli2.get_invoice(payment_hash)
        assert cli_invoice["status"] == "Cancelled"

    def test_new_invoice_with_expiry(self):
        """Create invoice with custom expiry via CLI."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        preimage = self.generate_random_preimage()

        invoice_result = cli2.new_invoice(
            amount=1 * 100000000,
            currency="Fibd",
            description="expiry test",
            payment_preimage=preimage,
            hash_algorithm="sha256",
            expiry=7200,
        )
        assert "invoice_address" in invoice_result

        parsed = cli2.parse_invoice(invoice_result["invoice_address"])
        attrs = parsed["invoice"]["data"]["attrs"]
        expiry_found = False
        for attr in attrs:
            if isinstance(attr, dict):
                for key in attr:
                    if "expiry" in key.lower() or "Expiry" in key:
                        expiry_found = True
                        break
            if expiry_found:
                break
        assert (
            expiry_found
        ), f"Expiry attribute should be present in parsed invoice, got attrs: {attrs}"
