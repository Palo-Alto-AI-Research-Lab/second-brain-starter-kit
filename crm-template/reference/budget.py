# -*- coding: utf-8 -*-
r"""budget.py — per-account daily send cap + audit log.

Reference extract, trimmed to the contract `safe_send.py` depends on. The live
version additionally shards the log per machine (so several machines can append
without ever writing the same file) — that invariant is documented in
https://github.com/Palo-Alto-AI-Research-Lab/claude-consensus (docs/BUS.md §3),
and is deliberately left out here to keep this file readable.

Why a budget module at all, separate from the sender:
  the number "how many messages may this account send today" is the single most
  important safety dial in an outbound agent, and a human must be able to find it,
  read it, and change it without understanding async code. So it lives alone, it
  is plain SQLite, and it is testable with no network in the room.

  python budget.py status
  python budget.py selftest
"""
import os
import sys
import sqlite3
import datetime

DB_PATH = os.environ.get("CRM_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "crm.db"))
DEFAULT_DAILY_LIMIT = int(os.environ.get("DRIP_DAILY_LIMIT", "5"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS send_budget (
    account     TEXT NOT NULL,
    day         TEXT NOT NULL,
    sent        INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL,
    PRIMARY KEY (account, day)
);
CREATE TABLE IF NOT EXISTS send_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account    TEXT NOT NULL,
    day        TEXT NOT NULL,
    ts         TEXT NOT NULL,
    lead_slug  TEXT,
    kind       TEXT,
    preview    TEXT          -- first ~120 chars, so a human can audit what went out
);
"""


def _today():
    return datetime.date.today().isoformat()


def _norm(acc):
    return (acc or "").strip().upper()


def _conn(db=None):
    c = sqlite3.connect(db or DB_PATH)
    c.executescript(SCHEMA)
    return c


def get_limit(acc, db=None):
    acc, day = _norm(acc), _today()
    with _conn(db) as c:
        row = c.execute("SELECT daily_limit FROM send_budget WHERE account=? AND day=?",
                        (acc, day)).fetchone()
    return int(row[0]) if row else DEFAULT_DAILY_LIMIT


def sent_today(acc, db=None):
    acc, day = _norm(acc), _today()
    with _conn(db) as c:
        row = c.execute("SELECT COUNT(*) FROM send_log WHERE account=? AND day=?",
                        (acc, day)).fetchone()
    return int(row[0] or 0)


def remaining(acc, db=None):
    return max(0, get_limit(acc, db) - sent_today(acc, db))


def can_send(acc, db=None):
    return remaining(acc, db) > 0


def set_limit(acc, n, db=None):
    acc, day = _norm(acc), _today()
    with _conn(db) as c:
        c.execute("INSERT INTO send_budget(account, day, sent, daily_limit) "
                  "VALUES(?,?,0,?) ON CONFLICT(account, day) "
                  "DO UPDATE SET daily_limit=excluded.daily_limit", (acc, day, int(n)))
    return int(n)


def record_send(acc, lead_slug=None, kind=None, preview=None, db=None):
    """Append to the audit log and return how many went out today. Called ONLY by
    the sender, and only after the platform actually accepted the message."""
    acc, day = _norm(acc), _today()
    with _conn(db) as c:
        c.execute("INSERT INTO send_log(account, day, ts, lead_slug, kind, preview) "
                  "VALUES(?,?,?,?,?,?)",
                  (acc, day, datetime.datetime.now().isoformat(timespec="seconds"),
                   lead_slug, kind, (preview or "")[:120]))
        c.execute("INSERT INTO send_budget(account, day, sent, daily_limit) "
                  "VALUES(?,?,1,?) ON CONFLICT(account, day) "
                  "DO UPDATE SET sent=send_budget.sent+1",
                  (acc, day, DEFAULT_DAILY_LIMIT))
    return sent_today(acc, db)


def status(db=None):
    with _conn(db) as c:
        rows = c.execute("SELECT account, COUNT(*) FROM send_log WHERE day=? GROUP BY account",
                         (_today(),)).fetchall()
    return {a: {"sent": n, "limit": get_limit(a, db), "left": remaining(a, db)}
            for a, n in rows}


def _selftest():
    import tempfile
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    acc = "ACCOUNT_A"
    set_limit(acc, 3, db)
    assert can_send(acc, db) and remaining(acc, db) == 3
    for i in range(3):
        record_send(acc, "lead-%d" % i, "drip", "hello there", db)
    assert sent_today(acc, db) == 3, sent_today(acc, db)
    assert not can_send(acc, db), "cap must block the 4th send"
    assert remaining(acc, db) == 0
    # a second account is unaffected — the cap is per account, not global
    assert can_send("ACCOUNT_B", db)
    print("SELFTEST OK — cap blocks at the limit, per account, and the log has "
          "%d auditable rows." % sent_today(acc, db))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "selftest":
        _selftest()
    else:
        print(status())
