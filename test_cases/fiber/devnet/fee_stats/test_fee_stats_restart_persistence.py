"""Restart node after recording events — RocksDB store should retain fee/payment history."""

import time

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    skip_if_fee_stats_unavailable,
    u64,
)


class TestFeeStatsRestartPersistence(FiberTest):
    def test_forwarding_history_survives_fiber_restart(self):
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        fiber3 = self.start_new_fiber(self.generate_account(10000))
        fiber3.connect_peer(self.fiber2)

        hop_fee = 1000
        bal = 200 * 100000000
        self.open_channel(self.fiber1, self.fiber2, bal, bal, hop_fee, hop_fee)
        self.open_channel(self.fiber2, fiber3, bal, bal, hop_fee, hop_fee)

        payment_hash = self.send_payment(self.fiber1, fiber3, 5 * 100000000)

        before = self.fiber2.get_client().forwarding_history({"limit": hex(100)})
        count_before = u64(before["total_count"])
        assert count_before >= 1
        assert any(e["payment_hash"] == payment_hash for e in before["events"])

        self.fiber2.stop()
        self.fiber2.start()
        time.sleep(2)

        after = self.fiber2.get_client().forwarding_history({"limit": hex(100)})
        count_after = u64(after["total_count"])
        assert count_after >= count_before
        assert any(e["payment_hash"] == payment_hash for e in after["events"])
