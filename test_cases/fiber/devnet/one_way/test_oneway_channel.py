import time

import pytest

from framework.basic_fiber import FiberTest


class TestOneWayChannel(FiberTest):

    debug = False

    def _open_private_one_way_channel(self, funding_amount_ckb=500):
        open_channel_params = {
            "pubkey": self.fiber2.get_pubkey(),
            "funding_amount": hex(funding_amount_ckb * 100000000),
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
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY"
        )
        time.sleep(1)

    def _get_channel_id(self, client, peer_id, include_closed=False):
        channels = client.list_channels(
            {"pubkey": peer_id, "include_closed": include_closed}
        )
        assert len(channels["channels"]) > 0, channels
        return channels["channels"][0]["channel_id"]

    def test_one_way_channel_cannot_be_public(self):
        open_channel_params = {
            "pubkey": self.fiber2.get_pubkey(),
            "funding_amount": hex(500 * 100000000),
            "public": True,
            "one_way": True,
        }
        last_error = None
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
                assert (
                    "one-way" in error_str.lower() and "public" in error_str.lower()
                ), error_str
                return
        raise last_error

    def test_one_way_channel_can_only_send_one_direction(self):
        self._open_private_one_way_channel()

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["pubkey"],
                "amount": hex(10 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                }
            )
        expected_error_message = "Insufficient balance"
        assert (
            expected_error_message in exc_info.value.args[0]
            or "no path found" in exc_info.value.args[0]
        ), (
            f"Expected substring '{expected_error_message}' or 'no path found' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
