"""
Test for Fiber issue 1069: hold invoice with force shutdown and settle.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, Timeout
from framework.util import ckb_hash


class TestIssue1069(FiberTest):
    """
    Test issue 1069: send payment with hold invoice, force shutdown channel, then settle.
    Skipped: requires log confirmation.
    """

    @pytest.mark.skip(reason="Requires log confirmation")
    def test_issue_1069(self):
        """
        Hold invoice flow with force shutdown; settle on payee after shutdown.
        Step 1: Open channel (fiber1->fiber2). Step 2: Fiber2 new hold invoice, fiber1 send payment.
        Step 3: Fiber1 force shutdown channel. Step 4: Fiber2 settle_invoice.
        """
        # Step 1: Open channel
        self.open_channel(self.fiber1, self.fiber2, Amount.ckb(1000), 0)

        # Step 2: New hold invoice and send payment
        preimage = self.generate_random_preimage()
        payment_hash = ckb_hash(preimage)
        fiber2_invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(1)),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_hash": payment_hash,
                "allow_mpp": True,
            }
        )
        self.fiber1.get_client().send_payment(
            {"invoice": fiber2_invoice["invoice_address"]}
        )

        # Step 3: Force shutdown channel
        time.sleep(Timeout.POLL_INTERVAL)
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )

        # Step 4: Settle invoice on payee
        time.sleep(Timeout.SHORT)
        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
