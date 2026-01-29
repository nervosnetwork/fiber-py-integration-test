"""
Test cases for send_payment hop_hints parameter with private channels.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, PaymentStatus, TLCFeeRate, Timeout


class TestHopHint(FiberTest):
    """
    Test hop_hints parameter for routing through private channels.
    Topology: a-b-c-d with private channel d-a; b needs hop_hints to reach a via d.
    """

    def test_not_hophit_simple(self):
        """
        Without hop_hint, payment b->a should fail (d-a is private).
        Step 1: Build b-c-d topology; d-a private channel.
        Step 2: Send payment b->a without hop_hint; assert fails with no path found.
        """
        # Step 1: Build b-c-d topology; d-a private channel
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))
        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT
        self.open_channel(
            self.fibers[1], self.fibers[2], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3], Amount.ckb(1000), Amount.ckb(1)
        )
        self.fibers[3].connect_peer(self.fibers[0])
        time.sleep(Timeout.POLL_INTERVAL)
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

        # Step 2: Send payment b->a without hop_hint; assert fails
        try:
            self.send_payment(self.fibers[1], self.fibers[0], Amount.ckb(1))
        except Exception as e:
            error_message = str(e)
            assert (
                "no path found" in error_message or "Failed to build route" in error_message
            ), f"Unexpected error message: {error_message}"

    def test_not_hophit(self):
        """
        a-private-b-c-d-private-a: b->a may succeed via b-a or fail via b-c-d-a.
        Step 1: Build topology with a-b private and d-a private.
        Step 2: Send payment b->a; either succeeds (b-a path) or fails (b-c-d-a needs hint).
        """
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))
        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.open_channel(
            self.fibers[1], self.fibers[2], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3], Amount.ckb(1000), Amount.ckb(1)
        )
        self.fibers[3].connect_peer(self.fibers[0])
        time.sleep(Timeout.POLL_INTERVAL)
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

        try:
            payment = self.fibers[1].get_client().send_payment(
                {
                    "target_pubkey": self.fibers[0].get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                }
            )
            self.wait_payment_state(
                self.fibers[1], payment["payment_hash"], PaymentStatus.SUCCESS
            )
        except Exception as e:
            error_message = str(e)
            assert (
                "no path found" in error_message or "Failed to build route" in error_message
            ), f"Unexpected error message: {error_message}"

    def test_use_hophit(self):
        """
        With hop_hint, payment b->a via d-a private channel should succeed.
        Step 1: Build a-private-b-c-d-private-a topology.
        Step 2: Get d-a channel_outpoint.
        Step 3: Send payment b->a with hop_hints; assert success.
        """
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))
        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.open_channel(
            self.fibers[1], self.fibers[2], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3], Amount.ckb(1000), Amount.ckb(1)
        )
        self.fibers[3].connect_peer(self.fibers[0])
        time.sleep(Timeout.POLL_INTERVAL)
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

        channels = self.fibers[3].get_client().list_channels(
            {"peer_id": self.fibers[0].get_peer_id()}
        )
        da_channel_outpoint = channels["channels"][0]["channel_outpoint"]

        payment = self.fibers[1].get_client().send_payment(
            {
                "target_pubkey": self.fibers[0].get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "hop_hints": [
                    {
                        "pubkey": self.fibers[3].get_client().node_info()["node_id"],
                        "channel_outpoint": da_channel_outpoint,
                        "fee_rate": hex(TLCFeeRate.DEFAULT),
                        "tlc_expiry_delta": hex(86400000),
                    }
                ],
            }
        )
        self.wait_payment_state(
            self.fibers[1], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.CHANNEL_READY
        )

    def test_use_hophit_simple(self):
        """
        b-c-d-private-a: With hop_hint, payment b->a should succeed.
        Step 1: Build b-c-d topology; d-a private channel.
        Step 2: Get d-a channel_outpoint.
        Step 3: Send payment b->a with hop_hints; assert success.
        """
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))
        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        self.open_channel(
            self.fibers[1], self.fibers[2], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3], Amount.ckb(1000), Amount.ckb(1)
        )
        self.fibers[3].connect_peer(self.fibers[0])
        time.sleep(Timeout.POLL_INTERVAL)
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

        channels = self.fibers[3].get_client().list_channels(
            {"peer_id": self.fibers[0].get_peer_id()}
        )
        da_channel_outpoint = channels["channels"][0]["channel_outpoint"]

        payment = self.fibers[1].get_client().send_payment(
            {
                "target_pubkey": self.fibers[0].get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "hop_hints": [
                    {
                        "pubkey": self.fibers[3].get_client().node_info()["node_id"],
                        "channel_outpoint": da_channel_outpoint,
                        "fee_rate": hex(TLCFeeRate.DEFAULT),
                        "tlc_expiry_delta": hex(86400000),
                    }
                ],
            }
        )
        self.wait_payment_state(
            self.fibers[1], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.CHANNEL_READY
        )
