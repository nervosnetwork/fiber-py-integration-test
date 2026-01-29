"""
Debug-mode tests for send_payment (e.g. hop hint / private channel routing).
Uses debug fiber build; see https://github.com/nervosnetwork/fiber/issues/620
"""
from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, ChannelState, TLCFeeRate
from framework.test_fiber import FiberConfigPath


class TestWithDebug(FiberTest):
    """
    Test send_payment with debug build: private channels a-b and d-a, path b-c-d;
    a->b, a->c, a->d; a->a (self) and b->a route selection.
    """
    fiber_version = FiberConfigPath.CURRENT_DEV_DEBUG

    def test_not_hophit_issue620(self):
        """
        Topology a-private-b-c-d-private-a. a pays b,c,d; a->a (self); b->a must succeed (direct) or fail if path b-c-d-a without hint.
        Step 1: Start fiber3, fiber4; open a-b and d-a as private; open b-c, c-d; wait channel ready.
        Step 2: Send a->b, a->c, a->d; then a->a (self).
        Step 3: b->a keysend: either success (route b-a) or fail with "no path found" (route b-c-d-a without hop hint).
        """
        # Step 1: Build topology: a-private-b, b-c, c-d, d-private-a
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            1,
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[3],
            Amount.ckb(1000),
            1,
        )

        self.fibers[3].connect_peer(self.fibers[0])
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fibers[3].get_client(),
            self.fibers[0].get_peer_id(),
            ChannelState.CHANNEL_READY,
        )

        # Step 2: a->b, a->c, a->d; then a->a (self)
        for i in range(1, len(self.fibers)):
            self.send_payment(self.fibers[0], self.fibers[i], Amount.ckb(1))
        self.send_payment(self.fibers[0], self.fibers[0], Amount.ckb(1))

        # Step 3: b->a keysend: success with route b-a, or fail if route b-c-d-a without hop hint
        try:
            payment = self.fibers[1].get_client().send_payment(
                {
                    "target_pubkey": self.fibers[0].get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                }
            )
            channels = self.fibers[1].get_client().list_channels(
                {"peer_id": self.fibers[0].get_peer_id()}
            )
            ba_channel_outpoint = channels["channels"][0]["channel_outpoint"]
            assert (
                payment["routers"][0]["nodes"][0]["channel_outpoint"]
                == ba_channel_outpoint
            )
        except Exception as e:
            error_message = str(e)
            assert (
                "no path found" in error_message or "Failed to build route" in error_message
            ), f"Unexpected error message: {error_message}"
