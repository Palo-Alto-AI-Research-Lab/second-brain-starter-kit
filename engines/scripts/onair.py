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
"""onair.py -- ON AIR board: advisory work-declaration layer for the fleet (v1).

WHY (Anton 2026-07-05): a session starting LARGE STRUCTURAL work (redo sync / consensus /
skills-canon / content-factory) has no way to tell the OTHER sessions -- on this machine AND on
other machines -- "I have the conn on zone X now". The 15-min per-file lease is too fine; the
session journal is after-the-fact. This is the MIDDLE layer: a coarse, ADVISORY declaration
board, visible to every session, read at session start and before risky edits.

DESIGN = synthesis of DR26-07-05-HUB-07 (Grok + Gemini + ChatGPT), Decision Memo
decision-2026-07-05-onair-work-declaration-board.md. Key rules the code enforces:
  * ADVISORY, never a real lock (Syncthing is eventually-consistent; cannot guarantee single
    writer under partition -- honest coordination only). Precedent: Chubby COARSE advisory locks.
  * ONE FILE PER DECLARATION under _machine-bus/_onair/active/ -> single-writer, 0 sync-conflicts
    (only the holder ever writes its own file). ACTIVE_NOW.md is a generated CACHE, not truth.
  * 3 modes: EXCLUSIVE (do not touch zone+descendants) / COLLAB (talk-first) / FYI (heads-up).
  * DERIVED expiry = renewed_at + ttl_sec (never store a 2nd expires_at that can drift -- ChatGPT).
  * TTL: interactive 12h, headless 24h; heartbeat = min(3h, ttl/4). Multi-day = daily renew of a
    24h claim, not a static 72h claim. Hours-scale only (never minutes) under Syncthing lag.
  * Only the holder renews/closes its own claim. GC (`expire`) archives ONLY past-grace claims and
    NEVER deletes a live claim owned by someone else.
  * Split-brain: overlapping EXCLUSIVE after a partition -> the LATER one loses provisionally;
    final tie-break = fixed machine order (hub first) or human. (Flagged, not auto-resolved.)

AK-47: stdlib only, plain JSON files, everything hand-repairable. No server, no DB, no central
coordination store. Verbs: declare / list / check / heartbeat / renew / close / expire / summary /
zones. TG announce is OFF by default in v1 (set ONAIR_ANNOUNCE=1 to arm) to avoid chat spam until
the mechanics are proven.
"""
import argparse
import difflib
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone

# ---- paths ---------------------------------------------------------------
def _home():
    return os.path.expanduser("~")

def _bus_dir():
    return os.environ.get("MACHINE_BUS_DIR") or r"%VAULT%\_machine-bus"

ONAIR_DIR = os.path.join(_bus_dir(), "_onair")
ACTIVE_DIR = os.path.join(ONAIR_DIR, "active")
ARCHIVE_DIR = os.path.join(ONAIR_DIR, "archive")
SUMMARY_FILE = os.path.join(ONAIR_DIR, "ACTIVE_NOW.md")

# ---- identity ------------------------------------------------------------
MACHINE = (os.environ.get("MACHINE_KEY") or os.environ.get("COMPUTERNAME")
           or socket.gethostname() or "UNKNOWN").strip()
FRIENDLY = {
    "HUB1": "HUB",
    "LAPTOP1": "HP17",
    "NAT1": "NAT1-Nina",
    "MAC1": "MAC1",
    "MacBook-Rita": "MacBook-Rita",
    "ANCHOR1": "ANCHOR1-VPS",
}
# hub-first tie-break order (split-brain deterministic loser election).
# Always-on nodes rank first (hub, then VPS anchor), then Anton's boxes, then peers.
MACHINE_ORDER = ["HUB1", "ANCHOR1", "LAPTOP1", "MAC1", "NAT1",
                 "MacBook-Rita"]

def friendly(m):
    return FRIENDLY.get(m, m)

# ---- curated zone taxonomy (8-15 durable zones from /arch subsystems) -----
# Keep SMALL and path-like. Choose the narrowest zone that matches the work.
ZONES = [
    "sync",             # cross-machine Syncthing / bus transport
    "consensus",        # consensus.py / decision engine
    "canon-skills",     # CLAUDE.md / reglament-* / skills / Bible
    "memory-index",     # MEMORY.md / memory\*.md / index hygiene
    "vault-imports",    # _imports pipelines, brain_embed / RAG index
    "content-factory",  # posts / diary / funnel 05-06-07 / teasers
    "crm-leads",        # leads.db / CRM / outreach engines
    "connectors",       # TG/WhatsApp/Gmail/Calendar MCP + watchdogs
    "dashboards",       # _Dashboards / pulse
    "scheduled-tasks",  # cron / scheduled-tasks / hooks
    "secrets-auth",     # secrets store / auth / tokens (READ-heavy, declare rarely)
    "machine-bus",      # the bus itself / _machine-bus plumbing
    "arch-system",      # System Architect map / system.db
]

