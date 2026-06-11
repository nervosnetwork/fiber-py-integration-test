import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB


class TestWatchtowerTaskSurvivesRpcError(FiberTest):
    """
    PR-1397 regression (GHSA-49ph-wf39-5prx): a watchtower RPC error must NOT
    permanently kill the event-processing task. After the standalone watchtower
    becomes unreachable (connection refused), the task must survive so that once
    the watchtower is reachable again a subsequent settlement event is still
    forwarded and acted upon.

    Scenario:
      1. fiber2 uses standalone watchtower fiber3, built-in disabled.
      2. fiber3 (watchtower) is taken OFFLINE -> fiber2's watchtower forwarding
         hits an RPC connection error while the channel is live.
      3. fiber1 force-closes; fiber1 then stops and an epoch is generated so the
         settlement becomes claimable by the watchtower.
      4. fiber3 is brought back ONLINE.
      5. Assert the watchtower still produces the settlement tx (task survived).
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_event_task_survives_watchtower_rpc_error(self):
        self.fiber3 = self.start_new_fiber(self.generate_random_preimage())
        self.fiber2.stop()
        self.fiber2.prepare(
            {
                "fiber_standalone_watchtower_rpc_url": self.fiber3.get_client().url,
                "fiber_disable_built_in_watchtower": "true",
            }
        )
        self.fiber2.start()

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1)

        # Take the watchtower offline so forwarding RPC calls fail (connection refused).
        self.fiber3.stop()
        time.sleep(6)

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )
        tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx)
        self.fiber1.stop()
        self.node.getClient().generate_epochs("0x1", 0)

        # While the watchtower is offline, no settlement tx can be produced.
        with pytest.raises(Exception):
            self.wait_and_check_tx_pool_fee(1000, False, 20 * 5)

        # Bring the watchtower back online and fund it so it can build the tx.
        self.fiber3.start()
        self.faucet(self.fiber3.account_private, 1000)

        before_balance = self.get_fiber_balance(self.fiber3)
        # If the event-processing task had died on the earlier RPC error, no
        # settlement tx would ever appear here. Its appearance proves survival.
        tx = self.wait_and_check_tx_pool_fee(1000, False, 120 * 5)
        self.Miner.miner_until_tx_committed(self.node, tx)
        after_balance = self.get_fiber_balance(self.fiber3)
        result = self.get_balance_change([before_balance], [after_balance])
        assert abs(result[0]["ckb"] + DEFAULT_MIN_DEPOSIT_CKB) < 10000
