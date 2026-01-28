"""
Test cases for graph_nodes RPC: add nodes, node info, pagination and config change.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Timeout
from framework.util import generate_account_privakey


class TestGraphNodes(FiberTest):
    """
    Test graph_nodes RPC: add nodes and verify count, node_info fields, pagination, config change.
    """

    def test_add_nodes(self):
        """
        Add a chain of nodes and a branch; verify graph_nodes count and pagination.
        Step 1: Start chain of 10 fibers and connect to fiber1.
        Step 2: Add two more fibers connected to fiber2 and to the chain.
        Step 3: Wait until graph has 15 nodes.
        Step 4: Assert all fibers see 15 nodes and pagination (limit 1, 3, 10, 25, 1000) returns same set.
        """
        # Step 1: Add chain of nodes
        new_fibers = []
        current_fiber = self.start_new_fiber(generate_account_privakey())
        for i in range(10):
            new_fiber = self.start_new_fiber(generate_account_privakey())
            current_fiber.connect_peer(new_fiber)
            new_fibers.append(new_fiber)
            current_fiber = new_fiber
        time.sleep(Timeout.POLL_INTERVAL)
        current_fiber.connect_peer(self.fiber1)

        # Step 2: Add two more fibers
        current_fiber1 = self.start_new_fiber(generate_account_privakey())
        current_fiber1.connect_peer(self.fiber2)
        current_fiber2 = self.start_new_fiber(generate_account_privakey())
        current_fiber2.connect_peer(current_fiber)

        # Step 3: Wait until graph has 15 nodes
        self.wait_graph_nodes(self.fibers[3], 15, time_out=Timeout.SHORT)
        assert len(current_fiber.get_client().graph_nodes()["nodes"]) == 15
        assert len(current_fiber1.get_client().graph_nodes()["nodes"]) == 15
        assert len(current_fiber2.get_client().graph_nodes()["nodes"]) == 15
        assert len(self.fiber1.get_client().graph_nodes()["nodes"]) == 15
        assert len(self.fiber2.get_client().graph_nodes()["nodes"]) == 15

        # Step 4: Assert pagination returns same set for limit 1, 3, 10, 25, 1000
        for fiber in self.fibers:
            graph_nodes = get_graph_nodes(fiber, 3)
            total_graph_nodes = fiber.get_client().graph_nodes()
            assert len(graph_nodes) == len(total_graph_nodes["nodes"])
            assert graph_nodes == total_graph_nodes["nodes"]
            graph_nodes = get_graph_nodes(fiber, 1)
            assert len(graph_nodes) == len(total_graph_nodes["nodes"])
            assert graph_nodes == total_graph_nodes["nodes"]
            graph_nodes = get_graph_nodes(fiber, 10)
            assert len(graph_nodes) == len(total_graph_nodes["nodes"])
            assert graph_nodes == total_graph_nodes["nodes"]
            graph_nodes = get_graph_nodes(fiber, 25)
            assert len(graph_nodes) == len(total_graph_nodes["nodes"])
            assert graph_nodes == total_graph_nodes["nodes"]
            graph_nodes = get_graph_nodes(fiber, 1000)
            assert len(graph_nodes) == len(total_graph_nodes["nodes"])
            assert graph_nodes == total_graph_nodes["nodes"]

    def test_node_info(self):
        """
        Verify graph_nodes entries match node_info for each fiber (addresses, node_id, chain_hash, etc.).
        Step 1: Get graph_nodes and align order with node_info. Step 2: Assert each field matches.
        """
        # Step 1: Get graph_nodes and align order
        graph_nodes = self.fiber1.get_client().graph_nodes()
        node_info = self.fiber1.get_client().node_info()
        if graph_nodes["nodes"][0]["node_id"] != node_info["node_id"]:
            graph_nodes["nodes"].reverse()
        for i in range(len(graph_nodes["nodes"])):
            node = graph_nodes["nodes"][i]
            node_info = self.fibers[i].get_client().node_info()
            # alias
            # assert node['alias'] == node_info['node_name']
            # assert node["alias"] == ""
            # addresses
            assert node["addresses"] == node_info["addresses"]
            # node_id
            assert node["node_id"] == node_info["node_id"]
            # timestamp
            assert int(node["timestamp"], 16) <= int(time.time() * 1000)
            # chain_hash
            assert node["chain_hash"] == node_info["chain_hash"]
            # auto_accept_min_ckb_funding_amount
            assert (
                node["auto_accept_min_ckb_funding_amount"]
                == node_info["open_channel_auto_accept_min_ckb_funding_amount"]
            )
            # udt_cfg_infos
            assert node["udt_cfg_infos"] == node_info["udt_cfg_infos"]

            # features
            assert (
                node["features"] == node_info["features"]
            ), f"node:{node}, node_info:{node_info}"

    def test_change_node_info(self):
        """
        Change node config (fiber_auto_accept_amount), restart, and verify graph_nodes reflects node_info.
        Step 1: Stop fiber1, change config, start. Step 2: Assert graph_nodes matches node_info for all.
        """
        # Step 1: Change config and restart
        before_node_info = self.fiber1.get_client().node_info()
        self.fiber1.stop()
        self.fiber1.prepare({"fiber_auto_accept_amount": "100000001"})
        self.fiber1.start()
        time.sleep(Timeout.POLL_INTERVAL * 3)
        node_info = self.fiber1.get_client().node_info()
        graph_nodes = self.fiber1.get_client().graph_nodes()
        if graph_nodes["nodes"][0]["node_id"] != node_info["node_id"]:
            graph_nodes["nodes"].reverse()
        for i in range(len(graph_nodes["nodes"])):
            node = graph_nodes["nodes"][i]
            node_info = self.fibers[i].get_client().node_info()
            # alias
            # assert node['alias'] == node_info['node_name']
            # addresses
            assert node["addresses"] == node_info["addresses"]
            # node_id
            assert node["node_id"] == node_info["node_id"]
            # timestamp
            assert int(node["timestamp"], 16) <= int(time.time() * 1000)
            # chain_hash
            assert node["chain_hash"] == node_info["chain_hash"]
            # auto_accept_min_ckb_funding_amount
            assert (
                node["auto_accept_min_ckb_funding_amount"]
                == node_info["open_channel_auto_accept_min_ckb_funding_amount"]
            )
            # udt_cfg_infos
            assert node["udt_cfg_infos"] == node_info["udt_cfg_infos"]
        # check other nodes
        graph_nodes = self.fiber2.get_client().graph_nodes()
        node_info = self.fiber1.get_client().node_info()
        if graph_nodes["nodes"][0]["node_id"] != node_info["node_id"]:
            graph_nodes["nodes"].reverse()
        for i in range(len(graph_nodes["nodes"])):
            node = graph_nodes["nodes"][i]
            node_info = self.fibers[i].get_client().node_info()
            # addresses
            assert node["addresses"] == node_info["addresses"]
            # node_id
            assert node["node_id"] == node_info["node_id"]
            # timestamp
            assert int(node["timestamp"], 16) <= int(time.time() * 1000)
            # chain_hash
            assert node["chain_hash"] == node_info["chain_hash"]
            # auto_accept_min_ckb_funding_amount
            assert (
                node["auto_accept_min_ckb_funding_amount"]
                == node_info["open_channel_auto_accept_min_ckb_funding_amount"]
            )
            # udt_cfg_infos
            assert node["udt_cfg_infos"] == node_info["udt_cfg_infos"]

    def wait_graph_nodes(self, fiber, number, time_out=Timeout.SHORT):
        """Wait until graph_nodes has exactly `number` nodes or timeout."""
        start_time = time.time()
        while True:
            graph_nodes = fiber.get_client().graph_nodes()
            if len(graph_nodes["nodes"]) == number:
                return
            time.sleep(Timeout.POLL_INTERVAL)
            if time.time() - start_time > time_out:
                raise Exception("wait graph nodes timeout")


def get_graph_nodes(fiber, page_size):
    """Fetch all graph_nodes via pagination (limit=page_size, after cursor). Returns list of nodes."""
    after = None
    graph_nodes_ret = []
    while True:
        graph_nodes = fiber.get_client().graph_nodes(
            {"limit": hex(page_size), "after": after}
        )
        if len(graph_nodes["nodes"]) == 0:
            return graph_nodes_ret
        assert len(graph_nodes["nodes"]) <= page_size
        graph_nodes_ret.extend(graph_nodes["nodes"])
        after = graph_nodes["last_cursor"]
