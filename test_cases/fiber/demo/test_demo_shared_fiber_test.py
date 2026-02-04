"""
SharedFiberTest demo: shared Fiber environment within the same test class.

Demonstrates that when inheriting SharedFiberTest, setup_class starts fiber1/fiber2,
subclass initializes topology once in setUp (e.g. open channel), multiple test cases
reuse the same environment, teardown_class cleans up. Use for multiple parameter/scenario
validation on the same topology.
"""
from framework.basic_share_fiber import SharedFiberTest
from framework.constants import Amount, Timeout, PaymentStatus, PaymentFeeRate, TLCFeeRate


class TestDemoSharedFiberTest(SharedFiberTest):
    """
    SharedFiberTest demo: fiber1 and fiber2 start in setup_class,
    this class opens one fiber1<->fiber2 channel in setUp once, multiple cases share the topology.
    Case 1: Assert list_channels returns at least one channel.
    Case 2: fiber1 sends keysend payment to fiber2 and assert success.
    """

    def setUp(self):
        """Initialize once: open one channel between fiber1 and fiber2 for subsequent cases to reuse."""
        if getattr(TestDemoSharedFiberTest, "_channel_inited", False):
            return
        TestDemoSharedFiberTest._channel_inited = True

        # Build fiber1 <-> fiber2 single-hop channel (fiber1: 1000 CKB, fiber2: 0)
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(0),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

    def test_list_channels_after_shared_setup(self):
        """
        Query fiber1's channel list under shared topology, assert at least one channel with fiber2.
        Demonstrates SharedFiberTest reusing the channel built in setUp.
        Step 1: Query fiber1's channels with fiber2.
        Step 2: Assert at least one channel exists using assertion helper.
        """
        # Step 1: Query fiber1's channels with fiber2
        channels_resp = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )

        # Step 2: Assert at least one channel exists
        assert "channels" in channels_resp, "Response should contain channels field"
        assert len(channels_resp["channels"]) >= 1, "Should have at least one channel after shared setUp"

    def test_send_payment_shared_topology(self):
        """
        Under shared topology, fiber1 sends keysend payment to fiber2, wait for Success and assert.
        Demonstrates SharedFiberTest reusing the same topology for payment scenario.
        Step 1: fiber1 sends keysend payment to fiber2.
        Step 2: Wait for payment status to be Success.
        Step 3: Assert payment success using assertion helper.
        """
        amount = Amount.ckb(10)  # 10 CKB

        # Step 1: fiber1 sends keysend payment to fiber2
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "allow_self_payment": True,
                "max_fee_rate": hex(PaymentFeeRate.MAX),
            }
        )

        # Step 2: Wait for payment status to be Success
        self.wait_payment_state(
            self.fiber1,
            payment["payment_hash"],
            PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 3: Assert payment success using assertion helper
        self.assert_payment_success(self.fiber1, payment["payment_hash"])
