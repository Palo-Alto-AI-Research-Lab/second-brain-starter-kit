#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# PUBLISHED SAMPLE - the paths and identifiers below are placeholders, not live
# values. This file runs a real system on the author's machines. Before it runs
# on yours, replace:
#   %VAULT%        your Obsidian vault root
#   %IMPORTS%      wherever you keep these engines' data
#   %USERPROFILE%  your home directory
#   %WORKDIR%      your working folder
# Chat ids, handles, phone numbers and e-mail addresses were swapped for fakes of
# the same shape, so the code still reads and parses - but it talks to nothing
# until you point it at your own accounts.
# Passport (what it does / what breaks / how to fix): see engines/README.md.
# ---------------------------------------------------------------------------
# fb_guard.py -- deterministic RATE-LIMIT / SPACING guard for acting on Anton's LIVE Facebook account.
#
# WHY (Anton 2026-06-28, after Deep-Research #32): Facebook bans a personal profile not for "a bot wrote
# this" but for TEMPO and VOLUME -- too many actions, too fast. Deep Research gave concrete safe caps:
#   * posts   <= ~8/day
#   * replies <= ~40/day, spaced ~5 min apart, never burst (>2-3 in a row)
#   * DMs     <= single digits/day (5-10 NEW chats triggers a 24-72h message-request block)
# Draft-first alone does NOT save the account (FB judges by timing, not who clicked Send). What actually
# protects = a hard counter that REFUSES the action once the daily cap or the min-spacing is exceeded.
# This script IS that counter -- the root fix. The /fb-post and /fb-reply (and later /fb-dm) skills MUST
# call `check` BEFORE touching the browser, and `record` AFTER a successful action.
#
# THIN/deterministic (0 tokens). It does NO browser I/O -- the LLM drives Claude-in-Chrome. This only
# keeps the ledger (SQLite) and answers OK / BLOCKED with the reason.
#
# USAGE
#   python fb_guard.py check  <post|reply|dm>   -> "OK ..." (exit 0)  |  "BLOCKED ...: <reason>" (exit 3)
#   python fb_guard.py record <post|reply|dm>   -> logs one action now; prints new today-count
#   python fb_guard.py status                   -> today's counts + whether each type is allowed right now
#   python fb_guard.py gc                        -> drop ledger rows older than 30 days
#
# Limits live in DEFAULTS below; override per-machine with ~/.claude/fb_guard.json (optional), e.g.
#   { "post": {"per_day": 8,  "spacing_s": 0},
#     "reply":{"per_day": 40, "spacing_s": 300},
#     "dm":   {"per_day": 6,  "spacing_s": 1800} }
import os, sys, json, time, sqlite3
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = os.path.expanduser("~")
DB = os.environ.get("FB_GUARD_DB", os.path.join(HOME, ".claude", "fb_guard.db"))
CONFIG_PATH = os.environ.get("FB_GUARD_CONFIG", os.path.join(HOME, ".claude", "fb_guard.json"))

# Safe caps straight from Deep-Research #32 (conservative end of the ranges).
DEFAULTS = {
    "post":  {"per_day": 8,  "spacing_s": 0},      # vetted content, low volume
    "reply": {"per_day": 40, "spacing_s": 300},    # <=40/day, >=5 min apart (kills bursts)
    "dm":    {"per_day": 6,  "spacing_s": 1800},   # single digits/day, >=30 min apart
}
ACTIONS = tuple(DEFAULTS.keys())


def _limits():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if k in cfg and isinstance(v, dict):
                cfg[k] = {**cfg[k], **v}
    except FileNotFoundError:
        pass
    except Exception as e:
        sys.stderr.write(f"[fb_guard] bad config {CONFIG_PATH}: {e}\n")
    return cfg


def _now():
    return int(os.environ.get("FB_GUARD_NOW", int(time.time())))


