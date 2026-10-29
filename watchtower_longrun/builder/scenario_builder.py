"""Scenario builder (part 1 of 2).

Runs once (daily CI / workflow_dispatch / devnet e2e), builds N scenarios and
EXITS right after the force closes. It never waits for watchtower recovery;
that is the verifier's job and can take days on testnet.

Per scenario:
  1. pre-check env (WTL-09) and config (WTL-11)
  2. make sure every hop has a ready channel; for each pair in the chosen close
     set make sure there are `parallel` victim channels + `spare` channels
  3. send normal payments (settled off-chain), hold-invoice payments for
     preimage/timeout TLCs, pinning TLCs onto victim channels with build_router
  4. snapshot pending TLCs, force close every victim channel
  5. settle the preimage-type hold invoices on the receiver (after close, so
     the preimage has to be used on-chain by the watchtower)
  6. write the scenario record JSON
"""
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import random
import secrets
import sys
import time

from watchtower_longrun.common import (  # noqa
    wallet_shannons,
    CKB_SHANNONS,
    RpcError,
    Topology,
    h,
    i,
    now_ms,
    state_name,
    write_json_atomic,
)
from watchtower_longrun.config import (
    ConfigError,
    capacity_errors,
    load_config,
    parse_channel_ref,
    validate,
)

LOG = logging.getLogger("wtl.builder")
RECORD_VERSION = 1


def deadline_hours(cfg, tlcs):
    """Scenarios with timeout TLCs need > fnn's max random privacy expiry delta (14d)."""
    if cfg.get("timeout_deadline_hours") is not None and any(t.get("kind") == "timeout" for t in tlcs):
        return cfg["timeout_deadline_hours"]
    return cfg.get("deadline_hours", 30)


class BuildError(Exception):
    """Failure after TLCs were sent; carries them so the record is debuggable."""
    def __init__(self, msg, tlcs=None):
        super().__init__(msg)
        self.tlcs = list(tlcs or [])


class PrecheckError(Exception):
    pass


def ckb_hash(hex_data):
    from hashlib import blake2b

    d = blake2b(digest_size=32, person=b"ckb-default-hash")
    d.update(bytes.fromhex(hex_data[2:]))
    return "0x" + d.hexdigest()


def outpoint_tx(op):
    """channel_outpoint hex (32-byte tx hash + u32 LE index) -> (tx_hash, index)."""
    raw = op[2:]
    return "0x" + raw[:64], int.from_bytes(bytes.fromhex(raw[64:72]), "little")


def liquidity_action(topo, a, b, lq):
    """What auto-open does for a short hop a->b: open_upstream | open_downstream | fail.
    public-public is always fail (never opened)."""
    if topo.controlled(a):
        return "open_upstream"
    if topo.controlled(b) and lq.get("open_from_downstream", False):
        return "open_downstream"
    return "fail"


def liquidity_plan(topo, lq):
    return {f"{a}-{b}": liquidity_action(topo, a, b, lq) for a, b in topo.hop_pairs()}


