# -*- coding: utf-8 -*-
r"""budget.py — per-account daily send cap + audit log, safe under concurrency.

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

RESERVE-THEN-SEND, not check-then-send
--------------------------------------
The obvious design is `if can_send(): send()`. It is wrong twice, and both were
found by an external reviewer rather than by us:

  1. RACE. Two processes ask `can_send()` at the same moment, both see room under
     the cap, both send. With a cap of 1 you get 2 messages out. Any "check, then
     act" against shared state has this hole.
  2. CRASH WINDOW. The platform accepts the message and the process dies before
     the send is recorded. The message is out in the world but the budget never
     learned about it, so a retry sends it again — to a real human.

Both are fixed by the same move: **take the slot BEFORE dispatching**, inside one
`BEGIN IMMEDIATE` transaction, and confirm it afterwards.

  tok = reserve(acc, lead_slug, kind)   # atomic: counts and inserts 'pending'
  if tok is None: ...                   # cap reached — do not send
  <dispatch>
  confirm(tok, preview)                 # 'pending' -> 'sent'

A `pending` row still counts against the cap. So a crash between reserve and
confirm loses one slot for the day and sends nothing twice. That is the correct
way to fail: an outbound agent should under-send on ambiguity, never over-send.
`release(tok)` exists only for the case where dispatch provably did NOT happen
(e.g. the platform rejected the message before delivery).

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
# A reservation older than this was orphaned by a crash mid-dispatch. It is NOT
# auto-released: a human (or a nightly job) decides, because "did it actually go
# out?" is a question only the platform can answer.
STALE_RESERVATION_MIN = int(os.environ.get("DRIP_STALE_MIN", "30"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS send_budget (
    account     TEXT NOT NULL,
    day         TEXT NOT NULL,
    daily_limit INTEGER NOT NULL,
    PRIMARY KEY (account, day)
);
CREATE TABLE IF NOT EXISTS send_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    account   TEXT NOT NULL,
    day       TEXT NOT NULL,
    ts        TEXT NOT NULL,          -- when the slot was RESERVED
    sent_ts   TEXT,                   -- when dispatch was confirmed (NULL = pending)
    state     TEXT NOT NULL,          -- pending | sent | released
    lead_slug TEXT,
    kind      TEXT,                   -- drip / reply / intro / reactivation
    preview   TEXT                    -- first ~120 chars, so a human can audit it
);
CREATE INDEX IF NOT EXISTS ix_sendlog_day ON send_log(account, day, state);
"""


def _today():
    return datetime.date.today().isoformat()


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _norm(acc):
    return (acc or "").strip().upper()


def _conn(db=None):
    # isolation_level=None -> we drive transactions explicitly with BEGIN IMMEDIATE.
    c = sqlite3.connect(db or DB_PATH, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    return c


def get_limit(acc, db=None):
    acc, day = _norm(acc), _today()
    c = _conn(db)
    try:
        row = c.execute("SELECT daily_limit FROM send_budget WHERE account=? AND day=?",
                        (acc, day)).fetchone()
    finally:
        c.close()
    return int(row[0]) if row else DEFAULT_DAILY_LIMIT


def set_limit(acc, n, db=None):
    acc, day = _norm(acc), _today()
    c = _conn(db)
    try:
        c.execute("INSERT INTO send_budget(account, day, daily_limit) VALUES(?,?,?) "
                  "ON CONFLICT(account, day) DO UPDATE SET daily_limit=excluded.daily_limit",
                  (acc, day, int(n)))
    finally:
        c.close()
    return int(n)


def _taken(c, acc, day):
    """Slots consumed today = confirmed sends + outstanding reservations."""
    return int(c.execute(
        "SELECT COUNT(*) FROM send_log WHERE account=? AND day=? AND state IN ('pending','sent')",
        (acc, day)).fetchone()[0] or 0)


def sent_today(acc, db=None):
    """Confirmed dispatches only — what actually reached people."""
    acc, day = _norm(acc), _today()
    c = _conn(db)
    try:
        return int(c.execute("SELECT COUNT(*) FROM send_log WHERE account=? AND day=? "
                             "AND state='sent'", (acc, day)).fetchone()[0] or 0)
    finally:
        c.close()


def taken_today(acc, db=None):
    """Slots consumed — sends plus reservations still in flight. This is the number
    the cap is enforced against."""
    acc, day = _norm(acc), _today()
    c = _conn(db)
    try:
        return _taken(c, acc, day)
    finally:
        c.close()


def remaining(acc, db=None):
    return max(0, get_limit(acc, db) - taken_today(acc, db))


def can_send(acc, db=None):
    """Advisory only — TRUE here does not reserve anything, so two callers can both
    see TRUE. Never gate a real send on this; use reserve()."""
    return remaining(acc, db) > 0


def reserve(acc, lead_slug=None, kind=None, db=None):
    """Atomically take one slot for today. Returns a reservation id, or None if the
    cap is reached. The counting and the insert happen inside ONE write transaction,
    so two concurrent callers cannot both win the last slot."""
    acc, day = _norm(acc), _today()
    c = _conn(db)
    try:
        c.execute("BEGIN IMMEDIATE")          # write lock before we count
        row = c.execute("SELECT daily_limit FROM send_budget WHERE account=? AND day=?",
                        (acc, day)).fetchone()
        limit = int(row[0]) if row else DEFAULT_DAILY_LIMIT
        if _taken(c, acc, day) >= limit:
            c.execute("ROLLBACK")
            return None
        cur = c.execute("INSERT INTO send_log(account, day, ts, sent_ts, state, lead_slug, "
                        "kind, preview) VALUES(?,?,?,NULL,'pending',?,?,NULL)",
                        (acc, day, _now(), lead_slug, kind))
        tok = cur.lastrowid
        c.execute("COMMIT")
        return tok
    finally:
        c.close()


def confirm(tok, preview=None, db=None):
    """Dispatch succeeded: pending -> sent. Idempotent."""
    c = _conn(db)
    try:
        c.execute("UPDATE send_log SET state='sent', sent_ts=?, preview=? "
                  "WHERE id=? AND state='pending'", (_now(), (preview or "")[:120], tok))
    finally:
        c.close()
    return tok


def release(tok, db=None):
    """Dispatch provably did NOT happen — give the slot back. Do NOT call this
    'just in case' after an unclear failure: an unclear failure must keep the slot."""
    c = _conn(db)
    try:
        c.execute("UPDATE send_log SET state='released' WHERE id=? AND state='pending'", (tok,))
    finally:
        c.close()
    return tok


def stale_reservations(db=None):
    """Reservations left hanging by a crash. Surfaced, never auto-cleared: only the
    platform knows whether the message actually went out."""
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(minutes=STALE_RESERVATION_MIN)).isoformat(timespec="seconds")
    c = _conn(db)
    try:
        return [dict(zip(("id", "account", "ts", "lead_slug", "kind"), r)) for r in c.execute(
            "SELECT id, account, ts, lead_slug, kind FROM send_log "
            "WHERE state='pending' AND ts < ? ORDER BY ts", (cutoff,))]
    finally:
        c.close()


