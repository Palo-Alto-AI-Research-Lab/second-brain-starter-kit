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
# resolve_conflicts.py -- SAFE cleanup of Syncthing *.sync-conflict-* files across the synced trees.
#
# WHY (reglament-chp-poterya-sinka §6 TODO): the 2026-06-25 re-pairing left ~100+ sync-conflict copies
# (a quiet sign two machines fought over a file). They clutter the vault/config and /sync-check flags them.
# Deleting blindly is unsafe -- a conflict copy MIGHT hold content the live file lost. So this tool applies
# the proven rule: for each conflict file, compare to its LIVE counterpart; if the conflict has NO
# substantive line absent from live (i.e. it's a subset/older) -> SAFE to delete; otherwise -> FLAG for a
# human. Deterministic, 0 tokens. DRY-RUN by default; --apply deletes only the proven-safe ones.
# Syncthing's own .stversions + the live file remain, so a safe-delete is recoverable anyway.
import os, re, sys, glob, time, shutil

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# never touch already-archived / version-history / cache trees
EXCLUDE_DIRS = ("_sync-conflict-archive", "_sync-conflict-quarantine", ".stversions", "_archive", "__pycache__")
def _excluded(p):
    low = p.replace("/", "\\").lower()
    return any(("\\" + d.lower() + "\\") in low for d in EXCLUDE_DIRS)

DEFAULT_ROOTS = [
    r"%VAULT%",
    r"%IMPORTS%",
    os.path.join(os.path.expanduser("~"), ".claude"),
]
# conflict marker Syncthing inserts BEFORE the extension: name.sync-conflict-YYYYMMDD-HHMMSS-DEVID.ext
CONF_RE = re.compile(r"^(?P<base>.*)\.sync-conflict-\d{8}-\d{6}-[0-9A-Za-z]+(?P<ext>\.[^.\\/]+)?$")


def live_path(conf):
    d, name = os.path.split(conf)
    m = CONF_RE.match(name)
    if not m:
        return None
    return os.path.join(d, m.group("base") + (m.group("ext") or ""))


def _nonblank_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return set(ln.strip() for ln in f if ln.strip())
    except Exception:
        return None


def classify(conf):
    """Return ('safe'|'flag'|'orphan', detail). safe = conflict is a subset of live -> deletable."""
    live = live_path(conf)
    if not live or not os.path.exists(live):
        return "orphan", "no live counterpart (live deleted?) -> keep for review"
    cset = _nonblank_lines(conf)
    lset = _nonblank_lines(live)
    if cset is None or lset is None:
        # binary or unreadable -> compare bytes
        try:
            same = open(conf, "rb").read() == open(live, "rb").read()
        except Exception:
            return "flag", "unreadable -> manual"
        return ("safe", "binary identical to live") if same else ("flag", "binary differs -> manual")
    unique = cset - lset
    if not unique:
        return "safe", "subset of live (no unique lines)"
    return "flag", f"{len(unique)} unique line(s) -> manual review"


def main():
    apply = "--apply" in sys.argv            # delete proven-safe (subset) conflicts
    quarantine = "--quarantine" in sys.argv  # MOVE safe+flag live-tree conflicts to a dated archive (non-destructive)
    roots = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_ROOTS
    safe, flag, orphan = [], [], []
    for root in roots:
        if not os.path.exists(root):
            continue
        for conf in glob.glob(os.path.join(root, "**", "*.sync-conflict-*"), recursive=True):
            if os.path.isdir(conf) or _excluded(conf):
                continue
            kind, detail = classify(conf)
            (safe if kind == "safe" else flag if kind == "flag" else orphan).append((conf, detail))

    mode = "APPLY-DELETE" if apply else "QUARANTINE" if quarantine else "DRY-RUN"
    print(f"=== sync-conflict cleanup ({mode}) — live tree only (excludes archives/.stversions) ===")
    print(f"SAFE (subset of live): {len(safe)}")
    print(f"FLAG (has unique content): {len(flag)}")
    print(f"ORPHAN (no live counterpart -> keep): {len(orphan)}")
    if flag:
        print("\n--- FLAGGED ---")
        for p, d in flag[:40]:
            print(f"  [{d}] {p}")
    if orphan:
        print("\n--- ORPHANS (NEVER auto-touched) ---")
        for p, d in orphan[:20]:
            print(f"  {p}")

    if apply:
        n = 0
        for p, _ in safe:
            try: os.remove(p); n += 1
            except Exception as e: print("  ERR delete", p, e)
        print(f"\nDELETED {n} safe conflict files. (.stversions + live file remain.)")
    elif quarantine:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        n = 0
        for p, _ in (safe + flag):   # orphans are left alone (may be the only copy)
            try:
                # find which root this file is under -> archive within that root (vault files stay in vault)
                root = next((r for r in roots if os.path.abspath(p).lower().startswith(os.path.abspath(r).lower())), os.path.dirname(p))
                qdir = os.path.join(root, "_sync-conflict-archive", stamp)
                os.makedirs(qdir, exist_ok=True)
                dest = os.path.join(qdir, os.path.basename(p))
                k = 1
                while os.path.exists(dest):
                    dest = os.path.join(qdir, f"{k}_{os.path.basename(p)}"); k += 1
                shutil.move(p, dest); n += 1
            except Exception as e:
                print("  ERR move", p, e)
        print(f"\nQUARANTINED {n} conflict files to _sync-conflict-archive\\{stamp}\\ (moved, not deleted -> recoverable). Orphans left untouched.")
    else:
        print(f"\n(dry-run) --quarantine moves {len(safe)+len(flag)} live-tree conflicts to a dated archive (safe). --apply deletes only the {len(safe)} subset-safe. Orphans never auto-touched.")


if __name__ == "__main__":
    main()
