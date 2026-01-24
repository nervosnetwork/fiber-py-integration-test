from framework.basic_fiber import FiberTest


class TestHashAlgorithm(FiberTest):

    def test_ckbHash(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        # key send
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        # "fee_rate": hex((1 << 64) - 1),
                    },
                ],
                "hash_algorithm": "ckbhash",
            }
        )

    def test_sha256(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        # key send
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        # "fee_rate": hex((1 << 64) - 1),
                    },
                ],
                "hash_algorithm": "ckbhash",
            }
        )
