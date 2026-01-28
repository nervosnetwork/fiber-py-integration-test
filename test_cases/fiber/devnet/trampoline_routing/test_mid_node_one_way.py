"""
Trampoline routing tests: mid-node one-way channels; no path without trampoline,
path with trampoline and balance change.
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestMidNodeOneWay(FiberTest):
    """
    One-way channels: without trampoline_hops no path; with trampoline_hops
    payment succeeds and balance change matches.
    """

    def test_mid_node_one_way(self):
        """
        One-way f1->f2, f2->f3; without trampoline no path; with trampoline success.
        Step 1: Create fiber3; open one-way f1->f2, f2->f3.
        Step 2: Keysend without trampoline_hops; expect no path.
        Step 3: Keysend with trampoline_hops; wait success; assert balance change.
        """
        # Step 1: Create fiber3; open one-way f1->f2, f2->f3
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False, "one_way": True},
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False, "one_way": True},
        )

        # Step 2: Keysend without trampoline_hops; expect no path
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                }
            )
        expected = "no path found"
        assert expected in (exc_info.value.args[0] if exc_info.value.args else ""), (
            f"Expected '{expected}' in error."
        )

        # Step 3: Keysend with trampoline_hops; wait success; assert balance change
        before_balance = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        assert result == [
            {"local_balance": 100500000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -500000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -Amount.CKB, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]
