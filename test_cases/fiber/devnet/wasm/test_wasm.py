"""
Wasm module placeholder tests.
Originally contained multiple WasmFiber tests (two_wasm, open_channel, send_payment, etc.); kept minimal runnable subset.
Requires wasm fiber server; see README.md in this directory.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"


class TestWasm(FiberTest):
    """
    Minimal WasmFiber tests: open channel between WasmFiber and Fiber nodes.
    Other historical cases (two_wasm, send_payment, update_channel, etc.) remain commented in git history.
    """

    def test_wasm_open_channel(self):
        """
        Open channels between WasmFiber and Fiber1, WasmFiber and Fiber2; wait for CHANNEL_READY.
        Step 1: Generate WasmFiber account, reset WasmFiber.
        Step 2: Open WasmFiber <-> Fiber2 and WasmFiber <-> Fiber1 channels.
        Step 3: Wait for both channels to reach CHANNEL_READY.
        """
        # Step 1: Generate WasmFiber account and reset WasmFiber
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

        # Step 2: Open WasmFiber <-> Fiber2 and WasmFiber <-> Fiber1 channels
        bal = Amount.ckb(1000)
        self.open_channel(wasm_fiber, self.fiber2, bal, bal)
        self.open_channel(wasm_fiber, self.fiber1, bal, bal)

        # Step 3: Wait for both channels to reach CHANNEL_READY
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        self.wait_for_channel_state(
            wasm_fiber.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
