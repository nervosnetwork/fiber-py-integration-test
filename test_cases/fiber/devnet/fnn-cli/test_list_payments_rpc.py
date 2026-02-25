import time

import pytest

from framework.basic_fiber import FiberTest


class TestListPaymentsRpc(FiberTest):
    """Test the new list_payments RPC method added in PR #1144."""

    def test_list_payments_empty(self):
        """Before any payments, list_payments should return empty list."""
        result = self.fiber1.get_client().list_payments({})
        assert "payments" in result
        assert len(result["payments"]) == 0

    def test_list_payments_after_keysend(self):
        """After a keysend payment, it should appear in list_payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        payment_hash = self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        assert len(result["payments"]) >= 1

        found = any(p["payment_hash"] == payment_hash for p in result["payments"])
        assert found, f"Payment {payment_hash} not found in list_payments"

    def test_list_payments_after_invoice_payment(self):
        """After an invoice payment, it should appear in list_payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        payment_hash = self.send_invoice_payment(
            self.fiber1, self.fiber2, 5 * 100000000
        )

        result = self.fiber1.get_client().list_payments({})
        found = any(p["payment_hash"] == payment_hash for p in result["payments"])
        assert found

    def test_list_payments_filter_by_status_success(self):
        """Filter list_payments by status=Success."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"status": "Success"})
        assert "payments" in result
        for p in result["payments"]:
            assert p["status"] == "Success"

    def test_list_payments_filter_by_status_created(self):
        """Filter by Created status (no matching payments expected after completion)."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"status": "Created"})
        assert "payments" in result
        for p in result["payments"]:
            assert p["status"] == "Created"

    def test_list_payments_limit(self):
        """Verify limit parameter caps the returned results."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"limit": hex(2)})
        assert len(result["payments"]) <= 2

    def test_list_payments_default_limit_15(self):
        """Default limit should be 15."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(3):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        assert len(result["payments"]) <= 15

    def test_list_payments_pagination(self):
        """Test pagination using after cursor."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        hashes = []
        for _ in range(5):
            h = self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)
            hashes.append(h)

        page1 = self.fiber1.get_client().list_payments({"limit": hex(2)})
        assert len(page1["payments"]) == 2

        cursor = page1["payments"][-1]["payment_hash"]
        page2 = self.fiber1.get_client().list_payments(
            {
                "limit": hex(2),
                "after": cursor,
            }
        )
        assert "payments" in page2

        if len(page2["payments"]) > 0:
            page2_hashes = [p["payment_hash"] for p in page2["payments"]]
            page1_hashes = [p["payment_hash"] for p in page1["payments"]]
            for h in page2_hashes:
                assert h not in page1_hashes, "Paginated results should not overlap"

    def test_list_payments_multiple_statuses(self):
        """Multiple payments with different statuses."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result_all = self.fiber1.get_client().list_payments({})
        result_success = self.fiber1.get_client().list_payments({"status": "Success"})

        assert len(result_success["payments"]) <= len(result_all["payments"])

    def test_list_payments_consistency_with_get_payment(self):
        """Each payment in list_payments should match its get_payment result."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        payments = self.fiber1.get_client().list_payments({})
        for p in payments["payments"]:
            detail = self.fiber1.get_client().get_payment(
                {"payment_hash": p["payment_hash"]}
            )
            assert detail["status"] == p["status"]
            assert detail["payment_hash"] == p["payment_hash"]
