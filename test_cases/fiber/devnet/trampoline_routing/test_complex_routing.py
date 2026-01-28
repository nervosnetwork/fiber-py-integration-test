"""
Trampoline routing tests: star topology, mesh topology, alternating CKB/UDT,
private channels, one-way channels, round-trip routing.
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestComplexRouting(FiberTest):
    """
    Complex trampoline routing: star, mesh, CKB/UDT mix, private/one-way channels,
    round-trip. Uses FiberTest (per-test env).
    """

    def test_star_topology_routing(self):
        """
        Star topology: fiber1->fiber2->{fiber3,fiber4,fiber5}; pay to each via trampoline.
        Step 1: Create fiber3..5 and open star channels.
        Step 2: Send keysend to each target via trampoline; wait success.
        """
        # Step 1: Create fiber3..5 and open star channels
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
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber5,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Send keysend to each target via trampoline; wait success
        for target in [self.fiber3, self.fiber4, self.fiber5]:
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": target.get_client().node_info()["node_id"],
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

    def test_mesh_topology_routing(self):
        """
        Mesh topology: multiple paths to same target; pay via two trampoline paths.
        Step 1: Create fiber3..4 and open mesh channels.
        Step 2: Pay via path fiber1->f2->f4; wait success.
        Step 3: Pay via path fiber1->f3->f4; wait success.
        """
        # Step 1: Create fiber3..4 and open mesh channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber1, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Pay via path fiber1->f2->f4; wait success
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment1["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 3: Pay via path fiber1->f3->f4; wait success
        payment2 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber3.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment2["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_alternating_ckb_udt_channels(self):
        """
        Alternating CKB/UDT channels; UDT payment through mixed types should fail.
        Step 1: Create fiber3..4, faucet, open CKB-UDT-CKB chain.
        Step 2: Send UDT payment via trampoline; expect no path / failure.
        """
        # Step 1: Create fiber3..4, faucet, open CKB-UDT-CKB chain
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
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

        # Step 2: Send UDT payment via trampoline; expect no path / failure
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "udt_type_script": udt_script,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "no path found" in err or "Failed" in str(exc_info.value)

    def test_private_channel_routing(self):
        """
        Private channels; pay via trampoline through private hops.
        Step 1: Create fiber3..4; open private f1-f2, f2-f3; public f3-f4.
        Step 2: Keysend via trampoline; wait success.
        """
        # Step 1: Create fiber3..4; open private f1-f2, f2-f3; public f3-f4
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False},
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False},
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend via trampoline; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_one_way_channel_routing(self):
        """
        One-way channels; pay via trampoline in correct direction.
        Step 1: Create fiber3; open one-way f1->f2, f2->f3.
        Step 2: Keysend via trampoline; wait success.
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
        )

        # Step 2: Keysend via trampoline; wait success
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

    def test_round_trip_routing(self):
        """
        Round-trip: fiber1->f2->f3 and fiber3->f2->f1 via same trampoline.
        Step 1: Create fiber3; open f1-f2, f2-f3, f3-f2.
        Step 2: Pay f1->f3 via trampoline; wait success.
        Step 3: Pay f3->f1 via trampoline; wait success.
        """
        # Step 1: Create fiber3; open f1-f2, f2-f3, f3-f2
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Pay f1->f3 via trampoline; wait success
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment1["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 3: Pay f3->f1 via trampoline; wait success
        payment2 = self.fiber3.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber3, payment2["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
