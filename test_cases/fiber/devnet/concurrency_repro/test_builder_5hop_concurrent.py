"""Repro over the REAL builder path: 5-node devnet route N1..N5 (N3 public), send_mode=concurrent
(build_router + send_payment_with_router, normal + preimage + hold TLCs pipelined), force_close.skip.
Per round counts: 'unbalanced for over' log lines (all nodes), channels that left ChannelReady.
  REPRO_ROUNDS=10 [REPRO_VARIANT=bidir REPRO_REVERSE=1] bash scripts/concurrency_repro_devnet.sh -k 5hop
Per-round fnn log slices are archived under /workspace/logs/concurrency-repro/5hop-<variant>-<ts>/ (never overwritten).
Not a correctness assertion; results -> /workspace/logs/concurrency-repro/builder-5hop.json
"""
import glob, json, os, shutil, threading, time

from test_cases.fiber.devnet.watchtower_longrun import test_watchtower_longrun_devnet as _e2e  # module import: not collected

FINAL_DELTA_MS, TLC_DELTA_MS = _e2e.FINAL_DELTA_MS, _e2e.TLC_DELTA_MS
from framework.util import get_project_root

OUT = os.environ.get("REPRO_OUT", "/workspace/logs/concurrency-repro")
ROUNDS = int(os.environ.get("REPRO_ROUNDS", "3"))
TLCS = int(os.environ.get("REPRO_TLCS", "4"))  # per kind
MSG = "revocation nonce ledger has been unbalanced for over"
VARIANT = os.environ.get("REPRO_VARIANT", "forward")  # forward | bidir
REVERSE = os.environ.get("REPRO_REVERSE", "1") == "1"  # bidir: also keysend N5->N1 during the round
# force-close cause classification on each round's log slice
CAUSES = {"watchdog": "unbalanced for over", "shutdowning": "in shutdowning state",
          "inactive": "is inactive for a time"}


