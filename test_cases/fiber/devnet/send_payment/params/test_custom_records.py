"""
Test cases for send_payment custom_records parameter.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, PaymentStatus


class TestCustomRecords(FiberTest):
    """
    Test custom_records parameter: none, empty, multiple keys, min/max key, value size limit.
    """

    def test_custom(self):
        """
        Test custom_records: with records, empty dict, multiple keys, min/max key, oversized value.
        Step 1: Open channel and send payment with custom_records; assert get_payment returns them.
        Step 2: Send payment with empty custom_records; assert empty.
        Step 3: Send payment with 20 custom keys; assert all returned.
        Step 4: Send payment with min (0x0) and max (0xffff) keys; assert returned.
        Step 5: Assert value > 2048 bytes rejected.
        Step 6: Send payment without custom_records; assert None.
        """
        # Step 1: Open channel and send payment with custom_records; assert get_payment returns them
        self.open_channel(
            self.fiber1, self.fiber2, Amount.ckb(1000), Amount.ckb(1000)
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "allow_self_payment": True,
                "custom_records": {
                    "0x1": "0x1234",
                    "0x2": "0x5678",
                },
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert {"0x1": "0x1234", "0x2": "0x5678"} == payment["custom_records"]

        # Step 2: Send payment with empty custom_records; assert empty
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "allow_self_payment": True,
                "custom_records": {},
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert {} == payment["custom_records"]

        # Step 3: Send payment with 20 custom keys; assert all returned
        custom_records = {}
        for i in range(0, 20):
            custom_records.update({hex(i): self.generate_random_preimage()})
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "allow_self_payment": True,
                "custom_records": custom_records,
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert custom_records == payment["custom_records"]

        # Step 4: Send payment with min (0x0) and max (0xffff) keys; assert returned
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "allow_self_payment": True,
                "custom_records": {
                    hex(65535): "0x1234",
                    "0x0": "0x5678",
                },
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert {"0xffff": "0x1234", "0x0": "0x5678"} == payment["custom_records"]

        # Step 5: Assert value > 2048 bytes rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(100)),
                    "keysend": True,
                    "allow_self_payment": True,
                    "custom_records": {
                        "0x12": self.generate_random_str(4096 + 2),
                    },
                }
            )
        expected_error_message = "value can not more than 2048 bytes"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 6: Send payment without custom_records; assert None
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        time.sleep(1)
        payment = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert payment["custom_records"] is None
