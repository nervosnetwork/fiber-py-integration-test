"""
Test cases for Fiber version compatibility (data migration): start old Fiber 0.6.0,
open channel and send payments, then migrate to current version and verify send_payment and shutdown.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, FeeRate, TLCFeeRate, Timeout
from framework.test_fiber import FiberConfigPath


class TestData(FiberTest):
    """
    Test Fiber data compatibility: run old Fiber 0.6.0, open channel and stress pay,
    then migrate to current version, restart and verify send_payment and shutdown_channel output.
    """

    # @pytest.mark.skip("migration failed")
    def test_old_fiber_060(self):
        """
        Start Fiber 0.6.0, open channel and stress pay, then migrate to current and verify.
        Step 1: Start two fibers with 0.6.0 and connect.
        Step 2: Open channel between them with semantic constants.
        Step 3: Stress send_payment both directions.
        Step 4: Stop fibers, switch config to current, run migration and restart.
        Step 5: Send payments and shutdown channel; assert output cell matches peer.
        """
        # Step 1: Start two fibers with 0.6.0 and connect
        old_fiber_1 = self.start_new_fiber(
            self.generate_account(10000), fiber_version=FiberConfigPath.V060_DEV
        )
        old_fiber_2 = self.start_new_fiber(
            self.generate_account(10000), fiber_version=FiberConfigPath.V060_DEV
        )
        old_fiber_1.connect_peer(old_fiber_2)
        time.sleep(1)

        # Step 2: Open channel between them with semantic constants
        self.open_channel(
            old_fiber_1, old_fiber_2,
            Amount.ckb(1000),
            Amount.ckb(1000),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

        # Step 3: Stress send_payment both directions
        for i in range(20):
            self.send_payment(old_fiber_1, old_fiber_2, Amount.ckb(1), False)
            self.send_payment(old_fiber_2, old_fiber_1, Amount.ckb(1), False)

        # Step 4: Stop fibers, switch config to current, run migration and restart
        old_fiber_1.stop()
        old_fiber_2.stop()

        old_fiber_1.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        old_fiber_2.fiber_config_enum = FiberConfigPath.CURRENT_DEV

        old_fiber_1.migration()
        old_fiber_2.migration()

        time.sleep(5)
        old_fiber_1.start()
        old_fiber_2.start()
        time.sleep(Timeout.VERY_SHORT)

        # Step 5: Send payments and shutdown channel; assert output cell matches peer
        self.send_payment(old_fiber_1, old_fiber_2, Amount.ckb(100))
        self.send_payment(old_fiber_2, old_fiber_1, Amount.ckb(200))
        channels = old_fiber_1.get_client().list_channels({})
        old_fiber_1.get_client().shutdown_channel(
            {
                "channel_id": channels["channels"][0]["channel_id"],
                "close_script": self.get_account_script(self.Config.ACCOUNT_PRIVATE_1),
                "fee_rate": FeeRate.to_hex(1020),  # 0x3FC
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        tx_message = self.get_tx_message(tx_hash)
        assert {
            "args": self.get_account_script(old_fiber_2.account_private)["args"],
            "capacity": 100000000000 + DEFAULT_MIN_DEPOSIT_CKB,
        } in tx_message["output_cells"]
