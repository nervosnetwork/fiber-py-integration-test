"""MPP: same payment_hash may produce multiple forwarding rows (distinct channel ids).

Topology aligned with send_payment/mpp/test_mutil_path.test_one_to_mutil:
- One wide A–B channel + second A–B for parallel capacity
- Two parallel B–C channels so B can forward to C in two parts
- Invoice amount large enough that routing should use multiple parts (not single-path only)
"""

import time

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    skip_if_fee_stats_unavailable,
)


class TestFeeStatsMpp(FiberTest):
    def test_mpp_multiple_forwarding_rows_same_payment_hash(self):
        """
        B records multiple ForwardingEvents for one payment_hash when MPP splits
        across parallel B–C (and/or A–B) channels.
        """
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        # Parallel A–B (same as original fee_stats MPP test)
        self.open_channel(
            self.fiber1, self.fiber2, 2000 * 100000000, 0, hop_fee, hop_fee
        )
        self.open_channel(
            self.fiber1, self.fiber2, 2000 * 100000000, 0, hop_fee, hop_fee
        )
        # Two parallel B–C (see test_one_to_mutil): enables split on outgoing at B
        self.open_channel(self.fiber2, fiber3, 2000 * 100000000, 0, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, 2000 * 100000000, 0, hop_fee, hop_fee)

        # 4 public channels in the graph for this topology
        self.wait_graph_channels_sync(self.fiber1, 4)
        self.wait_graph_channels_sync(self.fiber2, 4)
        self.wait_graph_channels_sync(fiber3, 4)
        time.sleep(2)

        # Amount comparable to test_one_to_mutil (3000); must exceed typical single-hop
        # slice so the router prefers multi-part on parallel B–C.
        invoice_amount = 3000 * 100000000
        payment_hash = self.send_invoice_payment(
            self.fiber1,
            fiber3,
            invoice_amount,
            other_options={"allow_mpp": True},
        )

        time.sleep(1)
        fh = self.fiber2.get_client().forwarding_history({"limit": hex(200)})
        same_ph = [e for e in fh["events"] if e["payment_hash"] == payment_hash]
        assert len(same_ph) >= 1, "expected at least one forwarding event on B"

        inc_ids = [e["incoming_channel_id"] for e in same_ph]
        out_ids = [e["outgoing_channel_id"] for e in same_ph]
        assert len(same_ph) >= 2, (
            "expected MPP to produce multiple forwarding rows on B for this payment_hash; "
            f"got {len(same_ph)}. Check graph sync and invoice amount vs channel capacity."
        )
        assert len(set(inc_ids)) >= 2 or len(set(out_ids)) >= 2, (
            "expected distinct channel ids across MPP parts "
            f"(incoming={inc_ids!r}, outgoing={out_ids!r})"
        )
