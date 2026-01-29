"""
Test open_channel funding_amount: CKB/UDT zero, min, max, overflow, account balance.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, Timeout


class TestFundingAmount(FiberTest):
    """
    Test open_channel funding_amount validation: zero, below min, overflow, vs account balance.
    """

    start_fiber_config = {"fiber_auto_accept_amount": "0"}

    def test_funding_amount_ckb_is_zero(self):
        """
        CKB channel with funding_amount=0 should be rejected.
        Step 1: Call open_channel with funding_amount hex(0), public True.
        Step 2: Assert error message contains expected substring.
        """
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(0),
                    "public": True,
                }
            )
        expected_error_message = (
            "The funding amount (0) should be greater than or equal to"
        )
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    @pytest.mark.skip("dev only: script not found")
    def test_funding_amount_udt_is_zero(self):
        """
        UDT channel with funding_amount=0 (skipped on dev).
        Step 1: Open channel with funding_udt_type_script and funding_amount 0.
        Step 2: Wait for CHANNEL_READY.
        """
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(0),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_funding_amount_ckb_lt_62(self):
        """
        CKB funding_amount below DEFAULT_MIN_DEPOSIT_CKB should be rejected.
        Step 1: Call open_channel with funding_amount DEFAULT_MIN_DEPOSIT_CKB - 1.
        Step 2: Assert error message contains "should be greater than or equal to".
        """
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(DEFAULT_MIN_DEPOSIT_CKB - 1),
                    "public": True,
                }
            )
        expected_error_message = "should be greater than or equal to"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_funding_amount_ckb_0xfffffffffffffffffffffffffffffff(self):
        """
        CKB funding_amount hex overflow (0xf...f) should be rejected with "should be less than" message.
        Step 1: Call open_channel with funding_amount 0xffff...fff.
        Step 2: Assert error message contains expected max value.
        """
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": "0xfffffffffffffffffffffffffffffff",
                    "public": True,
                }
            )
        expected_error_message = "The funding amount (21267647932558653966460912964485513215) should be less than 18446744073709551615"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_funding_amount_udt_0xfffffffffffffffffffffffffffffffffffff(self):
        """
        UDT funding_amount with too many hex digits should be rejected as Invalid params.
        Step 1: Call open_channel with funding_udt_type_script and invalid hex amount.
        Step 2: Assert error message "Invalid params".
        """
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": "0xfffffffffffffffffffffffffffffffffffffffffffff",
                    "public": True,
                    "funding_udt_type_script": self.get_account_udt_script(
                        self.fiber1.account_private
                    ),
                }
            )
        expected_error_message = "Invalid params"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_funding_amount_udt_0xfffffffffffffffffffffffffffffff(self):
        """
        UDT funding_amount at max valid hex minus 1000: channel should reach CHANNEL_READY.
        Step 1: Faucet UDT, open channel with funding_amount 0xff...f - 1000.
        Step 2: Wait for CHANNEL_READY.
        """
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            int("0xfffffffffffffffffffffffffffffff", 16) - 1000,
        )
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(
                    int("0xfffffffffffffffffffffffffffffff", 16) - 1000
                ),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_funding_amount_udt_gt_account_balance(self):
        """
        UDT funding_amount greater than account balance: no channel created.
        Step 1: Create fiber3 with 1000 CKB UDT, open channel with funding_amount 1000 CKB + 1.
        Step 2: Wait briefly; assert both sides have zero channels.
        """
        account3_private = self.generate_account(
            1000, self.fiber1.account_private, Amount.ckb(1000)
        )
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber1)
        time.sleep(1)
        self.fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000) + 1),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        time.sleep(3)
        channels = self.fiber3.get_client().list_channels({})
        assert len(channels["channels"]) == 0
        channels = self.fiber1.get_client().list_channels({})
        assert len(channels["channels"]) == 0

    def test_funding_amount_ckb_gt_account_balance(self):
        """
        CKB funding_amount greater than account balance: channel stays NEGOTIATING_FUNDING.
        Step 1: Open channel from fiber2 with funding_amount = 2 * capacity.
        Step 2: Wait for NEGOTIATING_FUNDING.
        """
        capacity = self.Ckb_cli.wallet_get_capacity(self.account2["address"]["testnet"])
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(int(capacity) * 2)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.NEGOTIATING_FUNDING,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_funding_amount_ckb_eq_account_balance(self):
        """
        CKB funding_amount equal to account balance: channel reaches NEGOTIATING_FUNDING.
        Step 1: Open channel from fiber2 with funding_amount = capacity.
        Step 2: Wait for NEGOTIATING_FUNDING.
        """
        capacity = self.Ckb_cli.wallet_get_capacity(self.account2["address"]["testnet"])
        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(int(capacity))),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.NEGOTIATING_FUNDING,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_funding_amount_udt_eq_account_balance(self):
        """
        UDT funding_amount equal to account balance: channel reaches CHANNEL_READY.
        Step 1: Create fiber3 with 1000 CKB UDT, open channel with funding_amount 1000 CKB.
        Step 2: Wait for CHANNEL_READY.
        """
        account3_private = self.generate_account(
            1000, self.fiber1.account_private, Amount.ckb(1000)
        )
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber1)
        time.sleep(1)
        self.fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )

    def test_funding_amount_udt_lt_account_balance(self):
        """
        UDT funding_amount less than account balance: channel CHANNEL_READY, remaining UDT balance 1.
        Step 1: Create fiber3 with 1000 CKB UDT, open channel with funding_amount 1000 CKB - 1.
        Step 2: Wait for CHANNEL_READY.
        Step 3: Assert UDT list_cell balance is 1.
        """
        account3_private = self.generate_account(
            1000, self.fiber1.account_private, Amount.ckb(1000)
        )
        self.fiber3 = self.start_new_fiber(account3_private)
        self.fiber3.connect_peer(self.fiber1)
        time.sleep(1)
        self.fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000) - 1),
                "public": True,
                "funding_udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(),
            self.fiber1.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        account_balance = self.udtContract.list_cell(
            self.node.getClient(),
            self.get_account_script(self.fiber1.account_private)["args"],
            self.get_account_script(self.fiber3.account_private)["args"],
        )
        assert account_balance[0]["balance"] == 1

    @pytest.mark.skip("todo")
    def test_funding_amount_ckb_lt_account_balance(self):
        """
        CKB funding_amount less than account balance (todo: implement).
        Step 1: (Not implemented.)
        """
        pass

    def test_funding_amount_gt_int_max(self):
        """
        funding_amount > int.max (2^64) should be rejected.
        Step 1: Call open_channel with funding_amount 18446744073709551616.
        Step 2: Assert error message contains expected max 18446744073709551615.
        """
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel(
                {
                    "peer_id": self.fiber2.get_peer_id(),
                    "funding_amount": hex(18446744073709551616),
                    "public": True,
                }
            )
        expected_error_message = "The funding amount (18446744073709551616) should be less than 18446744073709551615"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
