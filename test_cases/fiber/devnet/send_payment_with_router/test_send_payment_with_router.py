"""
Test cases for send_payment_with_router RPC.
Verifies payment with explicitly specified router hops.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, PaymentStatus, TLCFeeRate, Timeout


class TestSendPaymentWithRouter(FiberTest):
    """
    Test send_payment_with_router RPC functionality:
    1. Basic: Use specified router to send payment d->a
    2. Auto routing: b->a via b-c-d-private-a (should fail - router not from b)
    3. Loop: b->b via b-c-d-a-b cycle
    """

    def test_base_send_payment_with_router(self):
        """
        Test d->a payment using build_router and send_payment_with_router.
        Step 1: Build topology b-c-d-private-a.
        Step 2: Build router from d to a using d-a channel outpoint.
        Step 3: Send payment from d to a with the router.
        Step 4: Wait for payment success.
        """
        # Step 1: Build topology b-c-d-private-a
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3],
            Amount.ckb(1000), Amount.ckb(1)
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
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Build router from d to a
        channels = self.fibers[3].get_client().list_channels(
            {"peer_id": self.fibers[0].get_peer_id()}
        )
        da_channel_outpoint = channels["channels"][0]["channel_outpoint"]

        router_hops = self.fibers[3].get_client().build_router(
            {
                "amount": hex(1 + DEFAULT_MIN_DEPOSIT_CKB),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[0].get_client().node_info()["node_id"],
                        "channel_outpoint": da_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )
        hop = router_hops["router_hops"][0]
        assert hop["channel_outpoint"] == da_channel_outpoint
        assert hop["target"] == self.fibers[0].get_client().node_info()["node_id"]
        assert hop["amount_received"] == hex(1 + DEFAULT_MIN_DEPOSIT_CKB)

        # Step 3: Send payment from d to a with the router
        payment = self.fibers[3].get_client().send_payment_with_router(
            {
                "payment_hash": None,
                "invoice": None,
                "keysend": True,
                "custom_records": None,
                "dry_run": False,
                "udt_type_script": None,
                "router": router_hops["router_hops"],
            }
        )

        # Step 4: Wait for payment success
        assert payment["status"] == PaymentStatus.CREATED
        self.wait_payment_state(
            self.fibers[3], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_auto_send_payment_with_router(self):
        """
        Test that b->a with d-a router fails (router must start from sender).
        Step 1: Build topology b-c-d-private-a.
        Step 2: Build router from d to a.
        Step 3: Attempt send_payment_with_router from b with d-a router.
        Step 4: Assert error (UnknownNextPeer or similar).
        """
        # Step 1: Build topology b-c-d-private-a
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3],
            Amount.ckb(1000), Amount.ckb(1)
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
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Build router from d to a
        channels = self.fibers[3].get_client().list_channels(
            {"peer_id": self.fibers[0].get_peer_id()}
        )
        da_channel_outpoint = channels["channels"][0]["channel_outpoint"]

        router_hops = self.fibers[3].get_client().build_router(
            {
                "amount": hex(1 + DEFAULT_MIN_DEPOSIT_CKB),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[0].get_client().node_info()["node_id"],
                        "channel_outpoint": da_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )

        # Step 3: Attempt send_payment_with_router from b with d-a router
        with pytest.raises(Exception) as exc_info:
            self.fibers[1].get_client().send_payment_with_router(
                {
                    "payment_hash": None,
                    "invoice": None,
                    "keysend": True,
                    "custom_records": None,
                    "dry_run": False,
                    "udt_type_script": None,
                    "router": router_hops["router_hops"],
                }
            )

        # Step 4: Assert error (UnknownNextPeer)
        error_message = str(exc_info.value)
        assert "UnknownNextPeer" in error_message or "Send payment first hop error" in error_message, (
            f"Expected UnknownNextPeer error, actual: {error_message}"
        )

    def test_loop_send_payment_with_router(self):
        """
        Test b->b self-payment through cycle b-c-d-a-b.
        Step 1: Build topology a-b-c-d-private-a (cycle).
        Step 2: Build router hops for b-c-d-a-b.
        Step 3: Send payment from b to b with the full router.
        Step 4: Wait for payment success.
        """
        # Step 1: Build topology a-b-c-d-private-a (cycle)
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        self.open_channel(
            self.fibers[0], self.fibers[1],
            Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3],
            Amount.ckb(1000), Amount.ckb(1)
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
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Build router hops for b-c-d-a-b
        bc_channel_outpoint = self._get_channel_outpoint(self.fibers[1], self.fibers[2])
        cd_channel_outpoint = self._get_channel_outpoint(self.fibers[2], self.fibers[3])
        da_channel_outpoint = self._get_channel_outpoint(self.fibers[3], self.fibers[0])
        ab_channel_outpoint = self._get_channel_outpoint(self.fibers[0], self.fibers[1])

        base_amount = 1 + DEFAULT_MIN_DEPOSIT_CKB
        bc_router_hops = self.fibers[1].get_client().build_router(
            {
                "amount": hex(4 * base_amount),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[2].get_client().node_info()["node_id"],
                        "channel_outpoint": bc_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )
        cd_router_hops = self.fibers[2].get_client().build_router(
            {
                "amount": hex(3 * base_amount),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[3].get_client().node_info()["node_id"],
                        "channel_outpoint": cd_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )
        da_router_hops = self.fibers[3].get_client().build_router(
            {
                "amount": hex(2 * base_amount),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[0].get_client().node_info()["node_id"],
                        "channel_outpoint": da_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )
        ab_router_hops = self.fibers[0].get_client().build_router(
            {
                "amount": hex(1 * base_amount),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fibers[1].get_client().node_info()["node_id"],
                        "channel_outpoint": ab_channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )

        bc_hop = bc_router_hops["router_hops"][0]
        cd_hop = cd_router_hops["router_hops"][0]
        da_hop = da_router_hops["router_hops"][0]
        ab_hop = ab_router_hops["router_hops"][0]

        base_expiry = 86400000
        delta = 172800000
        ab_hop["incoming_tlc_expiry"] = hex(base_expiry)
        da_hop["incoming_tlc_expiry"] = hex(base_expiry + delta)
        cd_hop["incoming_tlc_expiry"] = hex(base_expiry + 2 * delta)
        bc_hop["incoming_tlc_expiry"] = hex(base_expiry + 3 * delta)

        # Step 3: Send payment from b to b with the full router
        payment = self.fibers[1].get_client().send_payment_with_router(
            {
                "payment_hash": None,
                "invoice": None,
                "keysend": True,
                "custom_records": None,
                "dry_run": False,
                "udt_type_script": None,
                "router": [bc_hop, cd_hop, da_hop, ab_hop],
            }
        )

        # Step 4: Wait for payment success
        assert payment["status"] == PaymentStatus.CREATED
        self.wait_payment_state(
            self.fibers[1], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )

    def _get_channel_outpoint(self, from_fiber, to_fiber):
        """Get channel outpoint between from_fiber and to_fiber."""
        channels = from_fiber.get_client().list_channels(
            {"peer_id": to_fiber.get_peer_id()}
        )
        return channels["channels"][0]["channel_outpoint"]
