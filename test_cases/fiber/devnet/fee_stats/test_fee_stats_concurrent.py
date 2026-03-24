"""Concurrent payments through hub B — forwarding_history should record all events."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    skip_if_fee_stats_unavailable,
    u64,
)


class TestFeeStatsConcurrent(FiberTest):
    def test_concurrent_keysend_through_same_hub(self):
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        bal = 200 * 100000000
        self.open_channel(self.fiber1, self.fiber2, bal, bal, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, bal, bal, hop_fee, hop_fee)

        n = 5
        amounts = [3 * 100000000 + i * 100000 for i in range(n)]

        def _pay(i):
            amt = amounts[i]
            return self.send_payment(self.fiber1, fiber3, amt)

        hashes = []
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(_pay, i) for i in range(n)]
            for f in as_completed(futs):
                hashes.append(f.result())

        fh = self.fiber2.get_client().forwarding_history({"limit": hex(200)})
        assert len(fh["events"]) >= n
        assert u64(fh["total_count"]) == len(fh["events"])
        for h in hashes:
            assert any(
                e["payment_hash"] == h for e in fh["events"]
            ), f"missing forwarding event for {h}"
