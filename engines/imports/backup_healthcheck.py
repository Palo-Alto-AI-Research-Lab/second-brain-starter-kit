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
"""backup_healthcheck.py - weekly DETERMINISTIC check that the Obsidian offsite
backup is still alive (see backup_to_drive.py + Windows task 'Obsidian Backup to Drive').

Token-economy (Anton's law): this script does ALL the checking and prints a tiny
summary; the scheduled Claude routine only reads the verdict and pings Telegram.

Checks (filesystem-first = locale-independent, the real "did output land" signal):
  1. newest vault bundle present + fresh in BOTH targets (Drive folder on E: and C:).
  2. `git bundle verify` on the newest bundle in each target (corruption).
  3. _originals present in both targets and not lagging the source (copy-only mirror).
  4. Windows task exists / enabled / last result == success (best-effort via schtasks).

Writes %IMPORTS%\\backup_health\\health-<date>.md (+ health-latest.md).
Prints an ASCII summary ending with 'STATUS OK' or 'STATUS PROBLEM'. Exit 0 / 1.
Run: $env:PYTHONUTF8=1; python backup_healthcheck.py
"""
import sys, re, subprocess
from datetime import datetime
from pathlib import Path

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback
try:
    from _paths import ORIGINALS
except Exception:
    ORIGINALS = r"%VAULT_ROOT%\_originals"   # HP17 fallback
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
VAULT      = Path(VAULT)
VAULT_ORIG = Path(ORIGINALS)
def _resolve_offsite():
    """Resolve the offsite folder the SAME way the writer does (single source of truth).

    The checker used to hardcode the HP17 laptop path, so on the hub (where Drive is
    mirrored to machine.env GDRIVE_BACKUP_ROOT=D:\\GoogleDrive2023) it checked a folder
    that does not exist and screamed PROBLEM while the backup was landing fine.
    Importing is side-effect-free: backup_to_drive guards its work behind __main__.
    """
    try:
        from backup_to_drive import resolve_drive
        drive = resolve_drive()
        if drive:
            return Path(drive)
    except Exception:
        pass
    return Path(r"E:\Google Drive on HP Palo Alto\Obsidian-Backup")   # HP17 fallback


TARGETS = {
    "drive-offsite": _resolve_offsite(),
    "local-C":       Path(r"C:\ObsidianBackup"),
}
TASK        = "Obsidian Backup to Drive"
STALE_DAYS  = 2    # newer than this  -> healthy daily backup
BROKEN_DAYS = 8    # older than this  -> backup has clearly stopped
OUTDIR      = Path(IMPORTS) / "backup_health"


def p(*a):
    print(" ".join(str(x) for x in a).encode("ascii", "replace").decode("ascii"))


def newest_bundle(folder: Path):
    b = sorted(folder.glob("Owner-Knowledge-*.bundle")) if folder.exists() else []
    return b[-1] if b else None


def age_days(b: Path):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", b.name)
    if m:
        try:
            return (datetime.now() - datetime(int(m[1]), int(m[2]), int(m[3]))).days
        except ValueError:
            pass
    return (datetime.now() - datetime.fromtimestamp(b.stat().st_mtime)).days


def git_verify(b: Path):
    return subprocess.run(["git", "-C", str(VAULT), "bundle", "verify", str(b)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").returncode == 0


def count_files(folder: Path):
    return sum(1 for f in folder.rglob("*") if f.is_file()) if folder.exists() else 0


def task_info():
    try:
        r = subprocess.run(["schtasks", "/query", "/TN", TASK, "/FO", "LIST", "/V"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return {"found": False}
        info = {"found": True}
        for ln in r.stdout.splitlines():
            low = ln.lower()
            if "last result" in low and "last_result" not in info:
                info["last_result"] = ln.split(":", 1)[1].strip()
            elif "last run time" in low:
                info["last_run"] = ln.split(":", 1)[1].strip()
            elif "scheduled task state" in low:
                info["state"] = ln.split(":", 1)[1].strip()
            elif "next run time" in low:
                info["next_run"] = ln.split(":", 1)[1].strip()
        return info
    except Exception as e:
        return {"found": False, "err": str(e)[:80]}


def main():
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = datetime.now().strftime("%Y-%m-%d")
    problems, L = [], ["# Backup healthcheck  %s" % now, ""]

    src_orig = count_files(VAULT_ORIG)

    for name, root in TARGETS.items():
        L.append("## %s  (%s)" % (name, root))
        b = newest_bundle(root / "vault")
        if not b:
            problems.append("%s: NO bundle found -> backup not landing here" % name)
            L += ["- bundle: **MISSING**", ""]
            continue
        a = age_days(b)
        mb = b.stat().st_size / (1024 * 1024)
        fresh = "OK" if a <= STALE_DAYS else ("STALE" if a <= BROKEN_DAYS else "BROKEN")
        if fresh == "BROKEN":
            problems.append("%s: newest bundle is %d days old (backup stopped?)" % (name, a))
        elif fresh == "STALE":
            problems.append("%s: newest bundle is %d days old (PC off all week? check)" % (name, a))
        L.append("- bundle: %s  (%.0f MB, %d day(s) old) [%s]" % (b.name, mb, a, fresh))
        ok = git_verify(b)
        if not ok:
            problems.append("%s: bundle FAILED git verify (corruption)" % name)
        L.append("- integrity (git bundle verify): %s" % ("OK" if ok else "**FAILED**"))
        n = count_files(root / "_originals")
        if n < src_orig:
            problems.append("%s: _originals has %d files < source %d (copy lagging)" % (name, n, src_orig))
        L += ["- _originals files: %d (source has %d)" % (n, src_orig), ""]

    ti = task_info()
    L.append("## Windows task '%s'" % TASK)
    if not ti.get("found"):
        problems.append("Windows backup task '%s' MISSING (deleted?)" % TASK)
        L.append("- **NOT FOUND**")
    else:
        st = ti.get("state", "?"); lr = ti.get("last_result", "?")
        L.append("- state: %s  last result: %s  last run: %s  next: %s"
                 % (st, lr, ti.get("last_run", "?"), ti.get("next_run", "?")))
        if "disabl" in st.lower():
            problems.append("Windows backup task is DISABLED")
        if lr not in ("0", "0x0", "267011", "0x41303", "?"):   # 0x41303 = not yet run
            problems.append("Windows task last result = %s (not success)" % lr)
    L.append("")

    status = "OK" if not problems else "PROBLEM"
    L.append("## VERDICT: %s" % status)
    L += ["- [ ] %s" % pr for pr in problems]

    OUTDIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(L) + "\n"
    (OUTDIR / ("health-%s.md" % date)).write_text(body, encoding="utf-8")
    (OUTDIR / "health-latest.md").write_text(body, encoding="utf-8")

    p("=" * 60); p("BACKUP HEALTHCHECK", now)
    for name, root in TARGETS.items():
        b = newest_bundle(root / "vault")
        p(" ", name, ":", (b.name + " %d day(s) old" % age_days(b)) if b else "NO BUNDLE")
    if problems:
        p("problems:", len(problems))
        for pr in problems:
            p("  -", pr)
    p("verdict:", str(OUTDIR / "health-latest.md"))
    p("STATUS", status)
    sys.exit(0 if status == "OK" else 1)


if __name__ == "__main__":
    main()
