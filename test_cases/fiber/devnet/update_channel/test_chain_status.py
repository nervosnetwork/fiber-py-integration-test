"""
update_channel tests: call update_channel in AWAITING_TX_SIGNATURES and after shutdown.
"""
import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState, FeeRate

# TLC fee values in millionths (0.2%, 0.3%, 0.4%)
TLC_FEE_2000 = 2000
TLC_FEE_3000 = 3000
TLC_FEE_4000 = 4000


class TestChainStatus(FiberTest):
    """
    Test update_channel in pending state (AWAITING_TX_SIGNATURES) and after shutdown.
    Verifies tlc_fee_proportional_millionths can be updated and persists after shutdown.
    """

    def test_chain_status_pending(self):
        """
        Update tlc_fee in AWAITING_TX_SIGNATURES, then CHANNEL_READY, then after shutdown.
        Step 1: Open channel F1->F2; wait AWAITING_TX_SIGNATURES.
        Step 2: Update tlc_fee to 2000; wait CHANNEL_READY; assert list_channels shows 2000.
        Step 3: Update tlc_fee to 3000; assert list_channels shows 3000.
        Step 4: Shutdown channel (close_script, fee_rate); update tlc_fee to 4000; assert include_closed shows 4000.
        """
        # Step 1: Open channel F1->F2; wait AWAITING_TX_SIGNATURES
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(500)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.AWAITING_TX_SIGNATURES,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Update tlc_fee to 2000; wait CHANNEL_READY; assert list_channels shows 2000
        client = self.fiber1.get_client()
        ch_id = client.list_channels({})["channels"][0]["channel_id"]
        client.update_channel(
            {"channel_id": ch_id, "tlc_fee_proportional_millionths": hex(TLC_FEE_2000)}
        )
        self.wait_for_channel_state(
            client, self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        channels = client.list_channels({})
        assert channels["channels"][0]["tlc_fee_proportional_millionths"] == hex(TLC_FEE_2000)

        # Step 3: Update tlc_fee to 3000; assert list_channels shows 3000
        client.update_channel(
            {"channel_id": client.list_channels({})["channels"][0]["channel_id"], "tlc_fee_proportional_millionths": hex(TLC_FEE_3000)}
        )
        channels = client.list_channels({})
        assert channels["channels"][0]["tlc_fee_proportional_millionths"] == hex(TLC_FEE_3000)

        # Step 4: Shutdown channel (close_script, fee_rate); update tlc_fee to 4000; assert include_closed shows 4000
        ch_id = client.list_channels({})["channels"][0]["channel_id"]
        client.shutdown_channel(
            {
                "channel_id": ch_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        client.update_channel(
            {"channel_id": ch_id, "tlc_fee_proportional_millionths": hex(TLC_FEE_4000)}
        )
        channels = client.list_channels({"include_closed": True})
        assert channels["channels"][0]["tlc_fee_proportional_millionths"] == hex(TLC_FEE_4000)
