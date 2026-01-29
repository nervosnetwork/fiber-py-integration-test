"""
Test one-way channel: public not allowed, single-direction send only.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState, PaymentStatus, Timeout


class TestOneWayChannel(FiberTest):
    """
    Test one-way channel constraints: cannot be public, can only send in one direction.
    """

    debug = False

    def _open_private_one_way_channel(self, funding_amount_ckb=500):
        """Open a private one-way channel with retries for init/feature sync."""
        open_channel_params = {
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(Amount.ckb(funding_amount_ckb)),
            "public": False,
            "one_way": True,
        }
        last_error = None
        for _ in range(15):
            try:
                self.fiber1.get_client().open_channel(open_channel_params)
                last_error = None
                break
            except Exception as e:
                last_error = e
                error_str = str(e)
                if (
                    "feature not found" in error_str
                    or "waiting for peer to send Init message" in error_str
                ):
                    time.sleep(1)
                    continue
                raise
        if last_error is not None:
            raise last_error
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
            timeout=Timeout.CHANNEL_READY,
        )
        time.sleep(1)

    def _get_channel_id(self, client, peer_id, include_closed=False):
        """Get first channel_id for peer from list_channels."""
        channels = client.list_channels(
            {"peer_id": peer_id, "include_closed": include_closed}
        )
        assert len(channels["channels"]) > 0, channels
        return channels["channels"][0]["channel_id"]

    def test_one_way_channel_cannot_be_public(self):
        """
        One-way channel with public=True should be rejected.
        Step 1: Call open_channel with public=True and one_way=True (with retries for init).
        Step 2: Assert error message contains one-way and public.
        """
        open_channel_params = {
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(Amount.ckb(500)),
            "public": True,
            "one_way": True,
        }
        last_error = None
        # Step 1: Call open_channel with public=True and one_way=True (with retries for init)
        for _ in range(15):
            try:
                self.fiber1.get_client().open_channel(open_channel_params)
                pytest.fail("expected open_channel to fail")
            except Exception as e:
                last_error = e
                error_str = str(e)
                if (
                    "feature not found" in error_str
                    or "waiting for peer to send Init message" in error_str
                ):
                    time.sleep(1)
                    continue
                # Step 2: Assert error message contains one-way and public
                assert (
                    "one-way" in error_str.lower() and "public" in error_str.lower()
                ), error_str
                return
        raise last_error

    def test_one_way_channel_can_only_send_one_direction(self):
        """
        One-way channel: fiber1 can send to fiber2; fiber2 sending to fiber1 should fail (no path).
        Step 1: Open private one-way channel.
        Step 2: Send payment from fiber1 to fiber2 and wait for success.
        Step 3: Send payment from fiber2 to fiber1 and assert "no path found" error.
        """
        # Step 1: Open private one-way channel
        self._open_private_one_way_channel()
        # Step 2: Send payment from fiber1 to fiber2 and wait for success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, Timeout.MEDIUM
        )
        # Step 3: Send payment from fiber2 to fiber1 and assert "no path found" error
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                }
            )
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
