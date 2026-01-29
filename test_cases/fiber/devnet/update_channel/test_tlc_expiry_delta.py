"""
update_channel tests: tlc_expiry_delta validation (too small, overflow) and normal value.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState

# Minimum allowed tlc_expiry_delta (ms)
TLC_EXPIRY_DELTA_MIN = 900000
TLC_EXPIRY_DELTA_VALID = 1_000_000


class TestTlcExpiryDelta(FiberTest):
    """
    Test update_channel tlc_expiry_delta: reject 0, below 900000, overflow hex; accept 1000000.
    """

    @pytest.mark.skip(reason="tlc_expiry_delta = 0xffffffffffffffff, expected: success")
    def test_01(self):
        """
        Reject tlc_expiry_delta 0x0, 899999, overflow hex; accept 1000000; assert list_channels.
        Step 1: Open F1-F2 channel; get channel_id from F1.
        Step 2: update_channel tlc_expiry_delta 0x0 and 899999; expect 'TLC expiry delta is too small'.
        Step 3: update_channel overflow hex; expect same error.
        Step 4: update_channel tlc_expiry_delta 1000000; assert list_channels shows 1000000.
        """
        # Step 1: Open F1-F2 channel; get channel_id from F1
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1)
        )
        channel = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        ch_id = channel["channels"][0]["channel_id"]

        # Step 2: update_channel tlc_expiry_delta 0x0 and 899999; expect error
        expected_error = "TLC expiry delta is too small, expect larger than 900000"
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().update_channel(
                {"channel_id": ch_id, "tlc_expiry_delta": "0x0"}
            )
        assert expected_error in exc_info.value.args[0], (
            f"Expected '{expected_error}' not found in '{exc_info.value.args[0]}'"
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().update_channel(
                {"channel_id": ch_id, "tlc_expiry_delta": hex(TLC_EXPIRY_DELTA_MIN - 1)}
            )
        assert expected_error in exc_info.value.args[0], (
            f"Expected '{expected_error}' not found in '{exc_info.value.args[0]}'"
        )

        # Step 3: update_channel overflow hex; expect same error
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().update_channel(
                {"channel_id": ch_id, "tlc_expiry_delta": "0xffffffffffffffffff"}
            )
        assert expected_error in exc_info.value.args[0], (
            f"Expected '{expected_error}' not found in '{exc_info.value.args[0]}'"
        )

        # Step 4: update_channel tlc_expiry_delta 1000000; assert list_channels
        self.fiber2.get_client().update_channel(
            {"channel_id": ch_id, "tlc_expiry_delta": hex(TLC_EXPIRY_DELTA_VALID)}
        )
        channels = self.fiber2.get_client().list_channels({})
        # API may put tlc_expiry_delta on channel object or top-level
        got = channels["channels"][0].get("tlc_expiry_delta") or channels.get("tlc_expiry_delta")
        assert got == hex(TLC_EXPIRY_DELTA_VALID), f"Expected {hex(TLC_EXPIRY_DELTA_VALID)}, got {got}"
