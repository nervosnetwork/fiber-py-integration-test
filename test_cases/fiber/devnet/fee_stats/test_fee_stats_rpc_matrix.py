"""
RPC matrix aligned with Copilot fee-stats case list (PR #1201).

Covered here (live JSON-RPC):
  A-1, A-6, A-7 (partial), H-1 — fee_report
  B-4, B-10, H-2 — forwarding_history defaults / invalid limit / UDT filter no match
  C-1 — sent/received empty
  D-2, D-8 (partial) — payment_history limit / empty filter

Modules A-2–A-5, A-8–A-10, B-1–B-3, B-5–B-7, B-9, B-11–B-12, C-2–C-6, D-1, D-3–D-4, D-6–D-7,
E-*, F-*, G-*, H-3–H-4: primarily `fiber-lib` unit tests (`fiber/tests/fee.rs`, store tests)
or covered by E2E / concurrent / MPP / restart tests in this directory.
"""

import pytest

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    skip_if_fee_stats_unavailable,
)


class TestFeeStatsRpcMatrix(FiberTest):
    def test_a1_h1_fee_report_empty_no_forwarding(self):
        """A-1 / H-1: no forwarding yet → empty asset_reports; `{}` defaults."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        r = self.fiber1.get_client().fee_report({})
        assert r["asset_reports"] == []

    def test_a6_fee_report_days_over_90_invalid(self):
        """A-6: days > 90 → INVALID_PARAMS."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        with pytest.raises(Exception) as exc:
            self.fiber1.get_client().fee_report({"days": 91})
        assert "90" in str(exc.value) or "exceeds" in str(exc.value).lower()

    def test_a7_fee_report_time_range_with_no_events(self):
        """A-7 (spot): window [0, 1000] ms epoch → no CKB rows."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        r = self.fiber1.get_client().fee_report(
            {"start_time": hex(0), "end_time": hex(1000)}
        )
        assert r["asset_reports"] == []

    def test_c1_sent_received_empty(self):
        """C-1: empty store → empty asset_reports."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        s = self.fiber1.get_client().sent_payment_report()
        assert s["asset_reports"] == []
        rc = self.fiber1.get_client().received_payment_report()
        assert rc["asset_reports"] == []

    def test_b4_forwarding_history_limit_exceeds_max(self):
        """B-4: limit > 10000 → error."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        with pytest.raises(Exception) as exc:
            self.fiber1.get_client().forwarding_history({"limit": hex(10001)})
        msg = str(exc.value).lower()
        assert "10000" in str(exc.value) or "limit" in msg

    def test_d2_payment_history_limit_exceeds_max(self):
        """D-2: limit > 10000 → error."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        with pytest.raises(Exception) as exc:
            self.fiber1.get_client().payment_history({"limit": hex(10001)})
        msg = str(exc.value).lower()
        assert "10000" in str(exc.value) or "limit" in msg

    def test_b10_forwarding_history_udt_filter_no_match(self):
        """B-10: filter UDT script with no such events → empty page."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        fake_udt = {
            "code_hash": "0x" + "00" * 32,
            "hash_type": "type",
            "args": "0x01",
        }
        r = self.fiber1.get_client().forwarding_history(
            {"udt_type_script": fake_udt, "limit": hex(20)}
        )
        assert r["events"] == []
        assert int(r["total_count"], 16) == 0
        assert r.get("last_cursor") is None

    def test_h2_forwarding_history_default_params(self):
        """H-2: `{}` succeeds; response includes cursor fields."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        r = self.fiber1.get_client().forwarding_history({})
        assert "events" in r and "total_count" in r and "last_cursor" in r

    def test_h4_payment_history_empty_params(self):
        """H-4: payment_history `{}` succeeds (default limit=100 server-side)."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        r = self.fiber1.get_client().payment_history({})
        assert "events" in r and "total_count" in r and "last_cursor" in r

    def test_d8_payment_history_udt_filter_no_match(self):
        """D-8: no matching UDT events → empty list, last_cursor None."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())
        fake_udt = {
            "code_hash": "0x" + "11" * 32,
            "hash_type": "type",
            "args": "0x02",
        }
        r = self.fiber1.get_client().payment_history(
            {"udt_type_script": fake_udt, "limit": hex(20)}
        )
        assert r["events"] == []
        assert int(r["total_count"], 16) == 0
        assert r.get("last_cursor") is None
