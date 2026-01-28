"""
Test cases for open_channel tlc_expiry_delta parameter.
Validates boundary: too small rejects, too large rejects.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Timeout


class TestTlcLocktimeExpiryDelta(FiberTest):
    """
    Test open_channel tlc_expiry_delta validation.
    Covers: zero or too small rejects, larger than max rejects.
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    @pytest.mark.skip(reason="todo: tlc_expiry_delta=1 requires watchtower flow not yet covered")
    def test_tlc_expiry_delta_none(self):
        """
        tlc_expiry_delta = none (default behavior).
        Step 1: (Placeholder) Not implemented.
        """

    def test_tlc_expiry_delta_is_zero_or_bigger(self):
        """
        open_channel rejects when tlc_expiry_delta is 0 or larger than max.
        Step 1: Call open_channel with tlc_expiry_delta=0, assert error contains expected message.
        Step 2: Call open_channel with tlc_expiry_delta=0xffffffff, assert error contains expected message.
        """
        # Step 1: Call open_channel with tlc_expiry_delta=0, assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(200)),
                    "public": True,
                    "tlc_expiry_delta": "0x0",
                }
            )
        expected_error_message = "TLC expiry delta is too small, expect larger than"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 2: Call open_channel with tlc_expiry_delta=0xffffffff, assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(200)),
                    "public": True,
                    "tlc_expiry_delta": "0xffffffff",
                }
            )
        expected_error_message = "expected to be smaller than"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    @pytest.mark.skip(reason="todo: tlc_expiry_delta=1 requires watchtower to reclaim expired TLC")
    def test_tlc_expiry_delta_is_1(self):
        """
        tlc_expiry_delta = 1: after expiry, A can reclaim TLC via watchtower (not yet covered).
        Step 1: (Placeholder) Not implemented.
        """

    @pytest.mark.skip(reason="todo: tlc_expiry_delta != default scenario not yet covered")
    def test_tlc_expiry_delta_not_eq_default(self):
        """
        tlc_expiry_delta != default.
        Step 1: (Placeholder) Not implemented.
        """
