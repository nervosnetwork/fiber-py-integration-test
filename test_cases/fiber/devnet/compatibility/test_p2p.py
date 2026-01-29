"""
Test cases for Fiber P2P compatibility: old Fiber 0.5.0 open_channel with current node
expects "feature not found"; old node can open channel with large amount.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, TLCFeeRate
from framework.test_fiber import FiberConfigPath


class TestP2p(FiberTest):
    """
    Test P2P compatibility between old Fiber 0.5.0 and current: open_channel from
    current to old expects "feature not found"; old can open channel to current.
    """

    def test_old_fiber(self):
        """
        Old Fiber 0.5.0 connects to current; current open_channel to old fails with "feature not found";
        old open_channel to current (large amount) succeeds but list_channels on old shows 0 (expected).
        Step 1: Start old fiber 0.5.0 and connect to fiber1.
        Step 2: fiber1 (current) open_channel to old; expect "feature not found".
        Step 3: Old fiber open_channel to fiber1 with large amount.
        Step 4: Assert old fiber list_channels is empty (protocol difference).
        """
        # Step 1: Start old fiber 0.5.0 and connect to fiber1
        old_fiber = self.start_new_fiber(
            self.generate_account(10000), fiber_version=FiberConfigPath.V050_DEV
        )
        old_fiber.connect_peer(self.fiber1)
        time.sleep(1)

        # Step 2: fiber1 (current) open_channel to old; expect "feature not found"
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": old_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000) + DEFAULT_MIN_DEPOSIT_CKB),
                    "tlc_fee_proportional_millionths": hex(TLCFeeRate.DEFAULT),
                    "public": True,
                }
            )
        expected_error_message = "feature not found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Old fiber open_channel to fiber1 with large amount
        old_fiber.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(2000)),
                "tlc_fee_proportional_millionths": hex(TLCFeeRate.DEFAULT),
                "public": True,
            }
        )
        time.sleep(1)

        # Step 4: Assert old fiber list_channels is empty (protocol difference)
        channel = old_fiber.get_client().list_channels({})
        assert len(channel["channels"]) == 0
