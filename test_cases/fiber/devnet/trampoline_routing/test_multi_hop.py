"""
Trampoline routing tests: 3-hop and 4-hop, different fee rates, UDT, mixed CKB/UDT.
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestMultiHopTrampoline(FiberTest):
    """
    Multi-hop trampoline: 3-hop and 4-hop keysend, different fee rates,
    UDT chain, mixed CKB/UDT (expect no path).
    """

    def test_three_hop_trampoline_routing(self):
        """
        Keysend via 3 trampoline hops (f1->f2->f3->f4->f5); expect success.
        Step 1: Create fiber3..5; open linear channels.
        Step 2: Keysend with trampoline_hops [f2,f3,f4]; wait success.
        """
        # Step 1: Create fiber3..5; open linear channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with trampoline_hops [f2,f3,f4]; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_four_hop_trampoline_routing(self):
        """
        Keysend via 4 trampoline hops (f1->...->f6); expect success.
        Step 1: Create fiber3..6; open linear channels.
        Step 2: Keysend with trampoline_hops [f2,f3,f4,f5]; wait success.
        """
        # Step 1: Create fiber3..6; open linear channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.fiber6 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber5, self.fiber6,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with trampoline_hops [f2,f3,f4,f5]; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                    self.fiber5.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_multi_hop_with_different_fee_rates(self):
        """
        Multi-hop keysend (3 hops); expect success.
        Step 1: Create fiber3..5; open linear channels.
        Step 2: Keysend 10 CKB via trampoline; wait success.
        """
        # Step 1: Create fiber3..5; open linear channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend 10 CKB via trampoline; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_multi_hop_with_udt(self):
        """
        UDT keysend via 3 trampoline hops; expect success.
        Step 1: Faucet UDT; create fiber3..5; open UDT channels.
        Step 2: UDT keysend via trampoline; wait success.
        """
        # Step 1: Faucet UDT; create fiber3..5; open UDT channels
        self.fiber3 = self.start_new_fiber(self.generate_account(50000))
        self.fiber4 = self.start_new_fiber(self.generate_account(50000))
        self.fiber5 = self.start_new_fiber(self.generate_account(50000))
        for fa in [self.fiber2, self.fiber3, self.fiber4]:
            self.faucet(
                fa.account_private, 0,
                self.fiber1.account_private, Amount.ckb(100000),
            )
        self.faucet(
            self.fiber1.account_private, 0,
            self.fiber1.account_private, Amount.ckb(100000),
        )
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )

        # Step 2: UDT keysend via trampoline; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "udt_type_script": udt_script,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_multi_hop_mixed_ckb_udt(self):
        """
        Mixed CKB/UDT chain; UDT payment via trampoline expects no path / failure.
        Step 1: Faucet; create fiber3..5; open CKB-UDT-CKB-UDT chain.
        Step 2: UDT keysend via trampoline; expect no path or failure.
        """
        # Step 1: Faucet; create fiber3..5; open CKB-UDT-CKB-UDT chain
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.faucet(
            self.fiber2.account_private, 0,
            self.fiber1.account_private, Amount.ckb(10000),
        )
        self.faucet(
            self.fiber4.account_private, 0,
            self.fiber1.account_private, Amount.ckb(10000),
        )
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber4, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            udt=udt_script,
        )

        # Step 2: UDT keysend via trampoline; expect no path or failure
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "udt_type_script": udt_script,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                        self.fiber4.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "no path found" in err or "Failed" in str(exc_info.value)
