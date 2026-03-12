import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliSettleInvoice(FiberTest):
    """Test settle_invoice command via fnn-cli.

    settle_invoice requires a hold invoice (created with payment_hash only,
    no preimage) that has received a payment, then is settled using the preimage.
    """

    def test_settle_invoice_via_cli(self):
        """Create hold invoice via RPC, pay it, then settle via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        preimage = self.generate_random_preimage()
        import hashlib

        payment_hash = "0x" + hashlib.sha256(bytes.fromhex(preimage[2:])).hexdigest()

        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(5 * 100000000),
                "currency": "Fibd",
                "description": "hold invoice for CLI settle",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(5)

        got = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
        assert got["status"] == "Received"

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        cli2.settle_invoice(payment_hash, preimage)

        got_after = cli2.get_invoice(payment_hash)
        assert got_after["status"] == "Paid"

        self.wait_payment_state(self.fiber1, payment_hash, "Success")

    def test_settle_invoice_cli_vs_rpc_consistency(self):
        """Verify that settle_invoice via CLI produces the same invoice state as RPC."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        preimage = self.generate_random_preimage()
        import hashlib

        payment_hash = "0x" + hashlib.sha256(bytes.fromhex(preimage[2:])).hexdigest()

        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(3 * 100000000),
                "currency": "Fibd",
                "description": "settle consistency check",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(5)

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        cli2.settle_invoice(payment_hash, preimage)

        cli_result = cli2.get_invoice(payment_hash)
        rpc_result = self.fiber2.get_client().get_invoice(
            {"payment_hash": payment_hash}
        )
        assert cli_result["status"] == rpc_result["status"] == "Paid"

    def test_settle_invoice_wrong_preimage(self):
        """Settling with wrong preimage should fail."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        preimage = self.generate_random_preimage()
        import hashlib

        payment_hash = "0x" + hashlib.sha256(bytes.fromhex(preimage[2:])).hexdigest()

        self.fiber2.get_client().new_invoice(
            {
                "amount": hex(2 * 100000000),
                "currency": "Fibd",
                "description": "wrong preimage test",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
            }
        )

        wrong_preimage = self.generate_random_preimage()

        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        with pytest.raises(Exception):
            cli2.settle_invoice(payment_hash, wrong_preimage)

    def test_settle_invoice_nonexistent_hash(self):
        """Settling a non-existent invoice should fail."""
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")
        fake_hash = "0x" + "ab" * 32
        fake_preimage = "0x" + "cd" * 32

        with pytest.raises(Exception):
            cli2.settle_invoice(fake_hash, fake_preimage)