# v1.1 (2026-07-11): free-text zones from week 1 ("vault", "consensus-governance") silently
# bypassed the intersection check -- "vault" never matched "vault-imports", so two declarations
# about the same area did not see each other. declare/check now resolve aliases or REFUSE
# with a suggestion instead of WARN-and-accept.
ZONE_ALIASES = {
    "vault": "vault-imports",
    "imports": "vault-imports",
    "rag": "vault-imports",
    "consensus-governance": "consensus",
    "governance": "consensus",
    "canon": "canon-skills",
    "skills": "canon-skills",
    "bible": "canon-skills",
    "memory": "memory-index",
    "content": "content-factory",
    "posts": "content-factory",
    "crm": "crm-leads",
    "leads": "crm-leads",
    "bus": "machine-bus",
}

def resolve_zone(zone, strict=True):
    """Canonical zone or alias-mapped zone. Unknown: strict -> (None, suggestions);
    non-strict (also_touches) -> keep as-is + suggestions for a WARN."""
    z = (zone or "").strip()
    if z in ZONES or any(z.startswith(k + "/") for k in ZONES):
        return z, None
    if z in ZONE_ALIASES:
        return ZONE_ALIASES[z], None
    sugg = difflib.get_close_matches(z, ZONES + list(ZONE_ALIASES), n=3, cutoff=0.5)
    return (None, sugg) if strict else (z, sugg)

# ---- time helpers --------------------------------------------------------
def now_utc():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

GRACE_SEC = 3600  # 1h grace after expiry before a claim is GC-archived

# ---- io ------------------------------------------------------------------
def ensure_dirs():
    for d in (ACTIVE_DIR, ARCHIVE_DIR):
        os.makedirs(d, exist_ok=True)

def _slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (s or "")).strip("-")[:60]

