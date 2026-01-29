"""
Test cases for shutdown_channel fee_rate parameter.
"""
import time
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState


class TestFeeRate(FiberTest):
    """
    Test shutdown_channel fee_rate validation: too high fee_rate returns balance error.
    """

    def test_fee_rate_too_big(self):
        """
        shutdown_channel with fee_rate exceeding available balance returns error.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Wait for CHANNEL_READY.
        Step 3: Call shutdown_channel with very high fee_rate (fiber2 has 0 local balance).
        Step 4: Assert error contains available_max_fee limit.
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

        # Step 3: Call shutdown_channel with very high fee_rate (fiber2 has 0 local)
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

        # Step 4: Assert error contains available_max_fee limit
        assert "<= available_max_fee 100000000" in exc_info.value.args[0]
