"""
Test cases for shutdown_channel with channel_id parameter.
"""
import time
import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestChannelId(FiberTest):
    """
    Test shutdown_channel channel_id parameter: nonexistent vs existing channel.
    """

    def test_channel_id_not_exist(self):
        """
        shutdown_channel with nonexistent channel_id returns Channel not found error.
        Step 1: Call shutdown_channel with random channel_id.
        Step 2: Assert Channel not found error.
        """
        # Step 1: Call shutdown_channel with random channel_id
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": self.generate_random_preimage(),
                    "close_script": self.get_account_script(
                        self.fiber1.account_private
                    ),
                    "fee_rate": hex(FeeRate.MEDIUM),
                }
            )

        # Step 2: Assert Channel not found error
        assert "Channel not found error" in exc_info.value.args[0]

    def test_channel_id_exist(self):
        """
        shutdown_channel with existing channel_id closes channel and returns balance.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Wait for CHANNEL_READY and get channel_id.
        Step 3: Call shutdown_channel with valid close_script and fee_rate.
        Step 4: Wait for tx committed and channel CLOSED.
        Step 5: Assert channel_count is 0 and balance returned correctly.
        """
        # Step 1: Open channel
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Get channel_id
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

        # Step 3: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )

        # Step 4: Wait for tx committed and channel CLOSED
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.CHANNEL_READY,
            include_closed=True,
        )

        # Step 5: Assert channel_count is 0 and balance returned
        node_info = self.fiber1.get_client().node_info()
        assert node_info["channel_count"] == "0x0"
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
