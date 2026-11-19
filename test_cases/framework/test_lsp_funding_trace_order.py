"""Offline checks for TIMEOUT-04's first Closed observation at the final tip."""

import json
from types import SimpleNamespace

import pytest

import test_cases.fiber.devnet.lsp.test_channel_signing_deadline as deadline
from test_cases.fiber.devnet.lsp._funding_spend_gate import (
    require_funding_trace_before_close,
)

FUNDING = "0x" + "12" * 32
POINT = {"tx_hash": "0x" + "34" * 32, "index": "0x0"}


def _spent_poll(tip, start):
    calls = [
        ("get_tip_block_number", None, tip),
        ("get_transaction", [FUNDING], None),
        ("get_live_cell", [POINT, False], {"status": "unknown", "cell": None}),
        ("get_transaction", [POINT["tx_hash"]], {"tx_status": {"status": "committed"}}),
        ("get_transaction", [FUNDING], None),
    ]
    return [
        {
            "action": "forwarded",
            "request": {"id": i, "method": method, "params": params},
            "response": {"id": i, "result": result},
            "http_status": 200,
            "started": start + i,
            "upstream_finished": start + i + 0.25,
        }
        for i, (method, params, result) in enumerate(calls)
    ]


def test_complete_final_poll_may_precede_the_first_close_query():
    final = _spent_poll("0x104", 100)
    reads = require_funding_trace_before_close(
        _spent_poll("0x103", 90) + final,
        FUNDING,
        POINT,
        "0x104",
        since=99,
        closed_at=105,
    )
    assert reads == final


@pytest.mark.parametrize(
    "closed_at",
    [99.5, 104.1, 104.25],
    ids=["before-poll", "last-reply-in-flight", "equal"],
)
def test_later_or_simultaneous_final_reply_cannot_justify_first_close(closed_at):
    with pytest.raises(AssertionError, match="first Closed observed"):
        require_funding_trace_before_close(
            _spent_poll("0x104", 100),
            FUNDING,
            POINT,
            "0x104",
            since=99,
            closed_at=closed_at,
        )


@pytest.mark.parametrize(
    "events",
    [
        _spent_poll("0x103", 100),
        _spent_poll("0x104", 90),
        _spent_poll("0x104", 100)[:-1],
        _spent_poll("0x104", 100)[:-1] + _spent_poll("0x103", 106),
    ],
    ids=["wrong-tip", "before-mining", "missing-recheck", "different-round"],
)
def test_incomplete_or_unrelated_poll_cannot_justify_first_close(events):
    with pytest.raises(AssertionError, match="no complete spent-input poll"):
        require_funding_trace_before_close(
            events, FUNDING, POINT, "0x104", since=99, closed_at=120
        )


def test_closed_timestamp_is_taken_at_channel_reply_before_later_chain_reads(
    monkeypatch,
):
    case = object.__new__(deadline.TestChannelSigningDeadline)
    case.client = object()
    case.node = SimpleNamespace(rpcUrl="ckb")
    case.channel_id = "channel-under-test"
    case.tenant = {"agent": SimpleNamespace(poll=lambda: None)}
    case.funding_spend_gate = SimpleNamespace(errors=[])
    case._record_funding_spend = lambda *args, **kwargs: None
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(deadline, "time", SimpleNamespace(monotonic=lambda: clock.now))
    closed = {"channel_id": case.channel_id, "state": {"state_name": "Closed"}}
    replies = {
        "list_channels": {"channels": [closed]},
        "get_transaction": None,
        "get_live_cell": {"status": "unknown", "cell": None},
        "get_tip_block_number": "0x104",
    }

    def rpc(_client, method, _params, _until):
        clock.now += 1
        return replies[method]

    case._isolated_rpc = rpc
    sample = case._funding_spend_sample(FUNDING, [POINT], 120)
    assert sample["channel"] == closed
    assert sample["started"] == 100 and sample["channel_observed_at"] == 101
    assert clock.now == 104


def test_overlapping_pending_and_failed_rows_preserve_both_and_fail(tmp_path):
    case = object.__new__(deadline.TestChannelSigningDeadline)
    case.funding_spend_evidence = tmp_path
    case.node = SimpleNamespace(rpcUrl="ckb")
    case.client = object()
    case.channel_id = "same-channel"
    rows = [
        {"channel_id": case.channel_id, "state": {"state_name": name}}
        for name in ("AwaitingChannelReady", "Closed")
    ]

    def rpc(client, method, params, _until):
        assert client is case.client and method == "list_channels"
        assert params == [{"only_pending": True}]
        return {"channels": rows}

    case._isolated_rpc = rpc
    with pytest.raises(AssertionError, match="missing or duplicate"):
        case._funding_spend_sample(FUNDING, [POINT], 100)
    saved = json.loads((tmp_path / "observations.jsonl").read_text())
    assert (
        saved["stage"] == "opening_record_count_mismatch" and saved["pending"] == rows
    )
