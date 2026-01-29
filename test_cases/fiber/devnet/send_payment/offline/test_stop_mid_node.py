"""
Test cases for send_payment when mid node is stopped: payment fails, restart mid node, payment succeeds.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, PaymentStatus, Timeout


class TestStopMidNode(FiberTest):
    """
    Test send_payment behavior when the mid node in a 3-hop path is stopped.
    Payment should fail when mid node is down; succeed after mid node restarts.
    """

    def test_stop_mid_node(self):
        """
        Stop mid node during payment path; payment fails; restart mid node; payment succeeds.
        Step 1: Build fiber0->fiber1->fiber2->fiber3 topology and open channels.
        Step 2: Send keysend payment from fiber0 to fiber3; assert success.
        Step 3: Stop mid node (fiber2), send payment; assert payment fails.
        Step 4: Restart mid node, wait for reconnection.
        Step 5: Send keysend payment again; assert success.
        """
        # Step 1: Build fiber0->fiber1->fiber2->fiber3 topology and open channels
        fiber = self.start_new_fiber(self.generate_account(10000))
        self.fiber1.connect_peer(fiber)
        fiber = self.start_new_fiber(self.generate_account(10000))
        self.fiber1.connect_peer(fiber)
        self.open_channel(
            self.fibers[0], self.fibers[1], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[1], self.fibers[2], Amount.ckb(1000), Amount.ckb(1)
        )
        self.open_channel(
            self.fibers[2], self.fibers[3], Amount.ckb(1000), Amount.ckb(1)
        )

        # Step 2: Send keysend payment from fiber0 to fiber3; assert success
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": self.fibers[3].get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fibers[0],
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            Timeout.CHANNEL_READY,
        )

        # Step 3: Stop mid node (fiber2), send payment; assert payment fails
        self.fibers[2].stop()
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": self.fibers[3].get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fibers[0],
            payment["payment_hash"],
            PaymentStatus.FAILED,
            Timeout.CHANNEL_READY,
        )

        # Step 4: Restart mid node, wait for reconnection
        self.fibers[2].start()
        time.sleep(10)

        # Step 5: Send keysend payment again; assert success
        payment = self.fibers[0].get_client().send_payment(
            {
                "target_pubkey": self.fibers[3].get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fibers[0],
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            Timeout.CHANNEL_READY,
        )
