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
"""clan_alive.py -- THE deterministic answer to "is clan node X alive?" (0 LLM, read-only).

WHY (грабли 2026-07-04): asked to "contact Rita's Mac", the hub session judged the node
DEAD from stale `_machine-bus` file-marker mtimes (.read-*, .robot-done-*, no log-<node>.jsonl)
and raised a false alarm + nudged the human for nothing. The node was in fact `connected=True`
in Syncthing and posting to TG-03 -- it just speaks on the TG rail, where the file-decision-rail
markers are frozen BY DESIGN. Root of the CLASS: no single entry point answered "is X up?", so
the model improvised on the wrong signal.

FIX: judge liveness ONLY by LIVE signals, same source sync_monitor.py already trusts:
  1) Syncthing GET /rest/system/connections -> connected==true   (PRIMARY, authoritative)
  2) freshness of `.tg-seen-<node>` in the bus dir                (secondary, TG-rail proof)
File-marker mtimes (.read-*, .robot-done-*, log-<node>.jsonl) are NOT liveness -- do not use them.

Usage:
  python clan_alive.py            # table of every peer: 🟢/🔴 + conn + tg-seen age
  python clan_alive.py <node>     # just that node; exit 0 if alive, 1 if down/unknown
"""
import os, re, sys, json, time, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BUS = os.environ.get("MACHINE_BUS_DIR", r"%VAULT%\_machine-bus")
GREEN, WARN, RED, UNK = "🟢", "🟡", "🔴", "?"
TG_SEEN_FRESH_MIN = 90   # .tg-seen-<node> newer than this = the node's TG rail is live


def _alive(r):
    """LIVE by EITHER rail. A Syncthing flap (Tailscale) must NOT read as dead while the
    node is still posting on TG. This OR-logic is the whole point of the 2026-07-04 fix."""
    tg = r["tg_seen_min"]
    return r["connected"] or (tg is not None and tg <= TG_SEEN_FRESH_MIN)


def _apikey():
    k = (os.environ.get("STGUIAPIKEY") or "").strip()
    if k:
        return k
    cfg = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Syncthing", "config.xml")
    try:
        x = open(cfg, encoding="utf-8", errors="ignore").read()
        m = re.search(r"<apikey>([^<]+)</apikey>", x, re.I)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _api(path, key):
    req = urllib.request.Request("http://127.0.0.1:8384/rest" + path, headers={"X-API-Key": key})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def _tg_seen_age_min(node):
    """Freshest .tg-seen-* marker whose suffix matches this node (bus-key or device name)."""
    best = None
    try:
        for fn in os.listdir(BUS):
            if fn.startswith(".tg-seen-") and node.lower() in fn.lower():
                age = (time.time() - os.path.getmtime(os.path.join(BUS, fn))) / 60.0
                best = age if best is None else min(best, age)
    except Exception:
        pass
    return best


def collect():
    key = _apikey()
    if not key:
        return None, "no Syncthing API key (STGUIAPIKEY / config.xml)"
    try:
        myid = _api("/system/status", key).get("myID", "")
        conns = _api("/system/connections", key).get("connections", {})
        devs = {d["deviceID"]: d.get("name", "") for d in _api("/config/devices", key)}
    except Exception as e:
        return None, "Syncthing REST unreachable: %s" % str(e)[:60]
    rows = []
    for dev, c in conns.items():
        if dev == myid:
            continue
        name = devs.get(dev, dev[:7])
        connected = bool(c.get("connected"))
        at = (c.get("at") or "")[:19]
        tg_age = _tg_seen_age_min(name)
        rows.append({"device": dev[:7], "name": name, "connected": connected,
                     "at": at, "tg_seen_min": tg_age})
    rows.sort(key=lambda r: (not _alive(r), not r["connected"], r["name"].lower()))
    return rows, None


def _fmt(r):
    # 🟢 Syncthing connected · 🟡 alive on TG rail but Syncthing flapped · 🔴 dead on both
    g = GREEN if r["connected"] else (WARN if _alive(r) else RED)
    tg = "?" if r["tg_seen_min"] is None else (
        "%.0fм" % r["tg_seen_min"] + ("✓" if r["tg_seen_min"] <= TG_SEEN_FRESH_MIN else ""))
    note = "" if r["connected"] else ("  (TG-rail alive, Syncthing flapped)" if _alive(r) else "")
    return "%s %-20s dev=%s conn=%s at=%s tg-seen=%s%s" % (
        g, r["name"], r["device"], r["connected"], r["at"] or "-", tg, note)


def main():
    rows, err = collect()
    if err:
        print("%s clan_alive: %s" % (UNK, err))
        return 2
    want = sys.argv[1] if len(sys.argv) > 1 else None
    if want:
        hit = [r for r in rows if want.lower() in r["name"].lower() or want.lower() in r["device"].lower()]
        if not hit:
            print("%s %s: not a known Syncthing peer of this hub" % (UNK, want))
            return 1
        for r in hit:
            print(_fmt(r))
        return 0 if all(_alive(r) for r in hit) else 1
    alive = sum(1 for r in rows if _alive(r))
    print("CLAN LIVENESS (Syncthing conn OR fresh .tg-seen) -- %d/%d peers alive" % (alive, len(rows)))
    for r in rows:
        print("  " + _fmt(r))
    print("\nRULE: liveness = conn==True (primary) or fresh tg-seen (TG-rail). "
          "NEVER judge by .read-*/.robot-done-* mtime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
