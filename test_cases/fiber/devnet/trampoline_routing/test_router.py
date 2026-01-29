"""
Trampoline routing tests: CKB/UDT mixed topology; UDT path via trampoline.
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestRouter(FiberTest):
    """
    CKB/UDT mixed: f1-f3 CKB, f3-f2 UDT, f2-f4 CKB and UDT (private). UDT pay
    f1->f2 via trampoline f3 no path (insufficient UDT setup); after f3->f2 and
    f2->f4 UDT payments, f3->f4 UDT via trampoline f2 succeeds.
    """

    def test_ckb_and_udt_channel(self):
        """
        UDT path f1->f3->f2 via trampoline fails (no path); send UDT f3->f2, f2->f4;
        then UDT keysend f3->f4 via trampoline f2 succeeds.
        Step 1: Create fiber3..4; faucet; open f1-f3 CKB, f3-f2 UDT, f2-f4 CKB+UDT.
        Step 2: UDT keysend f1->f2 via trampoline f3; expect no path.
        Step 3: send_payment f3->f2 and f2->f4 (UDT).
        Step 4: UDT keysend f3->f4 via trampoline f2; wait success.
        """
        # Step 1: Create fiber3..4; faucet; open channels
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.ckb(10000))
        )
        self.faucet(
            self.fiber2.account_private, 0,
            self.fiber1.account_private, Amount.ckb(10000),
        )
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        self.open_channel(
            self.fiber1, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )
        self.open_channel(
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
            other_config={"public": False},
        )

        # Step 2: UDT keysend f1->f2 via trampoline f3; expect no path
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "udt_type_script": udt_script,
                    "max_fee_amount": hex(2000001),
                    "trampoline_hops": [self.fiber3.get_client().node_info()["node_id"]],
                }
            )
        assert "no path found" in (exc_info.value.args[0] if exc_info.value.args else ""), (
            "Expected 'no path found' in error."
        )

        # Step 3: send_payment f3->f2 and f2->f4 (UDT)
        self.send_payment(
            self.fiber3, self.fiber2, Amount.ckb(1),
            udt=udt_script,
        )
        self.send_payment(
            self.fiber2, self.fiber4, Amount.ckb(1),
            udt=udt_script,
        )

        # Step 4: UDT keysend f3->f4 via trampoline f2; wait success
        payment = self.fiber3.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "udt_type_script": udt_script,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber3, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
