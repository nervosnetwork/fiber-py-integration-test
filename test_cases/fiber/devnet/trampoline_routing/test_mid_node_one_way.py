import pytest

from framework.basic_fiber import FiberTest


class TestMidNodeOneWay(FiberTest):

    def test_mid_node_one_way(self):

        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, other_config={
            "public": False,
            "one_way": True
        })
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0, other_config={
            "public": False,
            "one_way": True
        })
        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment({
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                # "trampoline_hops": [
                #     self.fiber2.get_client().node_info()["node_id"],
                # ],
            })
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        before_balance = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment({
            "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
            "currency": "Fibd",
            "amount": hex(1 * 100000000),
            "keysend": True,
            "trampoline_hops": [
                self.fiber2.get_client().node_info()["node_id"],
            ],
        })
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        print("result:", result)
        assert result == [
            {'local_balance': 100500000, 'offered_tlc_balance': 0, 'received_tlc_balance': 0},
            {'local_balance': -500000, 'offered_tlc_balance': 0, 'received_tlc_balance': 0},
            {'local_balance': -100000000, 'offered_tlc_balance': 0, 'received_tlc_balance': 0}]
