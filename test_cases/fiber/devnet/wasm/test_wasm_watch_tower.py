"""
Wasm watch-tower tests: devnet-watch-tower config, force shutdown, capacity/args assertions.
Requires wasm fiber server; see README.md in this directory.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, FeeRate, PaymentStatus
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"
WATCH_TOWER_INTERVAL_SEC = 5
PAYMENTS_PER_ROUND = 5
EXPECTED_CAPACITY_DIFF = Amount.ckb(1099)  # input - output capacity diff for watch-tower claim tx


class TestWasmWatchTower(FiberTest):
    """
    Test WasmFiber with watch-tower (devnet-watch-tower): force shutdown, wait claim tx, assert capacity and lock args.
    Uses fiber_watchtower_check_interval_seconds = 5.
    """
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": WATCH_TOWER_INTERVAL_SEC}

    def test_wasm_watch_tower_force_shutdown(self):
        """
        Two rounds: open Wasm-F1 channel, send payments both ways, stop F1, force shutdown, mine, wait claim tx, assert capacity diff and F2 lock args; restart F1.
        Step 1: Generate WasmFiber account, reset; use devnet-watch-tower.
        Step 2: For each of 2 rounds: open Wasm-F1 channel; send PAYMENTS_PER_ROUND Wasm->F1 and F1->Wasm.
        Step 3: Stop F1; force shutdown Wasm-F1 channel; wait shutdown tx, mine; generate epochs; wait claim tx.
        Step 4: Assert claim tx input-output capacity diff and F2 lock args; restart F1.
        """
        # Step 1: Generate WasmFiber account, reset; use devnet-watch-tower
        account_private = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.udt(10_000),
        )
        WasmFiber.reset()
        wasm_fiber = WasmFiber(
            account_private,
            WASM_PEER_ID,
            "devnet-watch-tower",
        )
        bal = Amount.ckb(1000)
        amt = Amount.ckb(0.001)  # 100_000 shannon

        for round_idx in range(2):
            # Step 2: Open Wasm-F1 channel; send PAYMENTS_PER_ROUND Wasm->F1 and F1->Wasm
            self.open_channel(wasm_fiber, self.fiber1, bal, bal)
            for _ in range(PAYMENTS_PER_ROUND):
                self.send_payment(wasm_fiber, self.fiber1, amt, wait=False)
            for _ in range(PAYMENTS_PER_ROUND):
                self.send_payment(self.fiber1, wasm_fiber, amt, wait=False)

            # Step 3: Stop F1; force shutdown Wasm-F1; wait shutdown tx, mine; generate epochs; wait claim tx
            self.fiber1.stop()
            ch_id = wasm_fiber.get_client().list_channels({})["channels"][0]["channel_id"]
            wasm_fiber.get_client().shutdown_channel(
                {"channel_id": ch_id, "force": True}
            )
            time.sleep(Timeout.POLL_INTERVAL)
            shutdown_tx = self.wait_and_check_tx_pool_fee(
                FeeRate.DEFAULT,
                False,
                5 * Timeout.CHANNEL_READY,
            )
            self.Miner.miner_until_tx_committed(self.node, shutdown_tx)
            self.node.getClient().generate_epochs("0x1", 0)
            tx_hash = self.wait_and_check_tx_pool_fee(
                FeeRate.DEFAULT,
                False,
                Timeout.VERY_LONG,
            )
            message = self.get_tx_message(tx_hash)

            # Step 4: Assert claim tx capacity diff and F2 lock args; restart F1
            cap_in = message["input_cells"][0]["capacity"]
            cap_out = message["output_cells"][0]["capacity"]
            assert cap_in - cap_out == EXPECTED_CAPACITY_DIFF
            assert message["output_cells"][1]["args"] == self.fiber2.get_account()["lock_arg"]
            self.fiber1.start()

    @pytest.mark.skip(reason="Musig2RoundFinalizeError")
    def test_watch_tower_restart(self):
        """
        Open Wasm-F1 channel; F2 stop; F1 keysend to Wasm (allow_self_payment); wait Inflight; F2 start; Wasm refresh; wait Success; F1 stop; force shutdown; wait tx; assert. Skipped: Musig2RoundFinalizeError.
        Step 1: Generate WasmFiber, reset; open Wasm-F1; record F1 balance.
        Step 2: Stop F2; F1 keysend to Wasm; sleep 5; wait Inflight; start F2; Wasm refresh; wait Success.
        Step 3: Record F1 balance; stop F1; force shutdown Wasm-F1; wait shutdown tx, mine, claim tx.
        """
        account_private = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.udt(10_000),
        )
        WasmFiber.reset()
        wasm_fiber = WasmFiber(
            account_private,
            WASM_PEER_ID,
            "devnet-watch-tower",
        )
        self.open_channel(wasm_fiber, self.fiber1, Amount.ckb(1000), Amount.ckb(1000))
        wasm_node_id = wasm_fiber.get_client().node_info()["node_id"]
        before_balance = self.get_fiber_balance(self.fiber1)
        self.fiber2.stop()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": wasm_node_id,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        time.sleep(5)
        self.wait_payment_state(
            self.fiber1,
            payment["payment_hash"],
            status=PaymentStatus.INFLIGHT,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        self.fiber2.start()
        wasm_fiber.refresh()
        self.wait_payment_state(
            self.fiber1,
            payment["payment_hash"],
            status=PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        after_balance = self.get_fiber_balance(self.fiber1)
        self.fiber1.stop()
        ch_id = wasm_fiber.get_client().list_channels({})["channels"][0]["channel_id"]
        wasm_fiber.get_client().shutdown_channel({"channel_id": ch_id, "force": True})
        shutdown_tx = self.wait_and_check_tx_pool_fee(
            FeeRate.DEFAULT,
            False,
            5 * Timeout.CHANNEL_READY,
        )
        self.Miner.miner_until_tx_committed(self.node, shutdown_tx)
        self.node.getClient().generate_epochs("0x1", 0)
        self.wait_and_check_tx_pool_fee(FeeRate.DEFAULT, False, Timeout.VERY_LONG)
