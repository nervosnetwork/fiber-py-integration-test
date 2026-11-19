"""Keep the one approved funding transaction out of the real CKB pool."""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

import requests

from test_cases.fiber.devnet.lsp._commitment_broadcast_gate import (
    MAX_REQUEST_BYTES,
    _error_reply,
    _hash,
)

_FUNDING_BLOCKED = {"code": -32099, "message": "LSP_TEST_ORIGINAL_FUNDING_BLOCKED"}
_PROXY_FAILED = {"code": -32098, "message": "LSP_TEST_CKB_PROXY_FAILED"}
_RECORDED_METHODS = {
    "get_tip_block_number",
    "get_tip_header",
    "get_transaction",
    "get_live_cell",
    "send_transaction",
}


def find_funding_trace_poll(events, funding_hash, point, tip, *, spent, since):
    """Find one fresh FNN poll at the frozen tip in the proxy's real CKB replies."""
    funding_read = (
        "get_transaction",
        [funding_hash],
        lambda value: value is None or value["tx_status"]["status"] == "unknown",
    )
    expected = [
        ("get_tip_block_number", [], lambda value: value == tip),
        funding_read,
        (
            "get_live_cell",
            [point, False],
            lambda value: (
                value["status"] != "live" and value["cell"] is None
                if spent
                else value["status"] == "live"
            ),
        ),
    ]
    if spent:
        expected.extend(
            [
                (
                    "get_transaction",
                    [point["tx_hash"]],
                    lambda value: value["tx_status"]["status"] == "committed",
                ),
                funding_read,
            ]
        )

    matching = []
    for event in events:
        if event["action"] != "forwarded" or event["started"] < since:
            continue
        request = event["request"]
        request_id = request.get("id")
        if type(request_id) is not int:
            continue
        if request["method"] == "get_tip_block_number" and request_id == 0:
            matching = []  # The pinned tracer starts each poll with a fresh client.
        method, params, valid = expected[len(matching)]
        if matching:
            last = matching[-1]
            last_id = last["request"]["id"]
            if request_id <= last_id or event["started"] < last["upstream_finished"]:
                continue
            # The tracer may check other funding inputs before reaching this one.
            if method != "get_live_cell" and request_id != last_id + 1:
                continue
        elif request_id != 0:
            continue
        response = event["response"]
        if (
            request["method"] == method
            and (request.get("params") or []) == params
            and event["http_status"] == 200
            and response.get("id") == request_id
            and "error" not in response
            and "result" in response
            and valid(response["result"])
        ):
            matching.append(event)
            if len(matching) == len(expected):
                return matching
    return []


def require_funding_trace_before_close(
    events, funding_hash, point, tip, *, since, closed_at
):
    """Judge the first Closed observation using only the final mined tip's poll."""
    reads = find_funding_trace_poll(
        events, funding_hash, point, tip, spent=True, since=since
    )
    assert reads, f"no complete spent-input poll at final tip {tip} before first Closed"
    finished = reads[-1]["upstream_finished"]
    assert (
        finished < closed_at
    ), f"final tip {tip} poll finished at {finished}, first Closed observed at {closed_at}"
    return reads


class FundingSpendGate:
    """Forward all unrelated requests and retain the original CKB trace readings."""

    def __init__(self, upstream_url, evidence_path, transaction_hash):
        self.upstream_url = upstream_url
        self.transaction_hash = transaction_hash
        self.evidence_path = Path(evidence_path)
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_path.touch(exist_ok=False)
        self._condition = threading.Condition()
        self._events = []
        self._broadcast_attempts = []
        self._sent_hashes = set()
        self._active = 0
        self._funding_hash = None
        self._closed = False
        self.errors = []
        gate = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def do_POST(self):
                with gate._condition:
                    if gate._closed:
                        return
                    gate._active += 1
                event = {
                    "started": time.monotonic(),
                    "wall_ms": int(time.time() * 1000),
                }
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= MAX_REQUEST_BYTES:
                        raise ValueError("invalid CKB RPC Content-Length")
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("incomplete CKB RPC request body")
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("expected a single CKB RPC request")
                    event["request"] = payload
                    status, content_type, body = gate._dispatch(
                        event, raw, self.headers.get("Authorization")
                    )
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as error:
                    message = f"CKB funding gate: {type(error).__name__}: {error}"
                    with gate._condition:
                        gate.errors.append(message)
                    gate._record(
                        {**event, "action": "error", "error": message},
                    )
                    body = _error_reply(
                        event.get("request", {}).get("id"), _PROXY_FAILED
                    )
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except OSError:
                        pass
                finally:
                    with gate._condition:
                        gate._active -= 1
                        gate._condition.notify_all()

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
        )
        self.thread.start()

    def _record(self, event):
        with self._condition:
            with self.evidence_path.open("a") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            self._events.append(event)

    def _dispatch(self, event, raw, authorization):
        payload = event["request"]
        method = payload.get("method")
        if method == "send_transaction":
            tx_hash = _hash(self.transaction_hash(payload["params"][0]))
            event["tx_hash"] = tx_hash
            with self._condition:
                self._broadcast_attempts.append((event["started"], tx_hash))
                blocked = tx_hash == self._funding_hash
                if not blocked:
                    self._sent_hashes.add(tx_hash)
            if blocked:
                body = _error_reply(payload.get("id"), _FUNDING_BLOCKED)
                self._record(
                    {
                        **event,
                        "action": "blocked",
                        "http_status": 200,
                        "response": json.loads(body),
                        "upstream_finished": None,
                    }
                )
                return 200, "application/json", body

        headers = {"Content-Type": "application/json"}
        if authorization is not None:
            headers["Authorization"] = authorization
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
                self.upstream_url, data=raw, headers=headers, timeout=(2, 5)
            )
        if method in _RECORDED_METHODS:
            self._record(
                {
                    **event,
                    "action": "forwarded",
                    "http_status": response.status_code,
                    "response": response.json(),
                    "upstream_finished": time.monotonic(),
                }
            )
        return (
            response.status_code,
            response.headers.get("Content-Type", "application/json"),
            response.content,
        )

    def arm(self, funding_hash):
        funding_hash = _hash(funding_hash)
        with self._condition:
            assert (
                not self._closed and self._funding_hash is None
            ), "gate already armed or closed"
            assert not self.errors, self.errors
            assert (
                funding_hash not in self._sent_hashes
            ), "original funding sent before arming"
            self._funding_hash = funding_hash
        self._record(
            {"action": "armed", "tx_hash": funding_hash, "started": time.monotonic()}
        )

    @property
    def blocked(self):
        with self._condition:
            return [
                copy.deepcopy(event["request"]["params"][0])
                for event in self._events
                if event["action"] == "blocked"
            ]

    def read_events(self):
        with self._condition:
            return copy.deepcopy(self._events)

    def broadcast_attempts(self):
        """Include repeat submissions and writes still awaiting a CKB reply."""
        with self._condition:
            return list(self._broadcast_attempts)

    def close(self):
        with self._condition:
            if self._closed:
                return
            self._closed = True
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        with self._condition:
            drained = self._condition.wait_for(lambda: not self._active, timeout=9)
        assert drained and not self.thread.is_alive(), "CKB funding gate did not stop"