class Builder:
    def __init__(self, cfg, topo, records_dir, dry_run=False):
        self.cfg = cfg
        self.topo = topo
        self.records_dir = records_dir
        self.dry_run = dry_run
        self.rpcs = {n: topo.rpc(n) for n in topo.order}
        self.ckb = topo.ckb()
        self.pubkeys = {}
        self.wallets = {}
        self.liquidity_log = []
        os.makedirs(records_dir, exist_ok=True)

    # ---------- pre-checks (WTL-09) ----------
    def precheck_nodes(self):
        problems = []
        try:
            tip = i(self.ckb.get_tip_block_number())
        except Exception as e:  # noqa
            problems.append(f"ckb rpc unreachable: {e}")
            tip = None
        for n in self.topo.order:
            node = self.topo.by_name[n]
            rpc = self.rpcs[n]
            if rpc is None:
                if node.get("controlled"):
                    problems.append(f"{n}: controlled node without rpc_url")
                self.pubkeys[n] = node["pubkey"]
                continue
            try:
                info = rpc.node_info()
                self.pubkeys[n] = info.get("pubkey") or info.get("node_id")
                if node.get("pubkey") and node["pubkey"] != self.pubkeys[n]:
                    problems.append(f"{n}: pubkey mismatch")
                if node.get("controlled"):
                    w = wallet_shannons(self.ckb, info)
                    self.wallets[n] = w
                    wmin = self.cfg.get("wallet", {}).get("min_ckb", 0)
                    if w is not None and w < wmin * CKB_SHANNONS:
                        problems.append(f"{n}: wallet {w / CKB_SHANNONS:.0f} CKB < wallet.min_ckb {wmin}")
            except Exception as e:  # noqa
                problems.append(f"{n}: rpc unreachable: {e}")
        if problems:
            raise PrecheckError("; ".join(problems))
        return tip

    def channels_between(self, a, b, include_closed=False):
        rpc = self.rpcs[a]
        if rpc is None:  # public upstream: look from downstream side
            chans = self.rpcs[b].list_channels({"pubkey": self.pubkeys[a], "include_closed": include_closed})["channels"]
            return [dict(c, _view=b) for c in chans]
        chans = rpc.list_channels({"pubkey": self.pubkeys[b], "include_closed": include_closed})["channels"]
        return [dict(c, _view=a) for c in chans]

    def ready_channels(self, a, b):
        out = []
        for c in self.channels_between(a, b):
            name, _ = state_name(c["state"])
            if name == "ChannelReady" and c.get("channel_outpoint"):
                out.append(c)
        return out

    @staticmethod
    def upstream_balance(c):
        # balance usable to pay a->b, seen from the viewing node
        return i(c["local_balance"]) if c["_view_is_a"] else i(c["remote_balance"])

    def ready_with_balance(self, a, b):
        res = []
        for c in self.ready_channels(a, b):
            c["_view_is_a"] = c["_view"] == a
            res.append(c)
        return res

    def open_channel(self, a, b, capacity_ckb, tlc_expiry_delta, from_downstream=False):
        """Open a new a-b channel funded by a (default) or by b (from_downstream: balance ends up
        on b's side, i.e. return-direction liquidity only)."""
        opener, peer = (b, a) if from_downstream else (a, b)
        if not self.topo.controlled(opener):
            # funding from b would put the balance on the wrong side (we need a->b liquidity)
            raise PrecheckError(f"need a new channel {a}-{b} but the opening end {opener} is a public node")
        before = {c["channel_id"] for c in self.channels_between(a, b)}
        rpc = self.rpcs[opener]
        try:
            rpc.connect_peer({"pubkey": self.pubkeys[peer]})
        except RpcError:
            pass
        params = {"pubkey": self.pubkeys[peer], "funding_amount": h(int(capacity_ckb * CKB_SHANNONS)), "public": True}
        if tlc_expiry_delta:
            params["tlc_expiry_delta"] = h(tlc_expiry_delta)
        LOG.info("open_channel %s->%s %s CKB", opener, peer, capacity_ckb)
        rpc.open_channel(params)
        deadline = time.time() + self.cfg.get("open_channel_timeout_seconds", 900)
        while time.time() < deadline:
            for c in self.ready_channels(a, b):
                if c["channel_id"] not in before:
                    if tlc_expiry_delta and self.rpcs.get(peer):
                        self.rpcs[peer].update_channel({"channel_id": c["channel_id"], "tlc_expiry_delta": h(tlc_expiry_delta)})
                    return c
            time.sleep(3)
        raise PrecheckError(f"open_channel {a}-{b} not ready in time")

    def wait_graph(self, outpoints, timeout):
        """Wait until the payer's network graph knows every channel we will route over
        (with channel updates for both directions), so build_router can use it."""
        payer = self.rpcs[self.topo.order[0]]
        want = set(outpoints)
        deadline = time.time() + timeout
        while True:
            seen, after = set(), None
            while True:
                p = {"limit": h(500)}
                if after:
                    p["after"] = after
                r = payer.graph_channels(p)
                for c in r["channels"]:
                    if c.get("update_info_of_node1") and c.get("update_info_of_node2"):
                        seen.add(c["channel_outpoint"])
                if len(r["channels"]) < 500:
                    break
                after = r["last_cursor"]
            missing = want - seen
            if not missing:
                return
            if time.time() > deadline:
                raise PrecheckError(f"payer graph still misses {len(missing)} route channels")
            time.sleep(3)

    def graph_outpoints(self, rpc):
        seen, after = set(), None
        while True:
            p = {"limit": h(500)}
            if after:
                p["after"] = after
            r = rpc.graph_channels(p)
            seen.update(c["channel_outpoint"] for c in r["channels"])
            if len(r["channels"]) < 500:
                return seen
            after = r["last_cursor"]

    def wait_closed_out_of_graph(self, outpoints, timeout):
        """Post-scenario rebalance raced the victim force closes: the sender's graph still listed the
        closing channels, so routes could pick them. Wait until they are pruned (funding spent)."""
        sender = self.rpcs[self.topo.order[-1]]
        t0 = time.time()
        while True:
            left = set(outpoints) & self.graph_outpoints(sender)
            if not left or time.time() - t0 > timeout:
                return {"waited_s": round(time.time() - t0, 1), "still_in_graph": len(left)}
            time.sleep(5)

    def wait_funding_committed(self, txs, timeout, confirmations):
        ckb = self.topo.ckb()
        deadline = time.time() + timeout
        pending = set(txs)
        while pending:
            tip = i(ckb.get_tip_block_number())
            for tx in list(pending):
                r = ckb.get_transaction(tx)
                st = (r or {}).get("tx_status", {})
                if st.get("status") == "committed" and tip - i(st["block_number"]) >= confirmations:
                    pending.discard(tx)
            if not pending:
                return
            if time.time() > deadline:
                raise PrecheckError(f"funding tx not committed: {sorted(pending)}")
            time.sleep(2)

    # ---------- liquidity ----------
    def best_upstream(self, a, b):
        chans = self.ready_with_balance(a, b)
        return max((self.upstream_balance(c) for c in chans), default=0), chans

    def hop_ratios(self):
        out = {}
        for a, b in self.topo.hop_pairs():
            bal, chans = self.best_upstream(a, b)
            cap = max((self.upstream_balance(c) + (i(c["remote_balance"]) if c["_view_is_a"] else i(c["local_balance"])) for c in chans), default=0)
            out[(a, b)] = (bal, cap, bal / cap if cap else 0.0)
        return out

    def rebalance(self, stage):
        """Pull liquidity back along the route: keysend receiver(N5) -> payer(N1), sequentially."""
        rb = self.cfg.get("rebalance", {})
        if not rb.get("enabled") or self.dry_run:
            return []
        payer, receiver = self.topo.order[0], self.topo.order[-1]
        if not self.rpcs[receiver]:
            return []
        done = []
        for _ in range(int(rb.get("max_payments", 5))):
            ratios = self.hop_ratios()
            low = {f"{a}-{b}": round(r, 3) for (a, b), (_, _, r) in ratios.items() if r < rb.get("target_ratio", 0.3)}
            if not low:
                break
            amt = int(rb.get("amount_ckb", 100) * CKB_SHANNONS)
            # the return path needs receiver-side balance on every hop; after victims on the last hop
            # close, only channels funded by the upstream remain -> receiver has nothing to send
            short = {}
            for a, b in self.topo.hop_pairs():
                back = max((i(c["remote_balance"]) if c["_view"] == a else i(c["local_balance"])
                            for c in self.ready_channels(a, b)), default=0)
                if back < amt:
                    short[f"{a}-{b}"] = back
            if short:
                LOG.warning("rebalance (%s): skipped, no return liquidity (downstream-side balance < %s) on %s", stage, amt, short)
                done.append({"stage": stage, "low": low, "amount": amt, "status": "skipped_no_return_liquidity", "short_hops": short,
                             "min_ratio_before": min(low.values()), "min_ratio_after": min(low.values())})
                self.liquidity_log.append(done[-1])
                break
            LOG.info("rebalance (%s): low hops %s -> keysend %s CKB %s->%s", stage, low, amt / CKB_SHANNONS, receiver, payer)
            try:
                r = self.rpcs[receiver].send_payment({"target_pubkey": self.pubkeys[payer], "amount": h(amt), "keysend": True})
                st = self._wait_payment(self.rpcs[receiver], r["payment_hash"], rb.get("payment_timeout_seconds", 120))
            except RpcError as e:
                st = f"error: {str(e)[:120]}"
            after = min(r for (_, _, r) in self.hop_ratios().values())
            done.append({"stage": stage, "low": low, "amount": amt, "status": st,
                         "min_ratio_before": min(low.values()), "min_ratio_after": round(after, 4)})
            self.liquidity_log.append(done[-1])
            if st != "Success":
                break
        return done

    def _wait_payment(self, rpc, ph, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = rpc.get_payment({"payment_hash": ph})["status"]
            if st in ("Success", "Failed"):
                return st
            time.sleep(2)
        return "Timeout"

    def ensure_liquidity(self, need):
        """Hops whose best upstream balance is below liquidity.min_upstream_ckb (or below `need`):
        controlled upstream -> open a new channel from it; public upstream -> rely on rebalance, else fail."""
        lq = self.cfg.get("liquidity", {})
        if not lq.get("auto_open", False):
            return
        if self.dry_run:
            LOG.info("liquidity plan (dry-run, applied only to short hops): %s", liquidity_plan(self.topo, lq))
            return
        base_floor = lq.get("min_upstream_ckb", 0)
        by_hop = lq.get("min_upstream_ckb_by_hop", {}) or {}
        cap = lq.get("open_capacity_ckb", self.cfg["force_close"].get("reopen_capacity_ckb", 1000))
        for a, b in self.topo.hop_pairs():
            bal, _ = self.best_upstream(a, b)
            floor = max(int(by_hop.get(f"{a}-{b}", base_floor) * CKB_SHANNONS), need)
            if bal >= floor:
                continue
            act = liquidity_action(self.topo, a, b, lq)
            if act == "fail":
                raise PrecheckError(f"{a}-{b}: upstream balance {bal / CKB_SHANNONS:.1f} CKB < {floor / CKB_SHANNONS:.1f} CKB, "
                                    f"upstream {a} is a public node (cannot open), rebalance did not recover it")
            down = act == "open_downstream"
            opener = b if down else a
            LOG.info("liquidity: %s-%s upstream %s < %s -> open %s CKB from %s%s", a, b, bal, floor, cap, opener,
                     " (downstream: return-direction liquidity only; forward relies on rebalance)" if down else "")
            c = self.open_channel(a, b, cap, self.cfg.get("tlc_expiry_delta_ms"), from_downstream=down)
            self.liquidity_log.append({"stage": "auto_open_downstream" if down else "auto_open", "hop": f"{a}-{b}",
                                       "opener": opener, "upstream_before": bal, "channel_id": c["channel_id"]})

    # ---------- selection ----------
    def choose_close_set(self, slot):
        fc = self.cfg["force_close"]
        sets = fc["close_sets"]
        strategy = fc.get("strategy", "round_robin")
        if strategy == "fixed":
            idx = fc.get("fixed_index", 0)
        elif strategy == "random":
            idx = random.randrange(len(sets))
        else:
            day = dt.date.today().toordinal()
            idx = (day * self.cfg.get("scenarios_per_day", 1) + slot) % len(sets)
        return idx, [parse_channel_ref(r) for r in sets[idx]]

    # ---------- scenario ----------
    def build_one(self, slot):
        cfg = self.cfg
        sc = cfg["scenario"]
        fc = cfg["force_close"]
        set_idx, close_set = self.choose_close_set(slot)
        spare = int(fc.get("spare_parallel", 1))
        tlc_delta = cfg.get("tlc_expiry_delta_ms")
        amounts = {t: int(sc[t]["amount_ckb"] * CKB_SHANNONS) for t in ("normal_payments", "preimage_tlcs", "timeout_tlcs")}
        counts = {t: sc[t]["count"] for t in amounts}
        total = sum(amounts[t] * counts[t] for t in amounts)
        need = int(total * 1.01) + CKB_SHANNONS  # fees margin
        victims_needed = {(a, b): par for a, b, par in close_set}
        self.rebalance("pre")
        self.ensure_liquidity(need)

        # channel inventory + capacity check (WTL-11 capacity part / WTL-09)
        inventory = {}
        needed, available = {}, {}
        for a, b in self.topo.hop_pairs():
            chans = self.ready_with_balance(a, b)
            if (a, b) in victims_needed:
                want = victims_needed[(a, b)] + spare
                missing = want - len(chans)
                for _ in range(max(0, missing)):
                    if self.dry_run:
                        break
                    self.open_channel(a, b, fc.get("reopen_capacity_ckb", 1000), tlc_delta)
                chans = self.ready_with_balance(a, b)
                chans.sort(key=self.upstream_balance, reverse=True)
                victims = chans[: victims_needed[(a, b)]]
                per_victim = -(-need // max(1, len(victims)))
                for k, v in enumerate(victims):
                    needed[(a, b, k)] = per_victim
                    available[(a, b, k)] = self.upstream_balance(v)
                inventory[(a, b)] = {"victims": victims, "spares": chans[len(victims):]}
                if len(chans) < victims_needed[(a, b)] + spare and not self.dry_run:
                    raise PrecheckError(f"{a}-{b}: need {victims_needed[(a,b)]}+{spare} ready channels, have {len(chans)}")
            else:
                if not chans:
                    raise PrecheckError(f"{a}-{b}: no ChannelReady channel on the route")
                best = max(chans, key=self.upstream_balance)
                needed[(a, b, 0)] = need
                available[(a, b, 0)] = self.upstream_balance(best)
                inventory[(a, b)] = {"victims": [], "spares": [best]}
        errs = capacity_errors(cfg, needed, available)
        if errs:
            raise ConfigError("capacity: " + "; ".join(errs))
        if self.dry_run:
            return {"dry_run": True, "close_set_index": set_idx, "needed_shannons": need, "inventory": {f"{a}-{b}": len(v["victims"]) + len(v["spares"]) for (a, b), v in inventory.items()}}

        route_ops = [c["channel_outpoint"] for inv in inventory.values() for c in (inv["victims"] or inv["spares"][:1])]
        self.wait_graph(route_ops, cfg.get("gossip_timeout_seconds", 300))

        scen_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{slot}"
        payer, receiver = self.topo.order[0], self.topo.order[-1]
        prpc, rrpc = self.rpcs[payer], self.rpcs[receiver]
        final_delta = cfg["scenario"].get("final_tlc_expiry_delta_ms")
        tlcs = []
        victim_cycle = {pair: 0 for pair in victims_needed}

        def route_hops():
            hops = []
            for a, b in self.topo.hop_pairs():
                inv = inventory[(a, b)]
                if inv["victims"]:
                    k = victim_cycle[(a, b)] % len(inv["victims"])
                    victim_cycle[(a, b)] += 1
                    ch = inv["victims"][k]
                else:
                    ch = inv["spares"][0]
                hops.append({"pubkey": self.pubkeys[b], "channel_outpoint": ch["channel_outpoint"]})
            return hops

        def pay(kind, amount, hold):
            preimage = "0x" + secrets.token_hex(32)
            payment_hash = ckb_hash(preimage)
            inv = {"amount": h(amount), "currency": self.topo.currency, "description": f"wtl {scen_id} {kind}", "expiry": h(3600 * 24 * 3)}
            if final_delta:
                inv["final_expiry_delta"] = h(final_delta)
            if hold:
                inv["payment_hash"] = payment_hash
            else:
                inv["payment_preimage"] = preimage
            invoice = rrpc.new_invoice(inv)["invoice_address"]
            hops = route_hops()
            router = prpc.build_router({"amount": h(amount), "hops_info": hops, "final_tlc_expiry_delta": h(final_delta) if final_delta else None})
            prpc.send_payment_with_router({"router": router["router_hops"], "invoice": invoice})
            tlcs.append({"payment_hash": payment_hash, "preimage": preimage, "kind": kind, "amount": amount,
                         "route": [x["channel_outpoint"] for x in hops], "expected": {"normal": "offchain", "preimage": "preimage", "timeout": "timeout"}[kind]})

        # send_mode: "sequential" (default) waits for each payment to settle/arrive
        # before sending the next; "concurrent" fires all first (kept for repro of
        # fnn "revocation nonce ledger has been unbalanced").
        sequential = cfg.get("send_mode", "sequential") != "concurrent"
        pay_timeout = cfg.get("payment_timeout_seconds", 300)

        def wait_tlcs(group):
            deadline = time.time() + pay_timeout
            while True:
                ok = True
                for t in group:
                    if t["kind"] == "normal":
                        st = prpc.get_payment({"payment_hash": t["payment_hash"]})["status"]
                        ok &= st == "Success"
                        if st == "Failed":
                            raise BuildError(f"normal payment {t['payment_hash']} failed", tlcs)
                    else:
                        st = rrpc.get_invoice({"payment_hash": t["payment_hash"]})["status"]
                        ok &= st == "Received"
                    t["last_status"] = st
                if ok:
                    return
                if time.time() > deadline:
                    raise BuildError("payments did not reach Success/Received in time: " + ", ".join(f"{t['kind']}={t.get('last_status')}" for t in group), tlcs)
                time.sleep(1)

        plan = [("normal", amounts["normal_payments"], False)] * counts["normal_payments"] + \
               [("preimage", amounts["preimage_tlcs"], True)] * counts["preimage_tlcs"] + \
               [("timeout", amounts["timeout_tlcs"], True)] * counts["timeout_tlcs"]
        for kind, amt, hold in plan:
            pay(kind, amt, hold)
            if sequential:
                wait_tlcs([tlcs[-1]])
        wait_tlcs(tlcs)

        # snapshot channels along the route (+ pending tlcs/expiries)
        channels = []
        closing = []
        victim_ops = set()
        for (a, b), inv in inventory.items():
            for ch in inv["victims"]:
                victim_ops.add(ch["channel_outpoint"])
        for a, b in self.topo.hop_pairs():
            for c in self.channels_between(a, b):
                name, _ = state_name(c["state"])
                if name != "ChannelReady":
                    continue
                is_victim = c["channel_outpoint"] in victim_ops
                pend = [{"payment_hash": p["payment_hash"], "amount": i(p["amount"]), "expiry": i(p["expiry"]), "status": p["status"]} for p in c["pending_tlcs"]]
                tx, idx = outpoint_tx(c["channel_outpoint"])
                channels.append({
                    "nodes": [a, b], "channel_id": c["channel_id"], "outpoint": c["channel_outpoint"],
                    "funding_tx": tx, "funding_index": idx, "view": c["_view"],
                    "public_node": not (self.topo.controlled(a) and self.topo.controlled(b)),
                    "force_close": is_victim, "pending_tlcs": pend,
                    "local_balance": i(c["local_balance"]), "remote_balance": i(c["remote_balance"]),
                })
                if is_victim:
                    closing.append((a, c))
        for t in tlcs:
            exps = [p["expiry"] for ch in channels for p in ch["pending_tlcs"] if p["payment_hash"] == t["payment_hash"]]
            t["expiry_ms"] = max(exps) if exps else None
            t["min_expiry_ms"] = min(exps) if exps else None

        # force_close.skip (concurrency repro): build + send exactly like a real scenario, close nothing
        if cfg["force_close"].get("skip"):
            for ch in channels:
                ch["force_close"] = False
            closing = []
        # never force close a channel whose funding tx is not yet committed on CKB
        # (fnn would broadcast a commitment tx that spends an unknown outpoint and give up)
        self.wait_funding_committed([c["funding_tx"] for c in channels if c["force_close"]],
                                    cfg.get("funding_confirm_timeout_seconds", 600),
                                    cfg.get("funding_confirmations", 3))

        # force close
        closes = []
        for a, c in closing:
            by = a if self.rpcs[a] else c["_view"]
            LOG.info("force close %s (%s)", c["channel_id"], by)
            self.rpcs[by].shutdown_channel({"channel_id": c["channel_id"], "force": True})
            closes.append({"channel_id": c["channel_id"], "by": by, "at_ms": now_ms()})
        rec = {
            "version": RECORD_VERSION,
            "id": scen_id,
            "status": "built",
            "created_at_ms": now_ms(),
            "deadline_ms": now_ms() + int(deadline_hours(cfg, tlcs) * 3600 * 1000),
            "close_set_index": set_idx,
            "close_set": [[a, b, p] for a, b, p in close_set],
            "spare_parallel": spare,
            "topology": [{"name": n, "pubkey": self.pubkeys[n], "controlled": self.topo.controlled(n)} for n in self.topo.order],
            "channels": channels,
            "force_closes": closes,
            "tlcs": tlcs,
            "counts": counts,
            "post_check_amount": int(cfg.get("post_check_amount_ckb", 1) * CKB_SHANNONS),
            "wallets_shannons": self.wallets,
            "liquidity": list(self.liquidity_log),
        }
        path = os.path.join(self.records_dir, f"{scen_id}.json")
        write_json_atomic(path, rec)
        LOG.info("scenario record written: %s", path)
        # settle the preimage-type hold invoices AFTER the close
        time.sleep(cfg.get("settle_delay_seconds", 3))
        for t in tlcs:
            if t["kind"] == "preimage":
                rrpc.settle_invoice({"payment_hash": t["payment_hash"], "payment_preimage": t["preimage"]})
                t["settled_at_ms"] = now_ms()
        if cfg["force_close"].get("skip") and cfg["force_close"].get("cancel_holds", True):
            for t in tlcs:  # release hold TLCs so the next round starts clean
                if t["kind"] == "timeout":
                    try:
                        rrpc.cancel_invoice({"payment_hash": t["payment_hash"]})
                    except Exception as e:  # noqa
                        LOG.warning("cancel_invoice %s: %s", t["payment_hash"], e)
        if cfg.get("rebalance", {}).get("after_scenario", True):
            time.sleep(cfg.get("rebalance", {}).get("post_delay_seconds", 10))  # let preimage settles propagate
            closed = [c["outpoint"] for c in channels if c["force_close"]]
            if closed:
                w = self.wait_closed_out_of_graph(closed, cfg.get("rebalance", {}).get("post_wait_close_seconds", 600))
                LOG.info("post rebalance: victim channels out of sender graph: %s", w)
                self.liquidity_log.append(dict(stage="post_wait_close", **w))
            try:
                self.rebalance("post")
            except Exception as e:  # noqa: best effort, next run's "pre" rebalance retries
                LOG.warning("post-scenario rebalance failed: %s", e)
            rec["liquidity"] = list(self.liquidity_log)
        write_json_atomic(path, rec)  # record already exists; refresh with settle times
        return rec


def write_failure(records_dir, reason, stage, tlcs=None):
    os.makedirs(records_dir, exist_ok=True)
    sid = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-failed"
    rec = {"version": RECORD_VERSION, "id": sid, "status": "build_failed", "stage": stage, "reason": reason,
           "created_at_ms": now_ms(), "deadline_ms": now_ms(), "tlcs": tlcs or [], "channels": [], "force_closes": []}
    write_json_atomic(os.path.join(records_dir, f"{sid}.json"), rec)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="watchtower long-run scenario builder")
    ap.add_argument("--config", default="config/watchtower_longrun.yaml")
    ap.add_argument("--topology", default=os.environ.get("WTL_TOPOLOGY", "config/watchtower_longrun_topology.yaml"))
    ap.add_argument("--records-dir", default=os.environ.get("WTL_RECORDS_DIR", "/var/lib/wtl/records"))
    ap.add_argument("--dry-run", action="store_true", default=os.environ.get("WTL_DRY_RUN", "") in ("1", "true"))
    ap.add_argument("--scenarios", type=int, default=int(os.environ["WTL_SCENARIOS"]) if os.environ.get("WTL_SCENARIOS") else None, help="override scenarios_per_day for this run")
    for k in ("normal_count", "preimage_count", "timeout_count", "amount_ckb", "close_set"):
        ap.add_argument("--" + k.replace("_", "-"), dest=k, default=os.environ.get("WTL_" + k.upper()))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    overrides = {k: getattr(a, k) for k in ("normal_count", "preimage_count", "timeout_count", "amount_ckb", "close_set")}
    if a.scenarios:
        overrides["scenarios_per_day"] = a.scenarios
    topo = Topology.load(a.topology)
    try:
        cfg = load_config(a.config, overrides)
        validate(cfg, topo)
    except ConfigError as e:
        LOG.error("config invalid (WTL-11): %s", e)
        if not a.dry_run:
            write_failure(a.records_dir, str(e), "config")
        return 3
    b = Builder(cfg, topo, a.records_dir, dry_run=a.dry_run)
    try:
        b.precheck_nodes()
    except PrecheckError as e:
        LOG.error("pre-check failed (WTL-09): %s", e)
        if not a.dry_run:
            write_failure(a.records_dir, str(e), "precheck")
        return 2
    results = []
    for slot in range(cfg.get("scenarios_per_day", 1)):
        try:
            results.append(b.build_one(slot))
        except Exception as e:  # noqa: any error before the record is written
            label = "WTL-09" if isinstance(e, PrecheckError) else "build"
            LOG.exception("scenario %d aborted (%s): %s", slot, label, e)
            if not a.dry_run:
                write_failure(a.records_dir, str(e), "precheck" if isinstance(e, PrecheckError) else "build", getattr(e, "tlcs", None))
            return 2
    print(json.dumps([{"id": r.get("id"), "dry_run": r.get("dry_run", False), **({k: r[k] for k in ("needed_shannons", "inventory")} if r.get("dry_run") else {})} for r in results], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
