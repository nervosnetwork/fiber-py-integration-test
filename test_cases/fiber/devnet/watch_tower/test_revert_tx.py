"""
Watch tower tests for revert-tx (data restore) scenarios.
Verifies revocation tx correctness after one node reverts to backup and force shutdown.
"""

import shutil
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, PaymentStatus


class TestRevertTx(FiberTest):
    """
    Test watch tower revocation tx when one node reverts to pre-payment backup.
    Backup fiber data, send payment, restore backup, force shutdown; assert revocation tx.
    """

    def test_01(self):
        """
        fiber1 reverts after backup; fiber1 sends payment; restore backup, force shutdown; fiber2 posts revocation.
        Step 1: Open channel, stop fiber1 and backup its data, then restart.
        Step 2: Send payment fiber1 -> fiber2, wait success.
        Step 3: Stop both, restore fiber1 from backup, restart fiber1, force shutdown.
        Step 4: Mine shutdown tx, restart fiber2; wait revocation tx, mine and assert tx cells.
        """
        # Step 1: Open channel, backup fiber1 data, restart
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1000),
        )
        self.fiber1.stop()
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber", f"{self.fiber1.tmp_path}/fiber.bak"
        )
        self.fiber1.start()
        time.sleep(5)

        # Step 2: Send payment fiber1 -> fiber2, wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "amount": hex(Amount.ckb(1000)),
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # Step 3: Stop both, restore fiber1 from backup, restart fiber1, force shutdown
        self.fiber1.stop()
        self.fiber2.stop()
        shutil.rmtree(f"{self.fiber1.tmp_path}/fiber")
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber.bak", f"{self.fiber1.tmp_path}/fiber"
        )
        self.fiber1.start()
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )

        # Step 4: Mine shutdown, restart fiber2, wait revocation tx and assert
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.fiber2.start()
        revocation_tx = self.wait_and_check_tx_pool_fee(1000, False, 100000000)
        tx = self.get_tx_message(revocation_tx)
        lock_arg = self.fiber2.get_account()["lock_arg"]
        assert tx["input_cells"][1]["args"] == lock_arg
        assert tx["output_cells"][0]["args"] == lock_arg
        assert tx["output_cells"][1]["args"] == lock_arg
        assert tx["input_cells"][0]["capacity"] == tx["output_cells"][0]["capacity"]

    def test_02(self):
        """
        fiber1 reverts after backup; fiber2 sends payment; restore backup, force shutdown; fiber2 posts revocation.
        Step 1: Open channel, backup fiber1 data, restart.
        Step 2: Send payment fiber2 -> fiber1, wait success.
        Step 3: Stop both, restore fiber1 from backup, restart fiber1, force shutdown.
        Step 4: Mine shutdown tx, restart fiber2; wait revocation tx, mine and assert tx cells.
        """
        # Step 1: Open channel, backup fiber1 data, restart
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1000),
        )
        self.fiber1.stop()
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber", f"{self.fiber1.tmp_path}/fiber.bak"
        )
        self.fiber1.start()
        time.sleep(5)

        # Step 2: Send payment fiber2 -> fiber1, wait success
        payment = self.fiber2.get_client().send_payment(
            {
                "amount": hex(Amount.ckb(1000)),
                "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber2, payment["payment_hash"], PaymentStatus.SUCCESS
        )

        # Step 3: Stop both, restore fiber1 from backup, restart fiber1, force shutdown
        self.fiber1.stop()
        self.fiber2.stop()
        shutil.rmtree(f"{self.fiber1.tmp_path}/fiber")
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber.bak", f"{self.fiber1.tmp_path}/fiber"
        )
        self.fiber1.start()
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )

        # Step 4: Mine shutdown, restart fiber2, wait revocation tx and assert
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.fiber2.start()
        revocation_tx = self.wait_and_check_tx_pool_fee(1000, False, 100000000)
        tx = self.get_tx_message(revocation_tx)
        lock_arg = self.fiber2.get_account()["lock_arg"]
        assert tx["input_cells"][1]["args"] == lock_arg
        assert tx["output_cells"][0]["args"] == lock_arg
        assert tx["output_cells"][1]["args"] == lock_arg
        assert tx["input_cells"][0]["capacity"] == tx["output_cells"][0]["capacity"]
