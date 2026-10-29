#!/usr/bin/env bash
# One-command devnet e2e for the testnet watchtower long-run tooling.
# Needs: download/0.202.0 (ckb) as for other devnet suites, and a DEBUG fnn
# (2s epochs) at download/fiber/current/fnn — build fiber with `cargo build`
# and copy target/debug/fnn there.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${PYTHON:-}" ] && [ -x venv/bin/python ]; then PYTHON=venv/bin/python; fi
PY=${PYTHON:-python3}
[ -x download/fiber/current/fnn ] || { echo "missing download/fiber/current/fnn (debug build)"; exit 1; }
cleanup() {
  for pid in $(pgrep -f "ckb (run|miner)" || true); do case "$(readlink /proc/$pid/cwd 2>/dev/null)" in "$PWD"/tmp/*) kill -9 "$pid" 2>/dev/null || true;; esac; done
  pkill -f "$PWD/tmp/fiber/node[0-9]*/fiber" 2>/dev/null || true; pkill -f "$PWD/download/fiber/current/fnn" 2>/dev/null || true; }
# FIBER_CONTRACTS_DIR (e.g. $FIBER_SRC/tests/deploy/contracts): the test upgrades the snapshot's
# type-id commitment-lock cell to the binary matching the fnn under test.
# one devnet at a time: e2e and the concurrency repro share ckb :8114 and fnn ports
exec 9>/tmp/fiber-devnet.lock; flock -n 9 || { echo "another devnet run holds /tmp/fiber-devnet.lock"; exit 1; }
export FIBER_CONTRACTS_DIR=${FIBER_CONTRACTS_DIR:-}
BK=tmp/wtl-contract-backup  # restore leftovers from the earlier (ineffective) genesis overlay
if [ -d "$BK" ]; then cp "$BK"/* source/contract/fiber/; rm -rf "$BK"; fi
cleanup; sleep 2; trap cleanup EXIT
# fiber stores from an earlier chain gossip stale channels -> peers flag each other as malicious
rm -rf tmp/fiber/node* tmp/wtl-e2e
# debug fnn: secret-key KDF migration on first start can take >300s
export FIBER_START_TIMEOUT=${FIBER_START_TIMEOUT:-900}
# TLC expiry: fnn adds a privacy random delta of N x 4h (DEFAULT_TLC_EXPIRY_DELTA, graph.rs
# rand_tlc_expiry_delta) to every payment, so timeout TLCs expire 4h..14d out regardless of the
# 60s deltas we set. Wall-clock time can't be changed here (the watch_tower_wit_tlc tests use
# `sudo date`), so ckb+fnn run under libfaketime with an offset file the test advances.
FAKETIME_LIB=${FAKETIME_LIB:-/workspace/libfaketime/src/libfaketime.so.1}
if [ "${WTL_FAKETIME:-0}" = 1 ] && [ -f "$FAKETIME_LIB" ]; then  # opt-in: ckb hangs at startup under libfaketime (jemalloc/pthread)
  export WTL_FAKETIME_FILE=/tmp/wtl-faketime.rc; echo "+0" > "$WTL_FAKETIME_FILE"
  export LD_PRELOAD=$FAKETIME_LIB FAKETIME_TIMESTAMP_FILE=$WTL_FAKETIME_FILE FAKETIME_DONT_FAKE_MONOTONIC=1 FAKETIME_CACHE_DURATION=1
  echo "faketime enabled ($FAKETIME_LIB)"
fi
"$PY" -m pytest -s test_cases/fiber/devnet/watchtower_longrun/test_watchtower_longrun_devnet.py "$@"
