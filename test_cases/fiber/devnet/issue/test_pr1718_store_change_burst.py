import hashlib
import json
import threading
import time

import websocket

from framework.basic_fiber import FiberTest


def sha256_hex(preimage_hex):
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()


def subscribe_store_changes(rpc_port):
    """Open a websocket subscription to store changes; return (ws, sub_id)."""
    ws = websocket.create_connection(f"ws://127.0.0.1:{rpc_port}", timeout=5)
    ws.send(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "subscribe_store_changes",
                "params": [],
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            assert "result" in msg, f"subscribe failed: {msg}"
            return ws, msg["result"]


def count_notifications(ws, deadline_seconds):
    """Count subscription notifications until the deadline; return (count, payloads)."""
    count = 0
    payloads = []
    deadline = time.time() + deadline_seconds
    ws.settimeout(2)
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if "params" in msg and "subscription" in msg.get("params", {}):
            count += 1
            payloads.append(json.dumps(msg))
    return count, payloads


class TestPr1718StoreChangeBurst(FiberTest):
    """
    PR-1718: a burst of store changes must not kill store-change subscriptions.
    """

    BURST_THREADS = 16
    BURST_PER_THREAD = 10

    def _burst_invoices(self):
        """Create burst invoices from concurrent threads; return total count."""

        def worker(tid):
            for i in range(self.BURST_PER_THREAD):
                self._new_invoice(f"burst invoice {tid}-{i}")

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(self.BURST_THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return self.BURST_THREADS * self.BURST_PER_THREAD

    def _marker_invoice(self):
        """One invoice with a known payment hash, used to prove liveness."""
        marker_preimage = self.generate_random_preimage()
        marker_hash = sha256_hex(marker_preimage)
        self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": "marker invoice after burst",
                "payment_hash": marker_hash,
                "hash_algorithm": "sha256",
            }
        )
        return marker_hash

    def _new_invoice(self, description):
        return self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1 * 100000000),
                "currency": "Fibd",
                "description": description,
            }
        )

    # TEST-MAP: PR1718-01
    def test_subscription_survives_store_change_burst(self):
        ws, _sub_id = subscribe_store_changes(self.fiber1.rpc_port)
        try:
            burst_count = self._burst_invoices()
            # marker: proves the subscription is still alive after the burst
            marker_hash = self._marker_invoice()

            count, payloads = count_notifications(ws, 30)
            assert count >= burst_count + 1, (
                f"only {count} notifications after a burst of {burst_count} + 1 marker; "
                "subscription died during the burst"
            )
            assert any(
                marker_hash in p for p in payloads
            ), "marker invoice notification never arrived"
        finally:
            ws.close()

    # TEST-MAP: PR1718-02
    def test_closing_one_subscription_keeps_the_other_alive(self):
        ws_a, _sub_a = subscribe_store_changes(self.fiber1.rpc_port)
        ws_b, _sub_b = subscribe_store_changes(self.fiber1.rpc_port)
        try:
            burst_count = self._burst_invoices()
            # subscriber A goes away mid-stream; B must keep receiving
            ws_a.close()
            marker_hash = self._marker_invoice()

            count, payloads = count_notifications(ws_b, 30)
            assert count >= burst_count + 1, (
                f"surviving subscription got only {count} notifications after "
                f"a burst of {burst_count} + 1 marker"
            )
            assert any(
                marker_hash in p for p in payloads
            ), "marker invoice notification never arrived at surviving subscriber"
        finally:
            ws_b.close()
