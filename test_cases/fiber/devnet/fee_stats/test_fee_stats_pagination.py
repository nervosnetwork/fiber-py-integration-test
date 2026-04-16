"""Cursor pagination for forwarding_history and payment_history (Copilot B-8, D-5)."""

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    collect_forwarding_pages,
    collect_payment_history_pages,
    skip_if_fee_stats_unavailable,
)


class TestFeeStatsCursorPagination(FiberTest):
    def test_forwarding_history_cursor_walk_matches_single_fetch(self):
        """B-8: multi-page `after` walk returns same events as one large limit."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        bal = 200 * 100000000
        self.open_channel(self.fiber1, self.fiber2, bal, bal, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, bal, bal, hop_fee, hop_fee)

        for i in range(4):
            self.send_payment(self.fiber1, fiber3, (4 + i) * 100000000)

        c = self.fiber2.get_client()
        one_page = c.forwarding_history({"limit": hex(500)})
        walked = collect_forwarding_pages(c, page_limit=2)

        h1 = {e["payment_hash"] for e in one_page["events"]}
        h2 = {e["payment_hash"] for e in walked}
        assert h1 == h2
        assert len(walked) >= 4

    def test_payment_history_cursor_walk_includes_send_receive(self):
        """D-5 / D-7: cursor walk collects Send on A and Receive on C."""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        bal = 200 * 100000000
        self.open_channel(self.fiber1, self.fiber2, bal, bal, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, bal, bal, hop_fee, hop_fee)

        ph = self.send_payment(self.fiber1, fiber3, 7 * 100000000)

        ca = collect_payment_history_pages(self.fiber1.get_client(), page_limit=1)
        cc = collect_payment_history_pages(fiber3.get_client(), page_limit=1)

        types_a = {e["event_type"] for e in ca if e["payment_hash"] == ph}
        types_c = {e["event_type"] for e in cc if e["payment_hash"] == ph}
        assert "Send" in types_a
        assert "Receive" in types_c
