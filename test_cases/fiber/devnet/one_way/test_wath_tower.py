import time

from framework.basic_fiber import FiberTest
from framework.util import ckb_hash


class TestWatchTower(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 3}

    def test_normal_shutdown(self):
        """
        发送1笔交易
        Returns:
        """
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        before_balance = self.get_fibers_balance()
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            1000 * 1000000,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            1000 * 1000000,
            other_config={
                "public": False,
                "one_way": True,
            },
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )

        for channel in self.fiber1.get_client().list_channels({})["channels"]:
            self.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": channel["channel_id"],
                    "close_script": self.get_account_script(
                        self.fiber1.account_private
                    ),
                    "fee_rate": "0x3FC",
                }
            )
        time.sleep(10)
        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        print("result:", result)
        assert abs(result[0]["ckb"] - 1000000000) < 5000
        assert abs(result[1]["ckb"] + 1000000000) < 5000

        assert result[0]["udt"] == 1000000000
        assert result[1]["udt"] == -1000000000

    def test_wath_tower_ckb(self):
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, 10000 * 100000000)
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )

        before_balance = self.get_fibers_balance()
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(
            self.fiber2,
            self.fiber3,
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
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        # send hold invoice

        preimage = self.generate_random_preimage()
        payment_hash = ckb_hash(preimage)

        udt_preimage = self.generate_random_preimage()
        udt_payment_hash = ckb_hash(udt_preimage)

        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibd",
                "description": "test invoice",
                # "expiry": hex(15),
                "payment_hash": payment_hash,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )

        udt_invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "test invoice",
                # "expiry": hex(15),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "payment_hash": udt_payment_hash,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        # fiber1 send
        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )

        self.fiber1.get_client().send_payment(
            {
                "invoice": udt_invoice["invoice_address"],
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        # fiber1 force shutdown
        time.sleep(1)
        for channel in self.fiber1.get_client().list_channels({})["channels"]:
            self.fiber1.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )

        for channel in self.fiber3.get_client().list_channels({})["channels"]:
            self.fiber3.get_client().shutdown_channel(
                {"channel_id": channel["channel_id"], "force": True}
            )

        time.sleep(10)
        self.fiber3.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        self.fiber3.get_client().settle_invoice(
            {"payment_hash": udt_payment_hash, "payment_preimage": udt_preimage}
        )
        self.node.getClient().generate_epochs("0x1", wait_time=0)
        while len(self.get_commit_cells()) != 0:
            time.sleep(10)

        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        print("result:", result)
        # result: [
        # {'ckb': 100301863, 'udt': 0},
        # todo 后面手续费会变 {'ckb': -296501, 'udt': 0},
        # {'ckb': -99997964, 'udt': 0}]
        assert abs(result[0]["ckb"] - 1000000000) < 2 * 100000000
        assert abs(result[2]["ckb"] + 1000000000) < 2 * 100000000 + 200000

        assert result[0]["udt"] == 100300200
        assert result[1]["udt"] == -300200
        assert result[2]["udt"] == -100000000
