"""
Test cases for path finding in send_payment.
Covers linked network, multi-path routing, and cycle network topologies.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, PaymentStatus, TLCFeeRate, Timeout


class TestFindPath(FiberTest):
    """
    Test path finding for send_payment across various graph topologies:
    - Linked net: A->B->C linear topology
    - Multi-path: A->B->D, A->C->D, A->E->F->D with different fees
    - Cycle net: 0-1-2 / 3-4-5 grid with cycles
    """

    def test_linked_net(self):
        """
        Test payment through a simple linked network A->B->C.
        Step 1: Start fiber3 and connect to fiber1, fiber2.
        Step 2: Open multiple channels between fibers[0]-fibers[1] and fibers[1]-fibers[2].
        Step 3: Send payment from fibers[0] to fibers[2].
        """
        # Step 1: Start fiber3 and connect to fiber1, fiber2
        for _ in range(1):
            fiber = self.start_new_fiber(self.generate_account(10000))
            fiber.connect_peer(self.fiber1)
            fiber.connect_peer(self.fiber2)

        # Step 2: Open multiple channels between fibers
        for _ in range(2):
            self.open_channel(
                self.fibers[0], self.fibers[1],
                Amount.ckb(1000), Amount.ckb(1000)
            )
        self.open_channel(
            self.fibers[0], self.fibers[1],
            Amount.ckb(1000), Amount.ckb(1000)
        )
        for _ in range(2):
            self.open_channel(
                self.fibers[0], self.fibers[1],
                Amount.ckb(10000), Amount.ckb(1000)
            )
        for _ in range(2):
            self.open_channel(
                self.fibers[1], self.fibers[2],
                Amount.ckb(1000), Amount.ckb(1000)
            )
        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1000)
        )
        for _ in range(2):
            self.open_channel(
                self.fibers[1], self.fibers[2],
                Amount.ckb(1000), Amount.ckb(1000)
            )

        # Step 3: Send payment from fibers[0] to fibers[2]
        self.send_payment(self.fibers[0], self.fibers[2], Amount.ckb(300))

    def test_mul_path(self):
        """
        Test multi-path routing: A->B->D (B fee=3000), A->C->D (C fee=2500), A->E->F->D (E,F fee=1000).
        Step 1: Start 6 fibers with UDT config and connect to fiber2.
        Step 2: Build topology with channels and different TLC fees.
        Step 3: Send 3 payments from new_fibers[0] to new_fibers[3].
        Step 4: Verify all payments complete (lowest fee path preferred).
        """
        # Step 1: Start 6 fibers with UDT config and connect to fiber2
        deploy_hash, deploy_index = self.udtContract.get_deploy_hash_and_index()
        update_config = {
            "ckb_rpc_url": self.node.rpcUrl,
            "fiber_open_channel_auto_accept_min_ckb_funding_amount": "1000000000000000",
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": self.Contract.get_ckb_contract_codehash(
                deploy_hash, deploy_index, True, self.node.rpcUrl
            ),
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": deploy_index,
        }
        for _ in range(6):
            fiber = self.start_new_fiber(
                self.generate_account(1000000), update_config
            )
            self.fiber2.connect_peer(fiber)

        # Step 2: Build topology with channels and different TLC fees
        self.open_channel(
            self.new_fibers[0], self.new_fibers[2],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=3000
        )
        self.open_channel(
            self.new_fibers[2], self.new_fibers[3],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(
            self.new_fibers[0], self.new_fibers[1],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=2500
        )
        self.open_channel(
            self.new_fibers[1], self.new_fibers[3],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(
            self.new_fibers[0], self.new_fibers[4],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(
            self.new_fibers[4], self.new_fibers[5],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(
            self.new_fibers[5], self.new_fibers[3],
            Amount.ckb(110), Amount.ckb(110),
            fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT
        )

        # Step 3: Send 3 payments from new_fibers[0] to new_fibers[3]
        payment_hash1 = self.send_payment(
            self.new_fibers[0], self.new_fibers[3], Amount.ckb(100)
        )
        payment_hash2 = self.send_payment(
            self.new_fibers[0], self.new_fibers[3], Amount.ckb(100)
        )
        payment_hash3 = self.send_payment(
            self.new_fibers[0], self.new_fibers[3], Amount.ckb(100)
        )

        # Step 4: Verify all payments complete
        self.wait_payment_state(
            self.new_fibers[0], payment_hash1, PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        self.wait_payment_state(
            self.new_fibers[0], payment_hash2, PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        self.wait_payment_state(
            self.new_fibers[0], payment_hash3, PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_cycle_net(self):
        """
        Test payment in a cycle network (grid 0-1-2 / 3-4-5).
        Step 1: Start 4 fibers and build grid topology.
        Step 2: Send self-payments from each node (100 rounds).
        Step 3: Wait for all payments to finish.
        Step 4: Send 20 more self-payments per node until one succeeds.
        Step 5: Assert no offered/received TLC balance remains.
        """
        # Step 1: Start 4 fibers and build grid topology
        for _ in range(4):
            fiber = self.start_new_fiber(self.generate_account(10000))
            fiber.connect_peer(self.fiber1)

        for i in range(2):
            self.open_channel(
                self.fibers[i], self.fibers[i + 1],
                Amount.ckb(1000), Amount.ckb(1000)
            )
        for i in range(2):
            self.open_channel(
                self.fibers[i + 3], self.fibers[i + 4],
                Amount.ckb(1000), Amount.ckb(1000)
            )
        for i in range(3):
            self.open_channel(
                self.fibers[i], self.fibers[i + 3],
                Amount.ckb(1000), Amount.ckb(1000)
            )

        # Step 2: Send self-payments from each node (100 rounds)
        hashes = [[], [], [], [], [], []]
        for _ in range(100):
            for i in range(len(self.fibers)):
                try:
                    payment_hash = self.send_payment(
                        self.fibers[i], self.fibers[i],
                        Amount.ckb(50), wait=False
                    )
                    hashes[i].append(payment_hash)
                except Exception:
                    pass

        # Step 3: Wait for all payments to finish
        for i in range(len(hashes)):
            for payment_hash in hashes[i]:
                self.wait_payment_finished(
                    self.fibers[i], payment_hash,
                    timeout=Timeout.VERY_LONG
                )

        # Step 4: Send 20 more self-payments per node until one succeeds
        for i in range(len(self.fibers)):
            for attempt in range(20):
                payment_hash = self.send_payment(
                    self.fibers[i], self.fibers[i],
                    Amount.ckb(50), wait=False
                )
                result = self.wait_payment_finished(
                    self.fibers[i], payment_hash,
                    timeout=Timeout.VERY_LONG
                )
                if result["status"] == PaymentStatus.SUCCESS:
                    break
                time.sleep(Timeout.POLL_INTERVAL)
                if attempt == 19:
                    raise Exception("Payment failed after 20 attempts")

        # Step 5: Assert no offered/received TLC balance remains
        for i in range(len(self.fibers)):
            channels_balance = self.get_fiber_balance(self.fibers[i])
            assert channels_balance["ckb"]["offered_tlc_balance"] == 0
            assert channels_balance["ckb"]["received_tlc_balance"] == 0
