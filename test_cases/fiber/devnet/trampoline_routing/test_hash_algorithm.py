"""
Trampoline routing tests: send_payment with hash_algorithm ckb_hash / sha256.
"""

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, HashAlgorithm, PaymentStatus, Timeout


class TestHashAlgorithm(FiberTest):
    """
    Trampoline keysend with hash_algorithm ckb_hash or sha256; expect success.
    """

    def test_ckb_hash(self):
        """
        Keysend via trampoline with hash_algorithm=ckb_hash; expect success.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with hash_algorithm ckb_hash; wait success.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with hash_algorithm ckb_hash; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                "hash_algorithm": HashAlgorithm.CKB_HASH,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_sha256(self):
        """
        Keysend via trampoline with hash_algorithm=sha256; expect success.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with hash_algorithm sha256; wait success.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with hash_algorithm sha256; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )
