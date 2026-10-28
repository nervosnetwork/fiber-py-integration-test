#!/usr/bin/env bash
# Revocation-nonce-ledger concurrency repro. Shares ckb/fnn ports with the watchtower e2e, so both
# take /tmp/fiber-devnet.lock and never run together.
set -u
cd "$(dirname "$0")/.."
exec 9>/tmp/fiber-devnet.lock; flock -n 9 || { echo "another devnet run holds /tmp/fiber-devnet.lock"; exit 1; }
pkill -f "ckb run|fnn " ; sleep 2; rm -rf tmp/fiber/node*
FIBER_START_TIMEOUT=${FIBER_START_TIMEOUT:-900} timeout 1500 venv/bin/python -m pytest -s test_cases/fiber/devnet/concurrency_repro
