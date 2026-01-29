"""
Test cases for send_payment with graceful restart: sender/mid/receiver node stop and start.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    Currency,
    HashAlgorithm,
    PaymentStatus,
    Timeout,
)


class TestRestart(FiberTest):
    """
    Test send_payment behavior when nodes are gracefully restarted (stop/start).
    Scenarios: sender restart, mid node restart, receiver restart.
    """

    def test_restart_node_send_payment_key_send(self):
        """
        Keysend payment after graceful restart of sender, mid, and receiver nodes.
        Step 1: Build fiber1->fiber2->fiber3 topology and open channels.
        Step 2: Restart sender (fiber1), reconnect, send keysend payment.
        Step 3: Restart mid node (fiber2), reconnect, send keysend payment.
        Step 4: Restart receiver (fiber3), reconnect, send keysend payment.
        Step 5: Assert cumulative balance at receiver.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology and open channels
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
            Timeout.CHANNEL_READY,
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
            Timeout.CHANNEL_READY,
        )

        # Step 2: Restart sender (fiber1), reconnect, send keysend payment
        self.fiber1.stop()
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        self.fiber1.connect_peer(self.fiber3)
        time.sleep(Timeout.POLL_INTERVAL * 5)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        node3_info = self.fiber3.get_client().node_info()
        fiber3_pub = node3_info["node_id"]
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": fiber3_pub,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(10))

        # Step 3: Restart mid node (fiber2), reconnect, send keysend payment
        self.fiber2.stop()
        self.fiber2.start()
        self.fiber2.connect_peer(self.fiber1)
        self.fiber2.connect_peer(self.fiber3)
        time.sleep(Timeout.POLL_INTERVAL * 5)
        node_info = self.fiber2.get_client().node_info()
        assert node_info["peers_count"] == "0x2"
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": fiber3_pub,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(20))

        # Step 4: Restart receiver (fiber3), reconnect, send keysend payment
        self.fiber3.stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber2)
        self.fiber3.connect_peer(self.fiber1)
        time.sleep(Timeout.POLL_INTERVAL * 5)
        node_info = self.fiber3.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": fiber3_pub,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )

        # Step 5: Assert cumulative balance at receiver
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(30))

    def test_restart_node_send_payment_invoice(self):
        """
        Invoice payment after graceful restart of sender, mid, and receiver nodes.
        Step 1: Build fiber1->fiber2->fiber3 topology and open channels.
        Step 2: Restart sender (fiber1), reconnect, send invoice payment.
        Step 3: Restart mid node (fiber2), reconnect, send invoice payment.
        Step 4: Restart receiver (fiber3), reconnect, send invoice payment.
        Step 5: Assert cumulative balance at receiver.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology and open channels
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
            Timeout.CHANNEL_READY,
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
            Timeout.CHANNEL_READY,
        )

        # Step 2: Restart sender (fiber1), reconnect, send invoice payment
        self.fiber1.stop()
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        self.fiber1.connect_peer(self.fiber3)
        time.sleep(3)
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
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
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(10))

        # Step 3: Restart mid node (fiber2), reconnect, send invoice payment
        self.fiber2.stop()
        self.fiber2.start()
        self.fiber2.connect_peer(self.fiber1)
        self.fiber2.connect_peer(self.fiber3)
        time.sleep(3)
        node_info = self.fiber2.get_client().node_info()
        assert node_info["peers_count"] == "0x2"
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
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(20))

        # Step 4: Restart receiver (fiber3), reconnect, send invoice payment
        self.fiber3.stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber2)
        self.fiber3.connect_peer(self.fiber1)
        time.sleep(3)
        node_info = self.fiber3.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
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
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )

        # Step 5: Assert cumulative balance at receiver
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(30))

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/696")
    def test_send_stop(self):
        """
        Send payment, stop receiver, restart, send another payment (skipped due to issue 696).
        Step 1: Build topology and open channels.
        Step 2: Send first payment, stop receiver, restart, send second payment.
        """
        # Step 1: Build topology and open channels
        account3_private = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private)
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.fiber2, self.fiber3, Amount.ckb(1000), Amount.ckb(1000)
        )

        # Step 2: Send first payment, stop receiver, restart, send second payment
        self.send_payment(self.fiber1, self.fiber3, Amount.ckb(1))
        self.fiber3.stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber2)
        self.fiber3.connect_peer(self.fiber1)
        self.send_payment(self.fiber1, self.fiber3, Amount.ckb(2))

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/363")
    def test_restart_when_node_send_payment(self):
        """
        Restart sender/mid/receiver while payment is in flight; payment should complete after restart.
        Step 1: Build topology and open channels.
        Step 2: Send payment, stop sender during flight, restart, wait for success.
        Step 3: Send payment, stop mid node during flight, restart, wait for success.
        Step 4: Send payment, stop receiver during flight, restart, wait for finish.
        """
        # Step 1: Build topology and open channels
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
            Timeout.CHANNEL_READY,
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
            Timeout.CHANNEL_READY,
        )

        # Step 2: Send payment, stop sender during flight, restart, wait for success
        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
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
        time.sleep(1)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.fiber1.stop()
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        self.fiber1.connect_peer(self.fiber3)
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(10))

        # Step 3: Send payment, stop mid node during flight, restart, wait for success
        node_info = self.fiber2.get_client().node_info()
        assert node_info["peers_count"] == "0x2"
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
        time.sleep(5)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.fiber2.stop()
        self.fiber2.start()
        self.fiber2.connect_peer(self.fiber1)
        self.fiber2.connect_peer(self.fiber3)
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.CHANNEL_READY
        )
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(Amount.ckb(20))

        # Step 4: Send payment, stop receiver during flight, restart, wait for finish
        node_info = self.fiber3.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1
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
        time.sleep(5)
        payment = self.fiber1.get_client().send_payment(
            {"invoice": invoice["invoice_address"]}
        )
        self.fiber3.stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber2)
        self.fiber3.connect_peer(self.fiber1)
        self.wait_payment_finished(
            self.fiber1, payment["payment_hash"], Timeout.CHANNEL_READY
        )
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
