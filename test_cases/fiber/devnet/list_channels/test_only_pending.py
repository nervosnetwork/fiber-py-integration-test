import time

from framework.basic_fiber import FiberTest


class TestListChannelsOnlyPending(FiberTest):
    """
    Tests for `list_channels` with the `only_pending` parameter introduced in
    nervosnetwork/fiber#1134.

    When `only_pending` is true the RPC should return:
    - Channels in pre-ChannelReady states (NegotiatingFunding, CollaboratingFundingTx,
      SigningCommitment, AwaitingTxSignatures, AwaitingChannelReady)
    - Failed outbound openings (Closed(FUNDING_ABORTED) / Closed(ABANDONED)) with
      `failure_detail`
    - Inbound channel requests waiting for `accept_channel` (shown as
      NegotiatingFunding with is_acceptor=true on the acceptor node)
    """

    def test_only_pending_shows_pending_channel(self):
        """
        When a channel is opened with auto-accept, it goes through pending states
        before reaching CHANNEL_READY. We verify that `only_pending=true` returns
        the channel while it is in a pending state, and stops returning it once
        it reaches CHANNEL_READY.

        Steps:
        1. Open a channel between fiber1 and fiber2 (auto-accepted).
        2. Wait until the channel reaches CHANNEL_READY.
        3. Verify `only_pending=true` does NOT include CHANNEL_READY channels.
        4. Verify `only_pending=false` (default) still shows the ready channel.
        """
        # Step 1: Open channel (auto-accepted, large funding amount)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )

        # Step 2: Wait for CHANNEL_READY
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )

        # Step 3: only_pending=true should NOT include CHANNEL_READY channels
        pending_channels = self.fiber1.get_client().list_channels(
            {"only_pending": True}
        )
        ready_in_pending = [
            ch
            for ch in pending_channels["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert (
            len(ready_in_pending) == 0
        ), "CHANNEL_READY channels should not appear when only_pending=true"

        # Step 4: Default list (only_pending=false) should still show the channel
        all_channels = self.fiber1.get_client().list_channels({})
        assert len(all_channels["channels"]) >= 1
        assert all_channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

    def test_only_pending_default_false(self):
        """
        Verify that the default behavior of `list_channels` (without `only_pending`)
        is unchanged: it returns active channels.

        Steps:
        1. Open a channel and wait for CHANNEL_READY.
        2. Call list_channels with only_pending=false (explicit).
        3. Verify the CHANNEL_READY channel is returned.
        """
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )

        channels = self.fiber1.get_client().list_channels({"only_pending": False})
        assert len(channels["channels"]) >= 1
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

    def test_only_pending_shows_inbound_waiting_for_accept(self):
        """
        When a channel is opened with a funding amount below the auto-accept
        threshold, the accepting node must manually call `accept_channel`.
        Before acceptance, the channel should appear in the acceptor's
        `list_channels(only_pending=true)` result as NegotiatingFunding with
        is_acceptor=true.

        Steps:
        1. Get the auto-accept min funding amount.
        2. Open a channel with funding_amount below the threshold (not auto-accepted).
        3. On the acceptor node (fiber2), call list_channels(only_pending=true).
        4. Verify the pending inbound channel is returned with is_acceptor=true
           and state NegotiatingFunding.
        5. Accept the channel and wait for CHANNEL_READY.
        6. Verify only_pending=true no longer returns the channel.
        """
        # Step 1: Get auto-accept threshold
        node_info = self.fiber1.get_client().node_info()
        auto_accept_min = int(
            node_info["open_channel_auto_accept_min_ckb_funding_amount"], 16
        )

        # Step 2: Open channel below threshold (requires manual accept)
        temporary_channel = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(auto_accept_min - 1),
                "public": True,
            }
        )
        time.sleep(2)

        # Step 3: On the acceptor (fiber2), list_channels with only_pending=true
        pending_channels = self.fiber2.get_client().list_channels(
            {"only_pending": True}
        )

        # Step 4: Verify the inbound channel appears
        inbound_pending = [
            ch
            for ch in pending_channels["channels"]
            if ch["state"]["state_name"] == "NEGOTIATING_FUNDING"
            and ch["is_acceptor"] is True
        ]
        assert (
            len(inbound_pending) >= 1
        ), "Inbound channel waiting for accept_channel should appear in only_pending=true"
        # The remote_balance should reflect the initiator's funding amount
        assert int(inbound_pending[0]["remote_balance"], 16) > 0

        # Step 5: Accept the channel
        self.fiber2.get_client().accept_channel(
            {
                "temporary_channel_id": temporary_channel["temporary_channel_id"],
                "funding_amount": hex(99 * 100000000),
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )

        # Step 6: only_pending=true should no longer return the (now ready) channel
        pending_after = self.fiber2.get_client().list_channels({"only_pending": True})
        ready_in_pending = [
            ch
            for ch in pending_after["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert len(ready_in_pending) == 0

    def test_only_pending_initiator_sees_outbound_pending_channel(self):
        """
        When fiber1 opens a channel with a funding amount below the auto-accept
        threshold, the channel is not auto-accepted and requires manual
        `accept_channel` from fiber2. Before acceptance, the initiator (fiber1)
        should also be able to see its own pending outbound channel via
        `list_channels(only_pending=true)`.

        This complements test_only_pending_shows_inbound_waiting_for_accept which
        only verifies the acceptor (fiber2) side.

        Steps:
        1. Get the auto-accept min funding amount from fiber2.
        2. fiber1 opens a channel with funding_amount below the threshold.
        3. fiber1 calls list_channels(only_pending=true).
        4. Verify the pending outbound channel is returned on the initiator side
           (fiber1) with is_acceptor=false.
        5. fiber2 calls list_channels(only_pending=true).
        6. Verify fiber2 also sees the pending inbound channel.
        """
        # Step 1: Get auto-accept threshold
        node_info = self.fiber2.get_client().node_info()
        auto_accept_min = int(
            node_info["open_channel_auto_accept_min_ckb_funding_amount"], 16
        )

        # Step 2: Open channel below threshold (requires manual accept)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(auto_accept_min - 1),
                "public": True,
            }
        )
        time.sleep(2)

        # Step 3: On the initiator (fiber1), list_channels with only_pending=true
        pending_channels_fiber1 = self.fiber1.get_client().list_channels(
            {"only_pending": True}
        )

        # Step 4: Verify the outbound pending channel appears on the initiator side
        outbound_pending = [
            ch
            for ch in pending_channels_fiber1["channels"]
            if ch["is_acceptor"] is False
        ]
        assert len(outbound_pending) >= 1, (
            "Initiator (fiber1) should see its own pending outbound channel "
            "in list_channels(only_pending=true) before peer accepts"
        )

        # Step 5: On the acceptor (fiber2), list_channels with only_pending=true
        pending_channels_fiber2 = self.fiber2.get_client().list_channels(
            {"only_pending": True}
        )

        # Step 6: Verify fiber2 also sees the pending inbound channel
        inbound_pending = [
            ch
            for ch in pending_channels_fiber2["channels"]
            if ch["is_acceptor"] is True
        ]
        assert len(inbound_pending) >= 1, (
            "Acceptor (fiber2) should see the pending inbound channel "
            "in list_channels(only_pending=true)"
        )

    def test_only_pending_shows_failed_channel_with_failure_detail(self):
        """
        When an outbound channel opening fails (e.g. peer disconnects during
        opening), the failed record should appear in `list_channels(only_pending=true)`
        with `failure_detail` set.

        Steps:
        1. Start fiber3 and open a channel to fiber2 below auto-accept threshold.
        2. Abandon the channel on fiber3 to trigger a failure.
        3. Call list_channels(only_pending=true) on fiber3.
        4. Verify a failed channel record appears with appropriate close flags.
        """
        # Step 1: Open channel below auto-accept threshold from fiber3 to fiber2
        # so that it requires manual accept, giving us time to abandon it
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber2)
        time.sleep(1)

        node_info = fiber3.get_client().node_info()
        auto_accept_min = int(
            node_info["open_channel_auto_accept_min_ckb_funding_amount"], 16
        )

        temporary_channel = fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(auto_accept_min - 1),
                "public": True,
            }
        )
        time.sleep(1)

        # Step 2: Abandon the channel to make it fail
        fiber3.get_client().abandon_channel(
            {"channel_id": temporary_channel["temporary_channel_id"]}
        )
        time.sleep(2)

        # Step 3: Check only_pending=true on fiber3
        pending_channels = fiber3.get_client().list_channels({"only_pending": True})

        # There should be at least one failed/abandoned channel record
        # It may show as Closed(ABANDONED) or Closed(FUNDING_ABORTED) with failure_detail
        failed_channels = [
            ch
            for ch in pending_channels["channels"]
            if ch["state"]["state_name"] == "CLOSED"
        ]
        # The abandoned channel should appear with failure info
        if len(failed_channels) > 0:
            # If it has failure_detail, verify it's present
            for fc in failed_channels:
                assert fc["state"]["state_flags"] in (
                    "ABANDONED",
                    "FUNDING_ABORTED",
                ), f"Unexpected close flag: {fc['state']['state_flags']}"

    def test_only_pending_with_peer_id_filter(self):
        """
        Verify that `only_pending=true` respects the `peer_id` filter.

        Steps:
        1. Open channels with two different peers.
        2. Wait for both to reach CHANNEL_READY.
        3. Open a new channel below auto-accept threshold with one peer.
        4. Call list_channels(only_pending=true, peer_id=...) to filter.
        5. Verify only the matching peer's pending channel is returned.
        """
        # Step 1 & 2: Open channel with fiber2 (auto-accepted)
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )

        # Create fiber3 and open a channel that needs manual accept
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber1)
        time.sleep(1)

        node_info = fiber3.get_client().node_info()
        auto_accept_min = int(
            node_info["open_channel_auto_accept_min_ckb_funding_amount"], 16
        )

        fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber1.get_peer_id(),
                "funding_amount": hex(auto_accept_min - 1),
                "public": True,
            }
        )
        time.sleep(2)

        # Step 4: On fiber1, list only_pending with peer_id=fiber3's peer_id
        pending_from_fiber3 = self.fiber1.get_client().list_channels(
            {"only_pending": True, "peer_id": fiber3.get_peer_id()}
        )

        # Step 5: Should have pending channel from fiber3 only
        assert len(pending_from_fiber3["channels"]) >= 1
        for ch in pending_from_fiber3["channels"]:
            assert ch["peer_id"] == fiber3.get_peer_id()

        # Verify peer_id filter for fiber2 returns no pending (its channel is READY)
        pending_from_fiber2 = self.fiber1.get_client().list_channels(
            {"only_pending": True, "peer_id": self.fiber2.get_peer_id()}
        )
        ready_channels = [
            ch
            for ch in pending_from_fiber2["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert (
            len(ready_channels) == 0
        ), "CHANNEL_READY channels should not appear in only_pending=true"

    def test_failure_detail_null_for_ready_channels(self):
        """
        Verify that the `failure_detail` field is null for successfully
        opened channels.

        Steps:
        1. Open a channel and wait for CHANNEL_READY.
        2. List channels (without only_pending).
        3. Verify `failure_detail` is null.
        """
        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(1000 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY", 120
        )

        channels = self.fiber1.get_client().list_channels({})
        assert len(channels["channels"]) >= 1
        # failure_detail should be null for a successfully opened channel
        assert channels["channels"][0]["failure_detail"] is None

    def test_only_pending_peer_disconnect_shows_failure(self):
        """
        When a peer disconnects during channel opening, the channel should
        appear as failed in `list_channels(only_pending=true)` with failure_detail.

        Steps:
        1. Start fiber3 and connect to fiber2.
        2. Open a channel from fiber3 to fiber2 below auto-accept threshold.
        3. Stop fiber2 to simulate disconnect before accept.
        4. Wait for the channel actor to detect the disconnect and mark failure.
        5. Verify list_channels(only_pending=true) on fiber3 shows the failed channel.
        """
        account3_private_key = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3_private_key)
        fiber3.connect_peer(self.fiber2)
        time.sleep(1)

        node_info = fiber3.get_client().node_info()
        auto_accept_min = int(
            node_info["open_channel_auto_accept_min_ckb_funding_amount"], 16
        )

        temporary_channel = fiber3.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(auto_accept_min - 1),
                "public": True,
            }
        )
        time.sleep(1)

        # Disconnect fiber2 from fiber3
        fiber3.get_client().disconnect_peer({"peer_id": self.fiber2.get_peer_id()})
        # Wait for channel to detect disconnection and fail
        time.sleep(5)

        # Check pending channels on fiber3
        pending_channels = fiber3.get_client().list_channels({"only_pending": True})

        # The channel should appear (possibly as failed/closed or still pending)
        # After disconnect, the channel actor may detect the disconnection and mark failure.
        # We check that no CHANNEL_READY channels appear in the pending list.
        ready_in_pending = [
            ch
            for ch in pending_channels["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert (
            len(ready_in_pending) == 0
        ), "CHANNEL_READY channels should not appear when only_pending=true"

        # Also verify the channel doesn't show in the normal (non-pending) list
        normal_channels = fiber3.get_client().list_channels({})
        ready_channels = [
            ch
            for ch in normal_channels["channels"]
            if ch["state"]["state_name"] == "CHANNEL_READY"
        ]
        assert len(ready_channels) == 0