def load_active():
    ensure_dirs()
    out = []
    for p in sorted(glob.glob(os.path.join(ACTIVE_DIR, "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                rec = json.load(fh)
            rec["_path"] = p
            out.append(rec)
        except Exception as e:
            out.append({"_path": p, "_error": str(e), "id": os.path.basename(p)})
    return out

def derived_state(rec):
    """active / expiring / expired -- derived from renewed_at + ttl_sec (never stored)."""
    r = parse_iso(rec.get("renewed_at") or rec.get("created_at", ""))
    ttl = int(rec.get("ttl_sec", 0) or 0)
    if not r or ttl <= 0:
        return "unknown", 0
    age = (now_utc() - r).total_seconds()
    remain = ttl - age
    if remain <= 0:
        return "expired", remain
    if remain <= 0.2 * ttl:
        return "expiring", remain
    return "active", remain

def zones_of(rec):
    z = [rec.get("zone", "")]
    z += list(rec.get("also_touches", []) or [])
    return [x for x in z if x]

def intersects(zone_a, zone_b):
    """equal, or one is a path-prefix parent of the other (path-like zones)."""
    if not zone_a or not zone_b:
        return False
    if zone_a == zone_b:
        return True
    return zone_a.startswith(zone_b + "/") or zone_b.startswith(zone_a + "/")

def rec_intersects(a, b):
    for za in zones_of(a):
        for zb in zones_of(b):
            if intersects(za, zb):
                return True
    return False

# ---- TG announce (optional, off by default in v1) ------------------------
def announce(text):
    if os.environ.get("ONAIR_ANNOUNCE") != "1":
        return False
    bus_send = os.path.join(_home(), ".claude", "scripts", "bus_send.py")
    if not os.path.exists(bus_send):
        return False
    try:
        subprocess.run([sys.executable, bus_send, text], timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

# ---- commands ------------------------------------------------------------
def cmd_declare(a):
    ensure_dirs()
    zone, sugg = resolve_zone(a.zone)
    if zone is None:
        sys.stderr.write("[onair] REFUSED: zone '%s' not in taxonomy%s.\n[onair] Known zones: %s "
                         "(subzones by path, e.g. sync/protocol)\n"
                         % (a.zone.strip(),
                            (" -- did you mean: %s?" % ", ".join(sugg)) if sugg else "",
                            ", ".join(ZONES)))
        return 2
    if zone != a.zone.strip():
        print("[onair] zone alias '%s' -> '%s'" % (a.zone.strip(), zone))
    mode = a.mode.lower()
    if mode not in ("exclusive", "collab", "fyi"):
        sys.stderr.write("[onair] mode must be exclusive|collab|fyi\n")
        return 2
    kind = a.agent_kind or "interactive"
    ttl_h = a.ttl_hours if a.ttl_hours else (12 if kind == "interactive" else 24)
    ttl_sec = int(ttl_h * 3600)
    session = a.session or os.environ.get("CLAUDE_SESSION_ID") or "s?"
    ts = now_utc()
    rid = "%s-%s-%s-%s" % (iso(ts).replace(":", ""), MACHINE, _slug(session), _slug(zone))
    rec = {
        "schema": "onair/v1",
        "id": rid,
        "status": "active",
        "mode": mode,
        "zone": zone,
        "also_touches": _resolve_also(a.also),
        "title": a.title,
        "summary": a.summary or "",
        "holder": {
            "person": a.person or os.environ.get("CLAUDE_OPERATOR") or "Anton",
            "machine": MACHINE,
            "session_id": session,
            "agent_kind": kind,
            "contact": a.contact or "telegram:@personal_acct",
        },
        "created_at": iso(ts),
        "renewed_at": iso(ts),
        "ttl_sec": ttl_sec,
        "expected_end": a.expected_end or "",
        "links": {"journal": a.journal or "", "branch": a.branch or "", "telegram_thread": ""},
    }
    fname = "%s__%s__%s__%s.json" % (MACHINE, _slug(session), _slug(zone), iso(ts).replace(":", ""))
    path = os.path.join(ACTIVE_DIR, fname)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    print("[onair] DECLARED %s  mode=%s zone=%s ttl=%dh" % (rid, mode.upper(), zone, ttl_h))
    # intersect check against existing active claims
    conflicts = _check_intersections(rec)
    if conflicts:
        print("[onair] !! INTERSECTS %d active claim(s):" % len(conflicts))
        for c, verdict in conflicts:
            print("   %s" % verdict)
        announce("ON AIR: %s declared %s on '%s' -- INTERSECTS existing claim(s), see board"
                 % (friendly(MACHINE), mode.upper(), zone))
    else:
        announce("ON AIR: %s [%s] %s -- '%s' (%dh)"
                 % (friendly(MACHINE), mode.upper(), zone, a.title, ttl_h))
    regen_summary()
    return 0

def _resolve_also(raw):
    """also_touches: map aliases, keep-with-WARN unknowns (secondary zones stay soft)."""
    out = []
    for z in (raw or "").split(","):
        z = z.strip()
        if not z:
            continue
        rz, sugg = resolve_zone(z, strict=False)
        if rz == z and z not in ZONES and not any(z.startswith(k + "/") for k in ZONES):
            sys.stderr.write("[onair] WARN: also_touches '%s' not in taxonomy%s\n"
                             % (z, (" (close: %s)" % ", ".join(sugg)) if sugg else ""))
        out.append(rz)
    return out

def _check_intersections(rec):
    """Return [(other_rec, verdict_str)] for active, non-expired claims that intersect rec."""
    out = []
    for other in load_active():
        if other.get("id") == rec.get("id") or "_error" in other:
            continue
        state, _ = derived_state(other)
        if state == "expired":
            continue
        if not rec_intersects(rec, other):
            continue
        om = other.get("mode", "?").upper()
        h = other.get("holder", {})
        who = "%s/%s" % (friendly(h.get("machine", "?")), h.get("session_id", "?"))
        verdict = "%s [%s] zone=%s holder=%s (%s)" % (
            om, state, other.get("zone", "?"), who, other.get("title", ""))
        # split-brain: two EXCLUSIVE -> later loses provisionally; ties break by machine order.
        if om == "EXCLUSIVE" and rec.get("mode") == "exclusive":
            a_t = parse_iso(rec.get("created_at", "")) or now_utc()
            b_t = parse_iso(other.get("created_at", "")) or now_utc()
            if a_t == b_t:  # exact tie -> fixed machine order (hub first) decides the loser
                def _rank(m):
                    return MACHINE_ORDER.index(m) if m in MACHINE_ORDER else len(MACHINE_ORDER)
                loser = "MINE" if _rank(MACHINE) > _rank(other.get("holder", {}).get("machine", "")) else "THEIRS"
            else:
                loser = "MINE" if a_t >= b_t else "THEIRS"
            verdict += "  -> EXCLUSIVE x EXCLUSIVE: later loses provisionally = %s" % loser
        out.append((other, verdict))
    return out

def _my(rec):
    h = rec.get("holder", {})
    return h.get("machine") == MACHINE

def _find(rid):
    for rec in load_active():
        if rec.get("id") == rid or os.path.basename(rec.get("_path", "")) == rid:
            return rec
    return None

def cmd_heartbeat(a):
    rec = _find(a.id)
    if not rec:
        print("[onair] no active claim: %s" % a.id); return 1
    if not _my(rec):
        print("[onair] refuse: not my claim (holder=%s). Only the holder heartbeats."
              % friendly(rec.get("holder", {}).get("machine", "?"))); return 3
    rec["renewed_at"] = iso(now_utc())
    path = rec.pop("_path")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    print("[onair] heartbeat %s -> renewed_at=%s" % (rec["id"], rec["renewed_at"]))
    regen_summary()
    return 0

def cmd_renew(a):
    rec = _find(a.id)
    if not rec:
        print("[onair] no active claim: %s" % a.id); return 1
    if not _my(rec):
        print("[onair] refuse: not my claim."); return 3
    if a.ttl_hours:
        rec["ttl_sec"] = int(a.ttl_hours * 3600)
    rec["renewed_at"] = iso(now_utc())
    path = rec.pop("_path")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    print("[onair] renewed %s (ttl=%dh)" % (rec["id"], rec["ttl_sec"] // 3600))
    regen_summary()
    return 0

def cmd_close(a):
    rec = _find(a.id)
    if not rec:
        print("[onair] no active claim: %s" % a.id); return 1
    if not _my(rec) and not a.force:
        print("[onair] refuse: not my claim (holder=%s). Use --force only for confirmed-dead claims."
              % friendly(rec.get("holder", {}).get("machine", "?"))); return 3
    path = rec.pop("_path")
    rec["status"] = "closed"
    rec["closed_at"] = iso(now_utc())
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    dst = os.path.join(ARCHIVE_DIR, os.path.basename(path))
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    try:
        os.remove(path)
    except Exception:
        pass
    print("[onair] closed %s -> archived" % rec["id"])
    announce("ON AIR: %s CLOSED '%s' (%s)" % (friendly(MACHINE), rec.get("zone", "?"), rec.get("title", "")))
    regen_summary()
    return 0

def cmd_expire(a):
    """GC: archive claims past expiry+grace. NEVER touch live claims. Hub runs this (nightly)."""
    n = 0
    for rec in load_active():
        if "_error" in rec:
            continue
        state, remain = derived_state(rec)
        if state != "expired":
            continue
        if -remain < GRACE_SEC:   # still within grace window
            continue
        path = rec.pop("_path")
        rec["status"] = "expired"
        rec["expired_at"] = iso(now_utc())
        dst = os.path.join(ARCHIVE_DIR, os.path.basename(path))
        try:
            with open(dst, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=2)
            os.remove(path)
            n += 1
            print("[onair] expired+archived %s (holder=%s)"
                  % (rec.get("id"), friendly(rec.get("holder", {}).get("machine", "?"))))
        except Exception as e:
            print("[onair] expire failed for %s: %s" % (rec.get("id"), e))
    if n:
        regen_summary()
    print("[onair] expire: %d archived" % n)
    return 0

def _render_lines():
    recs = load_active()
    rows = []
    for rec in recs:
        if "_error" in rec:
            rows.append("  ?? unreadable: %s (%s)" % (rec.get("id"), rec.get("_error")))
            continue
        state, remain = derived_state(rec)
        icon = {"exclusive": "[R]", "collab": "[Y]", "fyi": "[G]"}.get(rec.get("mode", ""), "[?]")
        h = rec.get("holder", {})
        hrs = int(max(0, remain) // 3600)
        mins = int((max(0, remain) % 3600) // 60)
        rows.append("  %s %-9s %-16s %-9s %s/%s  ~%dh%02dm  %s" % (
            icon, rec.get("mode", "?").upper(), rec.get("zone", "?"), state,
            friendly(h.get("machine", "?")), h.get("session_id", "?"),
            hrs, mins, rec.get("title", "")))
    return recs, rows

def regen_summary():
    ensure_dirs()
    recs, rows = _render_lines()
    lines = ["# ON AIR -- active work declarations (generated cache; source = active\\*.json)",
             "", "_updated %s by %s_" % (iso(now_utc()), friendly(MACHINE)), ""]
    if rows:
        lines.append("```")
        lines += rows
        lines.append("```")
    else:
        lines.append("_(no active declarations)_")
    try:
        with open(SUMMARY_FILE, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass
    return recs, rows

def cmd_summary(a):
    recs, rows = regen_summary()
    active = [r for r in recs if "_error" not in r]
    if a.hook:
        # short ASCII line for SessionStart hook context; silent if empty
        if not active:
            return 0
        excl = [r for r in active if r.get("mode") == "exclusive"]
        print("[ON AIR] %d active declaration(s)%s -- see _onair\\ACTIVE_NOW.md"
              % (len(active), (" (%d EXCLUSIVE)" % len(excl)) if excl else ""))
        for r in active:
            state, remain = derived_state(r)
            if r.get("mode") == "exclusive" or state == "expiring":
                h = r.get("holder", {})
                print("  [%s] %s %s/%s -- %s" % (r.get("mode", "?").upper(), r.get("zone", "?"),
                      friendly(h.get("machine", "?")), h.get("session_id", "?"), r.get("title", "")))
        return 0
    print("ON AIR board -- %d active declaration(s):" % len(active))
    for line in rows:
        print(line)
    return 0

def cmd_check(a):
    """Guard: does zone Z (in mode M) intersect any active claim? exit 0=clear, 10=intersect, 2=unknown zone."""
    zone, sugg = resolve_zone(a.zone)
    if zone is None:
        print("[onair] UNKNOWN zone '%s'%s -- taxonomy: %s"
              % (a.zone.strip(),
                 (" -- did you mean: %s?" % ", ".join(sugg)) if sugg else "",
                 ", ".join(ZONES)))
        return 2
    if zone != a.zone.strip():
        print("[onair] zone alias '%s' -> '%s'" % (a.zone.strip(), zone))
    probe = {"id": "__probe__", "mode": (a.mode or "exclusive").lower(),
             "zone": zone, "also_touches": [], "created_at": iso(now_utc())}
    conflicts = _check_intersections(probe)
    if not conflicts:
        print("[onair] CLEAR: zone '%s' has no intersecting active claim." % a.zone)
        return 0
    print("[onair] INTERSECTS zone '%s':" % a.zone)
    for _, v in conflicts:
        print("   " + v)
    return 10

def cmd_list(a):
    return cmd_summary(argparse.Namespace(hook=False))

def cmd_zones(a):
    print("ON AIR zone taxonomy (choose the narrowest match; subzones by path e.g. sync/protocol):")
    for z in ZONES:
        print("  " + z)
    return 0

# ---- cli -----------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(prog="onair", description="ON AIR advisory work-declaration board")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("declare", help="hang a table (declare structural work on a zone)")
    d.add_argument("--zone", required=True)
    d.add_argument("--mode", required=True, help="exclusive|collab|fyi")
    d.add_argument("--title", required=True)
    d.add_argument("--summary", default="")
    d.add_argument("--also", default="", help="comma-separated also_touches zones")
    d.add_argument("--ttl-hours", type=float, default=0, dest="ttl_hours")
    d.add_argument("--session", default="")
    d.add_argument("--agent-kind", default="", dest="agent_kind", help="interactive|headless")
    d.add_argument("--person", default="")
    d.add_argument("--contact", default="")
    d.add_argument("--expected-end", default="", dest="expected_end")
    d.add_argument("--journal", default="")
    d.add_argument("--branch", default="")
    d.set_defaults(func=cmd_declare)

    for name, fn, hlp in [("heartbeat", cmd_heartbeat, "touch renewed_at (holder only)"),
                          ("renew", cmd_renew, "extend ttl / renew (holder only)")]:
        s = sub.add_parser(name, help=hlp)
        s.add_argument("id")
        if name == "renew":
            s.add_argument("--ttl-hours", type=float, default=0, dest="ttl_hours")
        s.set_defaults(func=fn)

    c = sub.add_parser("close", help="close+archive your own claim (holder only)")
    c.add_argument("id")
    c.add_argument("--force", action="store_true", help="close a confirmed-dead foreign claim")
    c.set_defaults(func=cmd_close)

    e = sub.add_parser("expire", help="GC: archive past-grace expired claims (hub/nightly)")
    e.set_defaults(func=cmd_expire)

    su = sub.add_parser("summary", help="regen ACTIVE_NOW.md + print board")
    su.add_argument("--hook", action="store_true", help="short ASCII line for SessionStart")
    su.set_defaults(func=cmd_summary)

    ck = sub.add_parser("check", help="guard: does a zone intersect an active claim?")
    ck.add_argument("--zone", required=True)
    ck.add_argument("--mode", default="exclusive")
    ck.set_defaults(func=cmd_check)

    ls = sub.add_parser("list", help="alias of summary")
    ls.set_defaults(func=cmd_list)

    z = sub.add_parser("zones", help="print the zone taxonomy")
    z.set_defaults(func=cmd_zones)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 0
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
