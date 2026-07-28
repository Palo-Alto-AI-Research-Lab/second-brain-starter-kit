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
"""backup_to_drive.py — 3-2-1 backup of the Obsidian vault + originals.

Writes consolidated, restorable artifacts to TWO places:
  * Google Drive (OFFSITE / cloud) : account owner.personal@example.com, path resolved per machine
        by resolve_drive() (hub: machine.env GDRIVE_BACKUP_ROOT=D:\\GoogleDrive2023 mirror;
        HP17: "E:\\Google Drive on HP Palo Alto"; else any DriveFS letter mount).
  * Local second disk (C:)         : "C:\\ObsidianBackup"  (separate physical SSD from E:).
=> E: working copy + C: local copy + Google cloud = 3 copies, 2 media, 1 offsite.

What it backs up (NOT a live folder-sync):
  1. The vault as a single git BUNDLE (full history) -> one file, restorable/migratable anywhere.
  2. _originals/ via COPY-ONLY (robocopy /E /XO, never /MIR) -> deletions never propagate.

Why bundle, not sync the folders: one file vs 90k loose files, no live-.git corruption,
no Obsidian "conflict copies", and ransomware/accidental-delete on E: can't wipe the cloud
copy (each bundle is a fresh dated file we never rewrite; _originals is copy-only).

Run:  $env:PYTHONUTF8=1; python backup_to_drive.py
ASCII-only stdout (cp1252 safety).
"""
import sys, subprocess, shutil
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
VAULT     = Path(VAULT)
ORIGINALS = Path(ORIGINALS)
IMPORTS   = Path(IMPORTS)
LOCAL     = Path(r"C:\ObsidianBackup")                 # separate physical disk
KEEP_BUNDLES = 14
# code repos that have local git history but were NOT offsite (added 2026-06-16) ->
# bundle them too so their history survives a disk death, not just the vault.
EXTRA_REPOS = [Path(r"%VAULT_ROOT%\scripts"), IMPORTS]


def p(*a):
    print(" ".join(str(x) for x in a).encode("ascii", "replace").decode("ascii"))


def _machine_env(key):
    """Read one key from ~/.claude/machine.env (per-machine, NOT synced). None if absent."""
    try:
        for ln in (Path.home() / ".claude" / "machine.env").read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                if k.strip() == key:
                    return v.strip()
    except Exception:
        pass
    return None


def resolve_drive():
    """Find the writable Google Drive (owner.personal@example.com) backup folder on THIS machine.
    Priority: machine.env GDRIVE_BACKUP_ROOT (per-machine override; the hub mirrors a@ into a
    local folder, e.g. D:\\GoogleDrive2023) -> laptop's known path -> E: glob -> any DriveFS
    letter mount (G:/H:/I:/... move when Drive re-mounts) that already holds Obsidian-Backup."""
    root = _machine_env("GDRIVE_BACKUP_ROOT")
    if root and Path(root).exists():
        return Path(root) / "Obsidian-Backup"
    known = Path(r"E:\Google Drive on HP Palo Alto")
    if known.exists():
        return known / "Obsidian-Backup"
    for base in Path("E:\\").glob("Google Drive on*"):   # portable-ish fallback
        return base / "Obsidian-Backup"
    for letter in "DEFGHIJKLMNOP":                       # DriveFS letters roam (H: became I:)
        for mount in ("My Drive", "GoogleDrive2023"):
            cand = Path("%s:\\" % letter) / mount / "Obsidian-Backup"
            try:
                if cand.exists():
                    return cand
            except OSError:
                pass
    return None


