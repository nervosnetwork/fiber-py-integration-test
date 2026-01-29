"""
Test cases for shutdown_channel RPC.
Covers: channel_id (existing / non-existing), close_script, force (online / offline), fee_rate, channel states.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestShutdownChannel(FiberTest):
    """
    Test shutdown_channel RPC: channel_id, close_script, force, fee_rate, and channel/peer state.
    Scenarios: existing channel, non-existent channel, online/offline peer, channel states.
    """

    def test_shutdown_existing_channel_succeeds(self):
        """
        shutdown_channel with existing channel_id and valid close_script should close and return balance.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Call shutdown_channel with close_script and fee_rate.
        Step 3: Wait for close tx and CLOSED; assert channel_count 0 and balance returned.
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
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
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

        # Step 2: Shutdown channel with close_script and fee_rate
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )

        # Step 3: Wait for close tx committed and channel CLOSED; assert balance returned
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.CHANNEL_READY,
            include_closed=True,
        )

        self.assert_channel_count(self.fiber1, 0)

        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        expected_delta_ckb = Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
        assert after_balance2 - before_balance2 == expected_delta_ckb, (
            f"Acceptor balance should increase by min deposit; "
            f"before={before_balance2}, after={after_balance2}, expected_delta={expected_delta_ckb}"
        )

    def test_shutdown_nonexistent_channel_fails(self):
        """
        shutdown_channel with non-existent channel_id should fail with Channel not found error.
        Step 1: Call shutdown_channel with invalid channel_id.
        Step 2: Assert error message contains Channel not found error.
        """
        # Step 1: Call shutdown_channel with non-existent channel_id
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": self.generate_random_preimage(),
                    "close_script": self.get_account_script(self.account1_private_key),
                    "fee_rate": hex(FeeRate.DEFAULT),
                }
            )
        # Step 2: Assert error message
        expected_error_message = "Channel not found error"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