class TestBuilder5HopConcurrent(_e2e.TestWatchtowerLongrunDevnet):
    test_watchtower_longrun_devnet = None  # don't re-run the e2e

    def _log(self, f):
        try:
            return open(f"{f.tmp_path}/node.log", errors="replace").read()
        except FileNotFoundError:
            return ""

    def test_builder_5hop_concurrent(self):
        os.makedirs(OUT, exist_ok=True)
        self.root = get_project_root()
        self.work = os.path.join(self.root, "tmp", "wtl-5hop-repro")
        shutil.rmtree(self.work, ignore_errors=True)
        os.makedirs(self.work)
        self.records = os.path.join(self.work, "records")
        for n in (3, 4, 5):
            shutil.rmtree(os.path.join(self.root, "tmp", "fiber", f"node{n}"), ignore_errors=True)
        f3, f4, f5 = (self.start_new_fiber(self._account()) for _ in range(3))
        fibers = [self.fiber1, self.fiber2, f3, f4, f5]
        for a, b in zip(fibers, fibers[1:]):
            self._open(a, b, 5000)
        time.sleep(10)
        names = ["N1", "N2", "N3", "N4", "N5"]
        self.topo_path = self._write_yaml("topology.yaml", {
            "ckb_rpc_url": self.node.rpcUrl, "explorer_tx_url": "x/{}", "currency": "Fibd",
            "nodes": [{"name": n, "controlled": n != "N3", "rpc_url": f.get_client().url, "pubkey": f.get_pubkey()} for n, f in zip(names, fibers)]})
        cfg = {
            "scenarios_per_day": 1, "deadline_hours": 0.5, "send_mode": "concurrent",
            "scenario": {"normal_payments": {"count": TLCS, "amount_ckb": 1}, "preimage_tlcs": {"count": TLCS, "amount_ckb": 1},
                         "timeout_tlcs": {"count": TLCS, "amount_ckb": 1}, "final_tlc_expiry_delta_ms": FINAL_DELTA_MS},
            "tlc_expiry_delta_ms": TLC_DELTA_MS,
            "force_close": {"strategy": "fixed", "fixed_index": 0, "spare_parallel": 0, "reopen_capacity_ckb": 1000,
                            "skip": True, "close_sets": [[["N1", "N2"]]]},
            "post_check_amount_ckb": 1, "rebalance": {"enabled": False}, "liquidity": {"auto_open": False},
            "limits": {"max_tlcs_per_scenario": 200, "max_scenarios_per_day": 1000},
        }
        if VARIANT == "bidir":
            cfg["force_close"]["cancel_holds"] = False  # previous round's holds are failed back DURING the next round
        p = self._write_yaml("cfg.yaml", cfg)
        run_dir = os.path.join(OUT, f"5hop-{VARIANT}-{time.strftime('%Y%m%d-%H%M%S')}")
        os.makedirs(run_dir)
        results = []
        prev_holds = []
        for rnd in range(ROUNDS):
            base = [len(self._log(f)) for f in fibers]
            stop = threading.Event()
            side = {"cancelled": 0, "reverse_ok": 0, "reverse_err": 0}

            def backflow():
                for h in prev_holds:  # removals flow N5->N1 while new adds flow N1->N5
                    try:
                        f5.get_client().cancel_invoice({"payment_hash": h}); side["cancelled"] += 1
                    except Exception:
                        pass
                    time.sleep(0.2)
                while REVERSE and not stop.is_set():
                    try:
                        f5.get_client().send_payment({"target_pubkey": self.fiber1.get_pubkey(), "amount": hex(10 ** 8), "keysend": True})
                        side["reverse_ok"] += 1
                    except Exception:
                        side["reverse_err"] += 1
                    time.sleep(1)
            th = threading.Thread(target=backflow, daemon=True) if VARIANT == "bidir" else None
            if th:
                time.sleep(0); th.start()
            r = self._run("watchtower_longrun.builder", "--config", p, "--topology", self.topo_path, "--records-dir", self.records)
            stop.set()
            if th:
                th.join(60)
            time.sleep(15)  # let watchdog fire if it will
            recs = sorted(glob.glob(os.path.join(self.records, "*.json")), key=os.path.getmtime)
            prev_holds = [t["payment_hash"] for t in json.load(open(recs[-1])).get("tlcs", []) if t["kind"] == "timeout"] if recs else []
            causes = {}
            for nm, f, b in zip(names, fibers, base):
                sl = self._log(f)[b:]
                with open(os.path.join(run_dir, f"round{rnd:02d}-{nm}.log"), "w") as o:
                    o.write(sl)
                causes[nm] = {k: sl.count(v) for k, v in CAUSES.items()}
            unb = [causes[nm]["watchdog"] for nm in names]
            not_ready = []
            for nm, f in zip(names, fibers):
                for c in f.get_client().list_channels({"include_closed": True})["channels"]:
                    if c["state"]["state_name"] != "ChannelReady":
                        not_ready.append((nm, c["channel_id"][:12], c["state"]["state_name"]))
            res = {"round": rnd, "builder_rc": r.returncode, "unbalanced_lines": dict(zip(names, unb)),
                   "not_ready": sorted(set(not_ready)), "causes": causes, "side": side, "builder_err_tail": r.stderr[-400:] if r.returncode else ""}
            print("REPRO5", json.dumps(res)); results.append(res)
        summary = {"variant": VARIANT, "reverse": REVERSE, "logs": run_dir, "rounds": ROUNDS,
                   "cause_totals": {k: sum(x["causes"][n][k] for x in results for n in names) for k in CAUSES}, "tlcs_per_round": 3 * TLCS,
                   "rounds_with_unbalanced": sum(1 for x in results if sum(x["unbalanced_lines"].values())),
                   "rounds_with_not_ready": sum(1 for x in results if x["not_ready"]),
                   "builder_failures": sum(1 for x in results if x["builder_rc"])}
        print("REPRO5-SUMMARY", json.dumps(summary))
        json.dump({"summary": summary, "rounds": results}, open(os.path.join(run_dir, "result.json"), "w"), indent=1)
