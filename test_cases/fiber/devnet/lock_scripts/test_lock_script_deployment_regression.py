import time

import yaml

from framework.basic_fiber import COMMIT_LOCK_CODE_HASH, FiberTest


class TestFiberLockScriptDeploymentRegression(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def _configured_scripts(self):
        with open(self.fiber1.fiber_config_path, encoding="utf-8") as config_file:
            config = yaml.load(config_file, Loader=yaml.BaseLoader)
        return {script["name"]: script for script in config["fiber"]["scripts"]}

    def _assert_type_id_cell_is_live(self, type_id_script, script_name):
        cells = self.node.getClient().get_cells(
            {
                "script": type_id_script,
                "script_type": "type",
                "script_search_mode": "exact",
            },
            "asc",
            "0x1",
            None,
        )["objects"]
        assert len(cells) == 1, f"{script_name} type-id cell should be live"

    def _assert_cell_dep_is_live(self, cell_dep, script_name):
        out_point = cell_dep["out_point"]
        cell = self.node.getClient().get_live_cell(
            out_point["index"], out_point["tx_hash"]
        )
        assert cell["status"] == "live", f"{script_name} cell dep should be live"

    def test_lock_script_deployment_cells_are_available_to_fiber(self):
        scripts = self._configured_scripts()

        for script_name in ["FundingLock", "CommitmentLock"]:
            assert script_name in scripts
            configured = scripts[script_name]
            assert configured["script"]["hash_type"] == "type"
            assert configured["script"]["args"] == "0x"

            type_id_dep, auth_dep = configured["cell_deps"]
            self._assert_type_id_cell_is_live(type_id_dep["type_id"], script_name)
            self._assert_cell_dep_is_live(auth_dep["cell_dep"], script_name)

    def test_lock_scripts_back_channel_force_settlement_flow(self):
        scripts = self._configured_scripts()

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(200 * 100000000),
                "public": True,
                "commitment_delay_epoch": "0x6",
                "tlc_expiry_delta": hex(86400000),
            }
        )
        funding_tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, funding_tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "ChannelReady", 120
        )

        funding_cell = self.node.getClient().get_live_cell("0x0", funding_tx_hash)
        assert funding_cell["status"] == "live"
        assert (
            funding_cell["cell"]["output"]["lock"]["code_hash"]
            == scripts["FundingLock"]["script"]["code_hash"]
        )

        channel_id = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "force": True,
            }
        )
        force_shutdown_tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, force_shutdown_tx_hash)

        force_shutdown_tx = self.node.getClient().get_transaction(
            force_shutdown_tx_hash
        )
        assert any(
            output["lock"]["code_hash"] == COMMIT_LOCK_CODE_HASH
            for output in force_shutdown_tx["transaction"]["outputs"]
        )
        assert len(self.get_commit_cells()) > 0

        self.node.getClient().generate_epochs("0x6", 0)
        for _ in range(180):
            if len(self.get_commit_cells()) == 0:
                return
            time.sleep(1)

        assert False, "commitment lock cells should be settled after delay epoch"
