import shutil
import time

from framework.basic_fiber import FiberTest


def input_outpoints(node, tx_hash):
    """Raw previous_output outpoints of a transaction."""
    tx = node.getClient().get_transaction(tx_hash)
    return {
        (i["previous_output"]["tx_hash"], i["previous_output"]["index"])
        for i in tx["transaction"]["inputs"]
    }


class TestFundingSkipsWatchtowerPoolCells(FiberTest):
    """
    PR-1707: a funding tx must not pick fee cells already spent by a watchtower
    tx that is still in the pool.
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    # TEST-MAP: PR1707-01
    def test_funding_skips_cells_held_by_watchtower_tx(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        # give fiber2 a second free cell so funding can proceed while the
        # watchtower tx holds the other one
        self.faucet(self.fiber2.account_private, 1000)

        # stale-commitment attack: back up fiber1 before the payment
        self.fiber1.stop()
        shutil.rmtree(f"{self.fiber1.tmp_path}/fiber.bak", ignore_errors=True)
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber", f"{self.fiber1.tmp_path}/fiber.bak"
        )
        self.fiber1.start()
        time.sleep(5)
        payment = self.fiber1.get_client().send_payment(
            {
                "amount": hex(100 * 100000000),
                "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        # roll fiber1 back to the pre-payment state and force-close -> old commitment
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
        commitment_tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, commitment_tx)

        # stop the auto miner so the watchtower tx stays in the pool and the
        # funding tx is built while it is still unconfirmed
        self.node.stop_miner()
        try:
            # fiber2's watchtower fires -> revocation tx enters the pool
            self.fiber2.start()
            revocation_tx = self.wait_and_check_tx_pool_fee(1000, False)

            self.fiber2.connect_peer(self.fiber3)
            self.fiber2.get_client().open_channel(
                {
                    "pubkey": self.fiber3.get_pubkey(),
                    "funding_amount": hex(500 * 100000000),
                    "public": True,
                }
            )

            # the pool now holds the revocation tx and the funding tx; the funding
            # tx is the one that is not the revocation tx
            self.wait_tx_pool(2, 300)
            pending = self.node.getClient().get_raw_tx_pool()["pending"]
            funding_tx_hash = [h for h in pending if h != revocation_tx]
            assert len(funding_tx_hash) == 1, f"unexpected pool contents: {pending}"
            funding_tx_hash = funding_tx_hash[0]

            shared = input_outpoints(self.node, revocation_tx) & input_outpoints(
                self.node, funding_tx_hash
            )
            assert not shared, f"funding tx reuses watchtower tx cells: {shared}"
        finally:
            self.node.start_miner()

        # everything settles: both txs commit, the new channel becomes ready
        self.Miner.miner_until_tx_committed(self.node, funding_tx_hash)
        self.Miner.miner_until_tx_committed(self.node, revocation_tx)
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_pubkey(), "ChannelReady"
        )
