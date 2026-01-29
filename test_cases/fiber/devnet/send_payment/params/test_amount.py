"""
Test cases for send_payment amount parameter: zero, min, max, overflow, UDT.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    PaymentStatus,
)


class TestAmount(FiberTest):
    """
    Test send_payment amount validation and behavior: zero, min, local_balance, overflow, UDT.
    """

    def test_ckb(self):
        """
        CKB amount validation: zero rejected, min accepted, local_balance/1.001 max.
        Step 1: Build fiber1->fiber2->fiber3 topology with large channels.
        Step 2: Assert amount=0 rejected.
        Step 3: Assert amount=1 accepted (dry_run).
        Step 4: Assert amount near local_balance/1.001 accepted for fiber2; local_balance/1.002001 for fiber3.
        Step 5: Send payment with amount local_balance/1.00101; assert success.
        """
        # Step 1: Build fiber1->fiber2->fiber3 topology with large channels
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex((1_000_000_000 - 36) * Amount.CKB),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex((1_000_000_000 - 36) * Amount.CKB),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        time.sleep(1)

        # Step 2: Assert amount=0 rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "amount": hex(0),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        expected_error_message = "amount must be greater than 0"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(0),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Assert amount=1 accepted (dry_run)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(1),
                "keysend": True,
                "dry_run": True,
            }
        )
        assert payment["fee"] == hex(0)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(1),
                "keysend": True,
                "dry_run": True,
            }
        )
        assert payment["fee"] == hex(1)

        # Step 4: Assert amount near local_balance/1.001 accepted
        channels = self.fiber1.get_client().list_channels({})
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(
                    int(int(channels["channels"][0]["local_balance"], 16) / 1.001)
                ),
                "keysend": True,
                "dry_run": True,
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(
                    int(int(channels["channels"][0]["local_balance"], 16) / 1.002001)
                ),
                "keysend": True,
                "dry_run": True,
            }
        )
        assert payment["fee"] == "0x5ac4909a6563"

        # Step 5: Send payment with amount local_balance/1.00101; assert success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(
                    int(int(channels["channels"][0]["local_balance"], 16) / 1.00101)
                ),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS
        )

    def test_over_flow_panic(self):
        """
        Assert amount exceeding u128 max is rejected.
        Step 1: Build topology with very large channels.
        Step 2: Assert amount 0xfffffffffffffffffffffffffffffff rejected.
        """
        # Step 1: Build topology with very large channels
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1_000_000_000 * Amount.CKB),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(1_000_000_000 * Amount.CKB),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        time.sleep(1)

        # Step 2: Assert amount 0xfffffffffffffffffffffffffffffff rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": "0xfffffffffffffffffffffffffffffff",
                    "keysend": True,
                    "dry_run": True,
                }
            )
        expected_error_message = "should be less than"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_send_mutil_channel(self):
        """
        Send payment across multiple channels between same pair (bidirectional).
        Step 1: Open bidirectional channels a1-b1.
        Step 2: Send payment a1->b1; assert success.
        Step 3: Send payment b1->a1; assert success.
        """
        # Step 1: Open bidirectional channels a1-b1
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
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        time.sleep(2)
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        time.sleep(1)

        # Step 2: Send payment a1->b1; assert success
        self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
                "dry_run": True,
            }
        )
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(100)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment1["payment_hash"], PaymentStatus.SUCCESS
        )

        # Step 3: Send payment b1->a1; assert success
        self.fiber2.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(200)),
                "keysend": True,
                "dry_run": True,
            }
        )
        payment2 = self.fiber2.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(200)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber2, payment2["payment_hash"], PaymentStatus.SUCCESS
        )

    def test_udt(self):
        """
        UDT amount validation: zero rejected, min accepted, local_balance max.
        Step 1: Faucet UDT, build topology with UDT channels.
        Step 2: Assert amount=0 rejected.
        Step 3: Assert amount=1 accepted (dry_run).
        Step 4: Assert amount near local_balance/1.00101 accepted for fiber2 and fiber3.
        """
        # Step 1: Faucet UDT, build topology with UDT channels
        open_channel_balance = 10_000_000_000_000_000 * Amount.CKB
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            open_channel_balance,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            open_channel_balance,
        )
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber2.connect_peer(self.fiber3)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(open_channel_balance),
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(open_channel_balance),
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        time.sleep(1)

        # Step 2: Assert amount=0 rejected
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                    "amount": hex(0),
                    "keysend": True,
                    "dry_run": True,
                    "udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )
        expected_error_message = "amount must be greater than 0"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(0),
                    "keysend": True,
                    "dry_run": True,
                    "udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Assert amount=1 accepted (dry_run)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(1),
                "keysend": True,
                "dry_run": True,
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        assert payment["fee"] == hex(0)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(1),
                "keysend": True,
                "dry_run": True,
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        assert payment["fee"] == hex(1)

        # Step 4: Assert amount near local_balance/1.00101 accepted
        channels = self.fiber1.get_client().list_channels({})
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(
                    int(int(channels["channels"][0]["local_balance"], 16) / 1.00101)
                ),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "keysend": True,
                "dry_run": True,
            }
        )
        assert payment["fee"] == "0x0"
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(
                    int(int(channels["channels"][0]["local_balance"], 16) / 1.00101)
                ),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "keysend": True,
                "dry_run": True,
            }
        )
        assert payment["fee"] == "0x3627c90ef6acdb22d1"
