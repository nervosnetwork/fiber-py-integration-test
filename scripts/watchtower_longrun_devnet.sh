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
# Devnet genesis (source/template/ckb/fiber/dev.toml) embeds source/contract/fiber/*, pinned to the
# release fnn. A develop fnn needs the matching contracts from its own tree, otherwise settlement
# txs fail commitment-lock with error 11 (InvalidExpiry). FIBER_CONTRACTS_DIR overlays them for
# this run only and restores the pinned files on exit.
FIBER_CONTRACTS_DIR=${FIBER_CONTRACTS_DIR:-}
BK=tmp/wtl-contract-backup
restore_contracts() { if [ -d "$BK" ]; then cp "$BK"/* source/contract/fiber/; rm -rf "$BK"; fi; }
restore_contracts
if [ -n "$FIBER_CONTRACTS_DIR" ]; then
  mkdir -p "$BK"; cp source/contract/fiber/{commitment-lock,funding-lock,auth} "$BK"/
  cp "$FIBER_CONTRACTS_DIR"/{commitment-lock,funding-lock,auth} source/contract/fiber/
  echo "using fiber contracts from $FIBER_CONTRACTS_DIR"
fi
cleanup; sleep 2; trap 'cleanup; restore_contracts' EXIT
# fiber stores from an earlier chain gossip stale channels -> peers flag each other as malicious
rm -rf tmp/fiber/node* tmp/wtl-e2e
# debug fnn: secret-key KDF migration on first start can take >300s
export FIBER_START_TIMEOUT=${FIBER_START_TIMEOUT:-900}
"$PY" -m pytest -s test_cases/fiber/devnet/watchtower_longrun/test_watchtower_longrun_devnet.py "$@"
