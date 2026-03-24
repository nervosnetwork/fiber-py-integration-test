"""E2E: A→B→C topology — verify fee_report / forwarding_history on B, sent_* on A, received_* on C.

Maps Copilot module F (channel integration): F-1 forwarding on B, F-2 Receive on C,
F-3 Send on A; B-11/B-12 forwarding field checks on CKB path.
"""

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    ckb_asset_report,
    skip_if_fee_stats_unavailable,
    u128,
    u64,
)


class TestFeeStatsE2EThreeHop(FiberTest):
    """Three-node line: fiber1 (A) — fiber2 (B) — fiber3 (C)."""

    def test_three_hop_keysend_fee_and_payment_reports(self):
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        bal = 200 * 100000000
        self.open_channel(self.fiber1, self.fiber2, bal, bal, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, bal, bal, hop_fee, hop_fee)

        pay_amount = 10 * 100000000
        payment_hash = self.send_payment(self.fiber1, fiber3, pay_amount)

        # B: forwarding fee + history
        fr_b = self.fiber2.get_client().fee_report({})
        assert "asset_reports" in fr_b
        ckb_b = ckb_asset_report(fr_b["asset_reports"])
        assert ckb_b is not None
        assert u64(ckb_b["daily_event_count"]) >= 1
        assert u128(ckb_b["daily_fee_sum"]) > 0

        fh_b = self.fiber2.get_client().forwarding_history({"limit": hex(50)})
        assert len(fh_b["events"]) >= 1
        assert u64(fh_b["total_count"]) >= 1
        match = [e for e in fh_b["events"] if e["payment_hash"] == payment_hash]
        assert len(match) >= 1
        ev = match[0]
        # B-11 / B-12 (Copilot): full fields; CKB → udt_type_script null
        for field in (
            "timestamp",
            "incoming_channel_id",
            "outgoing_channel_id",
            "incoming_amount",
            "outgoing_amount",
            "fee",
            "payment_hash",
        ):
            assert field in ev
        assert ev.get("udt_type_script") in (None, {})
        assert u128(ev["fee"]) > 0

        # A: sent
        sr_a = self.fiber1.get_client().sent_payment_report()
        ckb_a = ckb_asset_report(sr_a["asset_reports"])
        assert ckb_a is not None
        assert u64(ckb_a["daily_event_count"]) >= 1
        assert u128(ckb_a["daily_amount_sum"]) >= pay_amount

        ph_a = self.fiber1.get_client().payment_history({"limit": hex(50)})
        sends = [
            e
            for e in ph_a["events"]
            if e.get("event_type") == "Send" and e["payment_hash"] == payment_hash
        ]
        assert len(sends) >= 1

        # C: received
        rr_c = fiber3.get_client().received_payment_report()
        ckb_c = ckb_asset_report(rr_c["asset_reports"])
        assert ckb_c is not None
        assert u64(ckb_c["daily_event_count"]) >= 1

        ph_c = fiber3.get_client().payment_history({"limit": hex(50)})
        recvs = [
            e
            for e in ph_c["events"]
            if e.get("event_type") == "Receive" and e["payment_hash"] == payment_hash
        ]
        assert len(recvs) >= 1
