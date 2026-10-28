"""Builder config: load yaml, apply overrides, validate (WTL-11)."""
import copy

from watchtower_longrun.common import load_yaml

OVERRIDE_KEYS = {
    "scenarios_per_day": ("scenarios_per_day",),
    "normal_count": ("scenario", "normal_payments", "count"),
    "preimage_count": ("scenario", "preimage_tlcs", "count"),
    "timeout_count": ("scenario", "timeout_tlcs", "count"),
    "amount_ckb": None,  # applies to all three types
    "close_set": None,  # index into force_close.close_sets
}


class ConfigError(Exception):
    pass


def load_config(path, overrides=None):
    cfg = load_yaml(path)
    return apply_overrides(cfg, overrides or {})


def apply_overrides(cfg, overrides):
    cfg = copy.deepcopy(cfg)
    for key, value in overrides.items():
        if value in (None, ""):
            continue
        if key not in OVERRIDE_KEYS:
            raise ConfigError(f"unknown override {key}")
        if key == "amount_ckb":
            for t in ("normal_payments", "preimage_tlcs", "timeout_tlcs"):
                cfg["scenario"][t]["amount_ckb"] = float(value)
            continue
        if key == "close_set":
            cfg["force_close"]["strategy"] = "fixed"
            cfg["force_close"]["fixed_index"] = int(value)
            continue
        node = cfg
        path = OVERRIDE_KEYS[key]
        for p in path[:-1]:
            node = node[p]
        node[path[-1]] = int(value)
    return cfg


def parse_channel_ref(ref):
    """[N1, N2] or [N1, N2, {parallel: 2}] -> (a, b, parallel)."""
    if not isinstance(ref, (list, tuple)) or len(ref) < 2:
        raise ConfigError(f"bad channel ref {ref!r}")
    parallel = 1
    for extra in ref[2:]:
        if isinstance(extra, dict) and "parallel" in extra:
            parallel = int(extra["parallel"])
    return str(ref[0]), str(ref[1]), parallel


# WTL-11 validation logic (mapped by the devnet e2e)
def validate(cfg, topology):
    """Pure validation, no RPC. Raises ConfigError with all problems found."""
    errors = []
    sc = cfg.get("scenario", {})
    limits = cfg.get("limits", {})
    counts = {}
    for t in ("normal_payments", "preimage_tlcs", "timeout_tlcs"):
        item = sc.get(t, {})
        c = item.get("count", 0)
        a = item.get("amount_ckb", 0)
        if not isinstance(c, int) or c < 0:
            errors.append(f"scenario.{t}.count must be an integer >= 0, got {c!r}")
        if not isinstance(a, (int, float)) or a <= 0:
            errors.append(f"scenario.{t}.amount_ckb must be > 0, got {a!r}")
        counts[t] = c if isinstance(c, int) else 0
    pending = counts["preimage_tlcs"] + counts["timeout_tlcs"]
    if pending == 0:
        errors.append("scenario needs at least one preimage or timeout TLC")
    max_tlcs = limits.get("max_tlcs_per_scenario", 50)
    if sum(counts.values()) > max_tlcs:
        errors.append(f"total TLCs {sum(counts.values())} > limits.max_tlcs_per_scenario {max_tlcs}")
    spd = cfg.get("scenarios_per_day", 1)
    if not isinstance(spd, int) or spd < 1:
        errors.append(f"scenarios_per_day must be >= 1, got {spd!r}")
    elif spd > limits.get("max_scenarios_per_day", 4):
        errors.append(f"scenarios_per_day {spd} > limits.max_scenarios_per_day")
    fc = cfg.get("force_close", {})
    sets = fc.get("close_sets") or []
    if not sets:
        errors.append("force_close.close_sets is empty")
    pairs = set(topology.hop_pairs())
    for si, s in enumerate(sets):
        for ref in s:
            try:
                a, b, par = parse_channel_ref(ref)
            except ConfigError as e:
                errors.append(str(e))
                continue
            if a not in topology.by_name or b not in topology.by_name:
                errors.append(f"close_sets[{si}] unknown node in {ref}")
                continue
            if (a, b) not in pairs:
                errors.append(f"close_sets[{si}] {a}-{b} is not a hop on the route")
            if not (topology.controlled(a) and topology.controlled(b)):
                errors.append(f"close_sets[{si}] {a}-{b} involves a public node; only controlled-controlled channels may be force closed")
            if par < 1:
                errors.append(f"close_sets[{si}] parallel must be >= 1")
    if fc.get("strategy", "round_robin") not in ("round_robin", "fixed", "random"):
        errors.append("force_close.strategy must be round_robin|fixed|random")
    if fc.get("strategy") == "fixed" and not (0 <= fc.get("fixed_index", 0) < max(len(sets), 1)):
        errors.append("force_close.fixed_index out of range")
    for n in topology.order[:1] + topology.order[-1:]:
        if not topology.controlled(n):
            errors.append(f"route endpoint {n} must be a controlled node (payer/receiver)")
    if errors:
        raise ConfigError("; ".join(errors))
    return True


def capacity_errors(cfg, needed_by_pair, available_by_pair):
    """WTL-11 capacity part, evaluated by builder pre-check with live balances.

    needed_by_pair/available_by_pair: {(a,b): shannons}
    """
    errs = []
    for pair, need in needed_by_pair.items():
        have = available_by_pair.get(pair, 0)
        if have < need:
            errs.append(f"{pair[0]}-{pair[1]} local balance {have} < needed {need}")
    return errs
