"""
Test cases for send_payment through a long router path.
Verifies payment succeeds across a 14-hop linear topology.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    PaymentStatus,
    Timeout,
)


class TestLongRouter(FiberTest):
    """
    Test send_payment through a long linear router path (14 hops).
    Verifies payment succeeds and balance changes match expected fee distribution.
    """

    def test_long_router(self):
        """
        Test payment through a 14-hop linear path.
        Step 1: Start 13 fibers and build linear topology fiber0->fiber1->...->fiber13.
        Step 2: Send 10 CKB payment from fiber0 to fiber13.
        Step 3: Wait for payment success.
        Step 4: Assert balance changes match expected fee distribution.
        """
        # Step 1: Start 13 fibers and build linear topology
        router_length = 13
        for _ in range(router_length):
            account_private = self.generate_account(1000)
            fiber = self.start_new_fiber(account_private)
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)

        for i in range(len(self.fibers) - 1):
            linked_fiber = self.fibers[i + 1]
            current_fiber = self.fibers[i]
            linked_fiber.connect_peer(current_fiber)
            time.sleep(Timeout.POLL_INTERVAL)
            current_fiber.get_client().open_channel(
                {
                    "peer_id": linked_fiber.get_peer_id(),
                    "funding_amount": hex(Amount.ckb(500)),
                    "public": True,
                }
            )
            self.wait_for_channel_state(
                current_fiber.get_client(),
                linked_fiber.get_peer_id(),
                ChannelState.CHANNEL_READY,
                timeout=Timeout.CHANNEL_READY,
            )

        # Step 2: Send 10 CKB payment from fiber0 to fiber13
        before_balance = self.get_fibers_balance()
        time.sleep(Timeout.POLL_INTERVAL)
        pub_key = self.fibers[-1].get_client().node_info()["node_id"]
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": pub_key,
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "max_fee_rate": hex(99),  # 9.9% per-thousand, matches original expected balance
            }
        )

        # Step 3: Wait for payment success
        self.wait_payment_state(
            self.fibers[0], payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )

        # Step 4: Assert balance changes match expected fee distribution
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        expected = [
            {"local_balance": 1013078296, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1012067, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1011056, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1010046, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1009037, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1008029, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1007022, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1006016, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1005011, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1004007, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1003004, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1002001, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1001000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1000000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
            {"local_balance": -1000000000, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]
        assert result == expected, f"Balance change mismatch: {result}"
