"""
Trampoline routing tests: MPP + trampoline (one-way, no path; ckb_hash/sha256 success).
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, HashAlgorithm, PaymentStatus, Timeout


class TestMpp(FiberTest):
    """
    MPP + trampoline: invoice with allow_mpp and allow_trampoline_routing;
    one-way topology yields no path; ckb_hash/sha256 invoice pay via trampoline succeed.
    """

    def test_mpp_with_oneway(self):
        """
        MPP + trampoline with one-way channels; expect no path.
        Step 1: Create fiber3..4; open one-way f1->f2, f1-f2, f2-f3, f2-f4, f3-f4, f1-f4.
        Step 2: New invoice (allow_mpp, allow_trampoline_routing); send_payment via trampoline; expect no path.
        """
        # Step 1: Create fiber3..4; open channels including one-way
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False, "one_way": True},
        )
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False},
        )
        self.open_channel(
            self.fiber2, self.fiber4,
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
            self.fiber1, self.fiber4,
            fiber1_balance=Amount.ckb(5000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Invoice with allow_mpp + allow_trampoline_routing; pay via trampoline; expect no path
        invoice = self.fiber4.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1500)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_hash": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
        assert "no path found" in (exc_info.value.args[0] if exc_info.value.args else ""), (
            "Expected 'no path found' in error."
        )

    def test_mpp_with_oneway_ckb_hash(self):
        """
        MPP + trampoline with ckb_hash invoice; pay via trampoline; expect success.
        Step 1: Create fiber3..4; open channels (no one-way on f1-f2).
        Step 2: New invoice (ckb_hash, allow_mpp, allow_trampoline_routing); pay via trampoline; wait success.
        """
        # Step 1: Create fiber3..4; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(3000), fiber2_balance=Amount.ckb(0),
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
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber1, self.fiber4,
            fiber1_balance=Amount.ckb(5000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Invoice (ckb_hash, allow_mpp, allow_trampoline_routing); pay via trampoline; wait success
        invoice = self.fiber4.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1001)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.CKB_HASH,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(Amount.ckb(1000)),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_mpp_with_oneway_hash_algorithm_sha256(self):
        """
        MPP + trampoline with sha256 invoice; pay via trampoline; expect success.
        Step 1: Create fiber3..4; open channels (one-way f1->f2).
        Step 2: New invoice (sha256, allow_mpp, allow_trampoline_routing); pay via trampoline; wait success.
        """
        # Step 1: Create fiber3..4; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(3000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False, "one_way": True},
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
            other_config={"public": False},
        )
        self.open_channel(
            self.fiber2, self.fiber4,
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
            self.fiber1, self.fiber4,
            fiber1_balance=Amount.ckb(5000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Invoice (sha256, allow_mpp, allow_trampoline_routing); pay via trampoline; wait success
        invoice = self.fiber4.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1001)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(Amount.ckb(1000)),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
