"""
Test cases for send_payment timeout parameter.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, PaymentStatus, Timeout


class TestTimeout(FiberTest):
    """
    Test timeout parameter for send_payment.
    timeout=0 uses default/internal timeout; payment should succeed.
    """

    def test_01(self):
        """
        Send payment with timeout=0; payment should succeed.
        Step 1: Build fiber1->fiber2->fiber3 topology.
        Step 2: Send payment with timeout=hex(0).
        Step 3: Wait for payment success.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1000)
        )
        self.open_channel(
            self.fiber2, self.fiber3, Amount.ckb(1000), Amount.ckb(1000)
        )

        # Step 2: Send payment with timeout=hex(0)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "timeout": hex(0),
            }
        )

        # Step 3: Wait for payment success
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.TX_COMMITTED
        )
