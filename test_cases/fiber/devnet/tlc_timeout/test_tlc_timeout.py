"""
Test cases for TLC timeout: hold invoice expiry, mid-node shutdown, remote node shutdown.
Covers: remote node timeout, mid-node shutdown when d no expiry / d expiry, remote node shutdown.
"""
import time
from datetime import datetime

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    Timeout,
    ChannelState,
    PaymentStatus,
    Currency,
    FeeRate,
)
from framework.util import change_time


class TestTlcTimeout(FiberTest):
    """
    Test TLC timeout: hold invoice not settled, time advance, payment fails and TLC removed.
    Scenarios: remote node timeout, mid-node shutdown (d no expiry / d expiry), remote node shutdown.
    """

    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    @classmethod
    def teardown_class(cls):
        cls.restore_time()
        super().teardown_class(cls)

    def test_remote_node_timeout(self):
        router_length = 2
        for i in range(router_length):
            account_private = self.generate_account(10000)
            fiber = self.start_new_fiber(account_private)
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)
        for i in range(len(self.fibers) - 1):
            linked_fiber = self.fibers[(i + 1) % len(self.fibers)]
            current_fiber = self.fibers[i]
            linked_fiber.connect_peer(current_fiber)
            time.sleep(1)
            # open channel
            current_fiber.get_client().open_channel(
                {
                    "peer_id": linked_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                current_fiber.get_client(),
                linked_fiber.get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        time.sleep(1)

        invoice = (
            self.fibers[-1]
            .get_client()
            .new_invoice(
                {
                    "amount": hex(Amount.ckb(1)),
                    "currency": Currency.FIBD,
                    "description": "expired hold invoice",
                    "payment_hash": self.generate_random_preimage(),
                }
            )
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(10)

        # Get TLC expiry and advance time so TLC can be removed
        tlc = self.get_pending_tlc(self.fibers[-1], payment["payment_hash"])
        tlc_seconds = tlc["Inbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        change_time(hour, minutes)
        self.node.getClient().generate_epochs("0x1")
        time.sleep(10)

        begin_time = time.time()
        while (
            self.get_fiber_balance(self.fiber1)
            .get("ckb", {"offered_tlc_balance": 0})
            .get("offered_tlc_balance")
            > 0
        ):
            time.sleep(10)
        time.sleep(5)
        fiber1_balance = self.get_fiber_balance(self.fiber1)
        assert fiber1_balance["ckb"]["offered_tlc_balance"] == 0, (
            "fiber1 offered_tlc_balance should be 0 after TLC timeout"
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.FAILED
        )

    def test_mid_node_shutdown_when_d_no_expiry(self):
        """
        Topology a-b-c-d; b-c force shutdown. When d inbound near expiry: c-d remove_tlc off-chain;
        b-c settle TLC on-chain; a-b remove_tlc off-chain. Payment fails, TLC cleared.
        Step 1: Build linear chain, open channels, send hold-invoice payment.
        Step 2: Force shutdown b-c, wait CLOSED; advance time; wait offered_tlc_balance 0 on fiber1.
        Step 3: Assert channel a-b still exists and payment TLC cleared.
        """
        router_length = 2
        for i in range(router_length):
            account_private = self.generate_account(10000)
            fiber = self.start_new_fiber(account_private)
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)
        for i in range(len(self.fibers) - 1):
            linked_fiber = self.fibers[(i + 1) % len(self.fibers)]
            current_fiber = self.fibers[i]
            linked_fiber.connect_peer(current_fiber)
            time.sleep(1)
            # open channel
            current_fiber.get_client().open_channel(
                {
                    "peer_id": linked_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                current_fiber.get_client(),
                linked_fiber.get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        time.sleep(1)

        invoice = (
            self.fibers[-1]
            .get_client()
            .new_invoice(
                {
                    "amount": hex(Amount.ckb(1)),
                    "currency": Currency.FIBD,
                    "description": "expired hold invoice",
                    "payment_hash": self.generate_random_preimage(),
                }
            )
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(10)

        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": self.fiber2.get_client().list_channels(
                    {"peer_id": self.fibers[2].get_peer_id()}
                )["channels"][0]["channel_id"],
                "force": True,
            }
        )
        shutdown_tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, shutdown_tx)
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fibers[2].get_peer_id(),
            ChannelState.CLOSED,
            320,
            include_closed=True,
        )
        self.wait_for_channel_state(
            self.fibers[2].get_client(),
            self.fibers[1].get_peer_id(),
            ChannelState.CLOSED,
            320,
            include_closed=True,
        )

        tlc = self.get_pending_tlc(self.fibers[-1], payment["payment_hash"])
        tlc_seconds = tlc["Inbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        change_time(hour, minutes)
        self.node.getClient().generate_epochs("0x1")
        time.sleep(10)

        begin_time = time.time()
        while (
            self.get_fiber_balance(self.fibers[-2])
            .get("ckb", {"offered_tlc_balance": 0})
            .get("offered_tlc_balance")
            > 0
        ):
            time.sleep(10)
        tlc = self.get_pending_tlc(self.fiber1, payment["payment_hash"])
        tlc_seconds = tlc["Outbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        latest_commit_tx_number = self.get_latest_commit_tx_number()
        self.add_time_and_generate_epoch(hour, 1)
        time.sleep(20)
        new_latest_commit_tx_number = self.get_latest_commit_tx_number()
        assert new_latest_commit_tx_number != latest_commit_tx_number, (
            "New commit tx should appear after time advance"
        )
        for i in range(70):
            if (
                self.get_fiber_balance(self.fiber1)
                .get("ckb", {"offered_tlc_balance": 0})
                .get("offered_tlc_balance")
                == 0
            ):
                channels = self.fiber1.get_client().list_channels(
                    {"peer_id": self.fiber2.get_peer_id()}
                )["channels"]
                assert len(channels) == 1, "Channel a-b should still exist"
                return
            time.sleep(1)
        raise Exception("timeout waiting for offered_tlc_balance 0")

    def test_mid_node_shutdown_when_d_expiry(self):
        """
        Topology a-b-c-d; b-c force shutdown. When d inbound already expired: c-d remove_tlc off-chain;
        b-c settle TLC on-chain; a-b remove_tlc off-chain. Payment fails, TLC cleared.
        Step 1: Build linear chain, open channels, send hold-invoice payment, force shutdown b-c.
        Step 2: Advance time; wait offered_tlc_balance 0 on fibers[-2]; then advance for outbound; assert commit tx.
        Step 3: Wait offered_tlc_balance 0 on fiber1; assert channel a-b still exists.
        """
        router_length = 2
        for i in range(router_length):
            account_private = self.generate_account(10000)
            fiber = self.start_new_fiber(account_private)
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)
        for i in range(len(self.fibers) - 1):
            linked_fiber = self.fibers[(i + 1) % len(self.fibers)]
            current_fiber = self.fibers[i]
            linked_fiber.connect_peer(current_fiber)
            time.sleep(1)
            # open channel
            current_fiber.get_client().open_channel(
                {
                    "peer_id": linked_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                current_fiber.get_client(),
                linked_fiber.get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        time.sleep(1)

        invoice = (
            self.fibers[-1]
            .get_client()
            .new_invoice(
                {
                    "amount": hex(Amount.ckb(1)),
                    "currency": Currency.FIBD,
                    "description": "expired hold invoice",
                    "payment_hash": self.generate_random_preimage(),
                }
            )
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(10)

        self.fiber2.get_client().shutdown_channel(
            {
                "channel_id": self.fiber2.get_client().list_channels(
                    {"peer_id": self.fibers[2].get_peer_id()}
                )["channels"][0]["channel_id"],
                "force": True,
            }
        )

        tlc = self.get_pending_tlc(self.fibers[-1], payment["payment_hash"])
        tlc_seconds = tlc["Inbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        change_time(hour, minutes)
        self.node.getClient().generate_epochs("0x1")
        time.sleep(10)

        begin_time = time.time()
        while (
            self.get_fiber_balance(self.fibers[-2])
            .get("ckb", {"offered_tlc_balance": 0})
            .get("offered_tlc_balance")
            > 0
        ):
            time.sleep(10)
        tlc = self.get_pending_tlc(self.fiber1, payment["payment_hash"])
        tlc_seconds = tlc["Outbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        latest_commit_tx_number = self.get_latest_commit_tx_number()
        self.add_time_and_generate_epoch(hour, 1)
        time.sleep(20)
        new_latest_commit_tx_number = self.get_latest_commit_tx_number()
        assert new_latest_commit_tx_number != latest_commit_tx_number, (
            "New commit tx should appear after time advance"
        )
        for i in range(70):
            if (
                self.get_fiber_balance(self.fiber1)
                .get("ckb", {"offered_tlc_balance": 0})
                .get("offered_tlc_balance")
                == 0
            ):
                channels = self.fiber1.get_client().list_channels(
                    {"peer_id": self.fiber2.get_peer_id()}
                )["channels"]
                assert len(channels) == 1, "Channel a-b should still exist"
                return
            time.sleep(1)
        raise Exception("timeout waiting for offered_tlc_balance 0")

    def test_remote_node_shutdown(self):
        """
        Topology a-b-c-d; node d offline. When c-d inbound expired, c force shutdown and settle_tlc on-chain;
        b-c and a-b remove TLC off-chain. Assert offered_tlc_balance 0 on c and fiber1.
        """
        router_length = 2
        for i in range(router_length):
            account_private = self.generate_account(10000)
            fiber = self.start_new_fiber(account_private)
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)
        for i in range(len(self.fibers) - 1):
            linked_fiber = self.fibers[(i + 1) % len(self.fibers)]
            current_fiber = self.fibers[i]
            linked_fiber.connect_peer(current_fiber)
            time.sleep(1)
            # open channel
            current_fiber.get_client().open_channel(
                {
                    "peer_id": linked_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(1000)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                current_fiber.get_client(),
                linked_fiber.get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        time.sleep(1)

        invoice = (
            self.fibers[-1]
            .get_client()
            .new_invoice(
                {
                    "amount": hex(Amount.ckb(1)),
                    "currency": Currency.FIBD,
                    "description": "expired hold invoice",
                    # "expiry": "expiry_hex",
                    "payment_hash": self.generate_random_preimage(),
                    # "hash_algorithm": "sha256",
                }
            )
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
            }
        )
        time.sleep(10)
        self.fibers[-1].stop()

        tlc = self.get_pending_tlc(self.fibers[-2], payment["payment_hash"])
        tlc_seconds = tlc["Inbound"][0]["expiry_seconds"]
        tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
        hour = int(tlc_seconds / (60 * 60))
        minutes = int(tlc_seconds / 60 % 60)
        change_time(hour, 0)
        self.node.getClient().generate_epochs("0x1", 0)
        shutdown_tx_hash = self.wait_and_check_tx_pool_fee(
            FeeRate.DEFAULT, False, 60 * 5
        )
        self.Miner.miner_until_tx_committed(self.node, shutdown_tx_hash)
        self.node.getClient().generate_epochs("0x1", 0)
        settle_tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, shutdown_tx_hash)
        time.sleep(100)
        balance = self.get_fiber_balance(self.fibers[-2])
        assert balance["ckb"]["offered_tlc_balance"] == 0
        time.sleep(1)
        balance = self.get_fiber_balance(self.fiber1)
        assert balance["ckb"]["offered_tlc_balance"] == 0

    @pytest.mark.skip(reason="Long running: multiple paths and time advance")
    def test_remove_tlc_mix(self):
        """
        Two paths a-b-c-d-e and h-j-k-d-e-f; payments a->e and h->f; force shutdown d-e.
        Expect: a-b-c-d, e-f, h-j-k-d remove TLC on timeout without force shutdown.
        """
        self.nodeA = self.fiber1
        self.nodeB = self.fiber2
        #
        self.nodeC = self.start_new_fiber(self.generate_account(10000))
        self.nodeD = self.start_new_fiber(self.generate_account(10000))
        self.nodeE = self.start_new_fiber(self.generate_account(10000))
        self.nodeF = self.start_new_fiber(self.generate_account(10000))
        self.nodeH = self.start_new_fiber(self.generate_account(10000))
        self.nodeJ = self.start_new_fiber(self.generate_account(10000))
        self.nodeK = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.nodeA, self.nodeB, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeB, self.nodeC, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeC, self.nodeD, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeD, self.nodeE, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeH, self.nodeJ, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeJ, self.nodeK, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeK, self.nodeD, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.nodeE, self.nodeF, Amount.ckb(1000), Amount.ckb(1000)
        )

        # new invoice by node-E
        invoiceE = self.nodeE.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "expired hold invoice",
                # "expiry": "expiry_hex",
                "payment_hash": self.generate_random_preimage(),
                # "hash_algorithm": "sha256",
            }
        )
        paymentA = self.nodeA.get_client().send_payment(
            {
                "invoice": invoiceE["invoice_address"],
            }
        )
        time.sleep(5)
        # new invoice by node - F
        invoiceF = self.nodeF.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "expired hold invoice",
                # "expiry": "expiry_hex",
                "payment_hash": self.generate_random_preimage(),
                # "hash_algorithm": "sha256",
            }
        )
        paymentH = self.nodeH.get_client().send_payment(
            {
                "invoice": invoiceF["invoice_address"],
            }
        )

        tlc_seconds_list = []
        for i in range(len(self.fibers)):
            pending_tlcH = self.get_pending_tlc(
                self.fibers[i], paymentH["payment_hash"]
            )
            pending_tlcA = self.get_pending_tlc(
                self.fibers[i], paymentA["payment_hash"]
            )
            if len(pending_tlcA["Inbound"]) == 1:
                tlc_seconds_list.append(pending_tlcA["Inbound"][0]["expiry_seconds"])
            if len(pending_tlcH["Inbound"]) == 1:
                tlc_seconds_list.append(pending_tlcH["Inbound"][0]["expiry_seconds"])
        tlc_seconds_list.sort()
        add_hour = 0
        begin_time = datetime.now()
        for tlc_seconds in tlc_seconds_list:
            now = datetime.now()
            past_time = (now - begin_time).total_seconds()
            tlc_seconds = tlc_seconds - past_time
            tlc_seconds = tlc_seconds - 1 * 60 - 2 / 3 * 4 * 60 * 60
            hour = int(tlc_seconds / (60 * 60))
            minutes = int(tlc_seconds / 60 % 60)
            self.add_time_and_generate_epoch(hour, 1)
            change_time(0, minutes)
            self.node.getClient().generate_epochs("0x1", 0)
            time.sleep(5 * 60)
            offered_tlc_balance_is_zero = True
            for fiber in self.fibers:
                fiber_balance = self.get_fiber_balance(fiber).get(
                    "ckb", {"offered_tlc_balance": 0}
                )
                if fiber_balance["offered_tlc_balance"] != 0:
                    offered_tlc_balance_is_zero = False
            if offered_tlc_balance_is_zero:
                return
        raise Exception("offered_tlc_balance != zero")
