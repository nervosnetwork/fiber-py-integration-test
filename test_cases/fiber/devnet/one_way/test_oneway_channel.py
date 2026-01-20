import time

import pytest

from framework.basic_fiber import FiberTest
from framework.test_fiber import Fiber


class TestOneWayChannel(FiberTest):

    debug = True

    def _open_private_one_way_channel(self):
        open_channel_params = {
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(500 * 100000000),
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
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )
        time.sleep(1)

    def test_one_way_channel_cannot_be_public(self):
        open_channel_params = {
            "peer_id": self.fiber2.get_peer_id(),
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
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(10 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        try:
            reverse_payment = self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            assert "no path found" in error_str or "failed to build route" in error_str, error_str
            return

        result = self.wait_payment_finished(
            self.fiber2, reverse_payment["payment_hash"]
        )
        assert result["status"] == "Failed", result
        failed_error = result.get("failed_error")
        if failed_error is not None:
            failed_error = failed_error.lower()
            assert (
                "reverse direction" in failed_error
                or "incorrecttlcdirection" in failed_error
                or "one way" in failed_error
            ), result
