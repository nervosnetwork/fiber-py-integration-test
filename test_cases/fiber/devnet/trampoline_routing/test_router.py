import pytest

from framework.basic_fiber import FiberTest


# todo 多补充一些ckb 和udt channel 混合的用例
class TestRouter(FiberTest):

    def test_ckb_and_udt_channel(self):
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, 10000 * 100000000)
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(self.fiber1, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(
            self.fiber3,
            self.fiber2,
            1000 * 100000000,
            0,
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(self.fiber2, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(
            self.fiber2,
            self.fiber4,
            1000 * 100000000,
            0,
            udt=self.get_account_udt_script(self.fiber1.account_private),
            other_config={"public": False},
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                    "max_fee_amount": hex(2000001),
                    "trampoline_hops": [
                        {
                            "pubkey": self.fiber3.get_client().node_info()["node_id"],
                            # "fee_rate": hex(1000),
                        }
                    ],
                }
            )
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        self.send_payment(
            self.fiber3,
            self.fiber2,
            1 * 100000000,
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        self.send_payment(
            self.fiber2,
            self.fiber4,
            1 * 100000000,
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )

        payment = self.fiber3.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        # "fee_rate": hex(1000),
                    }
                ],
            }
        )
        self.wait_payment_state(self.fiber3, payment["payment_hash"], "Success")


