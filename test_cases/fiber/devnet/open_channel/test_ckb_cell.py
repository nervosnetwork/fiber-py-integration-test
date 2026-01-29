"""
Test open_channel with CKB cell constraints: capacity, multi-cell, config.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, PaymentStatus, Timeout


class TestCkbCell(FiberTest):
    """
    Test open_channel when account has single/multiple CKB cells and capacity vs funding_amount.
    """

    @pytest.mark.skip("todo")
    def test_account_cell_data_not_empty(self):
        """
        When account cell data is not empty, open_channel behavior (todo: implement).
        Step 1: (Not implemented.)
        """

    def test_account_cell_gt_funding_amount_10ckb(self):
        """
        When cell capacity minus funding_amount equals 10 CKB, open channel stays in NEGOTIATING_FUNDING.
        Step 1: Open channel from fiber2 to fiber1 with funding_amount = capacity - 10 CKB.
        Step 2: Wait for NEGOTIATING_FUNDING.
        """
        capacity = self.Ckb_cli.wallet_get_capacity(self.account2["address"]["testnet"])
        # Step 1: Open channel with funding_amount = capacity - 10 CKB
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(int(capacity) - 10)),
                "public": True,
            }
        )
        # Step 2: Wait for NEGOTIATING_FUNDING
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.NEGOTIATING_FUNDING,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_account_mutil_cell_gt_funding_amount(self):
        """
        When account has multiple cells and total balance > funding_amount, channel opens successfully.
        Step 1: Create account3 with two 1000 CKB transfers, start new fiber.
        Step 2: Open channel with funding_amount 990 CKB, wait for CHANNEL_READY.
        Step 3: Assert graph_channels shows one channel with expected capacity.
        """
        account3_private_key = (
            "0x100c06bfd800d27397002dca6fb0993d5ba6399b4238b2f29ee9deb97593d2b1"
        )
        account3 = self.Ckb_cli.util_key_info_by_private_key(account3_private_key)
        tx_hash = self.Ckb_cli.wallet_transfer_by_private_key(
            self.Config.ACCOUNT_PRIVATE_1,
            account3["address"]["testnet"],
            1000,
            self.node.rpcUrl,
        )
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        tx_hash = self.Ckb_cli.wallet_transfer_by_private_key(
            self.Config.ACCOUNT_PRIVATE_1,
            account3["address"]["testnet"],
            1000,
            self.node.rpcUrl,
        )
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        # Step 1: Start fiber3 and connect
        new_fiber = self.start_new_fiber(
            account3_private_key,
            {"ckb_rpc_url": self.node.rpcUrl},
        )
        new_fiber.connect_peer(self.fiber2)
        time.sleep(1)
        # Step 2: Open channel with funding_amount 990 CKB, wait for CHANNEL_READY
        new_fiber.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(990)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            new_fiber.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        # Step 3: Assert graph_channels shows one channel with expected capacity
        channels = new_fiber.get_client().graph_channels()
        assert len(channels["channels"]) == 1
        assert channels["channels"][0]["capacity"] == hex(
            Amount.ckb(990) - DEFAULT_MIN_DEPOSIT_CKB
        )

    def test_account_mutil_cell_gt_funding_amount_2(self):
        """
        Same as test_account_mutil_cell_gt_funding_amount but start_new_fiber without extra config.
        Step 1: Create account3 with two 1000 CKB transfers, start new fiber.
        Step 2: Open channel 990 CKB, wait for CHANNEL_READY.
        Step 3: Assert graph_channels capacity.
        """
        account3_private_key = (
            "0x100c06bfd800d27397002dca6fb0993d5ba6399b4238b2f29ee9deb97593d2b1"
        )
        account3 = self.Ckb_cli.util_key_info_by_private_key(account3_private_key)
        tx_hash = self.Ckb_cli.wallet_transfer_by_private_key(
            self.Config.ACCOUNT_PRIVATE_1,
            account3["address"]["testnet"],
            1000,
            self.node.rpcUrl,
        )
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        tx_hash = self.Ckb_cli.wallet_transfer_by_private_key(
            self.Config.ACCOUNT_PRIVATE_1,
            account3["address"]["testnet"],
            1000,
            self.node.rpcUrl,
        )
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        new_fiber = self.start_new_fiber(account3_private_key)
        new_fiber.connect_peer(self.fiber2)
        time.sleep(1)
        new_fiber.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(990)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            new_fiber.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = new_fiber.get_client().graph_channels()
        assert len(channels["channels"]) == 1
        assert channels["channels"][0]["capacity"] == hex(
            Amount.ckb(990) - DEFAULT_MIN_DEPOSIT_CKB
        )

    def test_config_not_eq(self):
        """
        When fiber3 is started with different ckb_rpc_url config, graph_nodes count matches after payment.
        Step 1: Start fiber3 with custom ckb_rpc_url, open channel fiber2->fiber3.
        Step 2: Send payment fiber2->fiber3, then fiber3->fiber2.
        Step 3: Assert graph_nodes from fiber2 and fiber3 have same length.
        """
        account3_private_key = self.generate_account(1000)
        new_fiber = self.start_new_fiber(
            account3_private_key,
            {"ckb_rpc_url": self.node.rpcUrl},
        )
        new_fiber.connect_peer(self.fiber2)
        time.sleep(1)
        self.fiber2.get_client().open_channel(
            {
                "peer_id": new_fiber.get_peer_id(),
                "funding_amount": hex(Amount.ckb(990)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            new_fiber.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = new_fiber.get_client().graph_channels()
        assert len(channels["channels"]) == 1
        assert channels["channels"][0]["capacity"] == hex(
            Amount.ckb(990) - DEFAULT_MIN_DEPOSIT_CKB
        )
        node3_info = new_fiber.get_client().node_info()
        fiber3_pub = node3_info["node_id"]
        payment = self.fiber2.get_client().send_payment(
            {
                "target_pubkey": fiber3_pub,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber2,
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            Timeout.CHANNEL_READY,
        )
        self.send_payment(new_fiber, self.fiber2, Amount.ckb(1))
        nodes = self.fiber2.get_client().graph_nodes({})
        new_nodes = new_fiber.get_client().graph_nodes({})
        assert len(nodes["nodes"]) == len(new_nodes["nodes"])

    def test_config_eq(self):
        """
        Default config: open channel fiber2->fiber3, send payment, wait for success.
        Step 1: Start fiber3, open channel fiber2->fiber3, wait CHANNEL_READY.
        Step 2: Send keysend payment fiber2->fiber3, wait payment success.
        """
        account3_private_key = self.generate_account(1000)
        new_fiber = self.start_new_fiber(account3_private_key)
        new_fiber.connect_peer(self.fiber2)
        time.sleep(1)
        self.fiber2.get_client().open_channel(
            {
                "peer_id": new_fiber.get_peer_id(),
                "funding_amount": hex(Amount.ckb(990)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            new_fiber.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = new_fiber.get_client().graph_channels()
        assert len(channels["channels"]) == 1
        assert channels["channels"][0]["capacity"] == hex(
            Amount.ckb(990) - DEFAULT_MIN_DEPOSIT_CKB
        )
        node3_info = new_fiber.get_client().node_info()
        fiber3_pub = node3_info["node_id"]
        payment = self.fiber2.get_client().send_payment(
            {
                "target_pubkey": fiber3_pub,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber2,
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            Timeout.CHANNEL_READY,
        )

    @pytest.mark.skip
    def test_open_chanel_same_time(self):
        """
        Open multiple channels at the same time (todo: add check for failed channel terminal state).
        Step 1: (Skipped.)
        """
        pass