def git(*a, check=True):
    r = subprocess.run(["git", "-C", str(VAULT), *a], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        p("  ! git", a[0], "rc=", r.returncode, (r.stderr or "").strip()[:300])
    return r


def commit_vault():
    """Use the canonical vault_backup.py (standing rule) to git-commit current state."""
    vb = IMPORTS / "vault_backup.py"
    if vb.exists():
        r = subprocess.run([sys.executable, str(vb), "pre-drive-backup " + datetime.now().strftime("%Y-%m-%d %H:%M")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        for ln in (r.stdout or "").strip().splitlines()[-2:]:
            p("  ", ln)
    return git("rev-parse", "--short", "HEAD", check=False).stdout.strip()


def make_bundle(dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if git("bundle", "create", str(dst), "--all").returncode != 0 or not dst.exists():
        return False
    ok = git("bundle", "verify", str(dst), check=False).returncode == 0
    p("bundle verify:", "OK" if ok else "FAILED")
    return ok


def prune_bundles(folder: Path, keep: int, prefix: str = "Owner-Knowledge"):
    for old in sorted(folder.glob(prefix + "-*.bundle"))[:-keep]:
        try:
            old.unlink(); p("  pruned old bundle:", old.name)
        except Exception as e:
            p("  ! prune failed", old.name, str(e)[:120])


LOGDIR = LOCAL / "logs"   # robocopy evidence lives NEXT TO the backup, not in the synced/bundled _imports


def robocopy_no_delete(src: Path, dst: Path, tag: str = "", snap=None):
    # Full robocopy output is SAVED per run/target (visibility layer, 2026-07-22).
    # History: the "silent miss" scare of 07-21/07-22 turned out NOT to be robocopy's
    # fault - dr_nightly's originals_reconcile (05:50) moves peer-delivered files into
    # _originals AFTER a 02:00 backup, so they simply were not there yet (proven via
    # NTFS ChangeTime = 05:50:01 on every "missed" file). Fix = backup runs at 06:15,
    # after the DR chain (collect 05:05 -> janitor 05:50 -> backup). The verbose log
    # stays so any FUTURE miss is attributable instead of invisible.
    dst.mkdir(parents=True, exist_ok=True)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    stamp_log = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    logf = LOGDIR / ("robocopy-%s-%s.log" % (tag or "run", stamp_log))
    n = 1
    while logf.exists():   # same tag + same second (e.g. tests) must not clobber evidence
        n += 1
        logf = LOGDIR / ("robocopy-%s-%s-%d.log" % (tag or "run", stamp_log, n))
    cmd = ["robocopy", str(src), str(dst), "/E", "/XO", "/R:1", "/W:1",
           "/V", "/TS", "/FP", "/X", "/NP"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        logf.write_text(
            "CMD: %s\nRC : %d  (0-7 = success, 8+ = some files FAILED)\n%s\n%s%s"
            % (" ".join(cmd), r.returncode, "-" * 60, r.stdout or "",
               ("\nSTDERR:\n" + r.stderr) if (r.stderr or "").strip() else ""),
            encoding="utf-8")
    except Exception as e:
        p("  ! robocopy log write failed:", str(e)[:120])
    for old in sorted(LOGDIR.glob("robocopy-*.log"))[:-28]:   # ~14 days x 2 targets
        try:
            old.unlink()
        except Exception:
            pass
    p("  robocopy rc=%d log=%s" % (r.returncode, logf))
    ok = r.returncode < 8   # robocopy 0-7 = success, 8+ = error
    # Deterministic post-verify (2026-07-22): closes the whole class "a source file is
    # present yet absent in the target while the run reports OK", whatever the cause
    # (ordering bugs like the 05:50-janitor case, future robocopy quirks, locks). snap =
    # source file list captured BEFORE robocopy, so files created mid-run can't false-alarm.
    if snap is not None:
        missing = [n for n in snap if not (dst / n).exists()]
        if missing:
            ok = False
            p("  ! POST-VERIFY: %d source file(s) MISSING in %s (first 10):" % (len(missing), dst))
            for n in missing[:10]:
                p("    -", n)
            try:
                with logf.open("a", encoding="utf-8") as fh:
                    fh.write("\nPOST-VERIFY: %d file(s) missing in dst:\n" % len(missing))
                    fh.writelines("  %s\n" % n for n in missing)
            except Exception as e:
                p("  ! post-verify log append failed:", str(e)[:120])
        else:
            p("  post-verify: all %d source files present in target" % len(snap))
    return ok


def mb(path: Path):
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)


MIGRATE = """# Obsidian backup - restore / migrate to a new computer

Backup of Anton's Obsidian vault (account owner.personal@example.com). Two parts:
  - vault/Owner-Knowledge-<date>.bundle : the WHOLE vault + full git history in ONE file.
  - _originals/                         : verbatim raw import sources (append-only, never deleted).

Last backup: {stamp}    vault HEAD: {head}

## Migrate the whole vault to a new machine
1. Install Git + Obsidian. Sign into Google Drive (owner.personal@example.com) so this folder syncs down.
2. Take the NEWEST bundle in vault/.
3. Rebuild the repo with full history:
       git clone "Owner-Knowledge-<date>.bundle" Owner-Knowledge
4. Open the resulting "Owner-Knowledge" folder as an Obsidian vault. Done.

## Restore just one file/folder
       git clone "<newest>.bundle" tmp
       copy the file out of tmp\\  (or: git -C tmp restore --source <hash> -- <path>)

## _originals
Plain files - just copy the folder. This is the upstream source of truth (raw exports);
NEVER delete anything here.

Generated by %IMPORTS%\\backup_to_drive.py
"""


def backup_repos(targets, date):
    """Bundle the code repos (scripts, _imports) to the same targets, in a repos/ subfolder.
    Built once on C: then copied out, same pattern as the vault bundle. Code-only history."""
    for repo in EXTRA_REPOS:
        if not (repo / ".git").exists():
            p("  ! skip repo (no .git):", repo); continue
        name = repo.name                                   # 'scripts' | '_imports'
        bn   = "%s-%s.bundle" % (name, date)
        c_b  = LOCAL / "repos" / bn
        c_b.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "-C", str(repo), "bundle", "create", str(c_b), "--all"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not c_b.exists():
            p("  ! repo bundle FAILED:", name, (r.stderr or "").strip()[:160]); continue
        ok = subprocess.run(["git", "-C", str(repo), "bundle", "verify", str(c_b)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace").returncode == 0
        p("repo bundle:", bn, "%.1f MB" % mb(c_b), "verify:", "OK" if ok else "FAILED")
        for tname, root in targets:
            rdir = root / "repos"; rdir.mkdir(parents=True, exist_ok=True)
            dst = rdir / bn
            if dst.resolve() != c_b.resolve() and not (dst.exists() and dst.stat().st_size == c_b.stat().st_size):
                shutil.copy2(c_b, dst)
            prune_bundles(rdir, KEEP_BUNDLES, name)


def main():
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date  = datetime.now().strftime("%Y-%m-%d")
    p("=" * 60); p("BACKUP vault + _originals  ", stamp)

    # local-C (separate physical disk) ALWAYS runs -- the offsite/cloud copy is added only if
    # Drive is mounted here. Never hard-abort on a missing Drive folder, or a Drive remount/
    # unmount silently kills ALL backups (caught on the hub 2026-06-22 and again 2026-07-16).
    drive = resolve_drive()
    targets = [("local-C", LOCAL)]
    if drive:
        targets.insert(0, ("drive-offsite", drive))
    else:
        p("WARN: Google Drive offsite folder not found on this machine -> LOCAL-C backup ONLY.")
        p("      To restore the offsite copy, set GDRIVE_BACKUP_ROOT in ~/.claude/machine.env")
        p("      to the writable Drive folder for owner.personal@example.com on this box.")

    head = commit_vault()
    p("vault HEAD:", head)

    # build the bundle once on the local C: disk (fast, separate spindle), verify, then fan out
    bundle_name = "Owner-Knowledge-%s.bundle" % date
    c_bundle = LOCAL / "vault" / bundle_name
    p("-" * 60); p("building + verifying vault bundle ->", c_bundle)
    if not make_bundle(c_bundle):
        p("ABORT: bundle build/verify failed; nothing distributed."); sys.exit(1)
    p("bundle:", bundle_name, "%.0f MB" % mb(c_bundle))

    # one source snapshot for BOTH targets, taken before any robocopy (post-verify baseline)
    snap = [f.relative_to(ORIGINALS) for f in ORIGINALS.rglob("*") if f.is_file()]
    p("_originals source snapshot: %d files" % len(snap))

    results = []
    for name, root in targets:
        p("-" * 60); p("TARGET:", name, "->", root)
        try:
            vdir = root / "vault"; vdir.mkdir(parents=True, exist_ok=True)
            dst = vdir / bundle_name
            if dst.resolve() != c_bundle.resolve() and not (dst.exists() and dst.stat().st_size == c_bundle.stat().st_size):
                shutil.copy2(c_bundle, dst)
            prune_bundles(vdir, KEEP_BUNDLES)
            ok_orig = robocopy_no_delete(ORIGINALS, root / "_originals", name, snap=snap)
            (root / "MIGRATE.md").write_text(MIGRATE.format(stamp=stamp, head=head), encoding="utf-8")
            (root / "last-backup.txt").write_text(
                "last backup : %s\nvault HEAD  : %s\nbundle      : %s (%.0f MB)\n_originals  : %s (copy-only)\ntarget      : %s\n"
                % (stamp, head, bundle_name, mb(c_bundle), "OK" if ok_orig else "PARTIAL", name),
                encoding="utf-8")
            p("  wrote bundle + _originals(%s) + MIGRATE.md + last-backup.txt" % ("OK" if ok_orig else "PARTIAL"))
            results.append((name, ok_orig))
        except Exception as e:
            p("  ! target FAILED:", str(e)[:200]); results.append((name, False))

    p("-" * 60); p("bundling code repos ->", ", ".join(r.name for r in EXTRA_REPOS))
    backup_repos(targets, date)

    p("=" * 60)
    for name, ok in results:
        p("RESULT", name, ":", "OK" if ok else "FAILED")
    p("Google Drive uploads the new files to the cloud in the background.")
    sys.exit(0 if all(ok for _, ok in results) else 1)


if __name__ == "__main__":
    main()
