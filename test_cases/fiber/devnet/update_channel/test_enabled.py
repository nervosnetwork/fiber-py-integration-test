"""
update_channel tests: enabled flag - disable channel to exclude from routing; re-enable to restore path.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, TLCFeeRate

# Error message when no path found
NO_PATH_ERROR = "no path found"


class TestEnabled(FiberTest):
    """
    Test update_channel enabled: (1) Disabled channel excluded from path; A->C and B->C fail, others ok.
    (2) Re-enable; A->C and B->C succeed. (3) Multiple channels between B-C; disable low-fee channel.
    """

    def test_true(self):
        """
        A-B-C: disable B-C channel; A->C and B->C fail with 'no path found'; B->A, C->B, C->A succeed; re-enable B-C; A->C and B->C succeed.
        Step 1: Start F3, open F1-F2 and F2-F3 channels; send F1->F3 payment.
        Step 2: F2 update_channel F2-F3 enabled=False; assert graph_channels still 2; assert list_channels enabled False (F2) / True (F3).
        Step 3: Assert F1->F3 and F2->F3 raise 'no path found'; F2->F1, F3->F2, F3->F1 succeed.
        Step 4: F2 update_channel F2-F3 enabled=True; assert list_channels enabled True on both.
        Step 5: F1->F3, F2->F3, F2->F1, F3->F2, F3->F1 succeed.
        """
        # Step 1: Start F3, open F1-F2 and F2-F3 channels; send F1->F3 payment
        self.start_new_fiber(self.generate_account(10_000))
        bal = Amount.ckb(1000)
        self.open_channel(self.fibers[0], self.fibers[1], bal, bal)
        self.open_channel(self.fibers[1], self.fibers[2], bal, bal)
        self.send_payment(self.fibers[0], self.fibers[2], Amount.ckb(1), wait=True)

        # Step 2: F2 update_channel F2-F3 enabled=False; assert graph_channels still 2; assert list_channels enabled
        f1, f2, f3 = self.fibers[0], self.fibers[1], self.fibers[2]
        channel = f2.get_client().list_channels({"peer_id": f3.get_peer_id()})
        assert len(f2.get_client().graph_channels({})["channels"]) == 2
        f2.get_client().update_channel(
            {"channel_id": channel["channels"][0]["channel_id"], "enabled": False}
        )
        time.sleep(3)
        assert len(f2.get_client().graph_channels({})["channels"]) == 2
        channel = f2.get_client().list_channels({"peer_id": f3.get_peer_id()})
        assert channel["channels"][0]["enabled"] is False
        channel = f3.get_client().list_channels({"peer_id": f2.get_peer_id()})
        assert channel["channels"][0]["enabled"] is True

        # Step 3: Assert F1->F3 and F2->F3 raise 'no path found'; F2->F1, F3->F2, F3->F1 succeed
        with pytest.raises(Exception) as exc_info:
            self.send_payment(f1, f3, Amount.ckb(1), wait=True)
        assert NO_PATH_ERROR in exc_info.value.args[0], (
            f"Expected '{NO_PATH_ERROR}' not found in '{exc_info.value.args[0]}'"
        )
        with pytest.raises(Exception) as exc_info:
            self.send_payment(f2, f3, Amount.ckb(1), wait=True)
        assert NO_PATH_ERROR in exc_info.value.args[0], (
            f"Expected '{NO_PATH_ERROR}' not found in '{exc_info.value.args[0]}'"
        )
        self.send_payment(f2, f1, Amount.ckb(1), wait=True)
        self.send_payment(f3, f2, Amount.ckb(1), wait=True)
        self.send_payment(f3, f1, Amount.ckb(1), wait=True)

        # Step 4: F2 update_channel F2-F3 enabled=True; assert list_channels enabled True on both
        channel = f2.get_client().list_channels({"peer_id": f3.get_peer_id()})
        f2.get_client().update_channel(
            {"channel_id": channel["channels"][0]["channel_id"], "enabled": True}
        )
        time.sleep(Timeout.POLL_INTERVAL)
        assert len(f2.get_client().graph_channels({})["channels"]) == 2
        channel = f2.get_client().list_channels({"peer_id": f3.get_peer_id()})
        assert channel["channels"][0]["enabled"] is True
        channel = f3.get_client().list_channels({"peer_id": f2.get_peer_id()})
        assert channel["channels"][0]["enabled"] is True

        # Step 5: F1->F3, F2->F3, F2->F1, F3->F2, F3->F1 succeed
        self.send_payment(f1, f3, Amount.ckb(1), wait=True)
        self.send_payment(f2, f3, Amount.ckb(1), wait=True)
        self.send_payment(f2, f1, Amount.ckb(1), wait=True)
        self.send_payment(f3, f2, Amount.ckb(1), wait=True)
        self.send_payment(f3, f1, Amount.ckb(1), wait=True)

    def test_channels_enabled_fee_more(self):
        """
        A-B-C: open B-C with two more channels (higher fees); disable the first B-C channel.
        Step 1: Start F3; open F1-F2 and F2-F3.
        Step 2: F2 disable first F2-F3 channel; open two more F2-F3 channels with fee 20000 and 30000 millionths.
        Step 3: Send F1->F3 payment (uses remaining enabled channels).
        """
        # Step 1: Start F3; open F1-F2 and F2-F3
        self.start_new_fiber(self.generate_account(10_000))
        bal = Amount.ckb(1000)
        self.open_channel(self.fibers[0], self.fibers[1], bal, bal)
        self.open_channel(self.fibers[1], self.fibers[2], bal, bal)

        # Step 2: F2 disable first F2-F3 channel; open two more F2-F3 channels with fee 20000 and 30000
        channel = self.fibers[1].get_client().list_channels(
            {"peer_id": self.fibers[2].get_peer_id()}
        )
        self.fibers[1].get_client().update_channel(
            {"channel_id": channel["channels"][0]["channel_id"], "enabled": False}
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            bal,
            bal,
            fiber1_fee=TLCFeeRate.MEDIUM * 2,  # 20000
            fiber2_fee=TLCFeeRate.MEDIUM * 2,
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            bal,
            bal,
            fiber1_fee=TLCFeeRate.MEDIUM * 3,  # 30000
            fiber2_fee=TLCFeeRate.MEDIUM * 3,
        )

        # Step 3: Send F1->F3 payment
        self.send_payment(self.fibers[0], self.fibers[2], Amount.ckb(1), wait=True)
