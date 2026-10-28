#!/usr/bin/env bash
# One-command devnet e2e for the testnet watchtower long-run tooling.
# Needs: download/0.202.0 (ckb) as for other devnet suites, and a DEBUG fnn
# (2s epochs) at download/fiber/current/fnn — build fiber with `cargo build`
# and copy target/debug/fnn there.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
[ -x download/fiber/current/fnn ] || { echo "missing download/fiber/current/fnn (debug build)"; exit 1; }
exec "$PY" -m pytest -s test_cases/fiber/devnet/watchtower_longrun/test_watchtower_longrun_devnet.py "$@"
