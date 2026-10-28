# Review feedback

## reviews/testnet/watchtower-longrun.md (acceptance-internal#1665)

- Decision: **all 13 cases (WTL-01 … WTL-13) approved unchanged** by the owner; implement on a
  local devnet first, then the testnet long-run.
- Steering: merge cases into shared scenarios (one scenario reports a PASS/FAIL row per WTL-ID);
  builder (CI, exits after force close + record write) and verifier (long-running) must be
  independent processes that only share the scenario record files.
- Case → scenario mapping is recorded at the end of `reviews/testnet/watchtower-longrun.md`.

## Timeout-path recovery: testnet-only (owner decision 2026-10-28)

- fnn adds a random +N×4h privacy delta (4h–14d, capped by `tlc_expiry_limit`) to every TLC expiry, so
  timeout TLCs cannot expire inside a devnet run. Decision: devnet does **not** verify timeout-path
  recovery; WTL-03/12/13 and the timeout parts of WTL-04..07 report `SKIP (testnet-only)`; the
  preimage/on-chain parts are still asserted on devnet (preimage-only scenario B).
- Testnet: scenarios with timeout TLCs use `timeout_deadline_hours` (default 384h = 16d) instead of
  `deadline_hours` (30h). Implication: a broken timeout claim is only reported FAIL up to ~16 days after
  the scenario was built (late alert); expiry-margin alerts, preimage leaks and WTL-06 still fire early.
