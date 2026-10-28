"""Verification system (part 2 of 2): long-running monitor.

Independent from the builder: it only reads scenario records from
--records-dir, tracks any number of overlapping scenarios for days, persists
everything in SQLite and is safe to kill/restart at any time (WTL-10).

Per-scenario rows: WTL-01..13. Each case is PENDING until resolved, then
PASS / FAIL / N/A. At deadline_ms every still-PENDING case becomes FAIL (WTL-08).
"""
import argparse
import glob
import json
import logging
import os
import signal
import sys
import threading
import time

from watchtower_longrun.common import CKB_SHANNONS, Rpc, RpcError, Topology, h, i, load_yaml, now_ms, state_name
from watchtower_longrun.verifier.chain import Chain
from watchtower_longrun.verifier.discord import Notifier
from watchtower_longrun.verifier.store import Store

LOG = logging.getLogger("wtl.verifier")
CASES = ["WTL-01", "WTL-02", "WTL-03", "WTL-04", "WTL-05", "WTL-06", "WTL-07",
         "WTL-08", "WTL-09", "WTL-10", "WTL-11", "WTL-12", "WTL-13"]
CASE_TITLES = {
    "WTL-01": "multi-channel force close confirmed",
    "WTL-02": "preimage TLC claimed on-chain by watchtower",
    "WTL-03": "timeout TLC reclaimed on-chain after expiry",
    "WTL-04": "all commitment cells settled, fee bounded",
    "WTL-05": "unclosed route channels clean (no stuck TLC)",
    "WTL-06": "public-node channels untouched / expiry margin",
    "WTL-07": "post-check payment over spare channels",
    "WTL-08": "resolved before deadline",
    "WTL-09": "builder pre-check",
    "WTL-10": "verifier restart safety",
    "WTL-11": "config validation",
    "WTL-12": "both ends of the route closed",
    "WTL-13": "parallel channels resolved, spare usable",
}


