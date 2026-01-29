"""
Test CKB contract deployment for Fiber.
Deploys xudt, auth, commitment-lock, funding-lock contracts.
"""
import pytest

from framework.basic import CkbTest
from test_cases.soft_fork.test_sync_again_with_other_node_when_sync_failed_tx import (
    tar_file,
)


class TestDeploy(CkbTest):
    """
    Test CKB contract deployment for Fiber network.
    Deploys xudt, auth, commitment-lock, funding-lock contracts to CKB devnet.
    """

    @pytest.mark.skip("deploy")
    def test_deploy(self):
        """
        Deploy Fiber contracts (xudt, auth, commitment-lock, funding-lock) to CKB.
        Step 1: Initialize CKB node and start.
        Step 2: Deploy xudt contract and get code hash.
        Step 3: Deploy auth contract and get code hash.
        Step 4: Deploy commitment-lock and funding-lock contracts.
        Step 5: Print deployed contract hashes for configuration.
        """
        # Step 1: Initialize CKB node and start
        self.node = self.CkbNode.init_dev_by_port(
            self.CkbNodeConfigPath.CURRENT_TEST, f"cluster/hardfork/node0", 8114, 8225
        )
        self.node.prepare()
        self.node.start()
        self.Miner.make_tip_height_number(self.node, 1100)

        # Step 2: Deploy xudt contract and get code hash
        xudt_tx_hash = self.Contract.deploy_ckb_contract(
            self.Config.MINER_PRIVATE_1,
            "/Users/guopenglin/PycharmProjects/ckb-py-integration-test/source/contract/fiber/xudt",
            2000,
            True,
            self.node.rpcUrl,
        )
        xudt_code_hash = self.Contract.get_ckb_contract_codehash(
            xudt_tx_hash, 0, True, self.node.rpcUrl
        )
        self.Miner.miner_until_tx_committed(self.node, xudt_tx_hash)

        # Step 3: Deploy auth contract and get code hash
        auth_tx_hash = self.Contract.deploy_ckb_contract(
            self.Config.MINER_PRIVATE_1,
            "/Users/guopenglin/PycharmProjects/ckb-py-integration-test/source/contract/fiber/auth",
            2000,
            True,
            self.node.rpcUrl,
        )
        auth_code_hash = self.Contract.get_ckb_contract_codehash(
            auth_tx_hash, 0, True, self.node.rpcUrl
        )
        self.Miner.miner_until_tx_committed(self.node, auth_tx_hash)

        # Step 4: Deploy commitment-lock and funding-lock contracts
        commitment_lock_tx_hash = self.Contract.deploy_ckb_contract(
            self.Config.MINER_PRIVATE_1,
            "/Users/guopenglin/PycharmProjects/ckb-py-integration-test/source/contract/fiber/commitment-lock",
            2000,
            True,
            self.node.rpcUrl,
        )
        commitment_lock__code_hash = self.Contract.get_ckb_contract_codehash(
            commitment_lock_tx_hash, 0, True, self.node.rpcUrl
        )
        self.Miner.miner_until_tx_committed(self.node, commitment_lock_tx_hash)

        funding_lock_tx_hash = self.Contract.deploy_ckb_contract(
            self.Config.MINER_PRIVATE_1,
            "/Users/guopenglin/PycharmProjects/ckb-py-integration-test/source/contract/fiber/funding-lock",
            2000,
            True,
            self.node.rpcUrl,
        )
        funding_lock_code_hash = self.Contract.get_ckb_contract_codehash(
            funding_lock_tx_hash, 0, True, self.node.rpcUrl
        )
        self.Miner.miner_until_tx_committed(self.node, funding_lock_tx_hash)

        # Step 5: Print deployed contract hashes for configuration
        print("xudt_code_hash:", xudt_code_hash)
        print("xudt_tx_hash:", xudt_tx_hash)
        print("auth_code_hash:", auth_code_hash)
        print("auth_tx_hash:", auth_tx_hash)
        print("commitment_lock_code_hash:", commitment_lock__code_hash)
        print("commitment_lock_tx_hash:", commitment_lock_tx_hash)
        print("funding_lock_code_hash:", funding_lock_code_hash)
        print("funding_lock_tx_hash:", funding_lock_tx_hash)

    def test_00000(self):
        """
        Placeholder test: verify CKB node is running.
        Step 1: Initialize CKB node.
        Step 2: Get tip block number to verify node is responsive.
        """
        # Step 1: Initialize CKB node
        self.node = self.CkbNode.init_dev_by_port(
            self.CkbNodeConfigPath.CURRENT_TEST, f"cluster/hardfork/node0", 8114, 8225
        )
        # Step 2: Get tip block number to verify node is responsive
        self.node.getClient().get_tip_block_number()
