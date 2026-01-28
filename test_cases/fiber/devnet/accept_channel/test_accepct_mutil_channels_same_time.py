"""
Accept_channel test cases: same-channel duplicate accept and multi-channel concurrent accept.
Verifies: duplicate accept on the same temporary channel should fail; multi-channel accept behavior (includes skipped case).
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


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

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/246")
    def test_accept_channel_diff_channel_same_time(self):
        """
        Multi-channel concurrent accept: fiber2 accepts multiple temporary channels in sequence,
        verify first to CHANNEL_READY, second to AWAITING_TX_SIGNATURES, then open new channel and accept to CHANNEL_READY.
        Skipped due to issue #246.
        Step 1: Generate account and start fiber3 (1000 CKB balance, consistent with framework).
        Step 2: fiber3 connects to fiber2.
        Step 3: Open one temp channel fiber1->fiber2 and one fiber3->fiber2.
        Step 4: fiber3 opens 5 more temp channels for concurrent accept.
        Step 5: fiber2 accepts first, second, then the other 5 in sequence.
        Step 6: Wait fiber1<->fiber2 channel ready; wait fiber3<->fiber2 to AWAITING_TX_SIGNATURES.
        Step 7: fiber3 opens one more channel, fiber2 accepts and wait CHANNEL_READY.
        """
        # Step 1: Generate account and start fiber3 (1000 CKB balance)
        account3 = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3)

        # Step 2: fiber3 connects to fiber2
        fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 3: Open one temp channel fiber1->fiber2 and one fiber3->fiber2
        temporary_channel1 = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
                "commitment_fee_rate": hex(FeeRate.DEFAULT),
                "funding_fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        temporary_channel2 = fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
                "commitment_fee_rate": hex(FeeRate.DEFAULT),
                "funding_fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: fiber3 opens 5 more temp channels for concurrent accept
        temporary_other_channels = []
        for _ in range(5):
            temporary_other_channels.append(
                fiber3.get_client().open_channel(
                    {
                        "peer_id": self.fiber2.get_peer_id(),
                        "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                        "public": True,
                        "commitment_fee_rate": hex(FeeRate.DEFAULT),
                        "funding_fee_rate": hex(FeeRate.DEFAULT),
                    }
                )
            )

        # Step 5: fiber2 accepts first, second, then the other 5 in sequence
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel1["temporary_channel_id"],
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
            }
        )
        time.sleep(Timeout.FAST_POLL_INTERVAL)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel2["temporary_channel_id"],
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
            }
        )
        time.sleep(Timeout.FAST_POLL_INTERVAL)
        for ch in temporary_other_channels:
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": ch["temporary_channel_id"],
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                }
            )
            time.sleep(Timeout.FAST_POLL_INTERVAL)

        # Step 6: Wait fiber1<->fiber2 channel ready
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        # Wait fiber3<->fiber2 to AWAITING_TX_SIGNATURES
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            fiber3.get_peer_id(),
            ChannelState.AWAITING_TX_SIGNATURES,
            timeout=Timeout.CHANNEL_READY,
        )
        time.sleep(5)  # Allow multi-channel processing to settle (short wait, not main logic)

        # Step 7: fiber3 opens one more channel, fiber2 accepts and wait CHANNEL_READY
        temporary_channel2 = fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
                "commitment_fee_rate": hex(FeeRate.DEFAULT),
                "funding_fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel2["temporary_channel_id"],
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
