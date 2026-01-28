"""
Test cases for Fiber issue #675: shutdown channel while TLCs are in flight.
Requirement: https://github.com/nervosnetwork/fiber/issues/675
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, FeeRate, Timeout


class TestIssue675(FiberTest):
    """
    Test issue #675: shutdown channel while payments (TLCs) are in flight.
    Verifies shutdown with close_script and fee_rate; payments finish or fail; channel reaches CLOSED.
    """

    def test_shutdown_in_tlc(self):
        """
        Shutdown channel while multiple payments are in flight; wait for payments to finish and channel CLOSED.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Send 30 payments without waiting.
        Step 3: Call shutdown_channel with close_script and fee_rate (retry on exception).
        Step 4: Wait for all payment hashes to finish.
        Step 5: Wait for channel state CLOSED.
        """
        # Step 1: Open channel between fiber1 and fiber2
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1000)
        )

        # Step 2: Send 30 payments without waiting
        payments = []
        for _ in range(30):
            payment = self.send_payment(
                self.fiber1, self.fiber2, Amount.ckb(1), wait=False
            )
            payments.append(payment)

        # Step 3: Call shutdown_channel with close_script and fee_rate (retry on exception)
        for _ in range(10):
            try:
                self.fiber1.get_client().shutdown_channel(
                    {
                        "channel_id": self.fiber1.get_client().list_channels({})[
                            "channels"
                        ][0]["channel_id"],
                        "force": False,
                        "close_script": self.get_account_script(
                            self.fiber1.account_private
                        ),
                        "fee_rate": hex(FeeRate.DEFAULT),
                    }
                )
                break
            except Exception:
                time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: Wait for all payment hashes to finish
        for payment_hash in payments:
            self.wait_payment_finished(
                self.fiber1, payment_hash, timeout=Timeout.CHANNEL_READY
            )

        # Step 5: Wait for channel state CLOSED
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.SHORT,
            include_closed=True,
        )
