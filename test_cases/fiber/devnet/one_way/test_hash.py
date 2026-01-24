from framework.basic_fiber import FiberTest


class TestHash(FiberTest):

    def test_hash(self):
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": "sha256"},
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1000 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": "sha256"},
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )

        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": "ckb_hash"},
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1000 * 100000001,
            other_options={"allow_mpp": True, "hash_algorithm": "ckb_hash"},
        )
