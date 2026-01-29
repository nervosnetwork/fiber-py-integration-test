"""
Wasm RPC smoke tests: connect_peer, open_channel, abandon_channel, accept_channel, list_channels,
update_channel, shutdown_channel, graph_nodes, graph_channels, node_info, new_invoice, parse_invoice,
get_invoice, cancel_invoice, send_payment, build_router, send_payment_with_router, disconnect_peer, list_peers.
Requires wasm fiber server; see README.md in this directory.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import (
    Amount,
    Timeout,
    ChannelState,
    PaymentStatus,
    InvoiceStatus,
    FeeRate,
    Currency,
    HashAlgorithm,
)
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"


class TestWasmRpc(FiberTest):
    """
    Smoke-test Wasm RPC: connect, open/abandon/accept channel, list/update/shutdown channel,
    graph, node_info, invoice (new/parse/get/cancel), send_payment, build_router, send_payment_with_router,
    disconnect_peer, list_peers.
    """

    def test_wasm_rpc(self):
        """
        Run Wasm RPC smoke: connect, open (abandon error), accept, list/update/shutdown, graph, invoice, payment, router, disconnect/list_peers.
        Step 1: Generate WasmFiber account, reset, connect to Fiber1; open channel, wait AWAITING_TX_SIGNATURES.
        Step 2: Abandon channel (expect error "our signature has been sent"); wait CHANNEL_READY.
        Step 3: Fiber1 open channel to Wasm, Wasm accept_channel; wait CHANNEL_READY; assert list_channels channel_id match.
        Step 4: Update channel tlc_fee_proportional_millionths; assert value. Shutdown channel; wait CLOSED.
        Step 5: Call graph_nodes, graph_channels, node_info (no assert). Send invoice payments Wasm<->F1.
        Step 6: Parse invoice (F1 new_invoice, Wasm parse_invoice). Wasm new_invoice, get_invoice, cancel_invoice; assert Cancelled.
        Step 7: Send keysend Wasm->F1. Build router, send_payment_with_router; wait Success.
        Step 8: Disconnect Wasm-F1, assert list_peers empty; connect again, assert list_peers length 1.
        """
        # Step 1: Generate WasmFiber account, reset, connect to Fiber1; open channel, wait AWAITING_TX_SIGNATURES
        account_private = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.udt(10_000),
        )
        WasmFiber.reset()
        wasm_fiber = WasmFiber(
            account_private,
            WASM_PEER_ID,
            "devnet",
        )
        time.sleep(Timeout.POLL_INTERVAL)
        wasm_fiber.connect_peer(self.fiber1)
        time.sleep(Timeout.POLL_INTERVAL)
        wasm_fiber.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000) + DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.AWAITING_TX_SIGNATURES,
            timeout=Timeout.CHANNEL_READY,
        )
        pending_channel_id = wasm_fiber.get_client().list_channels({})["channels"][0]["channel_id"]

        # Step 2: Abandon channel (expect error "our signature has been sent"); wait CHANNEL_READY
        with pytest.raises(Exception) as exc_info:
            wasm_fiber.get_client().abandon_channel({"channel_id": pending_channel_id})
        expected = " our signature has been sent. It cannot be abandoned"
        assert expected in exc_info.value.args[0], (
            f"Expected substring '{expected}' not found in '{exc_info.value.args[0]}'"
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 3: Fiber1 open channel to Wasm, Wasm accept_channel; wait CHANNEL_READY; assert list_channels match
        list_peers = self.fiber1.get_client().list_peers()
        wasm_node_id = wasm_fiber.get_client().node_info()["node_id"]
        wasm_fiber_peer_id = None
        for peer in list_peers["peers"]:
            if peer["pubkey"] == wasm_node_id:
                wasm_fiber_peer_id = peer["peer_id"]
                break
        assert wasm_fiber_peer_id is not None
        accept_funding = Amount.ckb(100) + DEFAULT_MIN_DEPOSIT_CKB
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": wasm_fiber_peer_id,
                "funding_amount": hex(accept_funding),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL * 2)
        wasm_fiber.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(accept_funding),
            }
        )
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        wasm_chans = wasm_fiber.get_client().list_channels({})
        f1_chans = self.fiber1.get_client().list_channels({})
        assert wasm_chans["channels"][0]["channel_id"] == f1_chans["channels"][0]["channel_id"]

        # Step 4: Update channel tlc_fee_proportional_millionths; assert. Shutdown channel; wait CLOSED
        update_channel_id = wasm_chans["channels"][0]["channel_id"]
        tlc_fee = 2000  # 0.2% (millionths)
        wasm_fiber.get_client().update_channel(
            {
                "channel_id": update_channel_id,
                "tlc_fee_proportional_millionths": hex(tlc_fee),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        chans = wasm_fiber.get_client().list_channels({})
        assert chans["channels"][0]["tlc_fee_proportional_millionths"] == hex(tlc_fee)

        shutdown_channel_id = chans["channels"][0]["channel_id"]
        wasm_fiber.get_client().shutdown_channel(
            {
                "channel_id": shutdown_channel_id,
                "close_script": self.get_account_script(account_private),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        tx_hash = self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False, Timeout.CHANNEL_READY)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CLOSED,
            include_closed=True,
            channel_id=shutdown_channel_id,
        )

        # Step 5: Call graph_nodes, graph_channels, node_info. Send invoice payments Wasm<->F1
        wasm_fiber.get_client().graph_nodes({})
        self.fiber1.get_client().graph_nodes({})
        wasm_fiber.get_client().graph_channels({})
        self.fiber1.get_client().graph_channels({})
        wasm_fiber.get_client().node_info()

        amt = Amount.ckb(1)
        self.send_invoice_payment(wasm_fiber, self.fiber1, amt, wait=True)
        self.send_invoice_payment(self.fiber1, wasm_fiber, amt, wait=True)

        # Step 6: Parse invoice (F1 new_invoice, Wasm parse). Wasm new_invoice, get_invoice, cancel; assert Cancelled
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": Currency.FIBD,
                "description": "test invoice generated by node2",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        wasm_fiber.get_client().parse_invoice({"invoice": invoice["invoice_address"]})

        wasm_inv = wasm_fiber.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": Currency.FIBD,
                "description": "test invoice generated by node2",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        ph = wasm_inv["invoice"]["data"]["payment_hash"]
        wasm_fiber.get_client().get_invoice({"payment_hash": ph})
        wasm_fiber.get_client().cancel_invoice({"payment_hash": ph})
        cancelled = wasm_fiber.get_client().get_invoice({"payment_hash": ph})
        assert cancelled["status"] == InvoiceStatus.CANCELLED

        # Step 7: Send keysend Wasm->F1. Build router, send_payment_with_router; wait Success
        self.send_payment(wasm_fiber, self.fiber1, Amount.ckb(1), wait=True)

        chs = wasm_fiber.get_client().list_channels({})
        channel_outpoint = chs["channels"][0]["channel_outpoint"]
        router = wasm_fiber.get_client().build_router(
            {
                "amount": hex(Amount.ckb(1)),
                "udt_type_script": None,
                "hops_info": [
                    {
                        "pubkey": self.fiber1.get_client().node_info()["node_id"],
                        "channel_outpoint": channel_outpoint,
                    },
                ],
                "final_tlc_expiry_delta": None,
            }
        )
        payment = wasm_fiber.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        self.wait_payment_state(
            wasm_fiber,
            payment["payment_hash"],
            status=PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 8: Disconnect Wasm-F1, assert list_peers empty; connect again, assert list_peers length 1
        wasm_fiber.get_client().disconnect_peer({"peer_id": self.fiber1.get_peer_id()})
        time.sleep(Timeout.POLL_INTERVAL)
        peers = wasm_fiber.get_client().list_peers()
        assert len(peers["peers"]) == 0
        wasm_fiber.connect_peer(self.fiber1)
        time.sleep(Timeout.POLL_INTERVAL)
        peers = wasm_fiber.get_client().list_peers()
        assert len(peers["peers"]) == 1
