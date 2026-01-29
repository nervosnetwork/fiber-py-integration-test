"""
Test cases for shutdown_channel RPC fee_rate parameter.
Covers: fee_rate too big returns error (local balance not enough to pay fee).
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState


class TestFeeRate(FiberTest):
    """
    Test shutdown_channel fee_rate: too big should fail with available_max_fee error.
    """

    def test_fee_rate_too_big(self):
        """
        shutdown_channel with very large fee_rate should fail: local balance not enough to pay fee.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Call shutdown_channel with fee_rate 0xffffffffffffff; assert error contains available_max_fee.
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

        # Step 2: Call shutdown_channel with too large fee_rate; expect error
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().shutdown_channel(
                {
                    "channel_id": channel_id,
                    "close_script": {
                        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": self.account2["lock_arg"],
                    },
                    "fee_rate": "0xffffffffffffff",
                }
            )
        expected_error_message = "<= available_max_fee 100000000"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
