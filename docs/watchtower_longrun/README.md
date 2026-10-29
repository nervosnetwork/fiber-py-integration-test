# Testnet watchtower long-run

Cases: `reviews/testnet/watchtower-longrun.md` (WTL-01..13). Design: `docs/design/testnet-watchtower-longrun.md`.

The system is two **independent** parts that share only the records directory:

| part | code | runs | does |
| --- | --- | --- | --- |
| 1. scenario builder | `watchtower_longrun/builder` | daily GitHub Actions job on the self-hosted runner (`.github/workflows/testnet-watchtower-longrun.yml`) | config validation (WTL-11), env pre-check (WTL-09), refills channels, sends normal/preimage/timeout TLCs, force closes the close set, settles preimage TLCs, writes `<records>/<id>.json`, **exits** |
| 2. verifier | `watchtower_longrun/verifier` | systemd service, forever | ingests records, tracks every open scenario (many may overlap) for days, SQLite state (restart safe, WTL-10), per-case PASS/FAIL, deadline (WTL-08), read-only web, Discord |

## One scenario verifies many cases

Default testnet close set `[[N1,N2,{parallel:2}]]`: one scenario -> rows WTL-01..07, 08, 09, 10, 11, 13 (WTL-12 = N/A, needs both route ends controlled).
With 4 controlled nodes `[[N1,N2],[N4,N5,{parallel:2}]]` covers WTL-12 too.

| case | how the verifier decides |
| --- | --- |
| 01 | commitment tx committed for every force-closed channel |
| 02 | every preimage TLC's preimage appears in a witness of the channel's on-chain trace |
| 03 | timeout TLC channels fully settled, preimage never on-chain |
| 04 | no live cell with the commitment lock code_hash left; per-channel fee <= `max_fee_ckb_per_channel` |
| 05 | unclosed route channels Ready, no scenario payment_hash still pending |
| 06 | public-node channels never ShuttingDown/Closed (latched FAIL); alert before an unresolved TLC expires |
| 07 | keysend N1->N5 over spare channels succeeds after 01-05 |
| 08 | all resolved before `deadline_hours` (`timeout_deadline_hours`, default 16d, when the scenario has timeout TLCs); otherwise every pending case FAIL + Discord alert |
| 09 | builder pre-check: bad RPC / missing channel -> exit 2, `build_failed` record, nothing closed |
| 10 | scenario stayed in flight across a verifier restart without duplicate events/alerts |
| 11 | invalid config -> exit 3 before any RPC write |
| 12 | both end segments settled with preimage + timeout claims |
| 13 | each parallel channel settled; spare channel still Ready |

## Run on devnet (one command)

```bash
bash scripts/watchtower_longrun_devnet.sh
```

Uses debug `fnn` (2 s epochs) in `download/fiber/current/`, a C-C-P-C-C 5-node devnet, short TLC deltas, mocked Discord.
Result: `tmp/wtl-e2e/result.json`, verifier log `tmp/wtl-e2e/verifier.log`.

## Run on testnet

1. Topology: copy `config/watchtower_longrun_topology.example.yaml` to `/etc/wtl/topology.yaml`, fill RPC URLs of controlled nodes (route order N1..N5) and pubkeys of public nodes.
2. Tune `config/watchtower_longrun.yaml` (`scenarios_per_day`, counts, amounts, `close_sets`, `deadline_hours`).
3. Verifier service:
   ```bash
   sudo useradd -r wtl; sudo mkdir -p /etc/wtl /var/lib/wtl/records; sudo chown -R wtl /var/lib/wtl
   sudo cp deploy/watchtower_longrun/verifier.env.example /etc/wtl/verifier.env  # put WTL_DISCORD_WEBHOOK here, chmod 600
   sudo cp deploy/watchtower_longrun/wtl-verifier.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now wtl-verifier
   ```
   Web: `http://127.0.0.1:8088/` (`/scenario/<id>`, `/nodes`, `/api/...`). Expose through your own reverse proxy if needed.
4. Builder: the workflow runs daily on `[self-hosted, fiber-testnet]`; `workflow_dispatch` accepts the overrides and `dry_run`. Manual:
   ```bash
   python -m watchtower_longrun.builder --config config/watchtower_longrun.yaml --topology /etc/wtl/topology.yaml --records-dir /var/lib/wtl/records [--dry-run]
   ```

Secrets: the Discord webhook lives only in `WTL_DISCORD_WEBHOOK` (env file / runner secret), never in git.
Safety: the builder refuses any close set that touches a non-controlled node; it never calls `shutdown_channel` on public-node channels.

### Liquidity / wallet
See the `rebalance`, `liquidity`, `wallet` and `verifier.wallet_warn_ckb` keys in `config/watchtower_longrun.yaml`. Auto-open only happens from a controlled upstream node; a public-public hop that runs out of liquidity becomes `build_failed`. The devnet e2e asserts `auto-open`, `rebalance` and `wallet`.
