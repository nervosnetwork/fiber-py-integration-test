"""
Test cases for accept_channel temporary_channel_id parameter.
Verifies: channel acceptance with various temporary_channel_id scenarios.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestTemporaryChannelId(FiberTest):
    """
    Test accept_channel with temporary_channel_id parameter.
    Verifies: error handling for non-existent and reused temporary channel IDs.
    """

    def test_temporary_channel_id_not_exist(self):
        """
        Test scenario where a temporary channel ID does not exist.
        Step 1: Attempt to accept a channel with a non-existent temporary channel ID.
        Step 2: Verify that the expected error message is raised.
        """
        # Step 1: Attempt to accept a channel with a non-existent temporary channel ID
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": "0x119fb7f26b72664b5cdfec9269591a6af1c9f111f47534b7bc7993413701599a",
                    "funding_amount": hex(Amount.ckb(100)),
                }
            )

        # Step 2: Verify that the expected error message is raised
        expected_error_message = "No channel with temp id"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def test_temporary_channel_id_again(self):
        """
        Test scenario where a temporary channel ID is used again after acceptance.
        Step 1: Get node information.
        Step 2: Open a channel with a funding amount slightly less than the minimum auto-accept amount.
        Step 3: Accept the channel with a specified funding amount.
        Step 4: Verify the channel ID.
        Step 5: Attempt to accept the channel again and verify the expected error message.
        """
        # Step 1: Get node information
        node_info = self.fiber1.get_client().node_info()
        open_channel_auto_accept_min_ckb_funding_amount = node_info[
            "open_channel_auto_accept_min_ckb_funding_amount"
        ]

        # Step 2: Open a channel with funding amount slightly below auto-accept minimum
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(
                    int(open_channel_auto_accept_min_ckb_funding_amount, 16) - 1
                ),
                "public": True,
                "commitment_fee_rate": hex(FeeRate.DEFAULT),
                "funding_fee_rate": hex(FeeRate.DEFAULT),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 3: Accept the channel with a specified funding amount
        accept_channel = self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(Amount.ckb(99)),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 4: Verify the channel ID
        channel = self.fiber1.get_client().list_channels({})
        assert channel["channels"][0]["channel_id"] == accept_channel["channel_id"]

        # Step 5: Attempt to accept the channel again and verify the expected error message
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().accept_channel(
                {
                    "temporary_channel_id": temporary_channel["temporary_channel_id"],
                    "funding_amount": hex(Amount.ckb(100)),
                }
            )

        expected_error_message = "No channel with temp id Hash256"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    @pytest.mark.skip("repeat")
    def test_ckb_temporary_channel_id_exist(self):
        """
        Test case for CKB channel with existing temporary channel ID.
        Skipped: duplicate of test_funding_amount.test_ckb_funding_amount_eq_auto_accept_channel_ckb_funding_amount
        """
        # test_funding_amount.test_ckb_funding_amount_eq_auto_accept_channel_ckb_funding_amount

    @pytest.mark.skip("repeat")
    def test_udt_temporary_channel_id_exist(self):
        """
        Test case for UDT channel with existing temporary channel ID.
        Skipped: duplicate of test_funding_amount.test_udt_funding_amount_zero
        """
        # test_funding_amount.test_udt_funding_amount_zero
