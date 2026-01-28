"""
Test cases for MPP force shutdown: pending TLC and force shutdown channel.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate, TLCFeeRate


class TestMppForceShutdown(FiberTest):
    """
    Test MPP with force shutdown: send payment (hold invoice), cancel; then force shutdown
    channels with pending TLC and assert commitment tx behaviour.
    Placeholder: full scenario is todo; tests kept skipped until implemented.
    """

    @pytest.mark.skip(reason="todo: MPP force shutdown scenario to be implemented")
    def test_force_shutdown_placeholder(self):
        """
        Placeholder for force shutdown test: open channels, send MPP, cancel invoice,
        force shutdown channels with pending TLC, generate epochs and assert tx/fee.
        Step 1: Build topology and send hold-invoice MPP.
        Step 2: Cancel invoice; assert offered/received TLC non-zero.
        Step 3: Shutdown channels with pending TLC; wait tx; generate epochs; assert fee.
        """
        # Step 1: Build topology and send hold-invoice MPP (placeholder)
        _ = Amount.ckb(2000)
        _ = FeeRate.MIN
        _ = TLCFeeRate.DEFAULT
        # Step 2 & 3: Not implemented
        pass
