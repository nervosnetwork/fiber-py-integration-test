"""On-chain tracing of a force-closed channel, using only CKB RPC + indexer.

funding cell --(commitment tx)--> cells locked by the commitment lock
  --(settlement txs, possibly several partial ones)--> ... until no live
cell with the commitment lock code_hash remains. The commitment lock
code_hash is learned from the commitment tx output[0], not hardcoded."""


def _i(v):
    return int(v, 16) if isinstance(v, str) else int(v)


class Chain:
    def __init__(self, ckb):
        self.ckb = ckb
        self._tx = {}

    def tip(self):
        return _i(self.ckb.get_tip_block_number())

    def tx(self, tx_hash):
        if tx_hash in self._tx:
            return self._tx[tx_hash]
        r = self.ckb.get_transaction(tx_hash)
        if r and r.get("tx_status", {}).get("status") == "committed":
            self._tx[tx_hash] = r
        return r

    def output(self, tx_hash, idx):
        t = self.tx(tx_hash)
        return t["transaction"]["outputs"][idx] if t and t.get("transaction") else None

    def spender(self, tx_hash, idx):
        """Committed tx spending (tx_hash, idx), or None."""
        out = self.output(tx_hash, idx)
        if out is None:
            return None
        key = {"script": out["lock"], "script_type": "lock"}
        after = None
        while True:
            res = self.ckb.get_transactions(key, "asc", "0x64", after)
            for o in res["objects"]:
                if o["io_type"] != "input":
                    continue
                t = self.tx(o["tx_hash"])
                if not t or t["tx_status"]["status"] != "committed":
                    continue
                for inp in t["transaction"]["inputs"]:
                    po = inp["previous_output"]
                    if po["tx_hash"] == tx_hash and _i(po["index"]) == idx:
                        return o["tx_hash"]
            if not res["objects"] or len(res["objects"]) < 100:
                return None
            after = res["last_cursor"]

    def fee(self, tx_hash):
        t = self.tx(tx_hash)["transaction"]
        cin = sum(_i(self.output(p["previous_output"]["tx_hash"], _i(p["previous_output"]["index"]))["capacity"]) for p in t["inputs"])
        cout = sum(_i(o["capacity"]) for o in t["outputs"])
        return cin - cout

    def block_time(self, tx_hash):
        t = self.tx(tx_hash)
        bh = t["tx_status"].get("block_hash")
        if not bh:
            return None
        return _i(self.ckb.get_header(bh)["timestamp"])

    def trace(self, funding_tx, funding_idx, prev=None):
        """Incremental trace. Returns dict(commitment_tx, txs, live, complete, lock_code_hash)."""
        tr = prev or {"commitment_tx": None, "txs": [], "live": [], "complete": False, "lock_code_hash": None}
        if tr["complete"]:
            return tr
        if not tr["commitment_tx"]:
            c = self.spender(funding_tx, funding_idx)
            if not c:
                return tr
            tr["commitment_tx"] = c
            tr["txs"] = [c]
            outs = self.tx(c)["transaction"]["outputs"]
            tr["lock_code_hash"] = outs[0]["lock"]["code_hash"]
            tr["live"] = [[c, k] for k, o in enumerate(outs) if o["lock"]["code_hash"] == tr["lock_code_hash"]]
        progressed = True
        while progressed:
            progressed = False
            still = []
            for th, k in tr["live"]:
                s = self.spender(th, k)
                if not s:
                    still.append([th, k])
                    continue
                progressed = True
                if s not in tr["txs"]:
                    tr["txs"].append(s)
                    outs = self.tx(s)["transaction"]["outputs"]
                    still += [[s, j] for j, o in enumerate(outs) if o["lock"]["code_hash"] == tr["lock_code_hash"]]
            tr["live"] = still
        tr["complete"] = bool(tr["commitment_tx"]) and not tr["live"]
        return tr

    def witnesses_contain(self, tx_hashes, needle_hex):
        n = needle_hex[2:].lower()
        for th in tx_hashes:
            for w in self.tx(th)["transaction"]["witnesses"]:
                if n in w.lower():
                    return th
        return None
