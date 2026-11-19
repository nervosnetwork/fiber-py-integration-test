"""Offline checks for TIMEOUT-05 channel history, chain and activity evidence."""

from copy import deepcopy
import json
from types import SimpleNamespace
import threading

import pytest

from test_cases.fiber.devnet.lsp._aborted_opening import (
    aborted_opening_snapshot,
    replay_activity,
)
from test_cases.fiber.devnet.lsp._funding_spend_gate import FundingSpendGate


def test_abort_snapshot_keeps_full_history_and_checks_conflict_input_and_block():
    funding, point, conflict = (
        "original",
        {"tx_hash": "previous", "index": "0x1"},
        "conflict",
    )
    status = {"status": "committed", "block_number": "0x15", "block_hash": "block"}
    closed = {
        "channel_id": "A",
        "state": {"state_name": "Closed", "state_flags": "FUNDING_ABORTED"},
        "failure_detail": "Funding input spent by another committed transaction",
        "channel_outpoint": None,
        "shutdown_transaction_hash": None,
        "latest_commitment_transaction_hash": None,
    }
    missing = {"status": "unknown", "cell": None}
    tx = {"inputs": [{"previous_output": point}], "hash": conflict}
    canonical = "block"
    active = []

    def rpc(_client, method, params, _until):
        if method == "list_channels":
            reply = [closed] if params == [{"only_pending": True}] else active
            return {"channels": deepcopy(reply)}
        if method == "get_transaction":
            return (
                None
                if params == [funding]
                else {"tx_status": status, "transaction": deepcopy(tx)}
            )
        if method == "get_live_cell":
            assert params[0] in [point, {"tx_hash": funding, "index": "0x0"}]
            return missing.copy()
        assert method == "get_block_hash" and params == ["0x15"]
        return canonical

    case = SimpleNamespace(
        _isolated_rpc=rpc,
        channel_id="A",
        client="tenant",
        node=SimpleNamespace(rpcUrl="ckb"),
    )

    def sample():
        return aborted_opening_snapshot(case, funding, point, conflict, status, 60)

    baseline = sample()
    assert sample() == baseline
    closed["latest_commitment_transaction_hash"] = "unexpected"
    assert sample() != baseline
    active.append({"channel_id": "new-active"})
    with pytest.raises(AssertionError):
        sample()
    active.clear()
    canonical = "reorg"
    with pytest.raises(AssertionError):
        sample()
    canonical = "block"
    tx["inputs"][0]["previous_output"] = {**point, "index": "0x0"}
    with pytest.raises(AssertionError):
        sample()


def test_activity_compares_live_source_frames_and_duplicate_broadcast_attempts():
    request = {
        "type": "channel_signing",
        "data": {
            "channel_id": "A",
            "status": {
                "type": "SignatureRequired",
                "request_id": "r1",
                "transition": "CompleteReceivedCommitment",
            },
        },
    }
    received = [(10, 2, request)]
    delivered = [(11, 2, request)]
    link = SimpleNamespace(
        started=8,
        frames=lambda: received,
        delivered_frames=lambda: delivered,
        errors=[],
        transport_errors=[],
        ended=threading.Event(),
    )
    proxy = SimpleNamespace(
        lock=threading.RLock(),
        errors=[],
        notifications_paused=False,
        successful_subscriptions=lambda: [(9, link, 2, "channel_signing")],
        _active=lambda stream: not stream.ended.is_set(),
    )
    attempts = [(1, "funding"), (2, "some-other-transaction")]
    case = SimpleNamespace(
        tenant={"agent": SimpleNamespace(poll=lambda: None)},
        subscription_proxy=proxy,
        funding_spend_gate=SimpleNamespace(
            errors=[], broadcast_attempts=lambda: attempts
        ),
    )

    def activity():
        return replay_activity(case, "A", "r1", "funding")

    before = activity()
    attempts.append((3, "funding"))
    assert activity() == before
    received.append((12, 2, request))  # FNN request still undelivered to the SDK
    assert activity() != before
    received.pop()
    attempts.append((4, "some-other-transaction"))
    assert activity() != before
    attempts.pop()
    link.started = 13
    assert activity() != before
    link.ended.set()
    with pytest.raises(AssertionError, match="continuously live"):
        activity()


def test_broadcast_attempt_visible_while_ckb_call_is_in_flight(tmp_path, monkeypatch):
    from test_cases.fiber.devnet.lsp import _funding_spend_gate as module

    tx_hash = "0x" + "11" * 32
    gate = FundingSpendGate(
        "http://127.0.0.1", tmp_path / "gate.jsonl", lambda tx: tx_hash
    )
    payload = {"id": 1, "method": "send_transaction", "params": [{}]}

    def upstream(_self, url, **kwargs):
        # The real upstream has not returned yet, so no completed event exists.
        assert gate.broadcast_attempts() == [(10.0, tx_hash)]
        assert not gate.read_events()
        return SimpleNamespace(
            status_code=200,
            headers={},
            content=b"{}",
            json=lambda: {"id": 1, "result": tx_hash},
        )

    monkeypatch.setattr(module.requests.Session, "post", upstream)
    try:
        gate._dispatch(
            {"started": 10.0, "request": payload}, json.dumps(payload).encode(), None
        )
        assert gate.read_events()[0]["tx_hash"] == tx_hash
    finally:
        gate.close()
