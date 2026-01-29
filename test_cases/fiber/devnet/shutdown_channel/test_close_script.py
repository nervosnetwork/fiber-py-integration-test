"""
Test cases for shutdown_channel close_script parameter.
Covers secp256k1_blake160_sighash_all, non-standard scripts, and CKB/UDT arg variants.
"""
import time
import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestCloseScript(FiberTest):
    """
    Test shutdown_channel close_script: secp256k1, non-standard scripts, CKB/UDT args.
    """

    def test_secp256k1_blake160_sighash_all(self):
        """
        shutdown_channel with secp256k1_blake160_sighash_all close_script succeeds.
        Step 1: Open channel and wait for CHANNEL_READY.
        Step 2: Shutdown with standard secp256k1 close_script.
        Step 3: Assert balance returned correctly.
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

        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().graph_channels()

        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 2: Shutdown with standard secp256k1 close_script
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # Step 3: Assert balance returned correctly
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)

    def test_not_secp256k1_blake160_sighash_all(self):
        """
        shutdown_channel with non-secp256k1 close_script succeeds.
        Step 1: Open channel and wait for CHANNEL_READY.
        Step 2: Shutdown with different code_hash close_script.
        Step 3: Assert channel closed and balance returned.
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

        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().graph_channels()

        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 2: Shutdown with non-secp256k1 close_script
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )

        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.CHANNEL_READY,
            include_closed=True,
        )

        # Step 3: Assert channel closed and balance returned
        node_info = self.fiber1.get_client().node_info()
        assert node_info["channel_count"] == "0x0"
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)

    def test_ckb_arg_change_long_not_enough(self):
        """
        shutdown_channel with long args (400 chars) that cause insufficient capacity fails.
        Step 1: Open channel and wait for CHANNEL_READY.
        Step 2: Shutdown with close_script args=400 chars.
        Step 3: Assert Local balance is not enough error.
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

        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().graph_channels()

        # Step 2: Shutdown with long args (insufficient capacity)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": channel_id,
                    "close_script": {
                        "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": self.generate_random_str(400),
                    },
                    "fee_rate": hex(FeeRate.MEDIUM),
                }
            )

        # Step 3: Assert Local balance is not enough error
        assert "Local balance is not enough to pay the fee, expect fee" in exc_info.value.args[0]

    def test_ckb_arg_change_long_enough(self):
        """
        shutdown_channel with long args (100 chars) and sufficient capacity succeeds.
        Step 1: Open channel. Step 2: Shutdown. Step 3: Assert balance returned.
        """
        new_arg = self.generate_random_str(100)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().graph_channels()

        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"], self.node.getClient().url
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"], self.node.getClient().url
        )
        before_account_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        time.sleep(5)
        after_account_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"], self.node.getClient().url
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"], self.node.getClient().url
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
        assert (
            int(after_account_balance1["capacity"], 16)
            - int(before_account_balance1["capacity"], 16)
            >= Amount.ckb(199)
        )

    def test_ckb_arg_change_short(self):
        """
        shutdown_channel with short args (0x1222) succeeds.
        Step 1: Open channel with shutdown_script. Step 2: Shutdown. Step 3: Assert balance.
        """
        new_arg = "0x1222"
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1651)),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(
            Amount.ckb(1651) - DEFAULT_MIN_DEPOSIT_CKB
        )
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        before_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        after_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        assert (
            int(after_balance1["capacity"], 16) - int(before_balance1["capacity"], 16)
            >= Amount.ckb(1650)
        )

    def test_arg_udt_change_short(self):
        new_arg = "0x1222"
        temporary_channel_id = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(1000 * 100000000)
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        N1N2_CHANNEL_ID = channels["channels"][0]["channel_id"]
        before_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        # shut down
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": N1N2_CHANNEL_ID,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "fee_rate": "0x3FC",
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        after_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        print("before_balance1:", before_balance1)
        print("after_balance1:", after_balance1)
        assert (
            int(after_balance1["capacity"], 16) - int(before_balance1["capacity"], 16)
            >= 622 * 100000000
        )

    @pytest.mark.skip("不存在")
    def test_arg_udt_change_long_enough_ckb(self):
        pass

    def test_arg_udt_change_long_not_enough_ckb(self):
        new_arg = self.generate_random_str(1002)
        temporary_channel_id = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(1000 * 100000000)
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        N1N2_CHANNEL_ID = channels["channels"][0]["channel_id"]
        before_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        # shut down
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": N1N2_CHANNEL_ID,
                    "close_script": {
                        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": new_arg,
                    },
                    "fee_rate": "0x3FC",
                }
            )
        expected_error_message = (
            "Local balance is not enough to pay the fee, expect fee"
        )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_arg_udt_change_short(self):
        new_arg = self.generate_random_str(100)
        temporary_channel_id = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), "CHANNEL_READY", 120
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(1000 * 100000000)
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        N1N2_CHANNEL_ID = channels["channels"][0]["channel_id"]
        before_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        # shut down
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": N1N2_CHANNEL_ID,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "fee_rate": "0x3FC",
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        after_balance1 = self.node.getClient().get_cells_capacity(
            {
                "script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "script_type": "lock",
                "script_search_mode": "prefix",
            }
        )
        print("before_balance1:", before_balance1)
        print("after_balance1:", after_balance1)
        assert (
            int(after_balance1["capacity"], 16) - int(before_balance1["capacity"], 16)
            >= 622 * 100000000
        )
