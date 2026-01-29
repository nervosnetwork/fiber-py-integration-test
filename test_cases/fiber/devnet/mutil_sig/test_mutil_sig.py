"""
Test cases for multi-signature / multi-payment scenarios: UDT channel, repeated payments,
disconnect/reconnect, shutdown channel.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout


class MutilSigTestCase(FiberTest):
    """
    Test multi-signature and multi-payment flows: UDT channel, batch payments,
    disconnect/reconnect cycles, and shutdown channel.
    """
    debug = True

    def test_00000(self):
        """
        UDT channel: faucet UDT to fiber1, open UDT channel, send 10 payments without wait.
        Step 1: Faucet UDT to fiber1 account.
        Step 2: Open channel fiber1-fiber2 with UDT type script.
        Step 3: Send 10 payments (1 CKB each) without waiting.
        """
        # Step 1: Faucet UDT to fiber1 account
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )

        # Step 2: Open channel fiber1-fiber2 with UDT type script
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(0),
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )

        # Step 3: Send 10 payments (1 CKB each) without waiting
        for _ in range(10):
            self.send_payment(
                self.fiber1,
                self.fiber2,
                Amount.ckb(1),
                wait=False,
                udt=self.get_account_udt_script(self.fiber1.account_private),
            )

    def test_000001(self):
        """
        Disconnect/reconnect cycle: open UDT channel, then send 10 payments, disconnect, sleep, reconnect; repeat 10 times.
        Step 1: Faucet UDT, open UDT channel, get UDT script and fiber2 peer_id.
        Step 2: For 10 outer iterations: send 10 payments without wait, disconnect peer, sleep, reconnect, sleep.
        """
        # Step 1: Faucet UDT, open UDT channel, get UDT script and fiber2 peer_id
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.ckb(10000),
        )
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(0),
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        udt = self.get_account_udt_script(self.fiber1.account_private)
        fiber2_peer_id = self.fiber2.get_peer_id()

        # Step 2: For 10 outer iterations: send 10 payments, disconnect, sleep, reconnect, sleep
        for _ in range(10):
            for _ in range(10):
                self.send_payment(
                    self.fiber1, self.fiber2, Amount.ckb(1), wait=False, udt=udt
                )
            self.fiber1.get_client().disconnect_peer({"peer_id": fiber2_peer_id})
            time.sleep(Timeout.POLL_INTERVAL * 5)
            self.fiber1.connect_peer(self.fiber2)
            time.sleep(Timeout.POLL_INTERVAL * 5)

    def test_00022221(self):
        """
        Get tx message for given tx hashes (debug / trace).
        Step 1: Get tx message for first tx hash.
        Step 2: Get tx message for second tx hash.
        """
        # Step 1: Get tx message for first tx hash
        self.get_tx_message(
            "0x48e2479b46a2a8f0e817af92e26dcaa0975d103c5e750d62dfb8ccc7a26475da"
        )

        # Step 2: Get tx message for second tx hash
        self.get_tx_message(
            "0x85dd85357973264d6fb287ba63b5d8600f813c707d50be4778e825118a43003e"
        )

    def test_generate_epoch(self):
        """
        Generate epoch on CKB node (mining).
        Step 1: Call generate_epochs on node.
        """
        # Step 1: Call generate_epochs on node
        self.node.getClient().generate_epochs("0x2")

    def test0basad(self):
        """
        Shutdown second channel (fiber2 side) with force.
        Step 1: Get channel_id of second channel from fiber1 list_channels.
        Step 2: Call shutdown_channel on fiber2 with force=True.
        """
        # Step 1: Get channel_id of second channel from fiber1 list_channels
        channels = self.fiber1.get_client().list_channels({})

        # Step 2: Call shutdown_channel on fiber2 with force=True (second channel)
        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": channels["channels"][1]["channel_id"],
                "force": True,
            }
        )
