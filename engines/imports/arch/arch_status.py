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
"""
arch_status.py -- System Architect, on-demand status reader (for the /arch skill).
Reads system.db (built by the nightly architect) and prints a concise status.
Deterministic, 0 tokens, READ-ONLY.

Usage:
  python arch_status.py            # status summary
  python arch_status.py broken     # only broken/red items
  python arch_status.py dead       # dead-code candidates (scripts wired to nothing)
"""
import os, sqlite3, sys

DB = r"%IMPORTS%\arch\system.db"
mode = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()

if not os.path.exists(DB):
    print("system.db not found -- run sys_scan.py first"); sys.exit(0)

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
if not con.execute("SELECT name FROM sqlite_master WHERE name='asset'").fetchone():
    print("system.db has no asset table (half-built?) -- run sys_scan.py first"); sys.exit(0)
meta = {r["key"]: r["val"] for r in con.execute("SELECT * FROM meta")} \
       if con.execute("SELECT name FROM sqlite_master WHERE name='meta'").fetchone() else {}
broken = list(con.execute("SELECT kind,name,detail FROM asset WHERE status='broken' ORDER BY kind"))
disabled = list(con.execute("SELECT kind,name FROM asset WHERE status='disabled'"))
try:
    fails = list(con.execute("SELECT check_id,cadence,severity,detail FROM check_result WHERE status='fail'"))
    redflag = os.path.exists(r"%IMPORTS%\arch\RED.flag")
except Exception:
    fails, redflag = [], False

def edges_in(aid):
    return con.execute("SELECT COUNT(*) FROM edge WHERE dst=?", (aid,)).fetchone()[0]

if mode == "broken":
    print("BROKEN assets:")
    for r in broken: print("  [%s] %s -- %s" % (r["kind"], r["name"], r["detail"]))
    print("FAILED checks:")
    for r in fails: print("  [%s/%s] %s -- %s" % (r["cadence"], r["severity"], r["check_id"], r["detail"]))
    if not broken and not fails: print("  none -- all green")
elif mode == "dead":
    rows = list(con.execute("SELECT asset_id,name FROM asset WHERE kind='script'"))
    dead = [r["name"] for r in rows if edges_in(r["asset_id"]) == 0]
    print("Dead-code candidates (scripts referenced by no task/skill): %d" % len(dead))
    for n in dead: print("  -", n)
else:
    from collections import Counter
    kc = Counter(r["kind"] for r in con.execute("SELECT kind FROM asset"))
    print("=== SYSTEM STATUS ===")
    print("Score: %s/100   (generated %s)" % (meta.get("score", "?"), meta.get("generated_at", "?")))
    # local-db staleness banner (2026-07-04): the nightly scan lives on the HUB now;
    # a peer's system.db refreshes only on manual `/arch scan`. Say so honestly
    # instead of presenting days-old numbers as current.
    try:
        import datetime
        last = con.execute("SELECT MAX(run_at) FROM scan_run").fetchone()[0]
        age_h = (datetime.datetime.now()
                 - datetime.datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600.0
        if age_h > 36:
            print("!! LOCAL system.db is %.1f days stale (last scan %s) -- fresh = hub dashboard"
                  " (System-Health.html); `/arch scan` refreshes locally" % (age_h / 24.0, last))
    except Exception:
        pass
    # counts LIVE from asset table (meta snapshot goes stale when sys_scan re-runs
    # without build_system_docs -> phantom "broken N", 2026-07-02)
    total_live = con.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    print("Assets: %s total | broken %s | disabled %s | dead-script candidates %s"
          % (total_live, len(broken), len(disabled), meta.get("dead_scripts", "?")))
    print("RED flag: %s" % ("YES -- attention needed" if redflag else "no (all green)"))
    # dashboard provenance: a peer's stale engine can overwrite the canonical
    # dashboard via Syncthing (2026-07-02) -- warn right here, not only at 05:06
    dash = r"%VAULT%\_Dashboards\System-Health.html"
    try:
        head = open(dash, encoding="utf-8", errors="replace").read(2000)
        import re
        m = re.search(r"arch-source: (\S+) @ (\d{4}-\d\d-\d\d \d\d:\d\d)", head)
        if m:
            print("Dashboard source: %s @ %s%s" % (m.group(1), m.group(2).strip(),
                  "" if m.group(1) == "HUB1" else "  <-- FOREIGN ENGINE, not hub!"))
        else:
            print("Dashboard source: NO HUB STAMP -- overwritten by a stale/foreign engine?")
    except Exception:
        pass
    print("\nBy kind:")
    for k in sorted(kc): print("  %-16s %4d" % (k, kc[k]))
    if broken:
        print("\nBROKEN:")
        for r in broken: print("  [%s] %s -- %s" % (r["kind"], r["name"], r["detail"]))
    if fails:
        print("\nFAILED checks:")
        for r in fails: print("  [%s/%s] %s -- %s" % (r["cadence"], r["severity"], r["check_id"], r["detail"]))
    print("\nDashboard: _Dashboards/System-Health.html | Map: 00-System/_System-MOC.md")
con.close()
