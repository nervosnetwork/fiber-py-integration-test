"""TIMEOUT-05: observations of a single Hosted opening after funding abort."""


def aborted_opening_snapshot(
    case, funding_hash, point, conflict_hash, expected_conflict_status, until
):
    rpc = case._isolated_rpc
    pending = rpc(case.client, "list_channels", [{"only_pending": True}], until)[
        "channels"
    ]
    active = rpc(case.client, "list_channels", [{}], until)["channels"]
    ckb = case.node.rpcUrl
    original = rpc(ckb, "get_transaction", [funding_hash], until)
    original_input = rpc(ckb, "get_live_cell", [point, False], until)
    funding_output = rpc(
        ckb, "get_live_cell", [{"tx_hash": funding_hash, "index": "0x0"}, False], until
    )
    conflict = rpc(ckb, "get_transaction", [conflict_hash], until)
    canonical = rpc(
        ckb, "get_block_hash", [expected_conflict_status["block_number"]], until
    )

    # This independent environment opens only the one Hosted channel.
    assert len(pending) == 1 and pending[0]["channel_id"] == case.channel_id, pending
    failed = pending[0]
    assert failed["state"] == {
        "state_name": "Closed",
        "state_flags": "FUNDING_ABORTED",
    }, failed
    assert (
        "funding input spent by another committed transaction"
        in failed["failure_detail"].lower()
    ), failed
    assert (
        failed["channel_outpoint"] is None
        and failed["shutdown_transaction_hash"] is None
    ), failed
    assert not active, active
    assert original is None or original["tx_status"]["status"] == "unknown", original
    for cell in (original_input, funding_output):
        assert cell["cell"] is None and cell["status"] in {"dead", "unknown"}, cell
    assert conflict["tx_status"] == expected_conflict_status, conflict
    assert (
        expected_conflict_status["status"] == "committed"
        and canonical == expected_conflict_status["block_hash"]
    ), conflict
    transaction = conflict["transaction"]
    assert (
        transaction["hash"] == conflict_hash and conflict_hash != funding_hash
    ), transaction
    assert [item["previous_output"] for item in transaction["inputs"]] == [
        point
    ], transaction
    return {
        "pending": pending,
        "active": active,
        "original": original,
        "original_input": original_input,
        "funding_output": funding_output,
        "conflict": conflict,
        "canonical_block_hash": canonical,
    }


def replay_activity(case, channel_id, request_id, funding_hash):
    """Compare cumulative signing requests and broadcast attempts across replay."""
    assert case.tenant["agent"].poll() is None, "Hosted SDK exited"
    proxy = case.subscription_proxy
    with proxy.lock:
        assert not proxy.errors and not proxy.notifications_paused, proxy.errors
        streams = [
            (link, identity)
            for _, link, identity, topic in proxy.successful_subscriptions()
            if topic == "channel_signing" and proxy._active(link)
        ]
        assert (
            len(streams) == 1
        ), "a continuously live SDK channel-signing subscription is required"
        link, identity = streams[0]
        assert (
            not link.ended.is_set() and not link.errors and not link.transport_errors
        ), (link.errors, link.transport_errors)

        def required(frames):
            return [
                (
                    at,
                    event["data"]["status"]["request_id"],
                    event["data"]["status"]["transition"],
                )
                for at, sub, event in frames
                if type(sub) is type(identity)
                and sub == identity
                and event["type"] == "channel_signing"
                and event["data"]["channel_id"] == channel_id
                and event["data"]["status"]["type"] == "SignatureRequired"
            ]

        received = required(link.frames())
        delivered = required(link.delivered_frames())
        assert any(
            req == request_id
            and transition in {"CompleteReceivedCommitment", "SendCommitmentSigned"}
            for _, req, transition in delivered
        ), ("opening signature notification missing from the SDK stream", delivered)
        connection = {"started": link.started, "subscription_id": identity}

    gate = case.funding_spend_gate
    assert not gate.errors, gate.errors
    attempts = gate.broadcast_attempts()
    assert any(
        tx == funding_hash for _, tx in attempts
    ), "original funding broadcast was not observed"
    return {
        "connection": connection,
        "required_received": received,
        "required_delivered": delivered,
        # The gate blocks periodic rebroadcasts of the original funding hash.
        # Every other write is observable on entry, including a duplicate hash.
        "other_broadcasts": [(at, tx) for at, tx in attempts if tx != funding_hash],
    }
