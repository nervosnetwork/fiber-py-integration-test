import time

import pytest

from framework.basic_fiber import FiberTest
from framework.util import ckb_hash


class TestIssue1069(FiberTest):

    @pytest.mark.skip("需要看日志确认")
    def test_issue_1069(self):
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        # fiber new hold invoice
        preimage = self.generate_random_preimage()
        payment_hash = ckb_hash(preimage)
        fiber2_invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "test invoice",
                # "expiry": hex(15),
                "payment_hash": payment_hash,
                "allow_mpp": True,
            }
        )
        # fiber1 send
        self.fiber1.get_client().send_payment(
            {
                "invoice": fiber2_invoice["invoice_address"],
            }
        )
        # fiber1 force shutdown
        time.sleep(1)
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )
        time.sleep(10)
        self.fiber2.get_client().settle_invoice(
            {"payment_hash": payment_hash, "payment_preimage": preimage}
        )
        # check log
