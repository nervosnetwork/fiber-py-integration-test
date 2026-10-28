"""Read-only web page: overview, scenario detail (timeline + explorer links), node status.
Only GET handlers, no state-changing endpoints."""
import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from watchtower_longrun.verifier.monitor import CASE_TITLES, CASES

CSS = """body{font-family:system-ui,sans-serif;margin:24px;color:#222}table{border-collapse:collapse;margin:8px 0}
td,th{border:1px solid #ddd;padding:4px 8px;font-size:13px}th{background:#f4f4f4}.PASS{background:#d8f5d8}
.FAIL{background:#f8d0d0}.PENDING{background:#fff4c2}.NA{color:#888}a{color:#0645ad}code{font-size:12px}"""


def ts(ms):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000)) if ms else "-"


def cls(s):
    return "NA" if s == "N/A" else (s or "")


def page(title, body):
    return f"<!doctype html><html><head><meta charset=utf-8><title>{html.escape(title)}</title><style>{CSS}</style></head><body><p><a href='/'>overview</a> · <a href='/nodes'>nodes</a></p><h2>{html.escape(title)}</h2>{body}</body></html>"


def render_overview(store):
    rows = store.scenarios()
    head = "<tr><th>scenario</th><th>status</th><th>created</th><th>deadline</th>" + "".join(f"<th title='{html.escape(CASE_TITLES[c])}'>{c[4:]}</th>" for c in CASES) + "</tr>"
    out = []
    for r in rows:
        cs = store.cases(r["id"])
        cells = "".join(f"<td class='{cls(cs.get(c, {}).get('status'))}'>{html.escape(cs.get(c, {}).get('status', '-'))}</td>" for c in CASES)
        out.append(f"<tr><td><a href='/scenario/{html.escape(r['id'])}'>{html.escape(r['id'])}</a></td><td>{html.escape(r['status'])}</td><td>{ts(r['created_at_ms'])}</td><td>{ts(r['deadline_ms'])}</td>{cells}</tr>")
    return page("Watchtower long-run — scenarios", f"<table>{head}{''.join(out)}</table>")


def render_scenario(store, topo, sid):
    r = store.scenario(sid)
    if not r:
        return None
    rec = r["record"]
    link = lambda t: f"<a href='{html.escape(topo.explorer_tx_url.format(t))}'><code>{t[:18]}…</code></a>" if t else ""  # noqa
    cs = store.cases(sid)
    case_rows = "".join(f"<tr><td>{c}</td><td>{html.escape(CASE_TITLES[c])}</td><td class='{cls(cs.get(c, {}).get('status'))}'>{cs.get(c, {}).get('status', '-')}</td><td>{html.escape(cs.get(c, {}).get('detail') or '')}</td></tr>" for c in CASES)
    tl = "".join(f"<tr><td>{ts(e['at_ms'])}</td><td>{html.escape(e['kind'])}</td><td>{html.escape(e['message'])}</td><td>{link(e['tx_hash'])}</td></tr>" for e in store.events(sid))
    chans = []
    for ch in rec.get("channels", []):
        tr = store.trace(sid, ch["channel_id"]) or {}
        chans.append(f"<tr><td>{'-'.join(ch['nodes'])}</td><td><code>{ch['channel_id'][:14]}…</code></td><td>{'force close' if ch['force_close'] else ('public' if ch['public_node'] else 'kept')}</td><td>{len(ch['pending_tlcs'])}</td><td>{link(ch['funding_tx'])}</td><td>{'complete' if tr.get('complete') else ('live cells: %d' % len(tr.get('live', [])) if tr else '-')}</td></tr>")
    tlcs = "".join(f"<tr><td>{t['kind']}</td><td><code>{t['payment_hash'][:18]}…</code></td><td>{t['amount']}</td><td>{ts(t.get('min_expiry_ms'))}</td></tr>" for t in rec.get("tlcs", []))
    body = (f"<p>status <b>{html.escape(r['status'])}</b> · created {ts(r['created_at_ms'])} · deadline {ts(r['deadline_ms'])} · close set {html.escape(json.dumps(rec.get('close_set')))}</p>"
            f"<h3>Cases</h3><table><tr><th>case</th><th>check</th><th>result</th><th>detail</th></tr>{case_rows}</table>"
            f"<h3>Channels</h3><table><tr><th>hop</th><th>channel</th><th>role</th><th>pending TLCs at close</th><th>funding tx</th><th>trace</th></tr>{''.join(chans)}</table>"
            f"<h3>TLCs</h3><table><tr><th>kind</th><th>hash</th><th>shannons</th><th>earliest expiry</th></tr>{tlcs}</table>"
            f"<h3>Timeline</h3><table><tr><th>time</th><th>event</th><th>message</th><th>tx</th></tr>{tl}</table>")
    return page(f"Scenario {sid}", body)


def render_nodes(store):
    rows = "".join(f"<tr><td>{html.escape(n['name'])}</td><td>{ts(n['at_ms'])}</td><td><code>{html.escape(json.dumps(n['data']))}</code></td></tr>" for n in store.node_status())
    return page("Node status", f"<table><tr><th>node</th><th>checked</th><th>status</th></tr>{rows}</table>")


def serve(store, topo, host, port):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="text/html; charset=utf-8"):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            p = self.path.split("?")[0].rstrip("/") or "/"
            if p == "/":
                return self.send(200, render_overview(store))
            if p == "/nodes":
                return self.send(200, render_nodes(store))
            if p.startswith("/scenario/"):
                b = render_scenario(store, topo, p.split("/", 2)[2])
                return self.send(200, b) if b else self.send(404, "not found", "text/plain")
            if p == "/api/scenarios":
                data = [{"id": r["id"], "status": r["status"], "cases": {c: v["status"] for c, v in store.cases(r["id"]).items()}} for r in store.scenarios()]
                return self.send(200, json.dumps(data), "application/json")
            if p.startswith("/api/scenario/"):
                sid = p.split("/", 3)[3]
                r = store.scenario(sid)
                if not r:
                    return self.send(404, "{}", "application/json")
                return self.send(200, json.dumps({"scenario": r, "cases": store.cases(sid), "events": store.events(sid)}), "application/json")
            if p == "/api/nodes":
                return self.send(200, json.dumps(store.node_status()), "application/json")
            self.send(404, "not found", "text/plain")

    ThreadingHTTPServer((host, port), H).serve_forever()
