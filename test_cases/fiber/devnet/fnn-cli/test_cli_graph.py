import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliGraph(FiberTest):
    """Test graph query commands via fnn-cli."""

    def test_graph_nodes(self):
        """After opening a channel, graph should contain at least 2 nodes."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        time.sleep(3)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        nodes = cli1.graph_nodes()

        assert "nodes" in nodes
        assert len(nodes["nodes"]) >= 2

        rpc_nodes = self.fiber1.get_client().graph_nodes({})
        assert len(nodes["nodes"]) == len(rpc_nodes["nodes"])

    def test_graph_channels_after_open(self):
        """After opening a channel, graph should show it."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.graph_channels()

        assert "channels" in channels
        assert len(channels["channels"]) >= 1

    def test_graph_channels_cli_vs_rpc(self):
        """CLI and RPC graph_channels should return consistent data."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_channels = cli1.graph_channels()
        rpc_channels = self.fiber1.get_client().graph_channels({})

        assert len(cli_channels["channels"]) == len(rpc_channels["channels"])
        for i in range(len(cli_channels["channels"])):
            assert (
                cli_channels["channels"][i]["channel_outpoint"]
                == rpc_channels["channels"][i]["channel_outpoint"]
            )
            assert (
                cli_channels["channels"][i]["capacity"]
                == rpc_channels["channels"][i]["capacity"]
            )

    def test_graph_nodes_with_limit(self):
        """Test the limit parameter for graph_nodes."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        nodes = cli1.graph_nodes(limit=1)
        assert "nodes" in nodes
        assert len(nodes["nodes"]) <= 1

    def test_graph_nodes_pagination(self):
        """Test pagination for graph_nodes."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        page1 = cli1.graph_nodes(limit=1)
        assert len(page1["nodes"]) == 1

        if "last_cursor" in page1 and page1["last_cursor"]:
            page2 = cli1.graph_nodes(limit=1, after=page1["last_cursor"])
            assert "nodes" in page2
            if len(page2["nodes"]) > 0:
                assert page2["nodes"][0] != page1["nodes"][0]

    # ── graph_channels pagination ──────────────────────────────────

    def test_graph_channels_with_limit(self):
        """Test the limit parameter for graph_channels."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        channels = cli1.graph_channels(limit=1)
        assert "channels" in channels
        assert len(channels["channels"]) <= 1

    def test_graph_channels_pagination(self):
        """Test pagination for graph_channels via CLI."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        page1 = cli1.graph_channels(limit=1)
        assert len(page1["channels"]) >= 1

        if "last_cursor" in page1 and page1["last_cursor"]:
            page2 = cli1.graph_channels(limit=1, after=page1["last_cursor"])
            assert "channels" in page2

    def test_graph_channels_limit_greater_than_total(self):
        """Limit > total channels should return all channels."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.wait_graph_channels_sync(self.fiber1, 1)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        all_channels = cli1.graph_channels()
        limited = cli1.graph_channels(limit=100)

        assert len(limited["channels"]) == len(all_channels["channels"])
