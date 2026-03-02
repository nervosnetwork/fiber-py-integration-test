from framework.basic_fiber import FiberTest
from framework.test_fiber import Fiber
from framework.test_wasm_fiber import WasmFiber


class TestOneWayAndTrampolineRouting(FiberTest):

    def test_one_way_and_trampoline_routing(self):
        """

        Returns:
        """
        # wasm fiber-> fiber-> wasm fiber
        account_private = self.generate_account(
            10000, self.Config.ACCOUNT_PRIVATE_1, 10000 * 100000000
        )
        WasmFiber.reset()
        wasmFiber = WasmFiber(
            account_private,
            "0201010101010101010101010101010101010101010101010101010101010101",
            "devnet",
        )
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(
            wasmFiber,
            self.fiber1,
            1000 * 100000000,
            1000 * 100000000,
            other_config={"public": False, "one_way": True},
        )
        # self.send_payment(wasmFiber, self.fiber2, 1 * 100000000)
        payment = wasmFiber.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "max_fee_amount": hex(1 * 100000000),
                "max_fee_rate": hex(99),
                "trampoline_hops": [
                    self.fiber1.get_client().node_info()["pubkey"],
                ],
            }
        )
        self.wait_payment_state(wasmFiber, payment["payment_hash"], "Success")
