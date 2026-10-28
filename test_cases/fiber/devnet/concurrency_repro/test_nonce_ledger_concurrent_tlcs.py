"""Repro: N concurrent (pipelined) TLCs on ONE channel -> does fnn force close it via the
revocation-nonce-ledger watchdog (fiber #1701 / cd97934)? Not an assertion of correctness:
records per-round outcome to /workspace/logs/concurrency-repro/. Run:
  FIBER_START_TIMEOUT=900 venv/bin/python -m pytest -s test_cases/fiber/devnet/concurrency_repro
"""
import json, os, secrets, shutil, time

from framework.basic_fiber import FiberTest
from framework.util import ckb_hash

OUT = os.environ.get("REPRO_OUT", "/workspace/logs/concurrency-repro")
ROUNDS = int(os.environ.get("REPRO_ROUNDS", "3"))
N = int(os.environ.get("REPRO_TLCS", "6"))
MSG = "revocation nonce ledger has been unbalanced for over"


class TestNonceLedgerConcurrentTlcs(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 3}

    def _log(self, f):
        return open(f"{f.tmp_path}/node.log", errors="replace").read()

    def test_concurrent_tlcs_one_channel(self):
        os.makedirs(OUT, exist_ok=True)
        results = []
        for rnd in range(ROUNDS):
            self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
            chans = [c for c in self.fiber1.get_client().list_channels({})["channels"] if c["state"]["state_name"] == "ChannelReady"]
            ch = chans[-1]["channel_id"]
            base = [self._log(self.fiber1).count(MSG), self._log(self.fiber2).count(MSG)]
            hashes = []
            for i in range(N):
                pre = "0x" + secrets.token_hex(32)
                hold = i % 2 == 1
                inv = {"amount": hex(100000000), "currency": "Fibd", "description": f"r{rnd}-{i}", "expiry": hex(3600)}
                if hold:
                    inv["payment_hash"] = ckb_hash(pre)
                else:
                    inv["payment_preimage"] = pre
                addr = self.fiber2.get_client().new_invoice(inv)["invoice_address"]
                r = self.fiber1.get_client().send_payment({"invoice": addr})  # no wait: pipelined
                hashes.append((r["payment_hash"], hold))
            t0 = time.time(); forced = False
            while time.time() - t0 < 120:
                cnt = [self._log(self.fiber1).count(MSG) - base[0], self._log(self.fiber2).count(MSG) - base[1]]
                if sum(cnt):
                    forced = True; break
                st = [self.fiber1.get_client().get_payment({"payment_hash": h})["status"] for h, _ in hashes]
                if all(s in ("Success", "Inflight") for s in st) and \
                   all(self.fiber2.get_client().get_invoice({"payment_hash": h})["status"] in ("Received", "Paid") for h, _ in hashes):
                    break
                time.sleep(2)
            state = [c["state"] for c in self.fiber1.get_client().list_channels({"include_closed": True})["channels"] if c["channel_id"] == ch]
            res = {"round": rnd, "channel": ch, "tlcs": N, "watchdog_force_close": forced,
                   "elapsed_s": round(time.time() - t0, 1), "channel_state": state,
                   "payments": [self.fiber1.get_client().get_payment({"payment_hash": h})["status"] for h, _ in hashes]}
            print("REPRO", json.dumps(res)); results.append(res)
            # cancel holds so the next round starts clean
            for h, hold in hashes:
                if hold:
                    try: self.fiber2.get_client().cancel_invoice({"payment_hash": h})
                    except Exception as e: print("cancel", e)
            time.sleep(5)
        json.dump(results, open(f"{OUT}/results-{int(time.time())}.json", "w"), indent=1)
        for i, f in enumerate((self.fiber1, self.fiber2), 1):
            shutil.copy(f"{f.tmp_path}/node.log", f"{OUT}/fnn-node{i}-{int(time.time())}.log")
