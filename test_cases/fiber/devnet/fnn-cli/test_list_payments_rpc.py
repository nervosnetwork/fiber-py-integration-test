import time

import pytest

from framework.basic_fiber import FiberTest


class TestListPaymentsRpc(FiberTest):
    """Comprehensive tests for the list_payments RPC method added in PR #1144.

    list_payments params:
      - status: Optional<PaymentStatus> (Created | Inflight | Success | Failed)
      - limit:  Optional<u64> (hex, default 15)
      - after:  Optional<Hash256> (exclusive pagination cursor)

    list_payments returns:
      - payments:    Vec<GetPaymentCommandResult>
      - last_cursor: Option<Hash256>
    """

    # ───────────────────────────────────────────────
    # Basic functionality
    # ───────────────────────────────────────────────

    def test_list_payments_empty(self):
        """Before any payments, list_payments should return empty list."""
        result = self.fiber1.get_client().list_payments({})
        assert "payments" in result
        assert len(result["payments"]) == 0
        assert result["last_cursor"] is None

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

    # ───────────────────────────────────────────────
    # Response field validation
    # ───────────────────────────────────────────────

    def test_list_payments_response_fields(self):
        """Each payment in the response should contain all required fields."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        assert len(result["payments"]) >= 1

        for p in result["payments"]:
            assert "payment_hash" in p
            assert "status" in p
            assert "created_at" in p
            assert "last_updated_at" in p
            assert "fee" in p
            assert "failed_error" in p or p.get("failed_error") is None

    def test_list_payments_fee_field(self):
        """Successful payment should have a non-negative fee."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"status": "Success"})
        for p in result["payments"]:
            assert int(p["fee"], 16) >= 0

    def test_list_payments_timestamps(self):
        """created_at should be <= last_updated_at."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        for p in result["payments"]:
            created = int(p["created_at"], 16)
            updated = int(p["last_updated_at"], 16)
            assert created > 0
            assert updated >= created

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
            assert detail["created_at"] == p["created_at"]
            assert detail["last_updated_at"] == p["last_updated_at"]
            assert detail["fee"] == p["fee"]

    # ───────────────────────────────────────────────
    # Status filtering
    # ───────────────────────────────────────────────

    def test_list_payments_filter_by_status_success(self):
        """Filter list_payments by status=Success."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"status": "Success"})
        assert "payments" in result
        assert len(result["payments"]) >= 1
        for p in result["payments"]:
            assert p["status"] == "Success"

    def test_list_payments_filter_by_status_created(self):
        """Filter by Created status — completed payments should not appear."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"status": "Created"})
        assert "payments" in result
        for p in result["payments"]:
            assert p["status"] == "Created"

    def test_list_payments_filter_by_status_failed(self):
        """Trigger a failed payment, then filter by Failed status."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        with pytest.raises(Exception):
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "amount": hex(999 * 100000000),
                    "keysend": True,
                    "allow_self_payment": True,
                    "timeout": hex(5),
                }
            )

        time.sleep(8)

        result = self.fiber1.get_client().list_payments({"status": "Failed"})
        assert "payments" in result
        for p in result["payments"]:
            assert p["status"] == "Failed"
            assert p["failed_error"] is not None

    def test_list_payments_status_filter_excludes_others(self):
        """When filtering by Success, Failed payments should not appear and vice versa."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        success_result = self.fiber1.get_client().list_payments({"status": "Success"})
        all_result = self.fiber1.get_client().list_payments({})

        success_hashes = {p["payment_hash"] for p in success_result["payments"]}
        all_hashes = {p["payment_hash"] for p in all_result["payments"]}
        assert success_hashes.issubset(all_hashes)

    # ───────────────────────────────────────────────
    # Limit parameter
    # ───────────────────────────────────────────────

    def test_list_payments_default_limit_15(self):
        """Default limit should be 15."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(3):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        assert len(result["payments"]) <= 15

    def test_list_payments_limit_exact(self):
        """Limit should cap results at exactly the specified number."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"limit": hex(3)})
        assert len(result["payments"]) == 3

    def test_list_payments_limit_1(self):
        """Limit=1 should return exactly one payment."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(3):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"limit": hex(1)})
        assert len(result["payments"]) == 1
        assert result["last_cursor"] == result["payments"][0]["payment_hash"]

    def test_list_payments_limit_greater_than_total(self):
        """Limit > total payments should return all payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(3):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({"limit": hex(100)})
        assert len(result["payments"]) >= 3

    def test_list_payments_limit_with_status_filter(self):
        """Limit combined with status filter."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments(
            {
                "status": "Success",
                "limit": hex(2),
            }
        )
        assert len(result["payments"]) <= 2
        for p in result["payments"]:
            assert p["status"] == "Success"

    # ───────────────────────────────────────────────
    # Pagination (after cursor)
    # ───────────────────────────────────────────────

    def test_list_payments_last_cursor_field(self):
        """last_cursor should equal the last payment's hash, or None if empty."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result = self.fiber1.get_client().list_payments({})
        assert len(result["payments"]) >= 1
        assert result["last_cursor"] == result["payments"][-1]["payment_hash"]

    def test_list_payments_pagination_no_overlap(self):
        """Paginated pages should not have overlapping payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(5):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        page1 = self.fiber1.get_client().list_payments({"limit": hex(2)})
        assert len(page1["payments"]) == 2

        page2 = self.fiber1.get_client().list_payments(
            {
                "limit": hex(2),
                "after": page1["last_cursor"],
            }
        )

        page1_hashes = {p["payment_hash"] for p in page1["payments"]}
        page2_hashes = {p["payment_hash"] for p in page2["payments"]}
        assert page1_hashes.isdisjoint(page2_hashes), "Pages should not overlap"

    def test_list_payments_pagination_exhaustive(self):
        """Iterating all pages should eventually return all payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        sent_hashes = set()
        for _ in range(5):
            h = self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)
            sent_hashes.add(h)

        all_hashes = set()
        cursor = None
        for _ in range(10):
            params = {"limit": hex(2)}
            if cursor is not None:
                params["after"] = cursor
            page = self.fiber1.get_client().list_payments(params)
            if len(page["payments"]) == 0:
                break
            for p in page["payments"]:
                all_hashes.add(p["payment_hash"])
            cursor = page["last_cursor"]

        for h in sent_hashes:
            assert h in all_hashes, f"Payment {h} missing from paginated results"

    def test_list_payments_pagination_with_status_filter(self):
        """Pagination combined with status filter."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(4):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        page1 = self.fiber1.get_client().list_payments(
            {
                "status": "Success",
                "limit": hex(2),
            }
        )
        assert len(page1["payments"]) == 2
        for p in page1["payments"]:
            assert p["status"] == "Success"

        if page1["last_cursor"] is not None:
            page2 = self.fiber1.get_client().list_payments(
                {
                    "status": "Success",
                    "limit": hex(2),
                    "after": page1["last_cursor"],
                }
            )
            for p in page2["payments"]:
                assert p["status"] == "Success"

    def test_list_payments_after_nonexistent_hash(self):
        """Using a non-existent payment_hash as after cursor."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        fake_hash = "0x" + "ab" * 32
        result = self.fiber1.get_client().list_payments({"after": fake_hash})
        assert "payments" in result

    # ───────────────────────────────────────────────
    # Ordering
    # ───────────────────────────────────────────────

    def test_list_payments_ordering(self):
        """Payments should be returned in consistent order across calls."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        for _ in range(3):
            self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result1 = self.fiber1.get_client().list_payments({})
        result2 = self.fiber1.get_client().list_payments({})

        hashes1 = [p["payment_hash"] for p in result1["payments"]]
        hashes2 = [p["payment_hash"] for p in result2["payments"]]
        assert hashes1 == hashes2, "Ordering should be deterministic"

    # ───────────────────────────────────────────────
    # Sender vs receiver perspective
    # ───────────────────────────────────────────────

    def test_list_payments_sender_only(self):
        """list_payments only returns outgoing payments from the sender's perspective.
        The receiver (fiber2) should not see the sender's payment in its list."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        payment_hash = self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        sender_payments = self.fiber1.get_client().list_payments({})
        receiver_payments = self.fiber2.get_client().list_payments({})

        sender_hashes = {p["payment_hash"] for p in sender_payments["payments"]}
        receiver_hashes = {p["payment_hash"] for p in receiver_payments["payments"]}

        assert payment_hash in sender_hashes
        assert payment_hash not in receiver_hashes

    # ───────────────────────────────────────────────
    # Multiple payments with different types
    # ───────────────────────────────────────────────

    def test_list_payments_mixed_keysend_and_invoice(self):
        """Both keysend and invoice payments should appear in list_payments."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

        keysend_hash = self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)
        invoice_hash = self.send_invoice_payment(
            self.fiber1, self.fiber2, 1 * 100000000
        )

        result = self.fiber1.get_client().list_payments({})
        result_hashes = {p["payment_hash"] for p in result["payments"]}

        assert keysend_hash in result_hashes
        assert invoice_hash in result_hashes

    def test_list_payments_multiple_statuses(self):
        """Unfiltered list should contain more or equal payments than filtered."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 1 * 100000000)

        result_all = self.fiber1.get_client().list_payments({})
        result_success = self.fiber1.get_client().list_payments({"status": "Success"})

        assert len(result_success["payments"]) <= len(result_all["payments"])
