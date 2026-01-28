"""
Test one-way channel with different hash algorithms (sha256, ckb_hash).
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, HashAlgorithm


class TestHash(FiberTest):
    """
    Test one-way channel payment with sha256 and ckb_hash algorithms.
    """

    def test_hash(self):
        """
        Open one-way channels and send invoice payments with sha256 and ckb_hash.
        Step 1: Open one-way CKB channels (first two).
        Step 2: Send invoice payments with sha256 (small and large amount).
        Step 3: Open another one-way channel.
        Step 4: Send invoice payments with ckb_hash (small and large amount).
        """
        # Step 1: Open one-way CKB channels (first two)
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        # Step 2: Send invoice payments with sha256 (small and large amount)
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": HashAlgorithm.SHA256},
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000) + 1,
            other_options={"allow_mpp": True, "hash_algorithm": HashAlgorithm.SHA256},
        )
        # Step 3: Open another one-way channel
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        # Step 4: Send invoice payments with ckb_hash (small and large amount)
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": "ckb_hash"},
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000) + 1,
            other_options={"allow_mpp": True, "hash_algorithm": "ckb_hash"},
        )
