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
sys_check.py -- System Architect, Phase 4 (tiered integrity tests + restore drill)
Reads system.db, runs a cadence-tagged battery of checks, writes results back to
system.db (table `check_result`) and a RED flag file if anything critical/daily fails.
Deterministic, 0 tokens. SRE rule: page only on symptoms that need a human.

Run:  python sys_check.py
"""
import os, sqlite3, subprocess, datetime, glob, time

IMPORTS = r"%IMPORTS%"
VAULT   = r"%VAULT%"
ARCH    = os.path.join(IMPORTS, "arch")
DB_PATH = os.path.join(ARCH, "system.db")
REDFLAG = os.path.join(ARCH, "RED.flag")
NOW = datetime.datetime.now()
NOWS = NOW.strftime("%Y-%m-%d %H:%M:%S")

results = []  # dict(check_id, cadence, severity, status, detail)

def chk(cid, cadence, severity, status, detail=""):
    results.append(dict(check_id=cid, cadence=cadence, severity=severity,
                        status=status, detail=detail))

def age_hours(path):
    return (time.time() - os.path.getmtime(path)) / 3600.0

# ----------------------------------------------------------- nightly checks ----
def c_catalog_freshness():
    try:
        con = sqlite3.connect(DB_PATH)
        run = con.execute("SELECT run_at FROM scan_run ORDER BY run_at DESC LIMIT 1").fetchone()
        con.close()
        last = datetime.datetime.strptime(run[0], "%Y-%m-%d %H:%M:%S")
        h = (NOW - last).total_seconds() / 3600.0
        ok = h <= 26
        chk("chk-catalog-freshness", "nightly", "important",
            "pass" if ok else "fail", "scan age %.1fh" % h)
    except Exception as e:
        chk("chk-catalog-freshness", "nightly", "important", "fail", str(e))

def c_docs_fresh():
    for label, p in [("dashboard", os.path.join(VAULT, "_Dashboards", "System-Health.html")),
                     ("moc", os.path.join(VAULT, "00-System", "_System-MOC.md"))]:
        if not os.path.exists(p):
            chk("chk-docs-%s" % label, "nightly", "important", "fail", "missing"); continue
        h = age_hours(p)
        chk("chk-docs-%s" % label, "nightly", "important",
            "pass" if h <= 26 else "fail", "%.1fh old" % h)

def c_docs_provenance():
    # Canonical dashboard/MOC must be written by the HUB's engine. A peer's stale
    # engine can overwrite them via Syncthing with foreign data that still looks
    # "fresh" by mtime (happened 2026-07-02, masked real broken tasks all day).
    HUB = "HUB1"
    for label, p, needle in [
            ("dashboard", os.path.join(VAULT, "_Dashboards", "System-Health.html"),
             "arch-source: %s" % HUB),
            ("moc", os.path.join(VAULT, "00-System", "_System-MOC.md"),
             "machine: %s" % HUB)]:
        cid = "chk-provenance-%s" % label
        if not os.path.exists(p):
            chk(cid, "daily", "critical", "fail", "missing"); continue
        head = open(p, encoding="utf-8", errors="replace").read(2000)
        chk(cid, "daily", "critical",
            "pass" if needle in head else "fail",
            "hub stamp ok" if needle in head
            else "no hub stamp -- overwritten by a foreign/stale engine?")

def c_broken_assets():
    con = sqlite3.connect(DB_PATH)
    n = con.execute("SELECT COUNT(*) FROM asset WHERE status='broken'").fetchone()[0]
    names = [r[0] for r in con.execute("SELECT name FROM asset WHERE status='broken'")]
    con.close()
    chk("chk-broken-assets", "daily", "critical" if n else "important",
        "pass" if n == 0 else "fail", ("%d broken: %s" % (n, ", ".join(names[:5]))) if n else "0 broken")

# ------------------------------------------------------------- daily checks ----
def c_vault_backup_fresh():
    repo = None
    for cand in [VAULT, "%VAULT_ROOT%"]:
        if os.path.isdir(os.path.join(cand, ".git")):
            repo = cand; break
    if not repo:
        chk("chk-vault-backup-fresh", "daily", "critical", "fail", "no git repo found"); return
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%ct"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        h = (time.time() - int(out)) / 3600.0
        chk("chk-vault-backup-fresh", "daily", "critical",
            "pass" if h <= 26 else "fail", "last commit %.1fh ago (%s)" % (h, os.path.basename(repo)))
    except Exception as e:
        chk("chk-vault-backup-fresh", "daily", "critical", "fail", str(e))

def c_lint_flags():
    """Surface the lint gates' flag files as a REAL check (adversarial-review nit
    2026-07-02: the flags had no consumer -- alarm with no bell). Lints run BEFORE
    sys_check in run_architect.cmd so these flags are fresh, not last night's."""
    flags = {"_lint_llm.flag": "NEW LLM call site(s) in _imports",
             "_lint_encoding.flag": "NEW unguarded Cyrillic print site(s)",
             "_lint_vault_walk.flag": "NEW unguarded share-root walk (skips .stversions)",
             "_lint_path_hardcode.flag": "NEW hardcoded C:\\Users\\<name> path(s)",
             "_lint_approval.flag": "approval-ask routed past approval.py (02-POLICE-first bypassed)",
             "_lint_dangling.flag": "launcher calls a script that does NOT exist (silent-dead gate)",
             "_lint_canon_refs.flag": "canon prose (CLAUDE.md/skills) names a script that does NOT exist (silent-dead gate)",
             "_lint_tls_certifi.flag": "NEW urllib->public-https caller without certifi pin (expired-cert class)",
             "_lint_platform.flag": "NEW Windows-only call (tasklist/schtasks/NUL-redirect) in fleet .py without os.name guard (NUL-file sync-stall class)",
             "_lint_cli_argparse.flag": "NEW CLI script with side effects and NO argparse (--help-fires-the-weapon class, publish_canon 21.07)",
             "_lint_parcel_coverage.flag": "NEW fleet-parcel coverage gap (a node got skipped at registration -- fleet_nodes class 22.07)",
             "_lint_agents_mirror.flag": "AGENTS.md (Codex canon mirror) is STALE vs CLAUDE.md version -- Codex works by OLD rules (month-stale class 25.07)"}
    bad = []
    for fn, what in flags.items():
        p = os.path.join(ARCH, fn)
        if os.path.exists(p):
            bad.append("%s: %s" % (fn, what))
    chk("chk-lint-flags", "daily", "critical",
        "pass" if not bad else "fail",
        "lint gates green" if not bad else "; ".join(bad) + " -- see _lint_*.txt")

