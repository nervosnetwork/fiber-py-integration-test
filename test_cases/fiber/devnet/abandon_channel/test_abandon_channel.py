"""
Test cases for abandon_channel RPC: abandon by temporary_channel_id,
and reject when channel is already signed / ready / shutting down / closed.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState, FeeRate


class TestAbandonChannel(FiberTest):
    """
    Test abandon_channel RPC under different channel states.
    Covers: abandon by tmp_id; reject after accept (signed); reject when tx in pool;
    reject when CHANNEL_READY / SHUTTING_DOWN / CLOSED (should use shutdown instead).
    """

    def test_tmp_id(self):
        """
        Abandon channel with temporary_channel_id before accept; both sides end with no channel.
        Step 1: fiber1 opens channel (open_channel).
        Step 2: fiber1 abandons channel with temporary_channel_id.
        Step 3: fiber2 accepts the same temporary_channel_id (no effect).
        Step 4: Assert both sides have zero channels.
        """
        # Step 1: fiber1 opens channel
        funding = Amount.MIN_CHANNEL_CKB + Amount.ckb(1)  # 1 CKB + min channel amount
        channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(funding),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: fiber1 abandons channel with temporary_channel_id
        self.fiber1.get_client().abandon_channel(
            {"channel_id": channel["temporary_channel_id"]}
        )

        # Step 3: fiber2 accept has no effect; both sides should have no channel
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": channel["temporary_channel_id"],
                "funding_amount": hex(Amount.MIN_CHANNEL_CKB),
            }
        )

        # Step 4: Assert both sides have zero channels
        self.assert_channel_count(self.fiber1, 0)
        self.assert_channel_count(self.fiber2, 0)

    def test_abandon_channel_accept(self):
        """
        After accept, our side has signed; abandon_channel should be rejected with "cannot be abandoned".
        Step 1: fiber1 opens channel.
        Step 2: fiber2 accepts; fiber1 side is then signed.
        Step 3: Call abandon_channel with existing channel_id; expect exception.
        """
        # Step 1: fiber1 opens channel
        channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.MIN_CHANNEL_CKB),
                "public": True,
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: fiber2 accepts; fiber1 side is signed
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": channel["temporary_channel_id"],
                "funding_amount": hex(Amount.MIN_CHANNEL_CKB),
            }
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 3: abandon_channel with existing channel_id should raise
        channel_id = self.fiber1.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().abandon_channel({"channel_id": channel_id})

        expected_error_message = "cannot be abandoned"
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err, (
            f"Expected substring '{expected_error_message}' not found in actual: '{err}'"
        )

    def test_abandon_channel_when_tx_send(self):
        """
        When channel is in AwaitingTxSignatures (funding tx in pool), abandon_channel should be rejected.
        Step 1: Open channel and wait for tx to enter pool.
        Step 2: Get channel_id and call abandon_channel; expect exception.
        """
        # Step 1: Open channel and wait for funding tx to enter pool
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(1000)),
                "public": True,
            }
        )
        self.wait_and_check_tx_pool_fee(
            FeeRate.DEFAULT, False, Timeout.CHANNEL_READY
        )

        # Step 2: Get channel_id and call abandon_channel; expect rejection
        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().abandon_channel({"channel_id": channel_id})

        expected_error_message = "is in state AwaitingTxSignatures"
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err, (
            f"Expected substring '{expected_error_message}' not found in actual: '{err}'"
        )

    def test_chain_status_ready_or_shutdown_close(self):
        """
        When channel is CHANNEL_READY, SHUTTING_DOWN, or CLOSED,
        abandon_channel should be rejected with message to use shutdown instead.
        Step 1: Open channel and get channel_id.
        Step 2: Assert abandon rejected in CHANNEL_READY.
        Step 3: Shutdown channel then assert abandon rejected in SHUTTING_DOWN.
        Step 4: Wait for CLOSED then assert abandon still rejected.
        """
        # Step 1: Open channel and get channel_id
        self.open_channel(
            self.fiber1,
            self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(1),
        )
        channels = self.fiber1.get_client().list_channels({})
        channel_id = channels["channels"][0]["channel_id"]
        expected_error_message = (
            "cannot be abandoned, please shutdown the channel instead"
        )

        # Step 2: abandon should be rejected when CHANNEL_READY
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().abandon_channel({"channel_id": channel_id})
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err, (
            f"CHANNEL_READY: expected '{expected_error_message}' in '{err}'"
        )

        # Step 3: After shutdown (SHUTTING_DOWN), abandon should be rejected
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": self.get_account_script(self.Config.ACCOUNT_PRIVATE_1),
                "fee_rate": FeeRate.to_hex(FeeRate.DEFAULT),
            }
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().abandon_channel({"channel_id": channel_id})
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err, (
            f"SHUTTING_DOWN: expected '{expected_error_message}' in '{err}'"
        )

        # Step 4: After CLOSED, abandon should still be rejected
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CLOSED,
            timeout=Timeout.CHANNEL_READY,
            include_closed=True,
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().abandon_channel({"channel_id": channel_id})
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert expected_error_message in err, (
            f"CLOSED: expected '{expected_error_message}' in '{err}'"
        )
