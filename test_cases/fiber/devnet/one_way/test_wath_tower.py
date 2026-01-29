"""
Test one-way channel with watch tower: normal shutdown and CKB/UDT balance recovery.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency
from framework.util import ckb_hash


class TestWatchTower(FiberTest):
    """
    Test watch tower behavior with one-way channels (normal shutdown and force shutdown).
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 3}

    def test_normal_shutdown(self):
        """
        One-way CKB and UDT channels: shutdown all channels and verify balance change via watch tower.
        Step 1: Faucet and record balance.
        Step 2: Open one-way CKB and UDT channels.
        Step 3: Shutdown all channels with close_script and fee_rate.
        Step 4: Wait for watch tower processing, then assert CKB and UDT balance change.
        """
        # Step 1: Faucet and record balance
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        before_balance = self.get_fibers_balance()
        # Step 2: Open one-way CKB and UDT channels
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.udt(10),
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.udt(10),
            other_config={
                "public": False,
                "one_way": True,
            },
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        # Step 3: Shutdown all channels with close_script and fee_rate
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
        # Step 4: Wait for watch tower processing, then assert CKB and UDT balance change
        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        assert abs(result[0]["ckb"] - Amount.ckb(10)) < 5000
        assert abs(result[1]["ckb"] + Amount.ckb(10)) < 5000
        assert result[0]["udt"] == Amount.udt(10)
        assert result[1]["udt"] == -Amount.udt(10)

    def test_wath_tower_ckb(self):
        """
        Force shutdown with hold invoices: CKB and UDT payments via trampoline, then settle and verify balance.
        Step 1: Start fiber3, faucet, record balance.
        Step 2: Open CKB and UDT channels (fiber1-fiber2, fiber2-fiber3 one-way).
        Step 3: Create hold invoices and send CKB and UDT payments via trampoline.
        Step 4: Force shutdown fiber1 and fiber3 channels, wait, then settle invoices.
        Step 5: Generate epochs until commit cells clear, then assert balance change.
        """
        # Step 1: Start fiber3, faucet, record balance
        self.fiber3 = self.start_new_fiber(
            self.generate_account(
                10000, self.fiber1.account_private, Amount.ckb(10000)
            )
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        before_balance = self.get_fibers_balance()
        # Step 2: Open CKB and UDT channels (fiber1-fiber2, fiber2-fiber3 one-way)
        self.open_channel(self.fiber1, self.fiber2, Amount.ckb(1000), 0)
        self.open_channel(
            self.fiber2,
            self.fiber3,
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
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            Amount.ckb(1000),
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        # Step 3: Create hold invoices and send CKB and UDT payments via trampoline
        preimage = self.generate_random_preimage()
        payment_hash = ckb_hash(preimage)
        udt_preimage = self.generate_random_preimage()
        udt_payment_hash = ckb_hash(udt_preimage)
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_hash": payment_hash,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        udt_invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "payment_hash": udt_payment_hash,
                "allow_mpp": True,
                "allow_trampoline_routing": True,
            }
        )
        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "dry_run": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                ],
            }
        )
        self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                ],
            }
        )
        self.fiber1.get_client().send_payment(
            {
                "invoice": udt_invoice["invoice_address"],
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                ],
            }
        )
        # Step 4: Force shutdown fiber1 and fiber3 channels, wait, then settle invoices
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
            {
                "payment_hash": udt_payment_hash,
                "payment_preimage": udt_preimage,
            }
        )
        self.node.getClient().generate_epochs("0x1", wait_time=0)
        while len(self.get_commit_cells()) != 0:
            time.sleep(10)
        # Step 5: Assert balance change (CKB and UDT)
        after_balance = self.get_fibers_balance()
        result = self.get_balance_change(before_balance, after_balance)
        assert abs(result[0]["ckb"] - Amount.ckb(10)) < 2 * Amount.ckb(1) + 200000
        assert abs(result[2]["ckb"] + Amount.ckb(10)) < 2 * Amount.ckb(1) + 200000
        # UDT amounts in base units (100500000 = 1.005 UDT, 100000000 = 1 UDT)
        assert result[0]["udt"] == 100500000
        assert result[1]["udt"] == -500000
        assert result[2]["udt"] == -100000000
