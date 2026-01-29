"""
Test cases for new_invoice description parameter: max length, empty/space/emoji.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    Currency,
    HashAlgorithm,
    InvoiceStatus,
    PaymentStatus,
    Timeout,
)


class TestDescription(FiberTest):
    """
    Test new_invoice description: none, random string (ASCII/special/emoji), max length 639.
    """

    def test_description_max_data(self):
        """
        Description longer than 639 bytes should be rejected with length error.
        Step 1: Open channel and wait CHANNEL_READY.
        Step 2: Create invoice with description length 641; expect exception with max length 639.
        """
        # Step 1: Open channel and wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: Create invoice with description length 641; expect exception (max length 639)
        rand_str_length = 641
        rand_str = self.generate_random_str(rand_str_length)
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().new_invoice(
                {
                    "amount": hex(1),
                    "currency": Currency.FIBD,
                    "description": rand_str,
                    "expiry": "0xe10",
                    "final_cltv": "0x28",
                    "payment_preimage": self.generate_random_preimage(),
                    "hash_algorithm": HashAlgorithm.SHA256,
                }
            )
        expected_error_message = (
            "Description with length of 641 is too long, max length is 639"
        )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_description_rd_str(self):
        """
        Empty, space, and emoji descriptions should be accepted and round-trip in get_invoice.
        Step 1: Open channel and wait CHANNEL_READY.
        Step 2: For each description (empty, space, emoji): create invoice, send payment, assert invoice description and balance.
        """
        # Step 1: Open channel and wait CHANNEL_READY
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

        # Step 2: For each description: create invoice, send payment, assert description and balance
        test_description_str = ["", " ", "sa😧"]
        amount = 1
        for desc in test_description_str:
            invoice = self.fiber2.get_client().new_invoice(
                {
                    "amount": hex(amount),
                    "currency": Currency.FIBD,
                    "description": desc,
                    "expiry": "0xe10",
                    "final_cltv": "0x28",
                    "payment_preimage": self.generate_random_preimage(),
                    "hash_algorithm": HashAlgorithm.SHA256,
                }
            )
            time.sleep(Timeout.POLL_INTERVAL)

            before_channel = self.fiber1.get_client().list_channels({})
            payment = self.fiber1.get_client().send_payment(
                {"invoice": invoice["invoice_address"]}
            )
            self.wait_payment_state(
                self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS,
                timeout=Timeout.PAYMENT_SUCCESS
            )
            self.wait_invoice_state(
                self.fiber2, payment["payment_hash"], InvoiceStatus.PAID,
                timeout=Timeout.CHANNEL_READY
            )
            got = self.fiber2.get_client().get_invoice(
                {"payment_hash": payment["payment_hash"]}
            )
            assert (
                got["invoice"]["data"]["attrs"][0]["description"] == desc
            ), "Invoice description should round-trip"
            after_channel = self.fiber1.get_client().list_channels({})
            assert (
                int(before_channel["channels"][0]["local_balance"], 16)
                == int(after_channel["channels"][0]["local_balance"], 16) + amount
            )
