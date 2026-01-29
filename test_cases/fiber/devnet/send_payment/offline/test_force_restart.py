"""
Test cases for send_payment with force restart: sender/mid/receiver node force stop and restart.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    Currency,
    HashAlgorithm,
    InvoiceStatus,
    PaymentStatus,
    Timeout,
)


class TestForceRestart(FiberTest):
    """
    Test send_payment behavior when nodes are force-restarted during or after payment.
    Scenarios: sender force restart, mid node force restart, receiver force restart.
    """

    def test_restart_node_send_payment_key_send(self):
        """
        Keysend payment after force restart of sender, mid, and receiver nodes.
        Step 1: Build fiber1->fiber2->fiber3 topology and open channels.
        Step 2: Force restart sender (fiber1), reconnect, send keysend payment.
        Step 3: Force restart mid node (fiber2), reconnect, send keysend payment.
        Step 4: Force restart receiver (fiber3), reconnect, send keysend payment.
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

        # Step 2: Force restart sender (fiber1), reconnect, send keysend payment
        self.fiber1.force_stop()
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

        # Step 3: Force restart mid node (fiber2), reconnect, send keysend payment
        self.fiber2.force_stop()
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

        # Step 4: Force restart receiver (fiber3), reconnect, send keysend payment
        self.fiber3.force_stop()
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
        Invoice payment after force restart of sender, mid, and receiver nodes.
        Step 1: Build fiber1->fiber2->fiber3 topology and open channels.
        Step 2: Force restart sender (fiber1), reconnect, send invoice payment.
        Step 3: Force restart mid node (fiber2), reconnect, send invoice payment.
        Step 4: Force restart receiver (fiber3), reconnect, send invoice payment.
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

        # Step 2: Force restart sender (fiber1), reconnect, send invoice payment
        self.fiber1.force_stop()
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

        # Step 3: Force restart mid node (fiber2), reconnect, send invoice payment
        self.fiber2.force_stop()
        self.fiber2.start()
        self.fiber2.connect_peer(self.fiber1)
        self.fiber2.connect_peer(self.fiber3)
        time.sleep(Timeout.POLL_INTERVAL * 5)
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

        # Step 4: Force restart receiver (fiber3), reconnect, send invoice payment
        self.fiber3.force_stop()
        self.fiber3.start()
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)
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

    def test_restart_when_node_send_payment_begin_node(self):
        """
        Force restart sender while multiple invoice payments are in flight; payments should finish after restart.
        Step 1: Build topology and open channels.
        Step 2: Send 10 invoice payments without waiting.
        Step 3: Force stop sender before all payments complete; assert some are pending.
        Step 4: Restart sender, reconnect, wait for all payments to finish.
        """
        # Step 1: Build topology and open channels
        account3_private = self.generate_account(1000)
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(2000)),
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
                "funding_amount": hex(Amount.ckb(2000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber3.get_peer_id(),
            ChannelState.CHANNEL_READY,
            Timeout.CHANNEL_READY,
        )

        node_info = self.fiber1.get_client().node_info()
        assert int(node_info["peers_count"], 16) >= 1

        # Step 2: Send 10 invoice payments without waiting
        for _ in range(2):
            invoices = []
            payments = []
            for _ in range(10):
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
                invoices.append(invoice["invoice_address"])
            for invoice_address in invoices:
                payment = self.fiber1.get_client().send_payment(
                    {"invoice": invoice_address}
                )
                payments.append(payment)

            # Step 3: Force stop sender before all payments complete; assert some are pending
            self.fiber1.force_stop()
            contains_pending = False
            for payment in payments:
                invoice = self.fiber3.get_client().get_invoice(
                    {"payment_hash": payment["payment_hash"]}
                )
                if invoice["status"] != InvoiceStatus.PAID:
                    contains_pending = True
            assert contains_pending is True

            # Step 4: Restart sender, reconnect, wait for all payments to finish
            self.fiber1.start()
            self.fiber1.connect_peer(self.fiber2)
            self.fiber1.connect_peer(self.fiber3)
            time.sleep(Timeout.POLL_INTERVAL * 5)
            for payment in payments:
                self.wait_payment_finished(
                    self.fiber1, payment["payment_hash"], Timeout.CHANNEL_READY
                )

    @pytest.mark.skip("Musig2RoundFinalizeError")
    def test_restart_when_node_send_payment_mid_node(self):
        """
        Force restart mid node while payments are in flight (skipped due to Musig2RoundFinalizeError).
        Step 1: Build topology with open_channel helper.
        Step 2: Send payments, force stop mid node, assert pending, restart, wait for finish.
        """
        # Step 1: Build topology with open_channel helper
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(200), Amount.ckb(1)
        )
        self.open_channel(
            self.fiber2, self.fiber3, Amount.ckb(200), Amount.ckb(1)
        )

        # Step 2: Send payments, force stop mid node, assert pending, restart, wait for finish
        for _ in range(2):
            invoices = []
            payments = []
            for _ in range(10):
                invoice = self.fiber3.get_client().new_invoice(
                    {
                        "amount": hex(Amount.ckb(10)),
                        "currency": Currency.FIBD,
                        "description": "test invoice generated by node2",
                        "expiry": "0xe1000",
                        "payment_preimage": self.generate_random_preimage(),
                        "hash_algorithm": HashAlgorithm.SHA256,
                    }
                )
                invoices.append(invoice["invoice_address"])
            for invoice_address in invoices:
                payment = self.fiber1.get_client().send_payment(
                    {"invoice": invoice_address}
                )
                payments.append(payment)
            self.fiber2.force_stop()
            contains_pending = False
            for payment in payments:
                invoice = self.fiber3.get_client().get_invoice(
                    {"payment_hash": payment["payment_hash"]}
                )
                if invoice["status"] != InvoiceStatus.PAID:
                    contains_pending = True
            assert contains_pending is True
            self.fiber2.start()
            self.fiber2.connect_peer(self.fiber1)
            self.fiber2.connect_peer(self.fiber3)
            time.sleep(Timeout.POLL_INTERVAL * 5)
            for payment in payments:
                self.wait_payment_finished(
                    self.fiber1, payment["payment_hash"], Timeout.CHANNEL_READY
                )
