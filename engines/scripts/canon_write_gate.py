#!/usr/bin/env python3
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
"""canon_write_gate.py -- GATE before writing CANON (CLAUDE.md / Bible reglament-*/protocol-* /
operating-agreement / standing MEMORY.md).

Roaming-leader decision (2026-07-16, #b89596dd, HUMAN_APPROVED): canon may now be edited from ANY
of Anton's 4 machines in a LIVE Anton session -- not only the hub. This gate enforces the three
invariants that keep that safe:

  (a) OPERATOR   -- this is an Anton-machine AND a live Anton session (robots/routines have no
                    canon rights).  Follower machines (Nina/Rita) are receive-only.
  (b) FRESHNESS  -- Syncthing has fully converged (need=0) on the canon-bearing folders, so a
                    stale/unsynced tree can NEVER clobber newer canon (the 2026-07-16 resync-revert
                    class: a node with a reset index raced an OLD tree over live files).
  (c) BACKUP     -- a timestamped backup of the target is made before the write is allowed.

AK-47: Python stdlib only, no deps. Runs identically on Windows + macOS (the 4 Anton machines).

USAGE:
  python canon_write_gate.py <target_file>          # check + (on GO) make backup, print verdict
  python canon_write_gate.py <target_file> --dry    # check only, NO backup
  python canon_write_gate.py --selftest             # offline logic self-test

EXIT: 0 = GO (safe to write; backup made unless --dry) ; 2 = BLOCK (reason printed) ; 3 = usage error
"""
import os, sys, json, socket, shutil, argparse, datetime, urllib.request, urllib.parse

# --- the 4 Anton-machines that MAY hold the canon pen (roaming leader) --------------------------
ANTON_MACHINES = {"LAPTOP1", "HUB1", "ANCHOR1", "MAC1"}
# friendly-label aliases -> canonical key (macOS has no COMPUTERNAME; MACHINE_KEY env is canonical)
ALIASES = {"LAPTOP1": "LAPTOP1", "PALOALTO-DESKTOP": "HUB1",
           "ANCHOR1": "ANCHOR1", "ANCHOR1": "ANCHOR1"}
# Syncthing folder IDs that carry canon; require need=0 on every one that EXISTS on this machine.
CANON_FOLDERS = {"claude-config", "claude-home", "claude-memory", "Owner-Knowledge"}
ST_API = os.environ.get("SYNCTHING_URL", "http://127.0.0.1:8384/rest")


def machine_key():
    k = (os.environ.get("MACHINE_KEY") or os.environ.get("COMPUTERNAME") or "").strip()
    if not k:
        k = socket.gethostname().split(".")[0].strip()
    up = k.upper()
    return ALIASES.get(up, k)


def st_apikey():
    key = (os.environ.get("STGUIAPIKEY") or "").strip()
    if key:
        return key
    for p in (os.path.join(os.path.expanduser("~"), ".claude", "scripts", "_st_apikey.txt"),):
        try:
            with open(p, encoding="utf-8") as fh:
                v = fh.read().strip()
                if v:
                    return v
        except OSError:
            pass
    return ""


def _get(path, key):
    req = urllib.request.Request(ST_API + path, headers={"X-API-Key": key})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def sync_fresh():
    """Return (ok: bool, detail: str). ok=True only if every present canon folder has need=0."""
    key = st_apikey()
    if not key:
        return False, "no Syncthing API key (STGUIAPIKEY / _st_apikey.txt) -> cannot prove freshness"
    try:
        folders = _get("/config/folders", key)
    except Exception as e:
        return False, "Syncthing REST unreachable (%s) -> cannot prove freshness" % e
    present = [f["id"] for f in folders if f["id"] in CANON_FOLDERS]
    if not present:
        return False, "no canon folders configured here -> not a canon-bearing node"
    dirty = []
    for fid in present:
        try:
            st = _get("/db/status?folder=" + urllib.parse.quote(fid), key)
        except Exception as e:
            return False, "status(%s) failed: %s" % (fid, e)
        need = int(st.get("needFiles", 0)) + int(st.get("needDeletes", 0)) + int(st.get("needSymlinks", 0))
        state = st.get("state")
        if need or state != "idle":
            dirty.append("%s(need=%d,state=%s)" % (fid, need, state))
    if dirty:
        return False, "Syncthing NOT converged: " + ", ".join(dirty)
    return True, "fresh (need=0 on " + ", ".join(present) + ")"


