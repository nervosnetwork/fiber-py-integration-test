"""
Test cases for accept_channel max_tlc_value_in_flight parameter.
Verifies: channel acceptance with max_tlc_value_in_flight limit and payment behavior.
"""
import time

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate, PaymentStatus


class TestMaxTlcValueInFlight(FiberTest):
    """
    Test accept_channel with max_tlc_value_in_flight parameter.
    Verifies: channel can be accepted with max_tlc_value_in_flight limit, and payments exceeding the limit fail.
    """

    def test_max_tlc_value_in_flight_exist(self):
        """
        Test that max_tlc_value_in_flight limits the total value of in-flight TLCs.
        max_tlc_value_in_flight = 1 CKB
        Step 1: Open a new channel with fiber1 as the client and fiber2 as the peer.
        Step 2: Accept the channel with fiber2, setting max_tlc_value_in_flight to 1 CKB.
        Step 3: Wait for the channel state to be CHANNEL_READY.
        Step 4: Send payments within limit (should succeed).
        Step 5: Send payment exceeding limit (should fail).
        Step 6: Send payment in reverse direction (should succeed).
        """
        # Step 1: Open a new channel with fiber1 as the client and fiber2 as the peer
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Accept the channel with fiber2, setting max_tlc_value_in_flight to 1 CKB
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(Amount.ckb(1000)),
                "max_tlc_value_in_flight": hex(Amount.ckb(1)),
            }
        )

        # Step 3: Wait for the channel state to be CHANNEL_READY
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 4: Send payments within limit (should succeed)
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))
        self.send_payment(self.fiber2, self.fiber1, Amount.ckb(1))

        # Step 5: Send payment exceeding limit (should fail)
        payment_hash = self.send_payment(
            self.fiber2, self.fiber1, Amount.ckb(1) + 1, False
        )
        self.wait_payment_state(
            self.fiber2, payment_hash, PaymentStatus.FAILED, timeout=Timeout.PAYMENT_SUCCESS
        )

        # Step 6: Send payment in reverse direction (should succeed)
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1) + 1)
