"""Offline controls for the opening signature's Applied and cleared-channel receipts."""

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
import requests

from test_cases.fiber.devnet.lsp._opening_replay import (
    assert_channel_gone,
    direct_tenant_rpc,
    opening_applied_receipt,
)

CHANNEL = "0x" + "11" * 32
AUTH = "Bearer fixture-token"


def _applied():
    params = {
        "channel_id": CHANNEL,
        "request_id": "0x" + "22" * 32,
        "partial_signature": "0x" + "33" * 32,
        "next_material": {"next_commitment_point": "original material"},
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "submit_channel_signature",
        "params": [copy.deepcopy(params)],
    }
    return {
        "method": payload["method"],
        "action": "forward",
        "headers": {"authorization_sha256": hashlib.sha256(AUTH.encode()).hexdigest()},
        "payload": payload,
        "params": params,
        "reply": {"jsonrpc": "2.0", "id": 1, "result": {"type": "Applied"}},
        "error": None,
        "forward_started_at": 1.0,
        "forward_finished_at": 2.0,
        "reply_sent_at": 3.0,
    }


def test_original_applied_receipt_preserves_every_rpc_param():
    row = _applied()
    unchanged = copy.deepcopy(row)
    assert opening_applied_receipt({"requests": [row]}, CHANNEL, AUTH, 4.0) == unchanged


@pytest.mark.parametrize(
    "location, value",
    [
        (("headers", "authorization_sha256"), hashlib.sha256(b"other").hexdigest()),
        (("params", "channel_id"), "0x" + "44" * 32),
        (("reply", "result"), {"type": "AlreadyApplied"}),
        (("reply_sent_at",), None),
        (("reply_sent_at",), 4.5),
        (("payload", "params", 0, "next_material"), None),
    ],
    ids=[
        "other-tenant",
        "other-channel",
        "already-applied",
        "not-delivered",
        "after-wallet",
        "altered-material",
    ],
)
def test_unqualified_signature_does_not_supply_an_applied_receipt(location, value):
    row = _applied()
    field = row
    for key in location[:-1]:
        field = field[key]
    field[location[-1]] = value
    with pytest.raises(AssertionError):
        opening_applied_receipt({"requests": [row]}, CHANNEL, AUTH, 4.0)


def _missing():
    return {
        "request": _applied()["payload"],
        "http_status": 200,
        "body": {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": f"channel Hash256({CHANNEL}) not found",
            },
        },
    }


def test_fnn_missing_channel_error_is_accepted():
    assert_channel_gone(_missing(), CHANNEL)


@pytest.mark.parametrize(
    "amend",
    [
        {
            "error": {
                "code": -32000,
                "message": f"channel Hash256({'0x' + '55' * 32}) not found",
            }
        },
        {"error": {"code": -32000, "message": "unauthorized"}},
        {"error": {"code": -32000, "message": "signature request no longer pending"}},
        {"error": {"code": -32602, "message": f"channel Hash256({CHANNEL}) not found"}},
        {"error": {"code": -32601, "message": "method not found"}},
        {"result": {"type": "AlreadyApplied"}},
        {"result": {"type": "Applied"}},
        {"result": None, "error": _missing()["body"]["error"]},
        {},
        {"id": 2, "error": _missing()["body"]["error"]},
        {"error": {**_missing()["body"]["error"], "data": "wrong handler"}},
    ],
    ids=[
        "other-channel",
        "auth-denial",
        "stale-signature",
        "invalid-params",
        "missing-method",
        "already-applied",
        "applied",
        "both",
        "neither",
        "other-id",
        "error-data",
    ],
)
def test_wrong_rpc_outcome_cannot_qualify_as_removed_channel(amend):
    record = _missing()
    record["body"] = {"jsonrpc": "2.0", "id": 1, **amend}
    with pytest.raises(AssertionError):
        assert_channel_gone(record, CHANNEL)


@pytest.mark.parametrize("http_status", [200, 503])
def test_one_direct_call_uses_original_signature_and_authorization(
    monkeypatch, http_status
):
    original = _applied()
    response = requests.Response()
    response.status_code = http_status
    response._content = json.dumps(_missing()["body"]).encode()
    client = SimpleNamespace(
        url="http://localhost:1/", other_params={"Authorization": AUTH}
    )
    calls = []

    def send(session, request, **options):
        assert not session.trust_env
        assert request.url == client.url and request.headers["Authorization"] == AUTH
        assert options == {"timeout": 1.0, "allow_redirects": False}
        calls.append(json.loads(request.body))
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    record = direct_tenant_rpc(client, original["payload"], 1.0)
    assert calls == [original["payload"]]
    assert record["request"] == calls[0]
    assert record["authorization_sha256"] == original["headers"]["authorization_sha256"]
    if http_status == 200:
        assert_channel_gone(record, CHANNEL)
    else:
        with pytest.raises(AssertionError):
            assert_channel_gone(record, CHANNEL)
