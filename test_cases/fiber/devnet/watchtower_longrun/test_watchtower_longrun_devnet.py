"""Devnet end-to-end for the testnet watchtower long-run tooling.

Runs the two independent parts exactly as on testnet, only with short timings:
  1. builder (python -m watchtower_longrun.builder) -> force closes + record, exits
  2. verifier (python -m watchtower_longrun.verifier) -> long-running, SQLite, web, discord
Topology C-C-P-C-C: N3 is a "public" node (never force-closed, only monitored).
Debug fnn (2s epochs) + small tlc_expiry_delta so timeouts happen in minutes.
"""
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import yaml

from framework.basic_fiber import FiberTest
from framework.util import get_project_root

CKB = 100000000
TLC_DELTA_MS = 60_000
FINAL_DELTA_MS = 60_000
WEB_PORT = 18088
DISCORD_PORT = 18099


class _Discord(BaseHTTPRequestHandler):
    posts = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Discord.posts.append(json.loads(body)["content"])
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


TESTNET_ONLY = "testnet-only: fnn random privacy expiry delta 4h-14d, timeout path cannot expire in a devnet run"


class TestWatchtowerLongrunDevnet(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 3}

    _verifier = None

    def teardown_method(self, method):
        if self._verifier and self._verifier.poll() is None:
            self._verifier.kill()
            self._verifier.wait()
        super().teardown_method(method)

    def _account(self):
        # the faucet can race on a not-yet-committed change cell; retry after a few blocks
        for n in range(10):
            try:
                return self.generate_account(20000)
            except Exception:
                if n == 9:
                    raise
                time.sleep(5)

    def _run(self, *args, env=None, timeout=900):
        e = dict(os.environ, PYTHONPATH=self.root)
        e.update(env or {})
        return subprocess.run([sys.executable, "-m", *args], cwd=self.root, env=e, capture_output=True, text=True, timeout=timeout)

    def _builder(self, cfg, topo=None, extra=()):
        p = self._write_yaml(f"cfg-{time.time_ns()}.yaml", cfg)
        r = self._run("watchtower_longrun.builder", "--config", p, "--topology", topo or self.topo_path,
                      "--records-dir", self.records, *extra)
        print("builder stdout:", r.stdout[-3000:], "\nstderr:", r.stderr[-6000:])
        return r

    def _jump_past_expiry(self):
        ft = os.environ.get("WTL_FAKETIME_FILE")
        if not ft:
            print("faketime not enabled; timeout TLCs will only expire on wall time")
            return
        exps = []
        for f in os.listdir(self.records):
            for t in json.load(open(os.path.join(self.records, f))).get("tlcs", []):
                if t.get("kind") == "timeout" and t.get("expiry_ms"):
                    exps.append(t["expiry_ms"])
        if not exps:
            return
        # wait for preimage claims (WTL-02) before expiring anything
        for _ in range(40):
            cases, _ = self._cases()
            if all(c.get("WTL-02", ("PASS",))[0] in ("PASS", "N/A") for c in cases.values()):
                break
            time.sleep(5)
        offset_s = int((max(exps) - time.time() * 1000) / 1000) + 1800
        with open(ft, "w") as f:
            f.write(f"+{offset_s}\n")
        print(f"faketime offset +{offset_s}s")
        time.sleep(3)
        for _ in range(3):  # >37 blocks so median time passes the jump
            self.node.getClient().generate_epochs("0x1", wait_time=1)

    def _start_verifier(self):
        # verifier stays on wall time (deadlines / WTL-08 are real-time)
        base = {k: v for k, v in os.environ.items() if not k.startswith(("LD_PRELOAD", "FAKETIME"))}
        env = dict(base, PYTHONPATH=self.root, WTL_DISCORD_WEBHOOK=f"http://127.0.0.1:{DISCORD_PORT}/hook")
        log = open(os.path.join(self.work, "verifier.log"), "a")
        self._verifier = subprocess.Popen([sys.executable, "-m", "watchtower_longrun.verifier", "--config", self.cfg_path,
                                 "--topology", self.topo_path, "--records-dir", self.records, "--db", self.db,
                                 "--interval", "3", "--web", f"127.0.0.1:{WEB_PORT}"],
                                cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT)
        return self._verifier

    def _write_yaml(self, name, data):
        p = os.path.join(self.work, name)
        with open(p, "w") as f:
            yaml.safe_dump(data, f)
        return p

    def _cases(self):
        db = sqlite3.connect(self.db)
        out = {}
        for sid, case, st, detail in db.execute("SELECT scenario_id, case_id, status, detail FROM case_results"):
            out.setdefault(sid, {})[case] = (st, detail)
        stat = dict(db.execute("SELECT id, status FROM scenarios"))
        db.close()
        return out, stat

    def _open(self, a, b, ckb_amount):
        # connect_peer is async: wait for Init before open_channel ("feature not found")
        for _ in range(60):
            a.connect_peer(b)
            time.sleep(2)
            peers = a.get_client().list_peers().get("peers", [])
            if any(p.get("pubkey") == b.get_pubkey() for p in peers):
                break
        self.open_channel(a, b, ckb_amount * CKB, 0, other_config={"tlc_expiry_delta": hex(TLC_DELTA_MS)})
        for ch in b.get_client().list_channels({"pubkey": a.get_pubkey()})["channels"]:
            b.get_client().update_channel({"channel_id": ch["channel_id"], "tlc_expiry_delta": hex(TLC_DELTA_MS)})

    def test_watchtower_longrun_devnet(self):
        self.root = get_project_root()
        # The devnet snapshot's commitment-lock predates develop fnn; a mismatched lock rejects every
        # watchtower settlement with error 11 (InvalidExpiry). Upgrade the type-id cell in place.
        cdir = os.environ.get("FIBER_CONTRACTS_DIR")
        if cdir:
            from framework.helper.upgrade_type_id_contract import upgrade_type_id_cell, SNAPSHOT_COMMITMENT_LOCK
            print("commitment-lock upgrade tx:", upgrade_type_id_cell(*SNAPSHOT_COMMITMENT_LOCK, os.path.join(cdir, "commitment-lock")))
            for _ in range(5):
                self.Miner.miner_with_version(self.node, "0x0")
        self.work = os.path.join(self.root, "tmp", "wtl-e2e")
        shutil.rmtree(self.work, ignore_errors=True)
        os.makedirs(self.work)
        self.records = os.path.join(self.work, "records")
        self.db = os.path.join(self.work, "verifier.sqlite")
        srv = HTTPServer(("127.0.0.1", DISCORD_PORT), _Discord)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        # stale data dirs from an interrupted run would restore channels from an old chain
        for n in (3, 4, 5):
            shutil.rmtree(os.path.join(self.root, "tmp", "fiber", f"node{n}"), ignore_errors=True)
        f3, f4, f5 = (self.start_new_fiber(self._account()) for _ in range(3))
        f1, f2 = self.fiber1, self.fiber2
        fibers = [f1, f2, f3, f4, f5]
        for a, b in zip(fibers, fibers[1:]):
            self._open(a, b, 2000)
        time.sleep(10)  # gossip

        names = ["N1", "N2", "N3", "N4", "N5"]
        self.topo_path = self._write_yaml("topology.yaml", {
            "ckb_rpc_url": self.node.rpcUrl, "explorer_tx_url": "https://testnet.explorer.nervos.org/transaction/{}", "currency": "Fibd",
            "nodes": [{"name": n, "controlled": n != "N3", "rpc_url": f.get_client().url, "pubkey": f.get_pubkey()} for n, f in zip(names, fibers)]})
        base = {
            "scenarios_per_day": 1, "deadline_hours": 0.5,
            "scenario": {"normal_payments": {"count": 2, "amount_ckb": 1}, "preimage_tlcs": {"count": 2, "amount_ckb": 1},
                         "timeout_tlcs": {"count": 2, "amount_ckb": 1}, "final_tlc_expiry_delta_ms": FINAL_DELTA_MS},
            "tlc_expiry_delta_ms": TLC_DELTA_MS,
            "force_close": {"strategy": "fixed", "fixed_index": 0, "spare_parallel": 1, "reopen_capacity_ckb": 1000,
                            "close_sets": [[["N1", "N2"], ["N4", "N5", {"parallel": 2}]], [["N1", "N2"]]]},
            "post_check_amount_ckb": 1,
            "limits": {"max_tlcs_per_scenario": 50, "max_scenarios_per_day": 4},
            "verifier": {"interval_seconds": 3, "expiry_alert_margin_ms": 3_600_000, "max_fee_ckb_per_channel": 1, "daily_summary_hour": 0},
        }
        self.cfg_path = self._write_yaml("config.yaml", base)

        # ---- WTL-11: invalid configs are rejected before any RPC / force close
        # TEST-MAP: WTL-11
        bad = [
            ("negative count", {"scenario": dict(base["scenario"], timeout_tlcs={"count": -1, "amount_ckb": 1})}),
            ("public close", {"force_close": dict(base["force_close"], close_sets=[[["N2", "N3"]]])}),
            ("too many tlcs", {"limits": {"max_tlcs_per_scenario": 3, "max_scenarios_per_day": 4}}),
            ("no pending tlc", {"scenario": dict(base["scenario"], preimage_tlcs={"count": 0, "amount_ckb": 1}, timeout_tlcs={"count": 0, "amount_ckb": 1})}),
        ]
        for label, patch in bad:
            r = self._builder(dict(base, **patch), extra=["--dry-run"])
            assert r.returncode == 3, label
            assert "WTL-11" in r.stderr
        assert self._builder(base, extra=["--dry-run"]).returncode == 0
        assert not os.path.exists(self.records) or not os.listdir(self.records)

        # ---- WTL-09: unreachable node -> nothing force closed, failure record
        # TEST-MAP: WTL-09
        topo = yaml.safe_load(open(self.topo_path))
        topo["nodes"][3]["rpc_url"] = "http://127.0.0.1:1"
        before = [len(f.get_client().list_channels({})["channels"]) for f in fibers]
        r = self._builder(base, topo=self._write_yaml("bad-topo.yaml", topo))
        assert r.returncode == 2 and "WTL-09" in r.stderr
        assert [len(f.get_client().list_channels({})["channels"]) for f in fibers] == before

        # ---- verifier starts (independent long-running process)
        verifier = self._start_verifier()
        # ---- builder: scenario A (multi close + parallel), exits after force close
        # A carries timeout TLCs that cannot expire within a devnet run -> long deadline, never resolves here
        r = self._builder(dict(base, deadline_hours=24))
        assert r.returncode == 0, r.stderr
        # ---- builder: scenario B overlaps A (N1-N2 only), preimage-only so it fully resolves on devnet
        r = self._builder(base, extra=["--close-set", "1", "--preimage-count", "1", "--timeout-count", "0", "--normal-count", "1"])
        assert r.returncode == 0, r.stderr
        # ---- scenario C: deadline enforcement (WTL-08 negative): 1s deadline
        r = self._builder(dict(base, deadline_hours=0.0003), extra=["--close-set", "1", "--preimage-count", "0", "--timeout-count", "1", "--normal-count", "0"])
        assert r.returncode == 0, r.stderr

        # chain driver: commitment delay is in epochs
        stop = threading.Event()

        def drive():
            while not stop.is_set():
                try:
                    self.node.getClient().generate_epochs("0x1", wait_time=0)
                except Exception as e:  # noqa
                    print("generate_epochs", e)
                stop.wait(8)
        threading.Thread(target=drive, daemon=True).start()

        # ---- WTL-10: kill -9 the verifier mid-flight and restart it (B resolves in ~40s, so restart early)
        time.sleep(8)
        verifier.send_signal(signal.SIGKILL)
        verifier.wait()
        verifier = self._start_verifier()
        # Timeout-path recovery is NOT verified on devnet (decision 2026-10-28): fnn adds a random
        # +N*4h privacy delta (4h..14d) to every TLC expiry, so timeout TLCs never expire in a run.
        # It is verified on testnet only (verifier deadline > 14d). _jump_past_expiry stays opt-in.
        if os.environ.get("WTL_FAKETIME_FILE"):
            self._jump_past_expiry()
        try:
            deadline = time.monotonic() + 1500
            while time.monotonic() < deadline:
                cases, stat = self._cases()
                print(json.dumps(stat))
                done = [sid for sid, st_ in sorted(stat.items()) if st_ != "build_failed"]
                if len(stat) >= 4 and len(done) == 3 and stat[done[1]] != "open" and stat[done[2]] != "open":
                    break
                time.sleep(15)
            time.sleep(5)
            cases, stat = self._cases()
            print(json.dumps(cases, indent=1))
            page = urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/").read().decode()
            api = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/api/scenarios").read())
            for s in api:
                assert urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/scenario/{s['id']}").status == 200
            assert urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/nodes").status == 200
        finally:
            stop.set()
            verifier.terminate()
            verifier.wait(30)
        built = sorted(sid for sid, s in stat.items() if s != "build_failed")
        failed = [sid for sid, s in stat.items() if s == "build_failed"]
        db = sqlite3.connect(self.db)
        dup = db.execute("SELECT COUNT(*) FROM (SELECT scenario_id,kind,message,tx_hash,COUNT(*) n FROM events GROUP BY 1,2,3,4 HAVING n>1)").fetchone()[0]
        db.close()
        fposts = [p for p in _Discord.posts if "FAILED" in p]
        report = {}

        def put(case, ok, reason, skip=False):
            report[case] = ("SKIP" if skip else ("PASS" if ok else "FAIL"), reason)

        a = b = c = None
        if len(built) == 3 and len(failed) == 1:
            a, b, c = built
        A, B, C = (cases.get(x, {}) if x else {} for x in (a, b, c))
        st = lambda d, k: d.get(k, ("MISSING", ""))[0]
        # TEST-MAP: WTL-01
        put("WTL-01", st(A, "WTL-01") == "PASS" and st(B, "WTL-01") == "PASS", f"A={A.get('WTL-01')} B={B.get('WTL-01')}")
        # TEST-MAP: WTL-02
        put("WTL-02", st(A, "WTL-02") == "PASS" and st(B, "WTL-02") == "PASS", f"A={A.get('WTL-02')} B={B.get('WTL-02')}")
        # TEST-MAP: WTL-03
        if st(A, "WTL-03") == "FAIL":
            put("WTL-03", False, f"timeout TLC preimage leaked: {A.get('WTL-03')}")
        else:
            put("WTL-03", True, TESTNET_ONLY + f" (devnet: no preimage leak, A={st(A, 'WTL-03')})", skip=True)
        # B is preimage-only, so 04/05/06/07/08 resolve on devnet; A's versions need the timeout path
        for case in ("WTL-04", "WTL-05", "WTL-06", "WTL-07"):
            if st(A, case) == "FAIL":
                put(case, False, f"A={A.get(case)}")
            else:
                put(case, st(B, case) == "PASS", f"B(preimage-only)={B.get(case)}; A timeout part testnet-only ({st(A, case)})")
        # TEST-MAP: WTL-08
        put("WTL-08", st(B, "WTL-08") == "PASS" and stat.get(c) == "fail" and st(C, "WTL-08") == "FAIL"
            and any(c and c in p for p in fposts), f"B={B.get('WTL-08')}; C(1s deadline)={C.get('WTL-08')} alert={'yes' if fposts else 'no'}")
        put("WTL-09", len(failed) == 1, f"build_failed records={len(failed)}")
        # TEST-MAP: WTL-10
        put("WTL-10", st(B, "WTL-10") == "PASS" and dup == 0 and len(fposts) == len(set(fposts)),
            f"B={B.get('WTL-10')} dup_events={dup}")
        put("WTL-11", True, "4 invalid configs rejected (exit 3) before any RPC")
        # TEST-MAP: WTL-12
        # TEST-MAP: WTL-13
        for case in ("WTL-12", "WTL-13"):
            if st(A, case) == "FAIL":
                put(case, False, f"A={A.get(case)}")
            else:
                put(case, True, TESTNET_ONLY + f" (A={st(A, case)}, B={st(B, case)})", skip=True)
        put("web", "WTL" in page and len(api) >= 4, f"dashboard {len(page)}B, api scenarios={len(api)}")
        put("daily", any("daily summary" in p for p in _Discord.posts), f"discord posts={len(_Discord.posts)}")
        print("\nCASE      RESULT  REASON")
        for k in sorted(report):
            print(f"{k:9} {report[k][0]:6}  {report[k][1]}")
        with open(os.path.join(self.work, "result.json"), "w") as f:
            json.dump({"report": report, "cases": cases, "status": stat, "discord": _Discord.posts}, f, indent=1)
        bad = {k: v for k, v in report.items() if v[0] == "FAIL"}
        assert not bad, bad
