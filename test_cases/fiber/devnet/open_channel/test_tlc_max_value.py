# Fiber removed tlc_max_value option; tests kept for reference and possible restoration.
#
# Adapted to framework: use Amount, Timeout, ChannelState, FeeRate; English docstrings.
# When tlc_max_value is restored, uncomment the test body and remove the skip.

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Timeout


class TestTlcMaxValue(FiberTest):
    """
    Test open_channel tlc_max_value parameter (option removed from fiber).
    Tests are skipped until tlc_max_value is restored.
    """

    @pytest.mark.skip(reason="todo: tlc_max_value none scenario")
    def test_tlc_max_value_none(self):
        """
        tlc_max_value: none (default).
        Step 1: (Placeholder) Not implemented.
        """

    @pytest.mark.skip(reason="todo: CKB tlc_max_value != default")
    def test_ckb_tlc_max_value_not_eq_default(self):
        """
        tlc_max_value != default for CKB channel.
        Step 1: (Placeholder) Not implemented.
        """

    @pytest.mark.skip(reason="tlc_max_value option removed from fiber")
    def test_udt_tlc_max_value_not_eq_default(self):
        """
        UDT tlc_max_value != default: open with tlc_max_value, pay below then above, expect route fail for above.
        Step 1: Open UDT channel with tlc_max_value, pay 500 UDT (below max), assert success.
        Step 2: Try pay 160 UDT (above max), expect Failed to build route.
        Step 3: Shutdown channel and verify on-chain.
        """
        # When option is restored: use Amount.ckb/udt, Timeout.CHANNEL_READY, ChannelState.CHANNEL_READY,
        # FeeRate for shutdown; uncomment body from original test_udt_tlc_max_value_not_eq_default.
        pass
