"""
Test cases for graph_channels RPC: add/update/remove channels and channel info.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, FeeRate, Timeout, TLCFeeRate


class TestGraphChannels(FiberTest):
    """
    Test graph_channels RPC: add channels, update channel info, remove channels (force/close).
    """

    def test_add_channels(self):
        """
        Test adding channels.

        Steps:
            1. Generate a new account with 1000 units of balance
            2. Start a new fiber with the generated account
            3. Connect fiber3 to fiber2
            4. Open a new public channel with fiber1 as the client and fiber2 as the peer
            5. Check the graph channels for node1, node2, and node3
            6. Open a new private channel with fiber1 as the client and fiber2 as the peer
            7. Check the graph channels for node1, node2, and node3
            8. Open a new public channel with fiber2 as the client and fiber3 as the peer
            9. Check the graph channels for node1, node2, and node3
            10. Open a new private channel with fiber2 as the client and fiber3 as the peer
            11. Check the graph channels for node1, node2, and node3
            12. Start a new fiber and connect it to fiber3
            13. Check the graph channels for node4

        Returns:
        """
        # Step 1: Generate a new account with 1000 CKB balance
        account3_private_key = self.generate_account(1000)

        # Step 2: Start a new fiber with the generated account
        self.fiber3 = self.start_new_fiber(account3_private_key)

        # Step 3: Connect fiber3 to fiber2
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: Open a new public channel with fiber1 as the client and fiber2 as the peer
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 5: Check the graph channels for node1, node2, and node3
        time.sleep(Timeout.POLL_INTERVAL)
        node1_channels = self.fiber1.get_client().graph_channels()
        node2_channels = self.fiber2.get_client().graph_channels()
        node3_channels = self.fiber3.get_client().graph_channels()
        assert len(node1_channels["channels"]) == 1
        assert len(node2_channels["channels"]) == 1
        assert len(node3_channels["channels"]) == 1

        # Step 6: Open a new private channel with fiber1 as the client and fiber2 as the peer
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 7: Check the graph channels for node1, node2, and node3
        time.sleep(Timeout.POLL_INTERVAL)
        node1_channels = self.fiber1.get_client().graph_channels()
        node2_channels = self.fiber2.get_client().graph_channels()
        node3_channels = self.fiber3.get_client().graph_channels()
        assert len(node1_channels["channels"]) == 1
        assert len(node2_channels["channels"]) == 1
        assert len(node3_channels["channels"]) == 1

        # Step 8: Open a new public channel with fiber2 as the client and fiber3 as the peer
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 9: Check the graph channels for node1, node2, and node3
        time.sleep(Timeout.POLL_INTERVAL)
        node1_channels = self.fiber1.get_client().graph_channels()
        node2_channels = self.fiber2.get_client().graph_channels()
        node3_channels = self.fiber3.get_client().graph_channels()
        assert len(node1_channels["channels"]) == 2
        assert len(node2_channels["channels"]) == 2
        assert len(node3_channels["channels"]) == 2

        # Step 10: Open a new private channel with fiber2 as the client and fiber3 as the peer
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 11: Check the graph channels for node1, node2, and node3
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_graph_channels_sync(self.fiber1, 2)
        self.wait_graph_channels_sync(self.fiber2, 2)
        self.wait_graph_channels_sync(self.fiber3, 2)

        # Step 12: Start a new fiber and connect it to fiber3
        fiber4 = self.start_new_fiber(self.generate_random_preimage())
        fiber4.connect_peer(self.fiber3)
        # Step 13: Check the graph channels for node4
        self.wait_graph_channels_sync(fiber4, 2)

    def test_remove_channels_with_force(self):
        """
        Force close and normal close channel; verify graph_channels sync.
        Step 1: Build topology (fiber1-fiber2-fiber3), open two channels.
        Step 2: Shutdown n1-n2 channel with close_script and fee_rate.
        Step 3: Wait graph sync to 1 channel.
        Step 4: Force shutdown n2-n3 channel.
        Step 5: Wait channel CLOSED and graph sync to 0.
        """
        # Step 1: Build topology and open channels
        account3_private_key = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private_key)
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 2: Close n1-n2 channel with close_script and fee_rate (0x3FC = 1020 shannons per KB)
        N1N2_CHANNEL_ID = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": N1N2_CHANNEL_ID,
                "close_script": self.get_account_script(self.fiber1.account_private),
                "fee_rate": hex(1020),
            }
        )
        self.wait_tx_pool(1)
        for i in range(10):
            self.Miner.miner_with_version(self.node, "0x0")

        # Step 3: Wait graph sync to 1 channel
        self.wait_graph_channels_sync(self.fiber1, 1, Timeout.SHORT)
        self.wait_graph_channels_sync(self.fiber2, 1, Timeout.SHORT)
        self.wait_graph_channels_sync(self.fiber3, 1, Timeout.SHORT)

        # Step 4: Force shutdown n2-n3 channel
        N2N3_CHANNEL_ID = self.fiber3.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": N2N3_CHANNEL_ID,
                "force": True,
            }
        )
        self.wait_tx_pool(1)
        for i in range(10):
            self.Miner.miner_with_version(self.node, "0x0")

        # Step 5: Wait channel CLOSED and graph sync to 0
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=310,
            include_closed=True,
        )
        self.wait_graph_channels_sync(self.fiber1, 0, Timeout.SHORT)
        self.wait_graph_channels_sync(self.fiber2, 0, Timeout.SHORT)
        self.wait_graph_channels_sync(self.fiber3, 0, Timeout.SHORT)

    def test_update_channel_info(self):
        """
        Update channel (tlc_fee_proportional_millionths) and verify graph_channels reflects it.
        Step 1: Build topology, open channel. Step 2: Update channel params.
        Step 3: Verify graph_channels fee_rate matches update.
        """
        # Step 1: Build topology and open channel
        update_channel_param = {
            "enabled": True,
            "tlc_minimum_value": hex(100),
            "tlc_fee_proportional_millionths": hex(TLCFeeRate.DEFAULT * 2),
        }
        account3_private_key = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private_key)
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        channel = self.fiber1.get_client().list_channels({})
        update_channel_param["channel_id"] = channel["channels"][0]["channel_id"]
        self.fiber1.get_client().update_channel(update_channel_param)
        time.sleep(Timeout.POLL_INTERVAL * 5)

        # Step 2 & 3: Verify graph_channels fee_rate matches update
        node1_channels = self.fiber1.get_client().graph_channels()
        node2_channels = self.fiber2.get_client().graph_channels()
        node3_channels = self.fiber3.get_client().graph_channels()
        node_info = self.fiber1.get_client().node_info()
        key = (
            "update_info_of_node1"
            if node3_channels["channels"][0]["node1"] == node_info["node_id"]
            else "update_info_of_node2"
        )
        print("key:", key)
        assert (
            node1_channels["channels"][0][key]["fee_rate"]
            == update_channel_param["tlc_fee_proportional_millionths"]
        )
        key = (
            "update_info_of_node1"
            if node3_channels["channels"][0]["node1"] == node_info["node_id"]
            else "update_info_of_node2"
        )
        assert (
            node2_channels["channels"][0][key]["fee_rate"]
            == update_channel_param["tlc_fee_proportional_millionths"]
        )
        key = (
            "update_info_of_node1"
            if node3_channels["channels"][0]["node1"] == node_info["node_id"]
            else "update_info_of_node2"
        )
        assert (
            node3_channels["channels"][0][key]["fee_rate"]
            == update_channel_param["tlc_fee_proportional_millionths"]
        )

    def test_channel_info_check(self):
        """
        Open channel and verify graph_channels fields (channel_outpoint, node1/node2, fee_rate, capacity, chain_hash).
        Step 1: Build topology and open channel. Step 2: Assert graph_channels content.
        """
        # Step 1: Build topology and open channel
        account3_private_key = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private_key)
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        open_channel_tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )

        time.sleep(Timeout.POLL_INTERVAL)
        node1_channels = self.fiber1.get_client().graph_channels()
        node2_channels = self.fiber2.get_client().graph_channels()
        node3_channels = self.fiber3.get_client().graph_channels()

        # check channel_outpoint
        assert open_channel_tx_hash in node1_channels["channels"][0]["channel_outpoint"]
        assert open_channel_tx_hash in node2_channels["channels"][0]["channel_outpoint"]
        assert open_channel_tx_hash in node3_channels["channels"][0]["channel_outpoint"]

        # funding_tx_block_number
        # tx = self.node.getClient().get_transaction(open_channel_tx_hash)
        # assert (
        #     node1_channels["channels"][0]["funding_tx_block_number"]
        #     == tx["tx_status"]["block_number"]
        # )
        # funding_tx_index
        # todo funding_tx_index 是错的
        # assert node1_channels["channels"][0]["funding_tx_index"] == tx["tx_status"]["tx_index"]
        # node1
        node1_info = self.fiber1.get_client().node_info()
        node2_info = self.fiber2.get_client().node_info()
        nodes = [node1_info["node_id"], node2_info["node_id"]]
        # node2
        assert node1_channels["channels"][0]["node1"] in nodes
        assert node1_channels["channels"][0]["node2"] in nodes
        assert node2_channels["channels"][0]["node1"] in nodes
        assert node2_channels["channels"][0]["node2"] in nodes
        assert node3_channels["channels"][0]["node1"] in nodes
        assert node3_channels["channels"][0]["node2"] in nodes

        # last_updated_timestamp
        # created_timestamp
        # fee_rate_of_node2
        assert (
            node1_channels["channels"][0]["update_info_of_node2"]["fee_rate"]
            == node2_info["tlc_fee_proportional_millionths"]
        )
        assert (
            node2_channels["channels"][0]["update_info_of_node2"]["fee_rate"]
            == node2_info["tlc_fee_proportional_millionths"]
        )
        assert (
            node3_channels["channels"][0]["update_info_of_node2"]["fee_rate"]
            == node2_info["tlc_fee_proportional_millionths"]
        )

        # fee_rate_of_node1
        assert (
            node1_channels["channels"][0]["update_info_of_node1"]["fee_rate"]
            == node1_info["tlc_fee_proportional_millionths"]
        )
        assert (
            node2_channels["channels"][0]["update_info_of_node1"]["fee_rate"]
            == node1_info["tlc_fee_proportional_millionths"]
        )
        assert (
            node3_channels["channels"][0]["update_info_of_node1"]["fee_rate"]
            == node1_info["tlc_fee_proportional_millionths"]
        )

        # capacity (101 CKB = 100 funding + 1 min deposit)
        assert node1_channels["channels"][0]["capacity"] == hex(Amount.ckb(101))
        assert node2_channels["channels"][0]["capacity"] == hex(Amount.ckb(101))
        assert node3_channels["channels"][0]["capacity"] == hex(Amount.ckb(101))

        # chain_hash
        assert node1_channels["channels"][0]["chain_hash"] == node1_info["chain_hash"]
        assert node2_channels["channels"][0]["chain_hash"] == node1_info["chain_hash"]
        assert node3_channels["channels"][0]["chain_hash"] == node1_info["chain_hash"]

        # udt_type_script (CKB channel has None)
        assert node1_channels["channels"][0]["udt_type_script"] is None
        assert node2_channels["channels"][0]["udt_type_script"] is None
        assert node3_channels["channels"][0]["udt_type_script"] is None
