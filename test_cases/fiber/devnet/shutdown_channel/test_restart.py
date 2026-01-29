"""
Test cases for shutdown_channel with node restart scenarios.
Covers: initiator/acceptor restart during shutdown, CKB node restart, balance return after close.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestRestart(FiberTest):
    """
    Test shutdown_channel when Fiber nodes or CKB node restart during/after shutdown.
    Verifies channel closes and balance is returned correctly.
    """

    def test_restart_fiber_node_shutdown_channel(self):
        """
        Restart both Fiber nodes during shutdown; channel should close and balance return.
        Step 1: Open channel, wait CHANNEL_READY, record balances, start shutdown.
        Step 2: Stop acceptor (fiber2), then initiator (fiber1); restart fiber1 then fiber2.
        Step 3: Assert channel is closed and acceptor balance increased by min deposit (CKB).
        """
        # Step 1: Open channel, wait CHANNEL_READY, record balances, start shutdown
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        open_channel_tx_hash = self.wait_and_check_tx_pool_fee(
            FeeRate.DEFAULT, False
        )
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

        cell = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert cell["status"] == "live", "Funding cell should be live before shutdown"

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "live", "Cell still live before restart"

        # Step 2: Stop acceptor then initiator; restart initiator then acceptor
        self.fiber2.stop()
        time.sleep(10)
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown", "Cell should be unknown after acceptor stop"

        self.fiber1.stop()
        time.sleep(10)
        self.fiber1.start()
        time.sleep(10)
        self.fiber2.start()
        time.sleep(10)

        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown", "Cell should remain unknown after restarts"

        # Step 3: Assert channel closed and balance returned
        node_info = self.fiber1.get_client().node_info()
        assert node_info["channel_count"] == "0x0", "Channel count should be zero after close"

        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        expected_delta_ckb = Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
        assert after_balance2 - before_balance2 == expected_delta_ckb, (
            f"Acceptor balance should increase by min deposit; "
            f"before={before_balance2}, after={after_balance2}, expected_delta={expected_delta_ckb}"
        )

    def test_force_restart_fiber_node_shutdown_channel(self):
        """
        Force restart both Fiber nodes during shutdown; channel should close and balance return.
        Step 1: Open channel, wait CHANNEL_READY, start shutdown.
        Step 2: Force stop acceptor then initiator; restart initiator then acceptor.
        Step 3: Assert channel closed and acceptor balance increased by min deposit (CKB).
        """
        # Step 1: Open channel and start shutdown
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        open_channel_tx_hash = self.wait_and_check_tx_pool_fee(
            FeeRate.DEFAULT, False
        )
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

        cell = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert cell["status"] == "live", "Funding cell should be live before shutdown"

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "live", "Cell still live before restart"

        # Step 2: Force stop acceptor then initiator; restart both
        self.fiber2.force_stop()
        time.sleep(10)
        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown", "Cell should be unknown after acceptor force stop"

        self.fiber1.force_stop()
        time.sleep(10)
        self.fiber1.start()
        time.sleep(10)
        self.fiber2.start()
        time.sleep(10)

        result = self.node.getClient().get_live_cell("0x0", open_channel_tx_hash)
        assert result["status"] == "unknown", "Cell should remain unknown after restarts"

        # Step 3: Assert channel closed and balance returned
        node_info = self.fiber1.get_client().node_info()
        assert node_info["channel_count"] == "0x0", "Channel count should be zero after close"

        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        expected_delta_ckb = Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
        assert after_balance2 - before_balance2 == expected_delta_ckb, (
            f"Acceptor balance should increase by min deposit; "
            f"before={before_balance2}, after={after_balance2}, expected_delta={expected_delta_ckb}"
        )

    @pytest.mark.skip(reason="https://github.com/nervosnetwork/fiber/issues/938")
    def test_stop_ckb_node_shutdown_channel(self):
        """CKB node stopped during shutdown; after CKB restart, channel should reach CLOSED."""
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(0),
        )
        self.node.stop()
        channel_id = self.fiber1.get_client().list_channels({})["channels"][0]["channel_id"]
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(5)
        self.node.start()
        self.node.start_miner()
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=30,
            include_closed=True,
        )

    def test_restart_ckb_node_shutdown_channel(self):
        """
        CKB node restarts after shutdown; channel should close and balance return.
        Step 1: Open channel, shutdown, then stop and start CKB node.
        Step 2: Wait for close tx; assert channel count zero.
        Step 3: Assert acceptor balance increased by min deposit (CKB).
        """
        # Step 1: Open channel and shutdown
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": False,
            }
        )
        time.sleep(1)
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

        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(1)

        self.node.stop()
        time.sleep(10)
        self.node.start()
        self.node.start_miner()
        time.sleep(10)
        time.sleep(20)

        # Step 2: Assert channel closed
        node_info = self.fiber1.get_client().node_info()
        assert node_info["channel_count"] == "0x0", "Channel count should be zero after close"

        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 3: Assert balance returned
        expected_delta_ckb = Amount.to_ckb(DEFAULT_MIN_DEPOSIT_CKB)
        assert after_balance2 - before_balance2 == expected_delta_ckb, (
            f"Acceptor balance should increase by min deposit; "
            f"before={before_balance2}, after={after_balance2}, expected_delta={expected_delta_ckb}"
        )

    def test_restart_ckb_node_shutdown_channel2(self):
        """
        CKB node restarts after shutdown with non-zero peer balance; then force shutdown.
        Step 1: Open channel (fiber1 1000 CKB, fiber2 1 CKB), stop CKB, shutdown channel.
        Step 2: Start CKB and miner; list channels on both sides.
        Step 3: Force shutdown from fiber1 and verify no exception.
        """
        self.open_channel(
            self.fiber1,
            self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        self.node.stop()
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.account1_private_key),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(10)
        self.node.start()
        self.node.start_miner()
        time.sleep(10)

        node1_list_channels = self.fiber1.get_client().list_channels({})
        node2_list_channels = self.fiber2.get_client().list_channels({})

        self.fiber1.get_client().shutdown_channel(
            {"channel_id": channel_id, "force": True}
        )
