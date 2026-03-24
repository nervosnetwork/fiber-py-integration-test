"""Helpers for fee_stats integration tests (PR #1201 RPCs).

Pagination: `forwarding_history` / `payment_history` use **cursor** fields `after`
(request) and `last_cursor` (response). See
`fiber/crates/fiber-json-types/src/fee.rs`.

Copilot / matrix coverage: Rust unit tests in `fiber-lib` cover store batching,
saturating math, and mock-store scenarios (modules A–E, G). Python tests here
focus on JSON-RPC behaviour, E2E recording (module F), and cursor/validation
that are cheap to assert against a live node.
"""

import pytest


def skip_if_fee_stats_unavailable(client):
    """Skip tests when the fnn binary does not expose Info fee/payment RPCs."""
    try:
        client.fee_report({})
    except Exception as e:
        msg = str(e).lower()
        if (
            "method not found" in msg
            or "not found" in msg
            or "unknown method" in msg
            or "invalid request" in msg
        ):
            pytest.skip(
                "fnn binary does not support fee_report / fee stats RPCs (build from fiber with PR #1201)"
            )
        raise


def u64(hex_str):
    return int(hex_str, 16)


def u128(hex_str):
    return int(hex_str, 16)


def ckb_asset_report(asset_reports):
    """Return the fee/payment report entry for native CKB (no UDT script)."""
    for r in asset_reports:
        if r.get("udt_type_script") in (None, {}):
            return r
    return None


def scripts_equivalent(a, b):
    """Compare CKB `Script` JSON objects (hex case-insensitive)."""
    if a is None or b is None:
        return a == b
    return (
        str(a.get("code_hash", "")).lower() == str(b.get("code_hash", "")).lower()
        and a.get("hash_type") == b.get("hash_type")
        and str(a.get("args", "")).lower() == str(b.get("args", "")).lower()
    )


def udt_asset_report(asset_reports, udt_type_script):
    """Return the fee/payment report row matching the given UDT type script."""
    for r in asset_reports:
        u = r.get("udt_type_script")
        if u and scripts_equivalent(u, udt_type_script):
            return r
    return None


def collect_forwarding_pages(client, page_limit=2, max_pages=50):
    """Walk all pages via `after` / `last_cursor` (Copilot B-8 style)."""
    all_events = []
    after = None
    for _ in range(max_pages):
        params = {"limit": hex(page_limit)}
        if after is not None:
            params["after"] = after
        r = client.forwarding_history(params)
        es = r["events"]
        all_events.extend(es)
        after = r.get("last_cursor")
        if not es:
            break
        if after is None:
            break
    return all_events


def collect_payment_history_pages(client, page_limit=2, max_pages=50):
    """Walk all payment_history pages via cursor (Copilot D-5 style)."""
    all_events = []
    after = None
    for _ in range(max_pages):
        params = {"limit": hex(page_limit)}
        if after is not None:
            params["after"] = after
        r = client.payment_history(params)
        es = r["events"]
        all_events.extend(es)
        after = r.get("last_cursor")
        if not es:
            break
        if after is None:
            break
    return all_events