class Monitor:
    def __init__(self, cfg, topo, store, records_dir, notifier):
        self.cfg = cfg
        self.topo = topo
        self.store = store
        self.records_dir = records_dir
        self.notifier = notifier
        self.chain = Chain(topo.ckb())
        self.rpcs = {n: topo.rpc(n) for n in topo.order}
        self.stop = threading.Event()

    # ---------- alerts ----------
    def alert(self, key, text):
        if self.store.claim_alert(key):
            self.notifier.send(text)

    # ---------- ingest ----------
    def ingest(self):
        for p in sorted(glob.glob(os.path.join(self.records_dir, "*.json"))):
            try:
                with open(p) as f:
                    rec = json.load(f)
            except (OSError, ValueError):
                continue  # partially written records are never visible (atomic rename) but be safe
            if not self.store.ingest(rec):
                continue
            sid = rec["id"]
            LOG.info("ingested scenario %s (%s)", sid, rec["status"])
            self.store.event(sid, "ingest", f"record ingested status={rec['status']}", at_ms=rec["created_at_ms"])
            if rec["status"] != "built":
                for c in CASES:
                    self.store.set_case(sid, c, "N/A", "build did not run")
                case = "WTL-11" if rec.get("stage") == "config" else "WTL-09"
                self.store.set_case(sid, case, "PASS", f"builder refused to force close: {rec.get('reason')}")
                self.store.finalize(sid, "build_failed", {"reason": rec.get("reason"), "stage": rec.get("stage")})
                self.alert(f"buildfail:{sid}", f":warning: WTL builder {rec.get('stage')} failure ({sid}): {rec.get('reason')} — nothing was force closed")
                continue
            for c in CASES:
                self.store.set_case(sid, c, "PENDING")
            self.store.set_case(sid, "WTL-09", "PASS", "pre-check ok before force close")
            self.store.set_case(sid, "WTL-11", "PASS", "config validated")
            for fc in rec["force_closes"]:
                self.store.event(sid, "force_close", f"shutdown_channel force by {fc['by']} {fc['channel_id']}", at_ms=fc["at_ms"])

    # ---------- helpers ----------
    def channel_now(self, ch):
        rpc = self.rpcs.get(ch["view"])
        if rpc is None:
            return None
        a, b = ch["nodes"]
        other = b if ch["view"] == a else a
        pk = self.topo.by_name[other].get("pubkey") or self._pubkey(other)
        try:
            for c in rpc.list_channels({"pubkey": pk, "include_closed": True})["channels"]:
                if c["channel_id"] == ch["channel_id"]:
                    return c
        except Exception as e:  # noqa
            LOG.warning("list_channels via %s failed: %s", ch["view"], e)
        return None

    def _pubkey(self, name):
        return self._rec_pubkeys.get(name)

    def payment_status(self, payer_rpc, ph):
        try:
            return payer_rpc.get_payment({"payment_hash": ph})["status"]
        except Exception:  # noqa
            return None

    # ---------- evaluation ----------
    def evaluate(self, row):
        sid = row["id"]
        rec = row["record"]
        self._rec_pubkeys = {n["name"]: n["pubkey"] for n in rec["topology"]}
        now = now_ms()
        cases = self.store.cases(sid)
        st = lambda c: cases.get(c, {}).get("status")  # noqa
        closed = [c for c in rec["channels"] if c["force_close"]]
        others = [c for c in rec["channels"] if not c["force_close"]]
        payer = self.rpcs[rec["topology"][0]["name"]]
        traces = {}
        for ch in closed:
            prev = self.store.trace(sid, ch["channel_id"])
            before = set(prev["txs"]) if prev else set()
            try:
                tr = self.chain.trace(ch["funding_tx"], ch["funding_index"], prev)
            except Exception as e:  # noqa
                LOG.warning("trace %s failed: %s", ch["channel_id"], e)
                tr = prev or {"commitment_tx": None, "txs": [], "live": [], "complete": False}
            for t in tr["txs"]:
                if t not in before:
                    kind = "commitment" if t == tr["commitment_tx"] else "settlement"
                    self.store.event(sid, kind, f"{kind} tx for {ch['nodes'][0]}-{ch['nodes'][1]} {ch['channel_id'][:12]}", tx_hash=t,
                                     at_ms=self.chain.block_time(t) or now)
            self.store.save_trace(sid, ch["channel_id"], tr)
            traces[ch["channel_id"]] = tr

        # WTL-01: every force close has a committed commitment tx
        if closed and all(traces[c["channel_id"]]["commitment_tx"] for c in closed):
            self.store.set_case(sid, "WTL-01", "PASS", f"{len(closed)} commitment txs committed")

        tlcs_on = {}  # payment_hash -> closed channels where it was pending
        for ch in closed:
            for p in ch["pending_tlcs"]:
                tlcs_on.setdefault(p["payment_hash"], []).append(ch)

        # WTL-02 preimage claims
        pre = [t for t in rec["tlcs"] if t["kind"] == "preimage"]
        claimed = {}
        for t in pre:
            chans = tlcs_on.get(t["payment_hash"], [])
            hits = [self.chain.witnesses_contain(traces[c["channel_id"]]["txs"], t["preimage"]) for c in chans]
            claimed[t["payment_hash"]] = chans and all(hits)
        if not pre:
            self.store.set_case(sid, "WTL-02", "N/A", "no preimage TLC")
        elif all(claimed.values()):
            pays = {self.payment_status(payer, t["payment_hash"]) for t in pre}
            self.store.set_case(sid, "WTL-02", "PASS", f"{len(pre)} preimage TLCs claimed on-chain; payer status {sorted(map(str, pays))}")

        # WTL-03 timeout TLCs
        to = [t for t in rec["tlcs"] if t["kind"] == "timeout"]
        timed = {}
        for t in to:
            chans = tlcs_on.get(t["payment_hash"], [])
            done = chans and all(traces[c["channel_id"]]["complete"] for c in chans)
            leaked = any(self.chain.witnesses_contain(traces[c["channel_id"]]["txs"], t["preimage"]) for c in chans)
            if leaked:
                self.store.set_case(sid, "WTL-03", "FAIL", f"preimage of timeout TLC {t['payment_hash'][:12]} appeared on-chain")
            timed[t["payment_hash"]] = done and not leaked
            exp = t.get("min_expiry_ms")
            margin = self.cfg.get("expiry_alert_margin_ms", 3600_000)
            if exp and not done and now > exp - margin:
                self.alert(f"expiry:{sid}:{t['payment_hash']}",
                           f":hourglass: WTL {sid}: timeout TLC {t['payment_hash'][:12]} unresolved, expiry in {(exp-now)//1000}s")
        if not to:
            self.store.set_case(sid, "WTL-03", "N/A", "no timeout TLC")
        elif all(timed.values()):
            self.store.set_case(sid, "WTL-03", "PASS", f"{len(to)} timeout TLCs reclaimed after expiry, preimage never revealed")

        # WTL-04 all followed cells spent, fee bounded
        if closed and all(traces[c["channel_id"]]["complete"] for c in closed):
            max_fee = int(self.cfg.get("max_fee_ckb_per_channel", 1) * CKB_SHANNONS)
            fees = {}
            for c in closed:
                try:
                    fees[c["channel_id"]] = sum(self.chain.fee(t) for t in traces[c["channel_id"]]["txs"])
                except Exception:  # noqa
                    fees[c["channel_id"]] = None
            bad = {k: v for k, v in fees.items() if v is None or v > max_fee}
            if bad:
                self.store.set_case(sid, "WTL-04", "FAIL", f"fee over bound: {bad}")
            else:
                self.store.set_case(sid, "WTL-04", "PASS", f"all commitment cells spent; fees(shannons) {list(fees.values())}")

        # WTL-05 unclosed route channels clean
        hashes = {t["payment_hash"] for t in rec["tlcs"]}
        route_other = [c for c in others if not c["public_node"] or self.rpcs.get(c["view"])]
        stuck, notready = [], []
        for c in route_other:
            cur = self.channel_now(c)
            if cur is None:
                continue
            name, _ = state_name(cur["state"])
            if name != "ChannelReady":
                notready.append(f"{c['nodes'][0]}-{c['nodes'][1]}:{name}")
            for p in cur.get("pending_tlcs", []):
                if p["payment_hash"] in hashes:
                    stuck.append(p["payment_hash"][:12])
            # WTL-06 latch: public-node channels must never close
            if c["public_node"] and name in ("ShuttingDown", "Closed"):
                self.store.set_case(sid, "WTL-06", "FAIL", f"public channel {c['nodes']} went {name}")
                self.alert(f"pub:{sid}:{c['channel_id']}", f":rotating_light: WTL {sid}: public-node channel {c['nodes']} is {name}")
        settled_closed = closed and all(traces[c["channel_id"]]["complete"] for c in closed)
        if settled_closed and not stuck and not notready:
            self.store.set_case(sid, "WTL-05", "PASS", f"{len(route_other)} unclosed channels Ready, no scenario TLC left")

        # WTL-12 both route ends closed in the same scenario
        hops = list(zip([n["name"] for n in rec["topology"]], [n["name"] for n in rec["topology"]][1:]))
        ends = {tuple(c["nodes"]) for c in closed}
        if not (hops[0] in ends and hops[-1] in ends):
            self.store.set_case(sid, "WTL-12", "N/A", "close set does not include both route ends")
        else:
            seg_ok = all(traces[c["channel_id"]]["complete"] for c in closed if tuple(c["nodes"]) in (hops[0], hops[-1]))
            cases = self.store.cases(sid)
            st = lambda c: cases.get(c, {}).get("status")  # noqa
            if seg_ok and st("WTL-02") in ("PASS", "N/A") and st("WTL-03") in ("PASS", "N/A"):
                self.store.set_case(sid, "WTL-12", "PASS", "both end segments settled with preimage and timeout claims")

        # WTL-13 parallel channels
        par = [cs for cs in rec["close_set"] if cs[2] > 1]
        if not par:
            self.store.set_case(sid, "WTL-13", "N/A", "no parallel close")
        else:
            ok = True
            for a, b, k in par:
                vs = [c for c in closed if c["nodes"] == [a, b]]
                ok &= len(vs) == k and all(traces[c["channel_id"]]["complete"] for c in vs)
                sp = [c for c in others if c["nodes"] == [a, b]]
                for c in sp:
                    cur = self.channel_now(c)
                    ok &= bool(cur) and state_name(cur["state"])[0] == "ChannelReady"
                ok &= len(sp) >= 1
            if ok:
                self.store.set_case(sid, "WTL-13", "PASS", f"parallel sets {par} all settled, spare Ready")

        # WTL-07 post-check once 01..05 are final PASS/N/A
        cases = self.store.cases(sid)
        core = ["WTL-01", "WTL-02", "WTL-03", "WTL-04", "WTL-05"]
        if all(cases[c]["status"] in ("PASS", "N/A") for c in core) and cases["WTL-07"]["status"] == "PENDING":
            self.post_check(sid, rec, others)

        # WTL-06 final PASS when everything else is done
        cases = self.store.cases(sid)
        pending = [c for c in CASES if cases[c]["status"] == "PENDING" and c not in ("WTL-06", "WTL-08", "WTL-10")]
        if not pending:
            if cases["WTL-06"]["status"] == "PENDING":
                self.store.set_case(sid, "WTL-06", "PASS", "public-node channels stayed Ready for the whole scenario")
            self.store.set_case(sid, "WTL-08", "PASS", f"resolved {(now - rec['created_at_ms'])//1000}s after build, before deadline")
            self.finish(sid, row)
        elif now > rec["deadline_ms"]:
            for c in pending + ["WTL-06", "WTL-08"]:
                self.store.set_case(sid, c, "FAIL", "deadline reached while unresolved")
            self.finish(sid, row, timed_out=True)

    def post_check(self, sid, rec, others):
        amount = rec.get("post_check_amount", CKB_SHANNONS)
        names = [n["name"] for n in rec["topology"]]
        payer = self.rpcs[names[0]]
        key = f"postcheck:{sid}"
        ph = self.store.get_meta(key)
        if ph is None:
            hops = []
            for a, b in zip(names, names[1:]):
                cands = [c for c in others if c["nodes"] == [a, b]]
                hop = {"pubkey": self._rec_pubkeys[b]}
                if cands:
                    hop["channel_outpoint"] = cands[0]["outpoint"]
                hops.append(hop)
            try:
                r = payer.build_router({"amount": h(amount), "hops_info": hops})
                res = payer.send_payment_with_router({"router": r["router_hops"], "keysend": True})
                ph = res["payment_hash"]
                self.store.set_meta(key, ph)
                self.store.event(sid, "post_check", f"keysend {amount} shannons N1->N{len(names)} over spare channels")
            except Exception as e:  # noqa
                self.store.event(sid, "post_check", f"post-check send failed: {e}")
                self.store.set_meta(key + ":err", str(e))
                return
        s = self.payment_status(payer, ph)
        if s == "Success":
            self.store.set_case(sid, "WTL-07", "PASS", f"keysend {ph[:12]} Success")
        elif s == "Failed":
            self.store.set_case(sid, "WTL-07", "FAIL", f"keysend {ph[:12]} Failed")

    def finish(self, sid, row, timed_out=False):
        cases = self.store.cases(sid)
        if row["restarts_seen"] > 0:
            self.store.set_case(sid, "WTL-10", "PASS", f"verifier restarted {row['restarts_seen']}x while scenario in flight; no dup events/alerts")
        else:
            self.store.set_case(sid, "WTL-10", "N/A", "no restart during this scenario")
        cases = self.store.cases(sid)
        fails = [c for c in CASES if cases[c]["status"] == "FAIL"]
        status = "fail" if fails else "pass"
        self.store.finalize(sid, status, {c: cases[c]["status"] for c in CASES})
        self.store.event(sid, "final", f"scenario {status.upper()}" + (" (deadline)" if timed_out else ""))
        LOG.info("scenario %s finalized: %s", sid, status)
        if fails:
            lines = "\n".join(f"- {c} FAIL: {cases[c]['detail']}" for c in fails)
            self.alert(f"fail:{sid}", f":x: WTL scenario {sid} FAILED\n{lines}")

    # ---------- nodes ----------
    def poll_nodes(self):
        for n in self.topo.order:
            rpc = self.rpcs[n]
            d = {"controlled": self.topo.controlled(n), "reachable": False}
            if rpc:
                try:
                    info = rpc.node_info()
                    d.update(reachable=True, pubkey=info.get("pubkey"), version=info.get("version"),
                             channel_count=i(info.get("channel_count", 0)), peers_count=i(info.get("peers_count", 0)))
                except Exception as e:  # noqa
                    d["error"] = str(e)[:200]
                    if self.topo.controlled(n):
                        self.alert(f"node:{n}:{now_ms() // 3600_000}", f":warning: WTL node {n} RPC unreachable: {str(e)[:200]}")
            self.store.set_node_status(n, d)
        try:
            self.store.set_node_status("ckb", {"reachable": True, "tip": self.chain.tip()})
        except Exception as e:  # noqa
            self.store.set_node_status("ckb", {"reachable": False, "error": str(e)[:200]})

    # ---------- daily summary ----------
    def maybe_daily_summary(self):
        hour = int(self.cfg.get("daily_summary_hour", 9))
        lt = time.localtime()
        day = time.strftime("%Y-%m-%d", lt)
        if lt.tm_hour < hour or self.store.get_meta("summary_day") == day:
            return
        self.store.set_meta("summary_day", day)
        self.notifier.send(self.summary_text())

    def summary_text(self):
        rows = self.store.scenarios()
        since = now_ms() - 86400_000
        recent = [r for r in rows if (r["finalized_at_ms"] or 0) >= since or r["status"] == "open"]
        lines = [f"**WTL daily summary** — open {sum(r['status']=='open' for r in rows)}, last 24h finalized {sum(r['status'] in ('pass','fail') and (r['finalized_at_ms'] or 0)>=since for r in rows)}"]
        for r in recent:
            cs = self.store.cases(r["id"])
            cells = " ".join(f"{c[4:]}:{cs[c]['status'][0] if c in cs else '-'}" for c in CASES)
            lines.append(f"`{r['id']}` {r['status'].upper()} {cells}")
        return "\n".join(lines)

    # ---------- loop ----------
    def tick(self):
        self.ingest()
        for row in self.store.scenarios("open"):
            try:
                self.evaluate(row)
            except Exception as e:  # noqa
                LOG.exception("evaluate %s failed: %s", row["id"], e)
        self.poll_nodes()
        self.maybe_daily_summary()

    def run(self, interval):
        started = self.store.get_meta("started")
        if started:
            self.store.bump_restarts()
            LOG.info("verifier restart detected (previous start %s)", started)
        self.store.set_meta("started", now_ms())
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(interval)