# ------------------------------------------------------------ weekly checks ----
def c_db_integrity():
    bad = []
    for f in glob.glob(os.path.join(IMPORTS, "**", "*.db"), recursive=True):
        if any(x in f.lower() for x in ("_archive", "_bak", "_backup", "__pycache__")):
            continue
        try:
            con = sqlite3.connect("file:%s?mode=ro" % f, uri=True, timeout=10)
            r = con.execute("PRAGMA quick_check").fetchone()
            con.close()
            if r and r[0] != "ok":
                bad.append(os.path.basename(f))
        except Exception:
            bad.append(os.path.basename(f) + "(locked/err)")
    chk("chk-db-integrity", "weekly", "important",
        "pass" if not bad else "fail",
        "all dbs ok" if not bad else "bad: " + ", ".join(bad[:6]))

# ----------------------------------------------------------- monthly checks ----
def c_restore_drill():
    """Prove the vault git backup is RESTORABLE: extract a tracked file from HEAD."""
    repo = VAULT if os.path.isdir(os.path.join(VAULT, ".git")) else "%VAULT_ROOT%"
    try:
        ls = subprocess.run(["git", "-C", repo, "ls-tree", "--name-only", "HEAD"],
                            capture_output=True, encoding="utf-8", errors="replace",
                            timeout=30).stdout.splitlines()
        rel = next((x for x in ls if x.endswith(".md")), ls[0] if ls else None)
        if not rel:
            chk("chk-restore-drill", "monthly", "critical", "fail", "no tracked files"); return
        out = subprocess.run(["git", "-C", repo, "show", "HEAD:%s" % rel],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        ok = out.returncode == 0 and len(out.stdout or "") > 20
        chk("chk-restore-drill", "monthly", "critical",
            "pass" if ok else "fail",
            ("restored '%s' (%d bytes) from HEAD" % (rel, len(out.stdout))) if ok else "restore failed")
    except Exception as e:
        chk("chk-restore-drill", "monthly", "critical", "fail", str(e))

CHECKS = [c_catalog_freshness, c_docs_fresh, c_docs_provenance, c_broken_assets,
          c_vault_backup_fresh, c_lint_flags, c_db_integrity, c_restore_drill]

def main():
    for fn in CHECKS:
        try:
            fn()
        except Exception as e:
            chk(fn.__name__, "?", "important", "fail", "check crashed: %s" % e)

    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS check_result(
            run_at TEXT, check_id TEXT, cadence TEXT, severity TEXT, status TEXT, detail TEXT);
    """)
    # keep only latest per check_id: simplest = clear + reinsert this run's, plus history row
    con.execute("DELETE FROM check_result WHERE run_at <> ?", (NOWS,))  # noop first run
    for r in results:
        con.execute("INSERT INTO check_result VALUES(?,?,?,?,?,?)",
                    (NOWS, r["check_id"], r["cadence"], r["severity"], r["status"], r["detail"]))
    con.commit(); con.close()

    fails = [r for r in results if r["status"] == "fail"]
    red = [r for r in fails if r["severity"] == "critical" or r["cadence"] in ("daily", "nightly")]
    print("System checks @", NOWS)
    for r in results:
        mark = "OK " if r["status"] == "pass" else "XX "
        print("  %s [%s/%s] %-22s %s" % (mark, r["cadence"], r["severity"], r["check_id"], r["detail"]))
    print("\n%d checks, %d fail (%d RED)" % (len(results), len(fails), len(red)))

    if red:
        with open(REDFLAG, "w", encoding="utf-8") as f:
            f.write("RED @ %s\n" % NOWS)
            for r in red:
                f.write("[%s/%s] %s -- %s\n" % (r["cadence"], r["severity"], r["check_id"], r["detail"]))
        print("RED flag written ->", REDFLAG)
    elif os.path.exists(REDFLAG):
        os.remove(REDFLAG)
        print("RED flag cleared (all green)")

if __name__ == "__main__":
    main()
