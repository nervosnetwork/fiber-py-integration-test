"""
Test cases for accept_channel tlc_min_value parameter.
Verifies: channel acceptance with tlc_min_value and payment rejection when amount is below minimum.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState


class TestTlcMinValue(FiberTest):
    """
    Test accept_channel with tlc_min_value parameter.
    Verifies: channel can be accepted with tlc_min_value, payments at or above minimum succeed,
    payments below minimum are rejected with route build failure.
    """

    def test_tlc_min_value(self):
        """
        Test that tlc_min_value enforces minimum payment amount in the channel.
        Step 1: fiber1 opens channel with fiber2.
        Step 2: fiber2 accepts channel with tlc_min_value=1 CKB.
        Step 3: Wait for channel ready.
        Step 4: Send payment at minimum (1 CKB) - should succeed.
        Step 5: Send payment below minimum (1 CKB - 1) - should fail with route build error.
        Step 6: Send payment from fiber1 to fiber2 below minimum - should succeed (reverse direction).
        """
        # Step 1: fiber1 opens channel with fiber2
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": Amount.to_hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: fiber2 accepts channel with tlc_min_value=1 CKB
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": Amount.to_hex(Amount.ckb(1000)),
                "tlc_min_value": Amount.to_hex(Amount.ckb(1)),
            }
        )

        # Step 3: Wait for channel ready
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 4: Send payment at minimum (1 CKB) - should succeed
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))

        # Step 5: Send payment below minimum (1 CKB - 1) - should fail with route build error
        with pytest.raises(Exception) as exc_info:
            self.send_payment(
                self.fiber2, self.fiber1, Amount.ckb(1) - 1, wait=False
            )
        expected_error_message = "Failed to build route"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 6: Send payment from fiber1 to fiber2 below minimum - should succeed (reverse direction)
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1) - 1)
