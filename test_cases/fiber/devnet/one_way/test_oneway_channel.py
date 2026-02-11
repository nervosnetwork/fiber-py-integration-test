import time

import pytest

from framework.basic_fiber import FiberTest


class TestOneWayChannel(FiberTest):

    debug = False

    def _open_private_one_way_channel(self, funding_amount_ckb=500):
        open_channel_params = {
            "peer_id": self.fiber2.get_peer_id(),
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
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )
        time.sleep(1)

    def _get_channel_id(self, client, peer_id, include_closed=False):
        channels = client.list_channels(
            {"peer_id": peer_id, "include_closed": include_closed}
        )
        assert len(channels["channels"]) > 0, channels
        return channels["channels"][0]["channel_id"]

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

        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "no path found" in error_str or "failed to build route" in error_str
        ), error_str

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
            assert (
                "no path found" in error_str or "failed to build route" in error_str
            ), error_str
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

    def test_one_way_channel_source_payment_success(self):
        self._open_private_one_way_channel()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(1 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_one_way_channel_as_middle_hop_should_fail(self):
        self._open_private_one_way_channel()
        self.fiber3 = self.start_new_fiber(self.generate_account(1000))
        self.fiber3.connect_peer(self.fiber1)
        self.open_channel(self.fiber1, self.fiber3, 500 * 100000000, 0)

        try:
            reverse_payment = self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            assert (
                "no path found" in error_str
                or "failed to build route" in error_str
                or "incorrecttlcdirection" in error_str
                or "one way" in error_str
            ), error_str
            return

        result = self.wait_payment_finished(
            self.fiber2, reverse_payment["payment_hash"]
        )
        assert result["status"] == "Failed", result

    def test_one_way_channel_shutdown_remote_balance_gt_1000(self):
        self._open_private_one_way_channel(funding_amount_ckb=2000)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(1500 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        channel_id = self._get_channel_id(
            self.fiber1.get_client(), self.fiber2.get_peer_id()
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.fiber1.get_account()["lock_arg"],
                },
                "fee_rate": "0x3FC",
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CLOSED",
            360,
            True,
            channel_id,
        )

    def test_one_way_channel_shutdown_remote_balance_lt_90(self):
        self._open_private_one_way_channel(funding_amount_ckb=200)
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(50 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        channel_id = self._get_channel_id(
            self.fiber1.get_client(), self.fiber2.get_peer_id()
        )
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": channel_id,
                "close_script": {
                    "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                    "hash_type": "type",
                    "args": self.fiber1.get_account()["lock_arg"],
                },
                "fee_rate": "0x3FC",
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CLOSED",
            360,
            True,
            channel_id,
        )

    def test_one_way_channel_restart_should_keep_directional_rules(self):
        self._open_private_one_way_channel()
        self.fiber1.stop()
        self.fiber2.stop()
        time.sleep(3)
        self.fiber1.start()
        self.fiber2.start()
        time.sleep(3)
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(1)
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 180
        )

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(1 * 100000000),
                "keysend": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "dry_run": True,
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "no path found" in error_str or "failed to build route" in error_str
        ), error_str
