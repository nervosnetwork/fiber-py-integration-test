"""
Wasm connect_peer tests: connect WasmFiber to many Fiber nodes, open channels, send payments.
Requires wasm fiber server; see README.md in this directory.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, InvoiceStatus
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"
NUM_NODES = 20


class TestWasmConnectPeer(FiberTest):
    """
    Test WasmFiber connecting to multiple Fiber nodes, opening channels, and invoice/keysend payments.
    Topology: one WasmFiber plus NUM_NODES Fiber nodes; WasmFiber has a channel to each.
    """

    def test_connect_20_nodes(self):
        """
        Connect WasmFiber to 20 Fiber nodes, open channels, send invoice and keysend payments both ways.
        Step 1: Generate WasmFiber account and reset WasmFiber; start NUM_NODES Fiber nodes.
        Step 2: Open channel between WasmFiber and each Fiber node.
        Step 3: Send invoice payments (Fiber -> WasmFiber) and keysend payments (WasmFiber -> Fiber).
        Step 4: Wait for all keysend payments to finish.
        Step 5: Wait for all invoice payments (WasmFiber side) to reach PAID.
        """
        # Step 1: Generate WasmFiber account and reset WasmFiber; start NUM_NODES Fiber nodes
        account_private = self.generate_account(
            1_000_000,
            self.Config.ACCOUNT_PRIVATE_1,
            Amount.ckb(10_000),
        )
        WasmFiber.reset()
        wasm_fiber = WasmFiber(
            account_private,
            WASM_PEER_ID,
            "devnet",
        )
        for _ in range(NUM_NODES):
            self.start_new_fiber(self.generate_account(10_000))

        # Step 2: Open channel between WasmFiber and each Fiber node
        for f in self.fibers:
            self.open_channel(
                wasm_fiber,
                f,
                Amount.ckb(1000),
                Amount.ckb(1000),
            )

        # Step 3: Send invoice payments (Fiber -> WasmFiber) and keysend payments (WasmFiber -> Fiber)
        payments = []
        invoices = []
        amt = Amount.ckb(1)
        for f in self.fibers:
            inv_hash = self.send_invoice_payment(f, wasm_fiber, amt, wait=False)
            invoices.append(inv_hash)
            pay_hash = self.send_payment(wasm_fiber, f, amt, wait=False)
            payments.append(pay_hash)

        # Step 4: Wait for all keysend payments to finish
        for pay_hash in payments:
            self.wait_payment_finished(
                wasm_fiber,
                pay_hash,
                timeout=Timeout.PAYMENT_SUCCESS,
            )

        # Step 5: Wait for all invoice payments (WasmFiber side) to reach PAID
        for inv_hash in invoices:
            self.wait_invoice_state(
                wasm_fiber,
                inv_hash,
                status=InvoiceStatus.PAID,
                timeout=Timeout.CHANNEL_READY,
            )
