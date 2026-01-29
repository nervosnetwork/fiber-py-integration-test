"""
Test watch tower behavior when HTLC expires.
When TLC expires, watch tower should automatically trigger force shutdown.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, FeeRate, Timeout
from framework.test_fiber import FiberConfigPath


class TestHtlcExpired(FiberTest):
    """
    Test watch tower auto force shutdown when HTLC expires.
    Uses debug fiber version with shorter watchtower check interval.
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}
    fiber_version = FiberConfigPath.CURRENT_DEV_DEBUG

    def test_ready_status(self):
        """
        When channel is in ready state, expired TLC should trigger auto force shutdown.
        Step 1: Build topology fiber1->fiber2->fiber3 and open channels.
        Step 2: Add TLCs with short expiry on both channels.
        Step 3: Wait for TLC expiry and watch tower to trigger force shutdown.
        Step 4: Assert channels are closed and balances are correct.
        """
        # Step 1: Build topology fiber1->fiber2->fiber3 and open channels
        self.start_new_fiber(self.generate_account(Amount.ckb(1000)))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        self.open_channel(
            self.fiber2, self.fibers[2],
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        # Step 2: Add TLCs with short expiry on both channels
        channel_id = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 15) * 1000),
            }
        )
        channel_id = (
            self.fibers[2].get_client().list_channels({})["channels"][0]["channel_id"]
        )
        self.fiber2.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 10) * 1000),
            }
        )

        # Step 3: Wait for TLC expiry and watch tower to trigger force shutdown
        time.sleep(Timeout.SHORT)
        msg = self.get_fibers_balance_message()
        print(msg)

        # Step 4: Assert channels are closed and balances are correct
        self.assert_channel_count(self.fiber1, 0)
        channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fibers[2].get_peer_id()}
        )
        assert len(channels["channels"]) == 0

        for i in range(6):
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
        When channel is in shutdown state, expired TLC should trigger auto force shutdown.
        Step 1: Build topology and add TLCs with short expiry.
        Step 2: Initiate shutdown_channel (blocks due to pending TLC).
        Step 3: Wait for TLC expiry and watch tower to trigger force shutdown.
        Step 4: Assert channels are closed and balances are correct.
        """
        # Step 1: Build topology and add TLCs with short expiry
        self.start_new_fiber(self.generate_account(Amount.ckb(1000)))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        self.open_channel(
            self.fiber2, self.fibers[2],
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        before_balance1 = self.Ckb_cli.wallet_get_capacity(
            self.account1["address"]["testnet"]
        )
        before_balance2 = self.Ckb_cli.wallet_get_capacity(
            self.account2["address"]["testnet"]
        )

        channel_id1 = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.fiber1.get_client().add_tlc(
            {
                "channel_id": channel_id1,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 15) * 1000),
            }
        )
        channel_id = (
            self.fibers[2].get_client().list_channels({})["channels"][0]["channel_id"]
        )
        self.fiber2.get_client().add_tlc(
            {
                "channel_id": channel_id,
                "amount": hex(Amount.ckb(300)),
                "payment_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "expiry": hex((int(time.time()) + 10) * 1000),
            }
        )

        # Step 2: Initiate shutdown_channel (blocks due to pending TLC)
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id1,
                "close_script": self.get_account_script(self.fiber1.account_private),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )

        # Step 3: Wait for TLC expiry and watch tower to trigger force shutdown
        time.sleep(Timeout.SHORT)
        msg = self.get_fibers_balance_message()
        print(msg)

        # Step 4: Assert channels are closed and balances are correct
        self.assert_channel_count(self.fiber1, 0)
        channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fibers[2].get_peer_id()}
        )
        assert len(channels["channels"]) == 0

        for i in range(6):
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
