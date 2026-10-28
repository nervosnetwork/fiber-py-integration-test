# Review feedback

## reviews/testnet/watchtower-longrun.md (acceptance-internal#1665)

- Decision: **all 13 cases (WTL-01 … WTL-13) approved unchanged** by the owner; implement on a
  local devnet first, then the testnet long-run.
- Steering: merge cases into shared scenarios (one scenario reports a PASS/FAIL row per WTL-ID);
  builder (CI, exits after force close + record write) and verifier (long-running) must be
  independent processes that only share the scenario record files.
- Case → scenario mapping is recorded at the end of `reviews/testnet/watchtower-longrun.md`.
