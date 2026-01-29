"""
Test cases for node_info RPC: commit_hash, self-pay rejection, addresses, chain_hash, config fields, channel_count.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    Timeout,
    TLCFeeRate,
)


class TestNodeInfo(FiberTest):
    """
    Test node_info: commit_hash present, self-pay rejected when disabled, addresses match graph_nodes, chain_hash, config fields, channel_count and pending_channel_count.
    """

    def test_commit_hash(self):
        """
        node_info returns commit_hash; self-pay with keysend should fail when allow_self_payment is not enabled;
        addresses should match graph_nodes; chain_hash should match block 0; config and feature fields asserted.
        Step 1: Get node_info; assert commit_hash present.
        Step 2: send_payment to self (node_id) with keysend dry_run; expect "allow_self_payment is not enable".
        Step 3: Assert node_info addresses match one of graph_nodes addresses.
        Step 4: Assert chain_hash equals block 0 hash.
        Step 5: Assert open_channel_auto_accept_min_ckb_funding_amount, auto_accept_channel_ckb_funding_amount, tlc_*, peers_count, features.
        """
        # Step 1: Get node_info and assert commit_hash present
        node_info = self.fiber1.get_client().node_info()
        assert node_info["commit_hash"] is not None

        # Step 2: Self-pay with keysend dry_run should fail when allow_self_payment is not enabled
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": node_info["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        expected_error_message = "allow_self_payment is not enable"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Assert node_info addresses match one of graph_nodes
        nodes = self.fiber1.get_client().graph_nodes({})
        assert (
            nodes["nodes"][0]["addresses"] == node_info["addresses"]
            or nodes["nodes"][1]["addresses"] == node_info["addresses"]
        )

        # Step 4: Assert chain_hash equals block 0 hash
        block_hash = self.node.getClient().get_block_hash("0x0")
        assert block_hash == node_info["chain_hash"]

        # Step 5: Assert config and feature fields
        assert node_info["open_channel_auto_accept_min_ckb_funding_amount"] == hex(
            Amount.ckb(100)
        )
        assert node_info["auto_accept_channel_ckb_funding_amount"] == hex(
            Amount.ckb(98)
        )
        assert node_info["tlc_expiry_delta"] == hex(14400000)
        assert node_info["tlc_min_value"] == hex(0)
        assert node_info["tlc_fee_proportional_millionths"] == hex(
            TLCFeeRate.DEFAULT
        )
        assert node_info["peers_count"] == hex(1)
        assert node_info["features"] is not None, "features should not be None"

    def test_channel_count(self):
        """
        pending_channel_count increases when channel opening; after CHANNEL_READY it decreases; channel_count updates; after shutdown channel_count decreases.
        Step 1: Get node_info before open_channel.
        Step 2: Open channel; assert pending_channel_count +1 on both nodes.
        Step 3: Wait CHANNEL_READY; assert pending_channel_count decreased; channel_count unchanged from pending.
        Step 4: Shutdown channel; wait; assert channel_count decreased on both.
        """
        # Step 1: Get node_info before open_channel
        before_open_channel_node1_info = self.fiber1.get_client().node_info()
        before_open_channel_node2_info = self.fiber2.get_client().node_info()

        # Step 2: Open channel; assert pending_channel_count +1 on both
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        pending_node1_info = self.fiber1.get_client().node_info()
        pending_node2_info = self.fiber2.get_client().node_info()
        assert (
            int(pending_node1_info["pending_channel_count"], 16)
            == int(before_open_channel_node1_info["pending_channel_count"], 16) + 1
        )
        assert (
            int(pending_node2_info["pending_channel_count"], 16)
            == int(before_open_channel_node2_info["pending_channel_count"], 16) + 1
        )

        # Step 3: Wait CHANNEL_READY; assert pending_channel_count decreased
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        after_node1_info = self.fiber1.get_client().node_info()
        after_node2_info = self.fiber2.get_client().node_info()
        assert (
            int(after_node1_info["pending_channel_count"], 16)
            == int(pending_node1_info["pending_channel_count"], 16) - 1
        )
        assert int(after_node1_info["channel_count"], 16) == int(
            pending_node1_info["channel_count"], 16
        )
        assert (
            int(after_node2_info["pending_channel_count"], 16)
            == int(pending_node1_info["pending_channel_count"], 16) - 1
        )
        assert int(after_node2_info["channel_count"], 16) == int(
            pending_node1_info["channel_count"], 16
        )

        # Step 4: Shutdown channel; wait; assert channel_count decreased on both
        channel = self.fiber1.get_client().list_channels({})
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel["channels"][0]["channel_id"],
                "close_script": self.get_account_script(self.fiber1.account_private),
                "fee_rate": hex(1020),  # 1020 shannons per KB for shutdown
            }
        )
        time.sleep(20)
        after_shutdown_node1_info = self.fiber1.get_client().node_info()
        after_shutdown_node2_info = self.fiber2.get_client().node_info()
        assert (
            int(after_shutdown_node1_info["channel_count"], 16)
            == int(after_node1_info["channel_count"], 16) - 1
        )
        assert (
            int(after_shutdown_node2_info["channel_count"], 16)
            == int(after_node1_info["channel_count"], 16) - 1
        )

    @pytest.mark.skip("")
    def test_network_sync_status(self):
        """
        Placeholder: check network_sync_status.
        """
        pass

    def test_udt_cfg_infos(self):
        """
        After opening UDT channel, node_info (or udt config) can be checked.
        Step 1: Open UDT channel fiber1-fiber2 with funding_udt_type_script.
        Step 2: Wait CHANNEL_READY.
        """
        # Step 1: Open UDT channel
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        # Step 2: Wait CHANNEL_READY
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
