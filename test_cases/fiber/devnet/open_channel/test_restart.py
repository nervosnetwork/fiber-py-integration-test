"""
Test open_channel with node restart: fiber restart during open, CKB restart, channel_ready then restart and payment.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Currency, HashAlgorithm, PaymentStatus, Timeout


class TestRestart(FiberTest):
    """
    Test open_channel resilience to restarts: our node restart during open, peer restart during open,
    CKB node restart during open; channel_ready then restart fiber/CKB and verify payment still works.
    """

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/402")
    def test_restart_fiber_node_open_channel(self):
        """
        fiber1 <-> fiber2 <-> fiber3: restart fiber1/fiber2 during open_channel; then open fiber2-fiber3 and restart fiber3.
        Step 1: Open channel fiber1-fiber2; wait AWAITING_TX_SIGNATURES; restart fiber1 and fiber2; wait CHANNEL_READY.
        Step 2: Open channel fiber2-fiber3; restart fiber3; wait CHANNEL_READY.
        """
        # Step 1: Open channel fiber1-fiber2; restart during open
        account3_private = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            {
                "state_name": "AWAITING_TX_SIGNATURES",
                "state_flags": "OUR_TX_SIGNATURES_SENT | THEIR_TX_SIGNATURES_SENT",
            },
            timeout=Timeout.CHANNEL_READY,
        )
        self.fiber1.stop()
        self.fiber1.start()
        self.fiber2.stop()
        self.fiber2.start()
        time.sleep(3)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

        # Step 2: Open channel fiber2-fiber3; restart fiber3 during open
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber3.stop()
        self.fiber3.start()
        time.sleep(3)
        node_info = self.fiber2.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/402")
    def test_restart_ckb_node_openchannel(self):
        """
        CKB node restart during open_channel: channel should still reach CHANNEL_READY.
        Step 1: Open channel fiber1-fiber2; stop CKB, start CKB, mine; wait CHANNEL_READY.
        """
        account3_private = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        self.node.stop()
        time.sleep(5)
        self.node.start()
        for i in range(20):
            self.Miner.miner_with_version(self.node, "0x0")
        time.sleep(3)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/938")
    def test_restart_before_open_channel(self):
        """
        (Skipped) CKB stopped before open_channel; then start CKB and wait CHANNEL_READY.
        """
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL)
        self.node.stop()
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        time.sleep(5)
        self.node.start()
        self.node.start_miner()
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

    def test_restart_channel_ready(self):
        """
        After CHANNEL_READY: restart fiber1, fiber3, then CKB; then send payment and assert channel still valid.
        Step 1: Open fiber1-fiber2 and fiber2-fiber3; restart fiber1, reconnect; assert CHANNEL_READY.
        Step 2: Restart fiber3, reconnect; assert CHANNEL_READY.
        Step 3: Restart CKB; assert CHANNEL_READY.
        Step 4: Send payment fiber1 -> fiber3; assert local_balance.
        """
        account3_private = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 1: Restart fiber1 and fiber2; reconnect; assert CHANNEL_READY
        self.fiber1.stop()
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        self.fiber2.connect_peer(self.fiber3)
        time.sleep(5)
        node_info = self.fiber2.get_client().node_info()
        assert int(node_info["peers_count"], 16) == 2
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

        # Step 2: Restart fiber3; reconnect; assert CHANNEL_READY
        self.fiber3.stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)
        time.sleep(3)
        node_info = self.fiber2.get_client().node_info()
        assert int(node_info["peers_count"], 16) == 2
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

        # Step 3: Restart CKB
        self.node.stop()
        self.node.start()
        for i in range(20):
            self.Miner.miner_with_version(self.node, "0x0")
        time.sleep(3)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

        # Step 4: Send payment fiber1 -> fiber3; assert balance
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "test invoice generated by node2",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, 120
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(10))

    def test_restart_with_open_n_channel(self):
        """
        Multiple fibers open many channels to fiber1; restart fiber1; assert all channels CHANNEL_READY.
        Step 1: Start 5 more fibers; connect each to fiber1; open channels in loop (10 rounds).
        Step 2: Restart fiber1; wait; assert every channel is CHANNEL_READY.
        """
        for i in range(5):
            self.start_new_fiber(self.generate_account(100000))
        for i in range(1, 7):
            self.fiber1.connect_peer(self.fibers[i])
        time.sleep(Timeout.POLL_INTERVAL)
        fiber1_peer_id = self.fiber1.get_peer_id()
        for j in range(10):
            for i in range(1, 7):
                self.fibers[i].get_client().open_channel(
                    {
                        "peer_id": fiber1_peer_id,
                        "funding_amount": hex(Amount.ckb(1000)),
                        "public": True,
                    }
                )
            time.sleep(Timeout.FAST_POLL_INTERVAL)
        time.sleep(2)
        self.fiber1.stop()
        self.fiber1.start()
        time.sleep(30)
        for fiber in self.fibers:
            channels = fiber.get_client().list_channels({})
            for channel in channels["channels"]:
                assert channel["state"]["state_name"] == "CHANNEL_READY"
