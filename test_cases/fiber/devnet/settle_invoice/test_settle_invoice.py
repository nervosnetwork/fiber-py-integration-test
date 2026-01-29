"""
Test cases for settle_invoice RPC (hold invoice settle flow and error handling).
Requirement: PR-961 - only invoice in Received state can be settled.
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

        # Step 3: Send payment and wait for invoice Received (hold state)
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
        self.wait_payment_state(
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        # Step 5: Assert payment success and invoice Paid
        self.assert_invoice_paid(self.fiber1, payment_hash)

    def test_settle_with_wrong_preimage(self):
        """
        Settle with wrong preimage should fail with hash mismatch.
        Step 1: Open channel and create hold invoice.
        Step 2: Send payment (do not wait for Received).
        Step 3: Call settle_invoice with a different preimage; assert error.
        """
        # Step 1: Open channel
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )

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

        # Step 2: Send payment (do not wait for Received)
        payment = self.fiber2.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # Step 3: Settle with wrong preimage; expect hash mismatch
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
        Settle with non-existent payment_hash should fail with Invoice not found.
        Step 1: Call settle_invoice with random payment_hash; assert error.
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
        Settle expired hold invoice (skip: issue 1029).
        Step 1: Open channel, create short-expiry hold invoice, send payment.
        Step 2: Wait for expiry then settle; assert payment success.
        """
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )

        expiry_hex = "0x5"  # 5 seconds; 0x0 would be rejected as expired at creation
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
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_settle_already_settled_invoice(self):
        """
        Second settle on same invoice should fail with already paid.
        Step 1: Open channel, create hold invoice, send payment, settle once.
        Step 2: Call settle_invoice again; assert error.
        """
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        self.assert_invoice_paid(self.fiber1, payment_hash)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already paid" in exc_info.value.args[0]

    def test_settle_open_invoice_should_fail(self):
        """
        Settle invoice that is still Open (no payment sent) should fail.
        Step 1: Open channel, create invoice (do not send payment).
        Step 2: Call settle_invoice; assert error mentions open/open state.
        """
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "still open" in err or "Open" in err

    def test_settle_cancelled_invoice_should_fail(self):
        """
        Settle cancelled invoice should fail with already cancelled.
        Step 1: Open channel, create hold invoice, cancel it.
        Step 2: Call settle_invoice; assert error mentions already cancelled.
        """
        # Step 1: Open channel
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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

        # Step 2: Call settle_invoice; expect already cancelled
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already cancelled" in exc_info.value.args[0]

    @pytest.mark.skip("expiry_time limits sender; this scenario does not exist")
    def test_settle_expired_invoice_should_fail(self):
        """
        Settle expired invoice should fail with already expired.
        Step 1: Open channel, create short-expiry invoice, wait for expiry.
        Step 2: Call settle_invoice; assert error mentions already expired.
        """
        # Step 1: Open channel
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )

        expiry_hex = "0x5"
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber1.get_client().new_invoice(
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

        # Step 2: Call settle_invoice; expect already expired
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().settle_invoice(
                {"payment_hash": payment_hash, "payment_preimage": preimage}
            )
        assert "already expired" in exc_info.value.args[0]

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/965")
    def test_settle_sametime(self):
        """
        Two senders pay same hold invoice; one fails, then settle; exactly one succeeds.
        Step 1: Build topology fiber1-fiber2-fiber3, create hold invoice.
        Step 2: fiber1 and fiber3 both send payment to same invoice.
        Step 3: Assert one payment Failed before settle.
        Step 4: Settle invoice; wait both payments finished; assert one Success one Failed.
        """
        # Step 1: Build topology and create hold invoice
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1000),
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1000),
        )
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

        # Step 2: Both send payment to same invoice
        self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.fiber3.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )

        # Step 3: Assert one payment Failed before settle
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
        ), "Exactly one payment should fail before settle"

        # Step 4: Settle then wait both finished; one Success one Failed
        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        fiber1_result = self.wait_payment_finished(
            self.fiber1, payment_hash, timeout=Timeout.CHANNEL_READY
        )
        fiber3_result = self.wait_payment_finished(
            self.fiber3, payment_hash, timeout=Timeout.CHANNEL_READY
        )
        assert fiber1_result["status"] != fiber3_result["status"]
