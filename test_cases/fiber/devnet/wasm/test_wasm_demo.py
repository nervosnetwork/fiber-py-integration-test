"""
Wasm CKB/UDT demo: open CKB and UDT channels, payments, shutdown, refresh, node_info stability.
Requires wasm fiber server; see README.md in this directory.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState, FeeRate
from framework.test_wasm_fiber import WasmFiber

WASM_PEER_ID = "0201010101010101010101010101010101010101010101010101010101010101"


class TestWasmDemo(FiberTest):
    """
    Demo WasmFiber CKB and UDT: open channels, send payments, shutdown, refresh, assert node_info stable.
    Topology: WasmFiber <-> Fiber1 <-> Fiber2; CKB and UDT channels.
    """

    def test_ckb_udt_demo(self):
        """
        CKB then UDT channels, payments, shutdown both Wasm channels, refresh, assert node_id unchanged.
        Step 1: Generate WasmFiber account, reset WasmFiber; open CKB channels (F1-F2, Wasm-F1).
        Step 2: Warm-up CKB payments Wasm<->F2.
        Step 3: Faucet UDT, open UDT channels F1-F2 and Wasm-F1; send UDT payments both ways (wait=True).
        Step 4: Shutdown first Wasm-F1 channel (close_script, fee_rate); wait CLOSED.
        Step 5: Shutdown second Wasm-F1 channel; wait CLOSED; assert no channels left.
        Step 6: Record node_info, refresh, assert node_id unchanged before and after refresh.
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

        # Step 2: Warm-up CKB payments Wasm<->F2
        amt = Amount.ckb(1)
        self.send_payment(wasm_fiber, self.fiber2, amt, wait=True)
        self.send_payment(self.fiber2, wasm_fiber, amt, wait=True)

        # Step 3: Faucet UDT, open UDT channels F1-F2 and Wasm-F1; send UDT payments both ways
        self.faucet(
            self.fiber1.account_private,
            10_000,
            self.fiber1.account_private,
            Amount.ckb(10_000),
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
        self.send_payment(
            wasm_fiber,
            self.fiber2,
            amt,
            wait=True,
            udt=udt,
        )
        self.send_payment(
            self.fiber2,
            wasm_fiber,
            amt,
            wait=True,
            udt=udt,
        )

        # Step 4: Shutdown first Wasm-F1 channel (close_script, fee_rate); wait CLOSED
        wasm_client = wasm_fiber.get_client()
        chs = wasm_client.list_channels({})["channels"]
        ch_id_0 = chs[0]["channel_id"]
        wasm_client.shutdown_channel(
            {
                "channel_id": ch_id_0,
                "close_script": self.get_account_script(account_private),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        self.wait_for_channel_state(
            wasm_client,
            self.fiber1.get_peer_id(),
            ChannelState.CLOSED,
            include_closed=True,
        )

        # Step 5: Shutdown second Wasm-F1 channel; wait CLOSED; assert no channels left
        chs = wasm_client.list_channels({})["channels"]
        shutdown_channel_id = chs[0]["channel_id"]
        wasm_client.shutdown_channel(
            {
                "channel_id": shutdown_channel_id,
                "close_script": self.get_account_script(account_private),
                "fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.wait_for_channel_state(
            wasm_client,
            self.fiber1.get_peer_id(),
            ChannelState.CLOSED,
            include_closed=True,
            channel_id=shutdown_channel_id,
        )
        assert len(wasm_client.list_channels({})["channels"]) == 0

        # Step 6: Record node_info, refresh, assert node_id unchanged before and after refresh
        node_info0 = wasm_client.node_info()
        wasm_fiber.refresh()
        node_info1 = wasm_client.node_info()
        node_info2 = wasm_client.node_info()
        assert node_info1["node_id"] == node_info2["node_id"]
        assert node_info0["node_id"] == node_info1["node_id"]
