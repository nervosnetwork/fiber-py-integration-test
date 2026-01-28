"""
Watch tower tests for hash_algorithm (ckb_hash) with CKB and UDT channels.
Verifies balance correctness after force shutdown and watch tower split.
"""

from framework.basic_fiber import FiberTest
from framework.constants import Amount, HashAlgorithm


class TestHashAlgorithm(FiberTest):
    """
    Test watch tower behavior with hash_algorithm ckb_hash on CKB and UDT channels.
    Force shutdown after invoice payment, mine commits and split txs, then assert balances.
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_hash_algorithm(self):
        """
        CKB channel: invoice payment with ckb_hash, force shutdown, mine and split; assert CKB balance deltas.
        Step 1: Record balances for both fibers.
        Step 2: Open CKB channel, send invoice payment with hash_algorithm ckb_hash.
        Step 3: Force shutdown channel, mine shutdown and split txs.
        Step 4: Assert CKB balance changes (fiber1 −1 CKB, fiber2 +1 CKB) within tolerance.
        """
        # Step 1: Record balances for both fibers
        before_udt_balances = []
        for fiber in self.fibers:
            before_udt_balances.append(self.get_fiber_balance(fiber))

        # Step 2: Open CKB channel, send invoice payment with hash_algorithm ckb_hash
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1),
            other_options={"allow_mpp": True, "hash_algorithm": HashAlgorithm.CKB_HASH},
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )

        # Step 3: Mine shutdown and split txs
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.node.getClient().generate_epochs("0x1", 0)
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # Step 4: Assert CKB balance changes within tolerance
        after_udt_balances = []
        for fiber in self.fibers:
            after_udt_balances.append(self.get_fiber_balance(fiber))

        results = []
        for i in range(len(before_udt_balances)):
            results.append(
                {
                    "ckb": before_udt_balances[i]["chain"]["ckb"]
                    - after_udt_balances[i]["chain"]["ckb"],
                }
            )
        tolerance = 2000  # shannon
        assert abs(results[0]["ckb"] - Amount.ckb(1)) < tolerance
        assert abs(results[1]["ckb"] + Amount.ckb(1)) < tolerance

    def test_hash_algorithm_udt(self):
        """
        UDT channel: invoice payment with ckb_hash, force shutdown, mine and split; assert UDT balance deltas.
        Step 1: Faucet UDT, record balances.
        Step 2: Open UDT channel, send invoice payment with hash_algorithm ckb_hash.
        Step 3: Force shutdown, mine shutdown and split txs.
        Step 4: Assert UDT balance changes (fiber1 −1 UDT, fiber2 +1 UDT).
        """
        self.faucet(self.fiber1.account_private, 0, self.fiber1.account_private)
        before_udt_balances = []
        for fiber in self.fibers:
            before_udt_balances.append(self.get_fiber_balance(fiber))

        # Step 2: Open UDT channel, send invoice payment with ckb_hash
        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            0,
            udt=udt_script,
        )
        self.send_invoice_payment(
            self.fiber1,
            self.fiber2,
            1,
            udt=udt_script,
            other_options={"allow_mpp": True, "hash_algorithm": HashAlgorithm.CKB_HASH},
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )

        # Step 3: Mine shutdown and split txs
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        self.node.getClient().generate_epochs("0x1", 0)
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)

        # Step 4: Assert UDT balance changes
        after_udt_balances = []
        for fiber in self.fibers:
            after_udt_balances.append(self.get_fiber_balance(fiber))

        results = []
        for i in range(len(before_udt_balances)):
            results.append(
                {
                    "ckb": before_udt_balances[i]["chain"]["ckb"]
                    - after_udt_balances[i]["chain"]["ckb"],
                    "udt": before_udt_balances[i]["chain"]["udt"]
                    - after_udt_balances[i]["chain"]["udt"],
                }
            )
        assert results[0]["udt"] == 1
        assert results[1]["udt"] == -1
