"""Shared helpers for the long-running watchtower suite (builder + verifier).

The builder and the verifier are independent processes. The only contract
between them is the scenario record JSON written by the builder into
``records_dir`` (see docs/watchtower_longrun/README.md).
"""
import json
import os
import time

import requests
import yaml

CKB_SHANNONS = 100_000_000


class RpcError(Exception):
    pass


class Rpc:
    def __init__(self, url, timeout=30):
        self.url = url
        self.timeout = timeout

    def call(self, method, params=None):
        body = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params or []}
        r = requests.post(self.url, json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RpcError(f"{method}: {data['error']}")
        return data["result"]

    def __getattr__(self, method):
        if method.startswith("_"):
            raise AttributeError(method)
        return lambda *params: self.call(method, list(params))


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def now_ms():
    return int(time.time() * 1000)


def h(v):
    return hex(int(v))


def i(v):
    return int(v, 16) if isinstance(v, str) else int(v)


def write_json_atomic(path, obj):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def state_name(state):
    """ChannelState json is {"state_name": ..., "state_flags": ...}."""
    if isinstance(state, dict):
        return state.get("state_name", ""), str(state.get("state_flags", ""))
    return str(state), ""


class Topology:
    """Topology file: ordered list of nodes along the route N1..N5."""

    def __init__(self, data):
        self.nodes = data["nodes"]
        self.ckb_rpc_url = data["ckb_rpc_url"]
        self.explorer_tx_url = data.get(
            "explorer_tx_url", "https://testnet.explorer.nervos.org/transaction/{}"
        )
        self.currency = data.get("currency", "Fibt")
        self.by_name = {n["name"]: n for n in self.nodes}
        self.order = [n["name"] for n in self.nodes]

    @classmethod
    def load(cls, path):
        return cls(load_yaml(path))

    def controlled(self, name):
        return bool(self.by_name[name].get("controlled"))

    def rpc(self, name):
        url = self.by_name[name].get("rpc_url")
        return Rpc(url) if url else None

    def ckb(self):
        return Rpc(self.ckb_rpc_url)

    def hop_pairs(self):
        return list(zip(self.order, self.order[1:]))


def wallet_shannons(ckb, node_info):
    """On-chain CKB of a fiber node's funding wallet (default_funding_lock_script), via the ckb indexer."""
    lock = node_info.get("default_funding_lock_script")
    if not lock:
        return None
    r = ckb.get_cells_capacity({"script": lock, "script_type": "lock"})
    return i(r["capacity"]) if r else 0
