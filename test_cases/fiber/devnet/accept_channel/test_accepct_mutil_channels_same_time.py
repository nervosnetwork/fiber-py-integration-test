"""
Accept_channel test cases: same-channel duplicate accept and multi-channel concurrent accept.
Verifies: duplicate accept on the same temporary channel should fail; multi-channel accept behavior (includes skipped case).
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate
from framework.waiter import Waiter, WaitConfig


class TestAcceptMutilChannelsSameTime(FiberTest):
    """
    Test accept_channel behavior for "same channel duplicate accept" and "multi-channel concurrent accept".
    Case 1: First accept on same temp channel succeeds; second accept on same temp_id should raise with expected error, channel ends CHANNEL_READY.
    Case 2 (skip): Multi-channel concurrent accept, see issue #246.
    """

    def test_accept_chanel_same_channel_same_time(self):
        """
        Same temporary channel: first accept succeeds; second accept on same temp_id should raise,
        error message contains "No channel with temp id", and channel ends in CHANNEL_READY.
        Step 1: fiber1 opens channel, fiber2 is peer.
        Step 2: fiber2 accepts the channel for the first time.
        Step 3: Call accept again on same temporary_channel_id, expect exception.
        Step 4: Assert error message contains expected keyword.
        Step 5: Wait for channel ready.
        """
        # Step 1: fiber1 opens channel, fiber2 is peer
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
                "commitment_fee_rate": hex(FeeRate.DEFAULT),
                "funding_fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: fiber2 accepts the channel for the first time
        accept_amount = Amount.ckb(200000)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(accept_amount),
            }
        )

        # Step 3: Call accept again on same temporary_channel_id, expect exception
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": temporary_channel["temporary_channel_id"],
                    "funding_amount": hex(accept_amount),
                }
            )

        # Step 4: Assert error message contains expected keyword
        expected_error_message = "No channel with temp id"
        err_msg = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err_msg, (
            f"Expected substring '{expected_error_message}' not found in actual: {err_msg}"
        )

        # Step 5: Wait for channel ready
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

    debug = True

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/246")
    def test_accept_channel_diff_channel_same_time(self):
        """
        Multi-channel concurrent accept: fiber1 and fiber3 open N channels to fiber2,
        fiber2 accepts all channels simultaneously, verify all channels become CHANNEL_READY.
        Step 1: Generate account and start fiber3.
        Step 2: fiber3 connects to fiber2.
        Step 3: fiber1 opens N channels to fiber2.
        Step 4: fiber3 opens N channels to fiber2.
        Step 5: fiber2 accepts all channels simultaneously.
        Step 6: Wait and verify all channels are CHANNEL_READY.
        """
        channel_count = 3  # Number of channels each fiber opens to fiber2

        # Step 1: Generate account and start fiber3
        account3 = self.generate_account(10000)
        fiber3 = self.start_new_fiber(account3)

        # Step 2: fiber3 connects to fiber2
        fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 3: fiber1 opens N channels to fiber2
        fiber1_channels = []
        for _ in range(channel_count):
            temp_channel = self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                    "public": True,
                }
            )
            fiber1_channels.append(temp_channel)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: fiber3 opens N channels to fiber2
        fiber3_channels = []
        for _ in range(channel_count):
            temp_channel = fiber3.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                    "public": True,
                }
            )
            fiber3_channels.append(temp_channel)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 5: fiber2 accepts all channels simultaneously
        all_channels = fiber1_channels + fiber3_channels
        for ch in all_channels:
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": ch["temporary_channel_id"],
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                }
            )

        # Step 6: Wait and verify all channels are CHANNEL_READY (from fiber2's view)
        time.sleep(Timeout.POLL_INTERVAL)

        def _fiber2_ready_predicate() -> bool:
            channels = self.fiber2.get_client().list_channels({})["channels"]
            for ch in channels:
                if ch['state']['state_name'] != ChannelState.CHANNEL_READY:
                    return False
            return True

        Waiter.wait_until(
            _fiber2_ready_predicate,
            config=WaitConfig(timeout=Timeout.CHANNEL_READY, interval=Timeout.POLL_INTERVAL),
            error_message=f"fiber2 expected  related channels all CHANNEL_READY",
        )
