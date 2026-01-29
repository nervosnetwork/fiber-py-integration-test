"""
Test cases for shutdown_channel RPC close_script parameter.
Covers: secp256k1_blake160_sighash_all, non-secp close_script, CKB/UDT long/short args, insufficient capacity.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState


class TestCloseScript(FiberTest):
    """
    Test shutdown_channel close_script: secp256k1_blake160_sighash_all, other code_hash,
    CKB/UDT long/short args, and insufficient capacity error.
    """

    def test_secp256k1_blake160_sighash_all(self):
        """
        shutdown_channel with secp256k1_blake160_sighash_all close_script; channel closes, balance returned.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with account close_script and fee_rate.
        Step 3: Wait close tx committed; assert balance returned.
        """
        # Step 1: Open channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        # Step 2: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": "0x3FC",
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        # Step 3: Assert balance returned
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)

    def test_not_secp256k1_blake160_sighash_all(self):
        """
        shutdown_channel with non-secp close_script; channel closes, balance returned.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with other code_hash close_script; wait CLOSED.
        Step 3: Assert channel_count 0 and balance returned.
        """
        # Step 1: Open channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        # Step 2: Shutdown with non-secp close_script
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.account1["lock_arg"],
                },
                "fee_rate": "0x3FC",
            }
        )

        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CLOSED, timeout=Timeout.CHANNEL_READY, include_closed=True
        )
        self.assert_channel_count(self.fiber1, 0)
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        assert after_balance2 - before_balance2 == Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)

    def test_ckb_arg_change_long_not_enough(self):
        """
        shutdown_channel with long close_script args (not enough capacity) should fail with fee error.
        Step 1: Open channel, wait CHANNEL_READY, get channel_id.
        Step 2: Call shutdown_channel with long random args; assert error.
        """
        # Step 1: Open channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        # Step 2: Call shutdown_channel with long args; expect fee error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": channel_id,
                    "close_script": {
                        "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": self.generate_random_str(400),
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

    def test_ckb_arg_change_long_enough(self):
        """
        shutdown_channel with long close_script args (enough capacity); channel closes, balance to new args.
        Step 1: Open channel with long args, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with same close_script; wait close tx committed.
        Step 3: Assert balance returned and capacity to new args script.
        """
        new_arg = self.generate_random_str(100)
        # Step 1: Open channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        # Step 2: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": new_arg,
                },
                "fee_rate": "0x3FC",
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        time.sleep(5)
        # Step 3: Assert balance returned and capacity to new args script
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
        shutdown_channel with short close_script args (shutdown_script set at open); balance to script.
        Step 1: Open channel with shutdown_script short args, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with same close_script; wait close tx committed.
        Step 3: Assert capacity to close_script script increased by at least 1650 CKB.
        """
        new_arg = "0x1222"
        # Step 1: Open channel with shutdown_script and wait ready
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
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
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
        # Step 2: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
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

        # Step 3: Assert capacity to close_script script
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
        """
        shutdown_channel UDT channel with short close_script args; balance to script.
        Step 1: Open UDT channel with shutdown_script, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with close_script; wait close tx committed.
        Step 3: Assert capacity to close_script script increased.
        """
        new_arg = "0x1222"
        # Step 1: Open UDT channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(1000))
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
        # Step 2: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
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
        # Step 3: Assert capacity to close_script script
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
            >= Amount.ckb(622)
        )

    @pytest.mark.skip("Scenario does not exist")
    def test_arg_udt_change_long_enough_ckb(self):
        pass

    def test_arg_udt_change_long_not_enough_ckb(self):
        """
        shutdown_channel UDT channel with long close_script args (not enough CKB for fee) should fail.
        Step 1: Open UDT channel with shutdown_script, wait CHANNEL_READY, get channel_id.
        Step 2: Call shutdown_channel with long args; assert fee error.
        """
        new_arg = self.generate_random_str(1002)
        # Step 1: Open UDT channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(1000))
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
        # Step 2: Call shutdown_channel with long args; expect fee error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": channel_id,
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
        """
        shutdown_channel UDT channel with short close_script args (different from shutdown_script); balance to script.
        Step 1: Open UDT channel with shutdown_script long args, wait CHANNEL_READY, get channel_id.
        Step 2: Shutdown with short close_script args; wait close tx committed.
        Step 3: Assert capacity to close_script script increased.
        """
        new_arg = self.generate_random_str(100)
        # Step 1: Open UDT channel and wait ready
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "shutdown_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.generate_random_str(1000),
                },
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber1.get_peer_id(), ChannelState.CHANNEL_READY, timeout=Timeout.CHANNEL_READY
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(1000))
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
        # Step 2: Shutdown channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
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

        # Step 3: Assert capacity to close_script script
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
            >= Amount.ckb(622)
        )
