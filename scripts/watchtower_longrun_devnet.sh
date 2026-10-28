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
cleanup; sleep 2; trap cleanup EXIT
# fiber stores from an earlier chain gossip stale channels -> peers flag each other as malicious
rm -rf tmp/fiber/node* tmp/wtl-e2e
# debug fnn: secret-key KDF migration on first start can take >300s
export FIBER_START_TIMEOUT=${FIBER_START_TIMEOUT:-900}
"$PY" -m pytest -s test_cases/fiber/devnet/watchtower_longrun/test_watchtower_longrun_devnet.py "$@"
