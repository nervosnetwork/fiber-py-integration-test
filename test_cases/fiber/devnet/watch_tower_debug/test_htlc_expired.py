"""
Test watch tower behavior when HTLCs expire.
When TLCs expire, watch tower should automatically trigger force shutdown.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate, Timeout
from framework.test_fiber import FiberConfigPath


class TestHtlcExpired(FiberTest):
    """
    Test that expired TLCs trigger automatic force shutdown via watch tower.
    Covers both CHANNEL_READY and SHUTTING_DOWN states when TLCs expire.
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}
    fiber_version = FiberConfigPath.CURRENT_DEV_DEBUG

    def test_ready_status(self):
        """
        When channel is in CHANNEL_READY state and TLCs expire, watch tower should auto force shutdown.
        Step 1: Start fiber3 and open channels fiber1-fiber2 and fiber2-fiber3.
        Step 2: Record balances before adding TLCs.
        Step 3: Add TLCs to both channels with different expiry times.
        Step 4: Wait for watch tower to detect expiry and force shutdown.
        Step 5: Assert all channels are closed.
        Step 6: Generate epochs and assert balance changes match expected.
        """
        # Step 1: Start fiber3 and open channels
        self.start_new_fiber(self.generate_account(1000))
        fiber3 = self.fibers[2]
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        self.open_channel(
            self.fiber2, fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )

        # Step 2: Record balances before adding TLCs
        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 3: Add TLCs to both channels with different expiry times
        channel_id_1 = self.fiber1.get_client().list_channels({})["channels"][0]["channel_id"]
        self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id_1,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 15) * 1000),
            }
        )
        channel_id_2 = fiber3.get_client().list_channels({})["channels"][0]["channel_id"]
        self.fiber2.get_client().add_tlc(
            {
                "channel_id": channel_id_2,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 10) * 1000),
            }
        )

        # Step 4: Wait for watch tower to detect expiry and force shutdown
        time.sleep(Timeout.SHORT)

        # Step 5: Assert all channels are closed
        msg = self.get_fibers_balance_message()
        print(msg)
        channels = self.fiber1.get_client().list_channels({})
        assert len(channels["channels"]) == 0
        channels = self.fiber2.get_client().list_channels({"peer_id": fiber3.get_peer_id()})
        assert len(channels["channels"]) == 0

        # Step 6: Generate epochs and assert balance changes
        for _ in range(6):
            self.node.getClient().generate_epochs("0x2")
            time.sleep(6)
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        print("before_balance1:", int(before_balance1))
        print("after_balance1:", int(after_balance1))
        assert (int(after_balance1) - int(before_balance1)) == 1062
        print("before_balance2:", int(before_balance2))
        print("after_balance2:", int(after_balance2))
        assert (int(after_balance2) - int(before_balance2)) == 1124

    def test_shutdown_status(self):
        """
        When channel is in SHUTTING_DOWN state and TLCs expire, watch tower should complete force shutdown.
        Step 1: Start fiber3 and open channels.
        Step 2: Record balances before adding TLCs.
        Step 3: Add TLCs to both channels.
        Step 4: Initiate shutdown (blocked by pending TLCs).
        Step 5: Wait for watch tower to force shutdown after TLC expiry.
        Step 6: Assert all channels are closed and balance changes match expected.
        """
        # Step 1: Start fiber3 and open channels
        self.start_new_fiber(self.generate_account(1000))
        fiber3 = self.fibers[2]
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        self.open_channel(
            self.fiber2, fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )

        # Step 2: Record balances before adding TLCs
        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 3: Add TLCs to both channels
        channel_id_1 = self.fiber1.get_client().list_channels({})["channels"][0]["channel_id"]
        self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id_1,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 15) * 1000),
            }
        )
        channel_id_2 = fiber3.get_client().list_channels({})["channels"][0]["channel_id"]
        self.fiber2.get_client().add_tlc(
            {
                "channel_id": channel_id_2,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 10) * 1000),
            }
        )

        # Step 4: Initiate shutdown (normal shutdown blocked by pending TLCs)
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id_1,
                "close_script": self.get_account_script(self.fiber1.account_private),
                "fee_rate": hex(FeeRate.MEDIUM),
            }
        )

        # Step 5: Wait for watch tower to force shutdown after TLC expiry
        time.sleep(Timeout.SHORT)

        # Step 6: Assert all channels are closed and balance changes
        msg = self.get_fibers_balance_message()
        print(msg)
        channels = self.fiber1.get_client().list_channels({})
        assert len(channels["channels"]) == 0
        channels = self.fiber2.get_client().list_channels({"peer_id": fiber3.get_peer_id()})
        assert len(channels["channels"]) == 0
        for _ in range(6):
            self.node.getClient().generate_epochs("0x2")
            time.sleep(6)
        after_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        after_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )
        print("before_balance1:", int(before_balance1))
        print("after_balance1:", int(after_balance1))
        assert (int(after_balance1) - int(before_balance1)) == 1062
        print("before_balance2:", int(before_balance2))
        print("after_balance2:", int(after_balance2))
        assert (int(after_balance2) - int(before_balance2)) == 1124
