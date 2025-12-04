import time
import pytest
from framework.basic_fiber import FiberTest
from framework.util import ckb_hash


class TestFinalTlcExpiryDelta(FiberTest):

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/367")
    def test_final_tlc_expiry_delta(self):
        """
        1. none
            12h
        2. 0x0
            invalid final_tlc_expiry_delta, expect between 24 * 60 * 60 * 1000  and 1209600000\
        4. 24 * 60 * 60 * 1000
        5. 172800000
        6. 172800001
            invalid final_tlc_expiry_delta, expect between 24 * 60 * 60 * 1000  and 1209600000\
        7. todo 测试超时
        Returns:

        """
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber2)
        # open channel between fiber1 and fiber2
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )
        # open channel between fiber2 and fiber3
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), "CHANNEL_READY"
        )
        time.sleep(1)
        # send to fiber3 final_tlc_expiry_delta: 0x0
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "dry_run": True,
                    "final_tlc_expiry_delta": "0x0",
                }
            )
        expected_error_message = "invalid final_tlc_expiry_delta"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "dry_run": True,
                    "final_tlc_expiry_delta": hex(1209600001),
                }
            )
        expected_error_message = "invalid final_tlc_expiry_delta"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # final_tlc_expiry_delta: 24 * 60 * 60 * 1000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "final_tlc_expiry_delta": hex(24 * 60 * 60 * 1000),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "final_tlc_expiry_delta": hex(172800000),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        # todo how to test final_tlc_expiry_delta time out

        # node1
        channels = self.fiber1.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(int(380.98 * 10**8))
        # node3
        channels = self.fiber3.get_client().list_channels({})
        assert channels["channels"][0]["local_balance"] == hex(20 * 10**8)

    @pytest.mark.skip(
        "https://github.com/cryptape/acceptance-internal/issues/1262#issuecomment-3610878751"
    )
    def test_final_tlc_expiry_delta_with_final_tlc_expiry_delta(self):
        """
        new_invoice 的final_expiry_delta > final_tlc_expiry_delta ,预期失败
        new_invoice 的final_expiry_delta == final_tlc_expiry_delta，预期成功
        new_invoice 的final_expiry_delta < final_tlc_expiry_delta, 预期失败
        Returns:
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)

        # new_invoice 的final_expiry_delta > final_tlc_expiry_delta ,预期失败
        invoice_payment_preimage = self.generate_random_preimage()
        invoice_payment_hash = ckb_hash(invoice_payment_preimage)
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": "Fibd",
                "description": "test invoice generated by node2",
                "final_expiry_delta": hex(1000 * 60 * 60 * 16),
                "payment_hash": invoice_payment_hash,
            }
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                    "final_expiry_delta": hex(1000 * 60 * 60 * 24),
                }
            )
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # # new_invoice 的final_expiry_delta == final_tlc_expiry_delta ,预期成果
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "final_expiry_delta": hex(1000 * 60 * 60 * 16),
            }
        )
        time.sleep(1)
        pending_tlc_message = self.get_pending_tlc(self.fiber3, payment["payment_hash"])
        # todo assert tlc expiry ==   60 * 60 * 16
        assert abs(pending_tlc_message["Inbound"][0]["expiry"] - 60 * 60 * 16) < 60

        # new_invoice 的final_expiry_delta < final_tlc_expiry_delta, 预期失败
        invoice_payment_preimage = self.generate_random_preimage()
        invoice_payment_hash = ckb_hash(invoice_payment_preimage)
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": "Fibd",
                "description": "test invoice generated by node2",
                "final_expiry_delta": hex(1000 * 60 * 60 * 16),
                "payment_hash": invoice_payment_hash,
            }
        )

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                    "final_expiry_delta": hex(1000 * 60 * 60 * 25),
                    "tlc_expiry_limit": hex(1000 * 60 * 60 * 24),
                }
            )
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
