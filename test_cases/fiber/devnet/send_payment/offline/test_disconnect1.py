"""
Test cases for send_payment with peer disconnect (variant 1): key_send and invoice_send under disconnect.
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, TLCFeeRate


class TestDisconnect1(FiberTest):
    """
    Test send_payment with disconnect: open channel, send multiple payments without wait,
    disconnect peer, reconnect, wait for payments to finish and pending TLC zero.
    """

    def test_key_send_with_disconnect_and_reconnect(self):
        """
        Open channel a-b; in a loop send 30 key_send payments (no wait), disconnect a-b,
        reconnect a-b, wait all payments finished and pending TLC zero; then send one final payment.
        Step 1: Open channel fiber1-fiber2 with semantic amounts.
        Step 2: For 20 iterations: send 30 key_send payments (wait=False); disconnect fiber1-fiber2.
        Step 3: Reconnect fiber1-fiber2; wait all payment_hash finished; wait_fibers_pending_tlc_eq0.
        Step 4: Send one key_send payment with wait.
        """
        # Step 1: Open channel fiber1-fiber2 with semantic amounts
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

        # Step 2 & 3 & 4: Loop: send 30 payments, disconnect, reconnect, wait, then one final payment
        for _ in range(20):
            payment_hashs = []
            for _ in range(30):
                payment_hash = self.send_payment(
                    self.fiber1, self.fiber2,
                    Amount.ckb(1),
                    wait=False,
                )
                payment_hashs.append(payment_hash)
            self.fiber1.get_client().disconnect_peer(
                {"peer_id": self.fiber2.get_peer_id()}
            )
            time.sleep(1)
            before_fiber1_balance = self.get_fiber_balance(self.fiber1)
            assert before_fiber1_balance["ckb"]["offered_tlc_balance"] > 0, (
                "Expected offered_tlc_balance > 0 after disconnect"
            )
            self.fiber1.connect_peer(self.fiber2)
            for payment_hash in payment_hashs:
                self.wait_payment_finished(
                    self.fiber1, payment_hash,
                    timeout=Timeout.PAYMENT_SUCCESS,
                )
            self.wait_fibers_pending_tlc_eq0(self.fiber1)
            self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1), wait=True)
