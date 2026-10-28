"""Upgrade a type-id deployed contract cell in place (code_hash stays the same).

The devnet chain snapshot (source/fiber/data.fiber.tar.gz) ships fiber contracts deployed with
type-id by the miner key (framework/config.py). A develop fnn may need newer contract binaries
(e.g. commitment-lock); upgrading the type-id cell keeps the code_hash fnn's config points at.
"""
import json, os, tempfile
import requests
from framework.helper import ckb_cli

MINER_PRIVATE = "0x98400f6a67af07025f5959af35ed653d649f745b8f54bf3f07bef9bd605ee946"
SNAPSHOT_COMMITMENT_LOCK = ("0xdd935061bc8c9f514d8a6509c1a2cabec7f7f36008ae2767ad8c2b49c4002176", 0)
FEE = 1_000_000  # 0.01 CKB, enough for ~100KB tx


def _rpc(url, m, p):
    return requests.post(url, json={"id": 1, "jsonrpc": "2.0", "method": m, "params": p}).json()["result"]


def upgrade_type_id_cell(tx_hash, index, new_binary_path, private_key=MINER_PRIVATE, api_url="http://127.0.0.1:8114"):
    cell = _rpc(api_url, "get_live_cell", [{"tx_hash": tx_hash, "index": hex(index)}, True])
    assert cell["status"] == "live", cell
    out = cell["cell"]["output"]
    data = open(new_binary_path, "rb").read()
    if cell["cell"]["data"]["content"] == "0x" + data.hex():
        return None
    tx_file = tempfile.mktemp(suffix=".json")
    ckb_cli.tx_init(tx_file, api_url)
    ckb_cli.tx_add_input(tx_hash, index, tx_file, api_url)
    ckb_cli.tx_add_output(dict(out, capacity=hex(int(out["capacity"], 16) - FEE)), "0x" + data.hex(), tx_file)
    for s in ckb_cli.tx_sign_inputs(private_key, tx_file, api_url):
        ckb_cli.tx_add_signature(s["lock-arg"], s["signature"], tx_file, api_url)
    new_hash = ckb_cli.tx_send(tx_file, api_url).strip()
    os.remove(tx_file)
    return new_hash
