"""
Test open_channel funding_timeout: channel not accepted in time leads to timeout and no channels.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, Timeout, TLCFeeRate


class TestFundingTimeout(FiberTest):
    """
    Test funding timeout: when accept_channel is delayed beyond fiber_funding_timeout_seconds,
    no channel is created; after accept within timeout, normal open_channel works.
    """
    start_fiber_config = {"fiber_funding_timeout_seconds": 10}

    def test_funding_timeout(self):
        """
        When fiber2 does not accept in time, channels stay 0; after late accept still 0.
        Then open_channel with immediate accept succeeds.
        Step 1: Start fiber3, connect to fiber2.
        Step 2: Loop: open_channel from fiber3, wait past timeout, assert no channels; then accept late, assert still no channels.
        Step 3: Open three channels normally (fiber3->fiber2) using helper.
        """
        # Step 1: Start fiber3 and connect to fiber2
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Loop - open_channel, wait past timeout, assert no channels; late accept, assert no channels
        for _ in range(5):
            temporary_channel1 = self.fiber3.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(100)),
                    "public": True,
                    "tlc_fee_proportional_millionths": hex(TLCFeeRate.DEFAULT),
                }
            )
            time.sleep(5)  # Wait within funding timeout window
            channels = self.fiber3.get_client().list_channels({})
            assert len(channels["channels"]) == 0, "Channel should not exist before accept"
            time.sleep(15)  # Past funding timeout
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": temporary_channel1["temporary_channel_id"],
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                }
            )
            channels = self.fiber2.get_client().list_channels({})
            assert len(channels["channels"]) == 0
            time.sleep(Timeout.POLL_INTERVAL)
            channels = self.fiber2.get_client().list_channels({})
            assert len(channels["channels"]) == 0
            channels = self.fiber3.get_client().list_channels({})
            assert len(channels["channels"]) == 0

        # Step 3: Open three channels normally (immediate accept via helper)
        self.open_channel(
            self.fiber3, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )
        self.open_channel(
            self.fiber3, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )
        self.open_channel(
            self.fiber3, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )

    @pytest.mark.skip("todo check")
    def test_channel_status_is_sign_or_await_ready(self):
        """
        (Skipped) Verify channel status during sign or await ready after restart.
        Step 1: Open channel, wait for AWAITING_TX_SIGNATURES.
        Step 2: Stop fiber2, wait, list_channels, start fiber2, list_channels; todo assert statuses.
        """
        temporary_channel1 = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "tlc_fee_proportional_millionths": hex(TLCFeeRate.DEFAULT),
            }
        )
        time.sleep(2)
        self.fiber2.stop()
        time.sleep(20)
        self.fiber1.get_client().list_channels({})
        self.fiber2.start()
        self.fiber2.get_client().list_channels({})
        # todo: check fiber1 channels status, check fiber2 channels status