def record_send(acc, lead_slug=None, kind=None, preview=None, db=None):
    """Back-compat one-shot: reserve + confirm in one call. Safe against the RACE
    but NOT against the crash window — there is no gap to protect, because there is
    no dispatch in between. Use it only when you are recording something that has
    already happened. Returns confirmed sends today, or -1 if the cap blocked it."""
    tok = reserve(acc, lead_slug, kind, db)
    if tok is None:
        return -1
    confirm(tok, preview, db)
    return sent_today(acc, db)


def status(db=None):
    c = _conn(db)
    try:
        rows = c.execute("SELECT account, state, COUNT(*) FROM send_log WHERE day=? "
                         "GROUP BY account, state", (_today(),)).fetchall()
    finally:
        c.close()
    out = {}
    for a, st, n in rows:
        out.setdefault(a, {})[st] = n
    for a, d in out.items():
        d["limit"] = get_limit(a, db)
        d["left"] = remaining(a, db)
    return out


def _selftest():
    import tempfile
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    acc = "ACCOUNT_A"
    set_limit(acc, 3, db)
    assert remaining(acc, db) == 3

    # 1. normal path: reserve -> confirm
    for i in range(2):
        t = reserve(acc, "lead-%d" % i, "drip", db)
        assert t is not None
        confirm(t, "hello there", db)
    assert sent_today(acc, db) == 2, sent_today(acc, db)

    # 2. THE RACE: two reservations taken before either dispatches. Only one may win
    #    the last slot — under check-then-send both would have proceeded.
    a = reserve(acc, "lead-a", "drip", db)
    b = reserve(acc, "lead-b", "drip", db)
    assert a is not None, "third slot should be available"
    assert b is None, "cap must refuse the 4th reservation even before any confirm"

    # 3. THE CRASH WINDOW: 'a' is never confirmed (process died mid-dispatch).
    #    The slot stays consumed, so nothing is re-sent into the same cap.
    assert remaining(acc, db) == 0, remaining(acc, db)
    assert sent_today(acc, db) == 2, "an unconfirmed reservation is not a send"
    assert taken_today(acc, db) == 3, "but it DOES hold its slot"
    assert record_send(acc, "lead-c", "drip", "x", db) == -1, "cap must block back-compat path"

    # 4. the orphan is visible, not silently swallowed
    import time as _t
    globals()["STALE_RESERVATION_MIN"] = 0
    _t.sleep(1)
    assert any(r["id"] == a for r in stale_reservations(db)), "orphaned reservation must surface"

    # 5. a proven non-dispatch gives the slot back
    release(a, db)
    assert remaining(acc, db) == 1, remaining(acc, db)

    # 6. the cap is per account, not global
    assert reserve("ACCOUNT_B", "x", "drip", db) is not None

    print("SELFTEST OK — reserve-then-send closes the race (4th reservation refused "
          "with zero confirms) and the crash window (orphan keeps its slot, surfaces "
          "in stale_reservations, never double-sends).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "selftest":
        _selftest()
    elif cmd == "stale":
        for r in stale_reservations():
            print(r)
    else:
        print(status())
