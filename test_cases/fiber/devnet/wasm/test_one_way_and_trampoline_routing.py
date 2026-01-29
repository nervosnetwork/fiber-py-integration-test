"""
Wasm one-way channel and trampoline routing tests.
Topology: WasmFiber -> Fiber1 -> Fiber2; WasmFiber-Fiber1 is one-way, public=false.
Requires wasm fiber server; see README.md in this directory.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, Timeout, PaymentStatus
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"


class TestOneWayAndTrampolineRouting(FiberTest):
    """
    Test WasmFiber with one-way channel and trampoline routing.
    Topology: WasmFiber <-> Fiber1 <-> Fiber2; WasmFiber-Fiber1 is one-way, non-public.
    Payment path: WasmFiber -> Fiber1 (trampoline) -> Fiber2.
    """

    def test_one_way_and_trampoline_routing(self):
        """
        Open one-way WasmFiber-Fiber1 channel and Fiber1-Fiber2; send keysend via trampoline to Fiber2.
        Step 1: Generate WasmFiber account, reset WasmFiber, open Fiber1-Fiber2 and WasmFiber-Fiber1 (one-way).
        Step 2: Send keysend from WasmFiber to Fiber2 via trampoline (Fiber1); wait for Success.
        """
        # Step 1: Generate WasmFiber account, reset WasmFiber, open Fiber1-Fiber2 and WasmFiber-Fiber1 (one-way)
        account_private = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.ckb(10_000),
        )
        WasmFiber.reset()
        wasm_fiber = WasmFiber(
            account_private,
            WASM_PEER_ID,
            "devnet",
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1000),
        )
        self.open_channel(
            wasm_fiber,
            self.fiber1,
            Amount.ckb(1000),
            Amount.ckb(1000),
            other_config={"public": False, "one_way": True},
        )

        # Step 2: Send keysend from WasmFiber to Fiber2 via trampoline (Fiber1); wait for Success
        amt = Amount.ckb(1)
        payment = wasm_fiber.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(amt),
                "keysend": True,
                "max_fee_amount": hex(amt),
                "max_fee_rate": hex(99),  # 99 per thousand (9.9%) for trampoline routing
                "trampoline_hops": [
                    self.fiber1.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            wasm_fiber,
            payment["payment_hash"],
            status=PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
