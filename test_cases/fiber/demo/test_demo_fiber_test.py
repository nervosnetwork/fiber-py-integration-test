"""
FiberTest demo: each test case has an independent environment.

Demonstrates that when inheriting FiberTest, each test method gets a fresh fiber1/fiber2
in setup_method and cleanup in teardown_method. Use for simple connectivity, single
open_channel, etc.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState, TLCFeeRate
from framework.waiter import Waiter, WaitConfig


class TestDemoFiberTest(FiberTest):
    """
    FiberTest demo: each test case has independent CKB + fiber1/fiber2 environment.
    Case 1: Connect peer and verify node_info.
    Case 2: Open channel and verify list_channels.
    """

    def test_connect_peer_and_node_info(self):
        """
        Connect fiber1 to fiber2, query node_info, assert peers_count is 1.
        Demonstrates FiberTest's per-case isolated environment.
        Step 1: Connect fiber1 to fiber2 (base class starts both nodes in setup_method).
        Step 2: Wait for connection to be ready.
        Step 3: Get node_info and assert peers_count.
        """
        # Step 1: Connect fiber1 to fiber2 (base class already starts both nodes in setup_method)
        self.fiber1.connect_peer(self.fiber2)

        # Step 2: Wait for connection to be ready (use Waiter instead of time.sleep)
        Waiter.wait_until(
            condition=lambda: self.fiber1.get_client().node_info().get("peers_count") == "0x1",
            config=WaitConfig(timeout=Timeout.SHORT, interval=Timeout.POLL_INTERVAL),
            error_message="Peer connection not ready within timeout",
        )

        # Step 3: Get node_info and assert peers_count
        node_info = self.fiber1.get_client().node_info()
        assert node_info["peers_count"] == "0x1", "Should have 1 peer after connect"

    def test_open_channel_and_list_channels(self):
        """
        Open a channel between fiber1 and fiber2, then list_channels and assert READY channel exists.
        Demonstrates full flow of open_channel and list_channels.
        Step 1: Open channel between fiber1 and fiber2 (fiber1: 1000 CKB, fiber2: 0).
        Step 2: Wait for channel to reach CHANNEL_READY state.
        Step 3: Assert channel exists and state is CHANNEL_READY using assertion helper.
        """
        # Step 1: Open channel between fiber1 and fiber2 (fiber1: 1000 CKB, fiber2: 0)
        self.open_channel(
            self.fiber1,
            self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(0),
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT,
        )

        # Step 2: open_channel already waits for CHANNEL_READY internally

        # Step 3: Assert channel exists and state is CHANNEL_READY using assertion helper
        self.assert_channel_state(
            self.fiber1,
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY,
        )
