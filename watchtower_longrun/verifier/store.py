"""SQLite state for the verifier. All writes are idempotent so a restart
(WTL-10) re-derives state from chain + record without duplicating anything."""
import json
import sqlite3
import threading

from watchtower_longrun.common import now_ms

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios(
  id TEXT PRIMARY KEY, status TEXT, created_at_ms INTEGER, deadline_ms INTEGER,
  finalized_at_ms INTEGER, record TEXT, summary TEXT, restarts_seen INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS case_results(
  scenario_id TEXT, case_id TEXT, status TEXT, detail TEXT, updated_at_ms INTEGER,
  PRIMARY KEY(scenario_id, case_id));
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id TEXT, at_ms INTEGER, kind TEXT,
  message TEXT, tx_hash TEXT, UNIQUE(scenario_id, kind, message, tx_hash));
CREATE TABLE IF NOT EXISTS traces(
  scenario_id TEXT, channel_id TEXT, data TEXT, PRIMARY KEY(scenario_id, channel_id));
CREATE TABLE IF NOT EXISTS alerts_sent(key TEXT PRIMARY KEY, at_ms INTEGER);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS node_status(name TEXT PRIMARY KEY, at_ms INTEGER, data TEXT);
"""

FINAL = ("PASS", "FAIL", "N/A")


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def q(self, sql, *args):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, *args):
        with self.lock:
            cur = self.db.execute(sql, args)
            return cur.rowcount

    # meta
    def get_meta(self, k, default=None):
        r = self.q("SELECT value FROM meta WHERE key=?", k)
        return r[0]["value"] if r else default

    def set_meta(self, k, v):
        self.x("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", k, str(v))

    # scenarios
    def ingest(self, rec):
        status = "open" if rec["status"] == "built" else rec["status"]
        n = self.x("INSERT OR IGNORE INTO scenarios(id,status,created_at_ms,deadline_ms,record) VALUES(?,?,?,?,?)",
                   rec["id"], status, rec["created_at_ms"], rec["deadline_ms"], json.dumps(rec))
        return n == 1

    def scenarios(self, status=None):
        if status:
            rows = self.q("SELECT * FROM scenarios WHERE status=? ORDER BY created_at_ms", status)
        else:
            rows = self.q("SELECT * FROM scenarios ORDER BY created_at_ms DESC")
        for r in rows:
            r["record"] = json.loads(r["record"])
        return rows

    def scenario(self, sid):
        rows = self.q("SELECT * FROM scenarios WHERE id=?", sid)
        if not rows:
            return None
        r = rows[0]
        r["record"] = json.loads(r["record"])
        return r

    def finalize(self, sid, status, summary):
        self.x("UPDATE scenarios SET status=?, finalized_at_ms=?, summary=? WHERE id=?", status, now_ms(), json.dumps(summary), sid)

    def bump_restarts(self):
        self.x("UPDATE scenarios SET restarts_seen=restarts_seen+1 WHERE status='open'")

    # cases
    def set_case(self, sid, case, status, detail=""):
        cur = self.q("SELECT status FROM case_results WHERE scenario_id=? AND case_id=?", sid, case)
        if cur and cur[0]["status"] in ("PASS", "FAIL") and status not in ("PASS", "FAIL"):
            return False  # final results are sticky
        if cur and cur[0]["status"] == "FAIL":
            return False  # latched FAIL (e.g. WTL-06)
        changed = not cur or cur[0]["status"] != status
        self.x("INSERT INTO case_results(scenario_id,case_id,status,detail,updated_at_ms) VALUES(?,?,?,?,?) "
               "ON CONFLICT(scenario_id,case_id) DO UPDATE SET status=excluded.status, detail=excluded.detail, updated_at_ms=excluded.updated_at_ms",
               sid, case, status, detail, now_ms())
        return changed

    def cases(self, sid):
        return {r["case_id"]: r for r in self.q("SELECT * FROM case_results WHERE scenario_id=? ORDER BY case_id", sid)}

    # events / traces / alerts
    def event(self, sid, kind, message, tx_hash=None, at_ms=None):
        self.x("INSERT OR IGNORE INTO events(scenario_id,at_ms,kind,message,tx_hash) VALUES(?,?,?,?,?)",
               sid, at_ms or now_ms(), kind, message, tx_hash or "")

    def events(self, sid):
        return self.q("SELECT * FROM events WHERE scenario_id=? ORDER BY at_ms, id", sid)

    def save_trace(self, sid, cid, data):
        self.x("INSERT INTO traces(scenario_id,channel_id,data) VALUES(?,?,?) ON CONFLICT(scenario_id,channel_id) DO UPDATE SET data=excluded.data",
               sid, cid, json.dumps(data))

    def trace(self, sid, cid):
        r = self.q("SELECT data FROM traces WHERE scenario_id=? AND channel_id=?", sid, cid)
        return json.loads(r[0]["data"]) if r else None

    def claim_alert(self, key):
        """True exactly once per key (dedup across restarts)."""
        return self.x("INSERT OR IGNORE INTO alerts_sent(key,at_ms) VALUES(?,?)", key, now_ms()) == 1

    def set_node_status(self, name, data):
        self.x("INSERT INTO node_status(name,at_ms,data) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET at_ms=excluded.at_ms, data=excluded.data",
               name, now_ms(), json.dumps(data))

    def node_status(self):
        rows = self.q("SELECT * FROM node_status ORDER BY name")
        for r in rows:
            r["data"] = json.loads(r["data"])
        return rows
