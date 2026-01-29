"""
Trampoline routing tests: private channel (update enabled=False) and path failure.
"""

import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestPrivateChannel(FiberTest):
    """
    Trampoline via private channel: f2->f3 disabled; pay f1->f4 fails; pay f2->f4
    via trampoline f3 yields no path.
    """

    def test_private_channel(self):
        """
        Disable f2->f3 channel; pay f1->f4 via trampoline fails; pay f2->f4 via f3 no path.
        Step 1: Create fiber3..4; open f1-f2, f2-f3, f3-f4.
        Step 2: update_channel f2->f3 enabled=False; wait.
        Step 3: Keysend f1->f4 via trampoline [f2,f3]; wait Failed.
        Step 4: Keysend f2->f4 via trampoline [f3]; expect no path.
        """
        # Step 1: Create fiber3..4; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(1000),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(1000),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(1000),
        )

        # Step 2: update_channel f2->f3 enabled=False; wait
        channel = self.fiber2.get_client().list_channels(
            {"peer_id": self.fiber3.get_peer_id()}
        )
        self.fiber2.get_client().update_channel(
            {"channel_id": channel["channels"][0]["channel_id"], "enabled": False}
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 3: Keysend f1->f4 via trampoline [f2,f3]; wait Failed
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.FAILED,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 4: Keysend f2->f4 via trampoline [f3]; expect no path
        with pytest.raises(Exception) as exc_info:
            self.fiber2.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [self.fiber3.get_client().node_info()["node_id"]],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "no path found" in err or "Failed" in str(exc_info.value)