def check():
    reasons = []
    mk = machine_key()

    # (a1) machine allowlist
    if mk not in ANTON_MACHINES:
        reasons.append("machine '%s' is NOT an Anton-machine -> canon is receive-only here" % mk)

    # (a2) robot / headless routine guard -- these markers are set by the autonomous runners
    for flag in ("CLAUDE_BUS_NOADVANCE", "CLAUDE_ROBOT", "CONSENSUS_ROBOT"):
        if os.environ.get(flag):
            reasons.append("automated run detected (%s set) -> canon needs a LIVE Anton session" % flag)
            break

    # (a3) operator
    op = (os.environ.get("CLAUDE_OPERATOR") or "Anton").strip()
    if op.lower() != "anton":
        reasons.append("operator '%s' != Anton -> only Anton edits canon" % op)

    # (b) sync freshness
    ok, detail = sync_fresh()
    if not ok:
        reasons.append("SYNC: " + detail)
    return mk, op, detail, reasons


def main(argv):
    # argparse (wave-1 2026-07-21, class: "--help fires the weapon"): unknown flag -> exit 2
    # BEFORE any check/backup; the old hand parser silently IGNORED unknown --flags.
    p = argparse.ArgumentParser(
        prog="canon_write_gate.py",
        description="GATE before writing CANON: operator + Syncthing freshness + backup. "
                    "Exit 0=GO, 2=BLOCK/bad flag, 3=usage.")
    p.add_argument("target", nargs="?", help="canon file about to be written")
    p.add_argument("--dry", action="store_true", help="check only, do NOT make a backup")
    p.add_argument("--selftest", action="store_true", help="offline logic self-test")
    ns = p.parse_args(argv)
    if ns.selftest:
        return selftest()
    if not ns.target:
        print("usage: canon_write_gate.py <target_file> [--dry]")
        return 3
    target = ns.target
    dry = ns.dry
    mk, op, detail, reasons = check()

    print("canon-gate: machine=%s operator=%s target=%s" % (mk, op, target))
    if reasons:
        print("  ⛔ BLOCK:")
        for r in reasons:
            print("     - " + r)
        print("  -> resolve the above, or run canon on a fresh Anton-machine, before writing.")
        return 2

    print("  ✅ operator OK | %s" % detail)
    if not os.path.exists(target):
        print("  ✅ GO (new file, no backup needed)")
        return 0
    if dry:
        print("  ✅ GO (--dry: no backup made)")
        return 0
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = "%s.canonbak-%s" % (target, stamp)
    try:
        shutil.copy2(target, bak)
    except OSError as e:
        print("  ⛔ BLOCK: backup failed (%s)" % e)
        return 2
    print("  ✅ GO -- backup: %s" % bak)
    return 0


def selftest():
    fails = 0

    def ck(label, cond):
        nonlocal fails
        print(("  OK  " if cond else "  FAIL ") + label)
        if not cond:
            fails += 1

    ck("hub in allowlist", "HUB1" in ANTON_MACHINES)
    ck("Mac16 in allowlist", "MAC1" in ANTON_MACHINES)
    ck("Nina follower NOT in allowlist", "NAT1-Nina" not in ANTON_MACHINES)
    ck("Rita follower NOT in allowlist", "MacBook-Rita" not in ANTON_MACHINES)
    ck("alias LAPTOP1 -> canonical", ALIASES.get("LAPTOP1") == "LAPTOP1")
    # robot flag detection
    os.environ["CLAUDE_BUS_NOADVANCE"] = "1"
    _, _, _, reasons = check()
    ck("robot flag CLAUDE_BUS_NOADVANCE blocks", any("automated run" in r for r in reasons))
    del os.environ["CLAUDE_BUS_NOADVANCE"]
    # wrong operator
    os.environ["CLAUDE_OPERATOR"] = "Nina"
    _, _, _, reasons = check()
    ck("wrong operator blocks", any("!= Anton" in r for r in reasons))
    del os.environ["CLAUDE_OPERATOR"]
    print("\n" + ("ALL PASS" if fails == 0 else "%d FAILED" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