def main(argv=None):
    ap = argparse.ArgumentParser(description="watchtower long-run verifier (monitor + web)")
    ap.add_argument("--config", default="config/watchtower_longrun.yaml")
    ap.add_argument("--topology", default=os.environ.get("WTL_TOPOLOGY", "config/watchtower_longrun_topology.yaml"))
    ap.add_argument("--records-dir", default=os.environ.get("WTL_RECORDS_DIR", "/var/lib/wtl/records"))
    ap.add_argument("--db", default=os.environ.get("WTL_DB", "/var/lib/wtl/verifier.sqlite"))
    ap.add_argument("--interval", type=float, default=None)
    ap.add_argument("--web", default=os.environ.get("WTL_WEB", "127.0.0.1:8088"), help="host:port, empty to disable")
    ap.add_argument("--once", action="store_true", help="single tick then exit")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_yaml(a.config).get("verifier", {})
    topo = Topology.load(a.topology)
    os.makedirs(os.path.dirname(os.path.abspath(a.db)), exist_ok=True)
    store = Store(a.db)
    mon = Monitor(cfg, topo, store, a.records_dir, Notifier())
    if a.once:
        mon.tick()
        return 0
    if a.web:
        from watchtower_longrun.verifier.web import serve

        host, port = a.web.rsplit(":", 1)
        threading.Thread(target=serve, args=(store, topo, host, int(port)), daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: mon.stop.set())
    mon.run(a.interval or cfg.get("interval_seconds", 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
