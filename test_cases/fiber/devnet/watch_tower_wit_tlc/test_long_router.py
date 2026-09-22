import time

from framework.basic_fiber import FiberTest
from framework.test_fiber import FiberConfigPath
from framework.util import ckb_hash


class TestLongPath(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 3}
    fiber_version = FiberConfigPath.CURRENT_DEV

    def test_01(self):
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000), fiber_version=FiberConfigPath.CURRENT_DEV
        )
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        payment_preimages = []
        payment_hashs = []
        N = 1
        for i in range(N):
            payment_preimage = self.generate_random_preimage()
            payment_hash = ckb_hash(payment_preimage)
            invoice = self.fiber3.get_client().new_invoice(
                {
                    "amount": hex(1 * 100000000),
                    "currency": "Fibd",
                    "description": "xxx",
                    "payment_hash": payment_hash,
                    "hash_algorithm": "ckb_hash",
                }
            )
            payment_hashs.append(payment_hash)
            payment_preimages.append(payment_preimage)
            payment = self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                }
            )
        for payment_hash in payment_hashs:
            self.wait_payment_state(self.fiber1, payment_hash, "Inflight")
            self.wait_invoice_state(self.fiber3, payment_hash, "Received")

        time.sleep(10)
        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": self.fiber3.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )
        # todo : 在状态没转成closed前就直接settle invoice，就会导致链上settle tx后，节点2不转发交易
        shutdown_tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 20)
        self.Miner.miner_until_tx_committed(self.node, shutdown_tx_hash)
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber3.get_pubkey(),
            "Closed",
            include_closed=True,
        )
        for i in range(N):
            payment_preimage = payment_preimages[i]
            payment_hash = payment_hashs[i]
            self.fiber3.get_client().settle_invoice(
                {
                    "payment_hash": payment_hash,
                    "payment_preimage": payment_preimage,
                }
            )

        self.node.getClient().generate_epochs("0x1")
        for i in range(N):
            payment_hash = payment_hashs[i]
            self.wait_payment_state(self.fiber1, payment_hash, "Success", 370)

    # https://github.com/nervosnetwork/fiber/issues/1660
    def test_1660(self):
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000), fiber_version=FiberConfigPath.CURRENT_DEV
        )
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        payment_preimages = []
        payment_hashs = []
        N = 1
        for i in range(N):
            payment_preimage = self.generate_random_preimage()
            payment_hash = ckb_hash(payment_preimage)
            invoice = self.fiber3.get_client().new_invoice(
                {
                    "amount": hex(1 * 100000000),
                    "currency": "Fibd",
                    "description": "xxx",
                    "payment_hash": payment_hash,
                    "hash_algorithm": "ckb_hash",
                }
            )
            payment_hashs.append(payment_hash)
            payment_preimages.append(payment_preimage)
            payment = self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                }
            )
        for payment_hash in payment_hashs:
            self.wait_payment_state(self.fiber1, payment_hash, "Inflight")
            self.wait_invoice_state(self.fiber3, payment_hash, "Received")

        time.sleep(10)
        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": self.fiber3.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )
        time.sleep(1)
        # todo : 在状态没转成closed前就直接settle invoice，就会导致链上settle tx后，节点2不转发交易
        # shutdown_tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 20)
        # self.Miner.miner_until_tx_committed(self.node, shutdown_tx_hash)
        # self.wait_for_channel_state(
        #     self.fiber2.get_client(),
        #     self.fiber3.get_pubkey(),
        #     "Closed",
        #     include_closed=True,
        # )
        for i in range(N):
            payment_preimage = payment_preimages[i]
            payment_hash = payment_hashs[i]
            self.fiber3.get_client().settle_invoice(
                {
                    "payment_hash": payment_hash,
                    "payment_preimage": payment_preimage,
                }
            )

        self.node.getClient().generate_epochs("0x1")
        for i in range(N):
            payment_hash = payment_hashs[i]
            self.wait_payment_state(self.fiber1, payment_hash, "Success", 370)
