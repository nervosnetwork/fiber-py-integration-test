import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliInfo(FiberTest):
    """Verify that `fnn-cli info node_info` returns the same data as the RPC."""

    def test_node_info_json(self):
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli_result = cli.node_info()
        rpc_result = self.fiber1.get_client().node_info()

        assert cli_result["pubkey"] == rpc_result["pubkey"]
        assert cli_result["addresses"] == rpc_result["addresses"]
        assert cli_result["chain_hash"] == rpc_result["chain_hash"]
        assert cli_result["commit_hash"] == rpc_result["commit_hash"]

    def test_node_info_yaml_output(self):
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        yaml_result = cli.run_yaml(["info", "node_info"])
        assert yaml_result is not None
        assert "pubkey" in yaml_result

    def test_node_info_both_nodes(self):
        """Both fiber1 and fiber2 should return distinct pubkeys via CLI."""
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        cli2 = FnnCli(f"http://127.0.0.1:{self.fiber2.rpc_port}")

        info1 = cli1.node_info()
        info2 = cli2.node_info()
        assert info1["pubkey"] != info2["pubkey"]

    def test_node_info_wrong_url(self):
        """Connecting to a non-existent endpoint should raise an error."""
        cli = FnnCli("http://127.0.0.1:19999")
        with pytest.raises(Exception):
            cli.node_info()
