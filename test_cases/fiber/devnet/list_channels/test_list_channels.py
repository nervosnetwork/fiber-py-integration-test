"""
Test cases for list_channels RPC: filter by peer_id, list all, funding_udt_type_script,
created_at, is_public, channel fields, and closed channels.
"""
import datetime

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, FeeRate, Timeout, TLCFeeRate


class TestListChannels(FiberTest):
    """
    Test list_channels RPC: pending/accept/closed channels, peer_id filter,
    funding_udt_type_script, created_at, is_public, and channel result fields.
    """

    def test_peer_id(self):
        """
        List channels filtered by peer_id; channel_id should match on both sides.
        Step 1: Start fiber3 and connect to fiber1.
        Step 2: Open channel fiber1-fiber2, wait CHANNEL_READY.
        Step 3: Open channel fiber1-fiber3, wait CHANNEL_READY.
        Step 4: List channels by peer_id (fiber2) on fiber1 and fiber2; assert channel_id match.
        Step 5: List channels by peer_id (fiber3) on fiber1 and fiber3; assert channel_id match.
        """
        # Step 1: Start fiber3 and connect to fiber1
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber1)

        # Step 2: Open channel fiber1-fiber2, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: Open channel fiber1-fiber3, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 4: List channels by peer_id (fiber2); assert channel_id match on both sides
        n12_channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        n21_channels = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )
        assert (
            n12_channels["channels"][0]["channel_id"]
            == n21_channels["channels"][0]["channel_id"]
        )

        # Step 5: List channels by peer_id (fiber3); assert channel_id match on both sides
        n13_channels = self.fiber1.get_client().list_channels(
            {"peer_id": fiber3.get_peer_id()}
        )
        n31_channels = fiber3.get_client().list_channels(
            {"peer_id": self.fiber1.get_peer_id()}
        )
        assert (
            n13_channels["channels"][0]["channel_id"]
            == n31_channels["channels"][0]["channel_id"]
        )

    def test_empty(self):
        """
        List all channels (no peer_id filter); expect 2 channels after opening two.
        Step 1: Start fiber3 and connect to fiber1.
        Step 2: Open channel fiber1-fiber2, wait CHANNEL_READY.
        Step 3: Open channel fiber1-fiber3, wait CHANNEL_READY.
        Step 4: List all channels on fiber1; assert count is 2.
        """
        # Step 1: Start fiber3 and connect to fiber1
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber1)

        # Step 2: Open channel fiber1-fiber2, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: Open channel fiber1-fiber3, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 4: List all channels on fiber1; assert count is 2
        channels = self.fiber1.get_client().list_channels({})
        assert len(channels["channels"]) == 2

    def test_funding_udt_type_script(self):
        """
        list_channels returns funding_udt_type_script for channel opened with UDT.
        Step 1: Start fiber3 and connect to fiber1.
        Step 2: Open channel with funding_udt_type_script, wait CHANNEL_READY.
        Step 3: List channels; assert first channel funding_udt_type_script matches.
        """
        # Step 1: Start fiber3 and connect to fiber1
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber1)

        # Step 2: Open channel with funding_udt_type_script, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: List channels; assert funding_udt_type_script matches
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0][
            "funding_udt_type_script"
        ] == self.get_account_udt_script(self.fiber1.account_private)

    @pytest.mark.skip(reason="Placeholder: funding_udt_type_script none == ckb")
    def test_funding_udt_type_script_none(self):
        """
        When funding_udt_type_script is none, treat as CKB.
        Step 1: (Reserved)
        """
        pass

    def test_created_at(self):
        """
        list_channels returns created_at within reasonable time of now.
        Step 1: Start fiber3 and connect to fiber1.
        Step 2: Open channel, wait CHANNEL_READY.
        Step 3: List channels; assert created_at is within last 10 seconds.
        """
        # Step 1: Start fiber3 and connect to fiber1
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber1)

        # Step 2: Open channel, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: List channels; assert created_at is within last 10 seconds
        channels = self.fiber1.get_client().list_channels({})
        created_at_hex = int(channels["channels"][0]["created_at"], 16) / 1000
        now_sec = int(datetime.datetime.now().timestamp())
        assert (now_sec - int(created_at_hex / 1000)) < 10

    def test_is_public(self):
        """
        list_channels returns is_public true for public channel.
        Step 1: Open channel with public=True, wait CHANNEL_READY.
        Step 2: List channels; assert is_public is True.
        """
        # Step 1: Open channel with public=True, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: List channels; assert is_public is True
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["is_public"] is True

    def test_check_channel_result(self):
        """
        list_channels returns all expected channel fields (channel_id, is_public,
        channel_outpoint, peer_id, funding_udt_type_script, state, balances, etc.).
        Step 1: Open channel, wait for tx pool and CHANNEL_READY.
        Step 2: List channels and assert all key fields.
        Step 3: Force shutdown; assert include_closed shows closed channel.
        """
        # Step 1: Open channel, wait for tx pool and CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        open_tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: List channels and assert all key fields
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        assert channels["channels"][0]["channel_id"] is not None
        assert channels["channels"][0]["is_public"] is True
        assert channels["channels"][0]["channel_outpoint"] is not None
        assert open_tx_hash in channels["channels"][0]["channel_outpoint"]
        assert channels["channels"][0]["peer_id"] == self.fiber2.get_peer_id()
        assert channels["channels"][0][
            "funding_udt_type_script"
        ] == self.get_account_udt_script(self.fiber1.account_private)
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(1000))
        assert channels["channels"][0]["offered_tlc_balance"] == hex(0)
        assert channels["channels"][0]["remote_balance"] == hex(0)
        assert channels["channels"][0]["received_tlc_balance"] == hex(0)
        assert int(channels["channels"][0]["created_at"], 16) / 1000 > 0
        assert channels["channels"][0]["enabled"] is True
        assert channels["channels"][0]["tlc_expiry_delta"] == hex(14400000)
        assert channels["channels"][0]["tlc_fee_proportional_millionths"] == hex(
            TLCFeeRate.DEFAULT
        )

        # Step 3: Force shutdown; assert include_closed shows closed channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channels["channels"][0]["channel_id"],
                "force": True,
            }
        )
        self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False, 120)
        channel = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        assert len(channel["channels"]) == 0
        channel = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id(), "include_closed": True}
        )
        assert len(channel["channels"]) == 1

    def test_close_channels(self):
        """
        After shutdown_channel with close_script and fee_rate, channel state is CLOSED.
        Step 1: Open channel, wait CHANNEL_READY.
        Step 2: Shutdown with close_script and fee_rate.
        Step 3: Wait for channel state CLOSED.
        """
        # Step 1: Open channel, wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Shutdown with close_script and fee_rate
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        channel_id = channels["channels"][0]["channel_id"]
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.fiber1.account_private),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )

        # Step 3: Wait for channel state CLOSED
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.CHANNEL_READY,
            include_closed=True,
        )
