"""
Wasm multi-instance tests: two WasmFiber nodes, channels to Fiber1/Fiber2, invoice self-payments.
Requires wasm fiber server; see README.md in this directory.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount
from framework.test_wasm_fiber import WasmFiber

WASM1_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"
WASM2_PEER_ID = "2201010101010101010101010101010101010101010101010101010101010101"
NUM_SELF_PAYMENTS = 20


class TestWasmMutil(FiberTest):
    """
    Test two WasmFiber instances: Wasm1 <-> F1, Wasm2 <-> F1, Wasm2 <-> F2, Wasm1 <-> F2.
    Send invoice self-payments on each Wasm node.
    """

    def test_mutil(self):
        """
        Two WasmFiber nodes, open channels to F1/F2, send invoice self-payments on each Wasm.
        Step 1: Generate two accounts, reset WasmFiber; create Wasm1 and Wasm2 with distinct databasePrefix.
        Step 2: Open Wasm1-F1, Wasm2-F1, Wasm2-F2, Wasm1-F2 channels.
        Step 3: Send NUM_SELF_PAYMENTS invoice self-payments on Wasm1 and on Wasm2.
        """
        # Step 1: Generate two accounts, reset WasmFiber; create Wasm1 and Wasm2 with distinct databasePrefix
        account_private = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.udt(10_000),
        )
        account_private2 = self.generate_account(
            10_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.udt(10_000),
        )
        WasmFiber.reset()
        wasm_fiber1 = WasmFiber(
            account_private,
            WASM1_PEER_ID,
            "devnet",
            databasePrefix="wasm1",
        )
        wasm_fiber2 = WasmFiber(
            account_private2,
            WASM2_PEER_ID,
            "devnet",
            databasePrefix="wasm2",
        )

        # Step 2: Open Wasm1-F1, Wasm2-F1, Wasm2-F2, Wasm1-F2 channels
        bal = Amount.ckb(1000)
        self.open_channel(wasm_fiber1, self.fiber1, bal, bal)
        self.open_channel(wasm_fiber2, self.fiber1, bal, bal)
        self.open_channel(wasm_fiber2, self.fiber2, bal, bal)
        self.open_channel(wasm_fiber1, self.fiber2, bal, bal)

        # Step 3: Send NUM_SELF_PAYMENTS invoice self-payments on Wasm1 and on Wasm2
        amt = Amount.ckb(1)
        for _ in range(NUM_SELF_PAYMENTS):
            self.send_invoice_payment(wasm_fiber1, wasm_fiber1, amt)
            self.send_invoice_payment(wasm_fiber2, wasm_fiber2, amt)
