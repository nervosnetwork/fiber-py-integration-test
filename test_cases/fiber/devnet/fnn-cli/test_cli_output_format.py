import json

import yaml
import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliOutputFormat(FiberTest):
    """Test CLI output format options: json, yaml, and raw-data."""

    def test_json_output_is_valid_json(self):
        """--output-format json should produce valid JSON."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        raw = cli.run_raw(["info", "node_info"])
        parsed = json.loads(raw)
        assert "pubkey" in parsed

    def test_yaml_output_is_valid_yaml(self):
        """--output-format yaml should produce valid YAML."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        raw = cli._run(["info", "node_info"], output_format="yaml")
        parsed = yaml.safe_load(raw)
        assert parsed is not None

    def test_raw_data_flag(self):
        """--raw-data should output the raw JSON-RPC response."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        raw = cli._run(["info", "node_info"], raw_data=True)
        parsed = json.loads(raw)
        assert "pubkey" in parsed or "result" in parsed

    def test_json_and_yaml_contain_same_keys(self):
        """JSON and YAML outputs should contain the same top-level keys."""
        cli = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        json_result = cli._run_json(["info", "node_info"])
        yaml_result = cli._run_yaml(["info", "node_info"])

        json_keys = set(json_result.keys()) if isinstance(json_result, dict) else set()
        yaml_keys = set(yaml_result.keys()) if isinstance(yaml_result, dict) else set()
        assert json_keys == yaml_keys
