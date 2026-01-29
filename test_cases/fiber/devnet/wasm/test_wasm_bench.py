"""
Wasm CKB and UDT benchmark tests: CKB channels, UDT channels, bidirectional payments.
Requires wasm fiber server; see README.md in this directory.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"
BENCH_ROUNDS = 50


class TestWasmBench(FiberTest):
    """
    Benchmark WasmFiber CKB and UDT payments.
    Topology: WasmFiber <-> Fiber1 <-> Fiber2; CKB and UDT channels. Many bidirectional payments.
    """

    def test_ckb_bench(self):
        """
        Run CKB then UDT payment benchmark: open CKB channels, warm-up payments, open UDT channels, many bidirectional payments.
        Step 1: Generate WasmFiber account, reset WasmFiber; open CKB channels (F1-F2, Wasm-F1).
        Step 2: Warm-up CKB payments Wasm->F2 and F2->Wasm.
        Step 3: Faucet UDT, open UDT channels F1-F2 and Wasm-F1.
        Step 4: Send BENCH_ROUNDS bidirectional UDT payments (Wasm<->F2); collect payment hashes, ignore send errors.
        Step 5: Wait for all Wasm and F2 payments to finish.
        """
        # Step 1: Generate WasmFiber account, reset WasmFiber; open CKB channels (F1-F2, Wasm-F1)
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
        bal = Amount.ckb(1000)
        self.open_channel(self.fiber1, self.fiber2, bal, bal)
        self.open_channel(wasm_fiber, self.fiber1, bal, bal)

        # Step 2: Warm-up CKB payments Wasm->F2 and F2->Wasm
        amt = Amount.ckb(1)
        self.send_payment(wasm_fiber, self.fiber2, amt, wait=True)
        self.send_payment(self.fiber2, wasm_fiber, amt, wait=True)

        # Step 3: Faucet UDT, open UDT channels F1-F2 and Wasm-F1
        self.faucet(
            self.fiber1.account_private,
            10_000,
            self.fiber1.account_private,
            Amount.udt(10_000),
        )
        udt = self.get_account_udt_script(self.fiber1.account_private)
        self.open_channel(
            self.fiber1,
            self.fiber2,
            bal,
            bal,
            udt=udt,
        )
        self.open_channel(
            wasm_fiber,
            self.fiber1,
            bal,
            bal,
            udt=udt,
        )

        # Step 4: Send BENCH_ROUNDS bidirectional UDT payments (Wasm<->F2); collect hashes, ignore send errors
        wasm_hashes = []
        f2_hashes = []
        for _ in range(BENCH_ROUNDS):
            try:
                h = self.send_payment(
                    wasm_fiber,
                    self.fiber2,
                    amt,
                    wait=False,
                    udt=udt,
                    try_count=0,
                )
                wasm_hashes.append(h)
            except Exception:
                pass
            try:
                h = self.send_payment(
                    self.fiber2,
                    wasm_fiber,
                    amt,
                    wait=False,
                    udt=udt,
                    try_count=0,
                )
                f2_hashes.append(h)
            except Exception:
                pass

        # Step 5: Wait for all Wasm and F2 payments to finish
        for pay_hash in wasm_hashes:
            self.wait_payment_finished(
                wasm_fiber,
                pay_hash,
                timeout=Timeout.PAYMENT_SUCCESS,
            )
        for pay_hash in f2_hashes:
            self.wait_payment_finished(
                self.fiber2,
                pay_hash,
                timeout=Timeout.PAYMENT_SUCCESS,
            )
