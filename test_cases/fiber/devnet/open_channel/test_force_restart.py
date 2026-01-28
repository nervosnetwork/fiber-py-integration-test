"""
Test open_channel and channel behavior under force restart (fiber node and CKB node).
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, Currency, PaymentStatus, Timeout


class TestForceRestart(FiberTest):
    """
    Test open_channel and channel_ready under force restart:
    1) Local fiber node force restart during open_channel
    2) Remote fiber node force restart during open_channel
    3) CKB node force restart during open_channel
    4) After channel_ready: force restart fiber/CKB and verify invoice/send_payment still work
    """

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/402")
    def test_force_restart_fiber_node_open_channel(self):
        """
        fiber1 <-> fiber2 <-> fiber3: force restart fiber1 then fiber3 during open_channel.
        Step 1: Open channel fiber1-fiber2, force restart fiber1, wait CHANNEL_READY.
        Step 2: Open channel fiber2-fiber3, force restart fiber3, wait CHANNEL_READY.
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
        self.fiber1.force_stop()
        self.fiber1.start()
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
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(200)),
                "public": True,
            }
        )
        self.fiber3.force_stop()
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
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/402")
    def test_force_restart_ckb_node_openchannel(self):
        """
        Force restart CKB node during open_channel; then wait CHANNEL_READY.
        Step 1: Open channel fiber1-fiber2, stop/start CKB node, wait CHANNEL_READY.
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
        self.node.stop()
        self.node.start()
        self.Miner.make_tip_height_number(self.node, 20)
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
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY

    def test_force_restart_channel_ready(self):
        """
        After channel_ready: force restart fiber1, fiber3, CKB; then new_invoice and send_payment succeed.
        Step 1: Open channels fiber1-fiber2 and fiber2-fiber3, wait CHANNEL_READY.
        Step 2: Force restart fiber1, verify channel still CHANNEL_READY.
        Step 3: Force restart fiber3, verify channel still CHANNEL_READY.
        Step 4: Restart CKB node, verify channel still CHANNEL_READY.
        Step 5: Create invoice and send_payment, wait payment success, assert fiber3 local_balance.
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
        self.fiber1.force_stop()
        self.fiber1.start()
        time.sleep(3)
        node_info = self.fiber2.get_client().node_info()
        assert int(node_info["peers_count"], 16) == 2
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY
        self.fiber3.force_stop()
        self.fiber3.start()
        time.sleep(3)
        node_info = self.fiber2.get_client().node_info()
        assert int(node_info["peers_count"], 16) == 2
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY
        self.node.stop()
        self.node.start()
        self.Miner.make_tip_height_number(self.node, 20)
        time.sleep(3)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["state"]["state_name"] == ChannelState.CHANNEL_READY
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "test invoice generated by node2",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_payment_state(
            self.fiber1,
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            timeout=Timeout.CHANNEL_READY,
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(10))
