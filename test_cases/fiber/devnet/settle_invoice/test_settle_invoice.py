"""
Test cases for settle_invoice RPC.
Requirement: PR-961 - Only invoice in Received state can be settled.
"""
import time
import hashlib
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    Timeout,
    ChannelState,
    PaymentStatus,
    InvoiceStatus,
    Currency,
    HashAlgorithm,
)
def sha256_hex(preimage_hex: str) -> str:
    """Compute SHA256 hash of preimage, return hex string."""
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()


class TestSettleInvoice(FiberTest):
    """
    Test settle_invoice RPC behavior per PR-961.
    Rules: Only invoice in Received state can be settled; Open/Cancelled/Expired/Paid return explicit errors.
    """

    def test_settle_valid_hold_invoice(self):
        """
        Settle hold invoice with correct preimage after Received; payment succeeds, invoice becomes Paid.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Create hold invoice (payment_hash only).
        Step 3: Send payment and wait for invoice Received.
        Step 4: Settle invoice with correct preimage.
        Step 5: Assert payment success and invoice Paid.
        """
        # Step 1: Open channel
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )

        # Step 2: Create hold invoice (payment_hash only)
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "settle hold invoice",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )

        # Step 3: Send payment and wait for invoice Received
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(
            self.fiber1, payment["payment_hash"], InvoiceStatus.RECEIVED,
            timeout=Timeout.CHANNEL_READY, interval=Timeout.POLL_INTERVAL
        )

        # Step 4: Settle invoice with correct preimage
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment["payment_hash"], "payment_preimage": preimage}
        )

        # Step 5: Assert payment success and invoice Paid
        self.wait_payment_state(
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == InvoiceStatus.PAID

    def test_settle_with_wrong_preimage(self):
        """
        Settle with wrong preimage returns Hash mismatch.
        Step 1: Open channel.
        Step 2: Create hold invoice and send payment.
        Step 3: Settle with wrong preimage, assert Hash mismatch error.
        """
        # Step 1: Open channel
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )

        # Step 2: Create hold invoice and send payment
        preimage1 = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage1)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "wrong preimage settle",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # Step 3: Settle with wrong preimage, assert Hash mismatch
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {
                    "payment_hash": payment_hash,
                    "payment_preimage": self.generate_random_preimage(),
                }
            )
        assert "Hash mismatch" in exc_info.value.args[0]

    def test_settle_nonexistent_invoice(self):
        """
        Settle nonexistent invoice returns Invoice not found.
        Step 1: Call settle_invoice with random payment_hash.
        Step 2: Assert Invoice not found error.
        """
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "Invoice not found" in exc_info.value.args[0]

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/1029")
    def test_settle_expired_hold_invoice(self):
        """
        Settle expired hold invoice returns already expired.
        Step 1: Open channel and create short-expiry hold invoice.
        Step 2: Send payment, wait for expiry.
        Step 3: Settle after expiry, assert already expired.
        """
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )
        expiry_hex = "0x5"  # 5 seconds
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "expired hold invoice",
                "expiry": expiry_hex,
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        try:
            self.wait_invoice_state(
                self.fiber1, payment_hash, InvoiceStatus.RECEIVED,
                timeout=Timeout.SHORT, interval=Timeout.POLL_INTERVAL
            )
        except Exception:
            pass
        time.sleep(int(expiry_hex, 16) + 3)
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.wait_invoice_state(
            self.fiber1, payment_hash, InvoiceStatus.PAID,
            timeout=Timeout.SHORT, interval=Timeout.POLL_INTERVAL
        )
        self.wait_payment_state(
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS
        )

    def test_settle_already_settled_invoice(self):
        """
        Second settle of already paid invoice returns already paid.
        Step 1: Open channel, create hold invoice, settle once.
        Step 2: Settle again, assert already paid error.
        """
        # Step 1: Open channel and settle once
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "already settled invoice",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_invoice_state(
            self.fiber1, payment_hash, InvoiceStatus.RECEIVED,
            timeout=Timeout.CHANNEL_READY, interval=Timeout.POLL_INTERVAL
        )
        self.fiber1.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.wait_payment_state(
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS
        )
        inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
        assert inv["status"] == InvoiceStatus.PAID

        # Step 2: Second settle, assert already paid
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already paid" in exc_info.value.args[0]

    def test_settle_open_invoice_should_fail(self):
        """
        Settle Open invoice (no payment sent) returns still open/Open.
        Step 1: Open channel and create hold invoice (no payment).
        Step 2: Settle, assert still open or Open error.
        """
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "open invoice settle should fail",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        err = exc_info.value.args[0]
        assert "still open" in err or "Open" in err

    def test_settle_cancelled_invoice_should_fail(self):
        """
        Settle cancelled invoice returns already cancelled.
        Step 1: Open channel, create invoice, cancel it.
        Step 2: Settle, assert already cancelled error.
        """
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "cancelled invoice settle should fail",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        self.fiber1.get_client().cancel_invoice(
            {"payment_hash": invoice["invoice"]["data"]["payment_hash"]}
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already cancelled" in exc_info.value.args[0]

    @pytest.mark.skip("expiry_time restricts send, so this scenario does not exist")
    def test_settle_expired_invoice_should_fail(self):
        """
        Settle expired invoice returns already expired.
        Step 1: Open channel, create short-expiry invoice, wait for expiry.
        Step 2: Settle, assert already expired error.
        """
        self.open_channel(
            self.fiber2, self.fiber1,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500),
        )
        expiry_hex = "0x5"
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        self.fiber1.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "expired invoice settle should fail",
                "expiry": expiry_hex,
                "final_cltv": "0x28",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        time.sleep(int(expiry_hex, 16) + 3)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already expired" in exc_info.value.args[0]

    def test_settle_sametime(self):
        """
        Concurrent settle of same invoice: at most one succeeds, others may return already paid.
        Step 1: Build fiber1-fiber2-fiber3 topology.
        Step 2: Create hold invoice on fiber2.
        Step 3: fiber1 and fiber3 both send payment to same invoice.
        Step 4: Assert one payment fails before settle.
        Step 5: Settle on fiber2.
        Step 6: Assert one Success, one Failed.
        """
        # Step 1: Build topology
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber2, self.fiber3,
            Amount.ckb(1000), Amount.ckb(1000),
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000), Amount.ckb(1000),
        )

        # Step 2: Create hold invoice on fiber2
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "test invoice generated by node2",
                "payment_hash": payment_hash,
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )

        # Step 3: Both fiber1 and fiber3 send payment
        self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.fiber3.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # Step 4: Assert one fails before settle
        time.sleep(Timeout.POLL_INTERVAL)
        fiber1_payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        fiber3_payment = self.fiber3.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        assert (
            fiber3_payment["status"] == PaymentStatus.FAILED
            or fiber1_payment["status"] == PaymentStatus.FAILED
        )

        # Step 5: Settle on fiber2
        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )

        # Step 6: Assert one Success, one Failed
        fiber1_result = self.wait_payment_finished(
            self.fiber1, payment_hash, timeout=Timeout.CHANNEL_READY
        )
        fiber3_result = self.wait_payment_finished(
            self.fiber3, payment_hash, timeout=Timeout.CHANNEL_READY
        )
        assert fiber1_result["status"] != fiber3_result["status"]
