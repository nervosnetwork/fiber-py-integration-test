"""
Test cases for shutdown_channel RPC with channel_id parameter.
Covers: non-existent channel_id returns error; existing channel_id shuts down and balance returned.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState


class TestChannelId(FiberTest):
    """
    Test shutdown_channel behavior for channel_id: not exist (error) and exist (success, balance check).
    """

    def test_channel_id_not_exist(self):
        """
        shutdown_channel with non-existent channel_id should fail with Channel not found error.
        Step 1: Call shutdown_channel with random channel_id (invalid).
        Step 2: Assert error message contains Channel not found error.
        """
        # Step 1: Call shutdown_channel with non-existent channel_id
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": self.generate_random_preimage(),
                    "close_script": self.get_account_script(
                        self.fiber1.account_private
                    ),
                    "fee_rate": "0x3FC",
                }
            )
        # Step 2: Assert error message
        expected_error_message = "Channel not found error"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_channel_id_exist(self):
        """
        shutdown_channel with existing channel_id should close channel and return balance.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Call shutdown_channel with close_script and fee_rate.
        Step 3: Wait close tx committed and channel CLOSED; assert channel_count 0 and balance returned.
        """
        # Step 1: Open channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
            }
        )
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

        # Step 2: Shutdown channel
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

        # Step 3: Wait close tx committed and channel CLOSED; assert balance returned
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(),
            ChannelState.CLOSED, timeout=Timeout.CHANNEL_READY, include_closed=True
        )
        node_info = self.fiber1.get_client().node_info()
        self.assert_channel_count(self.fiber1, 0)

        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
