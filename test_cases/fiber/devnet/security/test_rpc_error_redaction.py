import json
import time
from pathlib import Path

import requests

from framework.basic_fiber import FiberTest


class TestRpcErrorRedaction(FiberTest):
    """
    PR-1405 regression: RPC errors must not echo request params or sensitive
    values back to the caller/logs.
    """

    def test_rpc_error_omits_request_data_and_preimage(self):
        payment_hash = "0x" + "11" * 32
        payment_preimage = "0x" + "22" * 32
        payload = {
            "id": 1405,
            "jsonrpc": "2.0",
            "method": "settle_invoice",
            "params": [
                {
                    "payment_hash": payment_hash,
                    "payment_preimage": payment_preimage,
                }
            ],
        }

        response = requests.post(
            self.fiber1.get_client().url,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()

        assert "error" in body
        error = body["error"]
        rendered = json.dumps(body)

        assert "data" not in error
        assert "params" not in rendered
        assert "payment_preimage" not in rendered
        assert payment_preimage not in rendered

        time.sleep(1)
        node_log = Path(self.fiber1.tmp_path) / "node.log"
        log_text = node_log.read_text(errors="replace")
        assert payment_preimage not in log_text
