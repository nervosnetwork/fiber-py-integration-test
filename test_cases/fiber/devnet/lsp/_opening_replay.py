"""Match one applied opening signature and attribute a retry on its closed channel."""

import hashlib
import json
import re
import time

import requests


def opening_applied_receipt(audit, channel_id, authorization, before):
    """Select an actual Applied reply delivered to the opening SDK before wallet submission."""
    assert authorization.startswith("Bearer ") and authorization[7:].strip()
    tenant_digest = hashlib.sha256(authorization.encode()).hexdigest()
    for row in audit["requests"]:
        if (
            row["method"] != "submit_channel_signature"
            or row["action"] != "forward"
            or row["error"] is not None
            or row["headers"]["authorization_sha256"] != tenant_digest
            or row["reply_sent_at"] is None
            or row["reply_sent_at"] >= before
        ):
            continue
        request, reply, params = row["payload"], row["reply"], row["params"]
        if params["channel_id"] != channel_id or reply.get("result") != {
            "type": "Applied"
        }:
            continue
        assert (
            row["forward_started_at"]
            <= row["forward_finished_at"]
            <= row["reply_sent_at"]
        )
        assert request["jsonrpc"] == "2.0" and request["method"] == row["method"]
        assert request["params"] == [
            params
        ], "snapshot differs from forwarded SDK payload"
        assert type(reply["id"]) is type(request["id"])
        assert reply["jsonrpc"] == "2.0" and reply["id"] == request["id"]
        assert "error" not in reply and "next_material" in params
        for key in ("request_id", "partial_signature"):
            assert re.fullmatch(r"0x[0-9a-fA-F]{64}", params[key]), key
        return row
    raise AssertionError(
        "no original Applied opening reply for this tenant and channel"
    )


def direct_tenant_rpc(client, payload, timeout):
    """Make one call, keeping its actual JSON, authorization digest and unmodified reply."""
    with requests.Session() as session:
        session.trust_env = False
        prepared = session.prepare_request(
            requests.Request(
                "POST", client.url, headers=client.other_params, json=payload
            )
        )
        authorization = prepared.headers["Authorization"]
        record = {
            "request": json.loads(prepared.body),
            "authorization_sha256": hashlib.sha256(authorization.encode()).hexdigest(),
            "http_status": None,
            "body": None,
            "started": time.monotonic(),
        }
        try:
            response = session.send(prepared, timeout=timeout, allow_redirects=False)
            record["http_status"] = response.status_code
            if authorization.removeprefix("Bearer ").encode() in response.content:
                # Preserve a fingerprint if an HTTP error page echoes the credential.
                record["credential_in_reply_sha256"] = hashlib.sha256(
                    response.content
                ).hexdigest()
            else:
                try:
                    record["body"] = response.json()
                except ValueError:
                    record["response_text"] = response.text
        except requests.RequestException as exc:
            record["transport_error"] = type(exc).__name__
        record["finished"] = time.monotonic()
    return record


def assert_channel_gone(record, channel_id):
    """The pinned FNN's cleared-channel error must be the only JSON-RPC outcome."""
    assert record["http_status"] == 200 and "transport_error" not in record, record
    request, reply = record["request"], record["body"]
    assert request["params"][0]["channel_id"] == channel_id
    assert isinstance(reply, dict) and reply.get("jsonrpc") == "2.0", reply
    assert "id" in reply and type(reply["id"]) is type(request["id"])
    assert reply["id"] == request["id"] and "result" not in reply, reply
    error = reply.get("error")
    assert isinstance(error, dict) and error.get("code") == -32000, reply
    assert error.get("message") == f"channel Hash256({channel_id}) not found", error
    assert error.get("data") is None, error
