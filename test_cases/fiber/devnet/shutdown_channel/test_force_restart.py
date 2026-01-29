"""
Test cases for shutdown_channel during force restart of fiber nodes.
Covers: initiator/acceptor force stop and restart during shutdown; channel closed and balance returned.
"""
import time

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState


class TestForceRestart(FiberTest):
    """
    Test shutdown_channel during force restart: initiator and acceptor force stop/start; channel closed, balance returned.
    """

    def test_force_restart_fiber_node_shutdown_channel(self):
        """
        Force restart both nodes during shutdown; channel should close and balance returned.
        Step 1: Open channel, wait CHANNEL_READY, call shutdown_channel.
        Step 2: Acceptor force stop; assert funding cell unknown.
        Step 3: Initiator force stop then start; acceptor start.
        Step 4: Assert channel_count 0 and balance returned.
        """
        # Step 1: Open channel and shutdown
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        open_channel_tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().graph_channels()

        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        channel_id = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        cell = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert cell["status"] == "live"

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": "0x3FC",
            }
        )
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "live"

        # Step 2: Acceptor force stop
        self.fiber2.force_stop()
        time.sleep(10)
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown"

        # Step 3: Initiator force stop then start; acceptor start
        self.fiber1.force_stop()
        time.sleep(10)
        self.fiber1.start()
        time.sleep(10)
        self.fiber2.start()
        time.sleep(10)
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown"

        # Step 4: Assert channel closed and balance returned
        self.assert_channel_count(self.fiber1, 0)
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
