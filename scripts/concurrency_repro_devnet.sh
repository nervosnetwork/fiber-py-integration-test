#!/usr/bin/env bash
# Revocation-nonce-ledger concurrency repro. Shares ckb/fnn ports with the watchtower e2e, so both
# take /tmp/fiber-devnet.lock and never run together.
set -u
cd "$(dirname "$0")/.."
exec 9>/tmp/fiber-devnet.lock; flock -n 9 || { echo "another devnet run holds /tmp/fiber-devnet.lock"; exit 1; }
# same cleanup as the e2e: stale ckb run/miner on :8114 made setup's get_consensus time out
cleanup() {
  for pid in $(pgrep -f "ckb (run|miner)" || true); do case "$(readlink /proc/$pid/cwd 2>/dev/null)" in "$PWD"/tmp/*) kill -9 "$pid" 2>/dev/null || true;; esac; done
  pkill -f "$PWD/tmp/fiber/node[0-9]*/fiber" 2>/dev/null || true; pkill -f "$PWD/download/fiber/current/fnn" 2>/dev/null || true; }
cleanup; sleep 3; trap cleanup EXIT
rm -rf tmp/fiber/node*
# wait until :8114 is free so the fresh ckb can bind it
for _ in $(seq 30); do (exec 3<>/dev/tcp/127.0.0.1/8114) 2>/dev/null || break; sleep 2; done
export FIBER_START_TIMEOUT=${FIBER_START_TIMEOUT:-900}
timeout ${REPRO_TIMEOUT:-3600} venv/bin/python -m pytest -s test_cases/fiber/devnet/concurrency_repro "$@"