def _today():
    # Local calendar day -> FB limits reset by your day, not UTC.
    return datetime.fromtimestamp(_now()).strftime("%Y-%m-%d")


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS actions(
        ts INTEGER, day TEXT, action TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_day ON actions(day, action)")
    return c


def _today_count(c, action):
    return c.execute("SELECT COUNT(*) FROM actions WHERE day=? AND action=?",
                     (_today(), action)).fetchone()[0]


def _last_ts(c, action):
    r = c.execute("SELECT MAX(ts) FROM actions WHERE action=?", (action,)).fetchone()
    return r[0] if r and r[0] else None


def _evaluate(c, action):
    """Return (ok: bool, reason: str, count: int, lim: dict)."""
    lim = _limits()[action]
    count = _today_count(c, action)
    if count >= lim["per_day"]:
        return False, f"daily cap reached ({count}/{lim['per_day']}) -- wait until tomorrow", count, lim
    last = _last_ts(c, action)
    if last is not None and lim["spacing_s"] > 0:
        gap = _now() - last
        if gap < lim["spacing_s"]:
            wait = lim["spacing_s"] - gap
            return (False,
                    f"too soon ({gap}s since last {action}, need {lim['spacing_s']}s) -- wait {wait}s",
                    count, lim)
    return True, "ok", count, lim


def cmd_check(action):
    c = _conn()
    try:
        ok, reason, count, lim = _evaluate(c, action)
    finally:
        c.close()
    if ok:
        print(f"OK {action} (today {count}/{lim['per_day']})")
        sys.exit(0)
    print(f"BLOCKED {action}: {reason}")
    sys.exit(3)


def cmd_record(action):
    c = _conn()
    try:
        # Re-check at record time so a race can't push us over the cap.
        ok, reason, count, lim = _evaluate(c, action)
        if not ok:
            print(f"BLOCKED {action}: {reason} -- NOT recorded")
            sys.exit(3)
        c.execute("INSERT INTO actions VALUES (?,?,?)", (_now(), _today(), action))
        c.commit()
        count = _today_count(c, action)
    finally:
        c.close()
    print(f"recorded {action} (today {count}/{lim['per_day']})")


def cmd_status():
    c = _conn()
    try:
        print(f"FB guard status -- {_today()}")
        for a in ACTIONS:
            ok, reason, count, lim = _evaluate(c, a)
            mark = "OK " if ok else "BLOCKED"
            extra = "" if ok else f"  <- {reason}"
            sp = f", spacing {lim['spacing_s']}s" if lim["spacing_s"] else ""
            print(f"  {a:6} {count}/{lim['per_day']}{sp}  [{mark}]{extra}")
    finally:
        c.close()


def cmd_gc():
    c = _conn()
    try:
        cutoff = _now() - 30 * 86400
        n = c.execute("DELETE FROM actions WHERE ts < ?", (cutoff,)).rowcount
        c.commit()
        print("removed", n)
    finally:
        c.close()


USAGE = """fb_guard.py -- rate-limit/spacing guard for Anton's live Facebook account (0 tokens).
  check  <post|reply|dm>   -> OK (exit 0) | BLOCKED ... (exit 3)   [call BEFORE the browser action]
  record <post|reply|dm>   -> log one action now                   [call AFTER a successful action]
  status                   -> today's counts + allowed-right-now per type
  gc                       -> drop rows older than 30 days
Limits: post 8/day; reply 40/day @5min; dm 6/day @30min (override in ~/.claude/fb_guard.json)."""

if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "status"
    arg = a[1] if len(a) > 1 else None
    if cmd in ("check", "record"):
        if arg not in ACTIONS:
            sys.stderr.write(f"[fb_guard] action must be one of {ACTIONS}\n"); sys.exit(2)
        (cmd_check if cmd == "check" else cmd_record)(arg)
    elif cmd == "status":
        cmd_status()
    elif cmd == "gc":
        cmd_gc()
    else:
        print(USAGE)
