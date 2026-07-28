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
"""Read-only deterministic inventory of recently built/changed REUSABLE artifacts.
Shared by skill /retro and the daily preference-sweep (Part B). Arg: [days] (default 7).
Writes a UTF-8 digest; prints an ASCII summary line (Windows console safe)."""
import os
import sys, subprocess, pathlib, time, datetime

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
CUT = time.time() - DAYS * 86400

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
VAULT = pathlib.Path(VAULT)
IMP = pathlib.Path(IMPORTS)
SKILLS = pathlib.Path(os.path.expanduser("~")) / ".claude" / "skills"  # cross-OS (r"~\..." не раскрывается на POSIX)
OUTDIR = IMP / "retro_candidates"
OUTDIR.mkdir(exist_ok=True)

def recent(p):
    try:
        return p.stat().st_mtime >= CUT
    except OSError:
        return False

def stamp(p):
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

# new/changed skills (by SKILL.md mtime)
skills = sorted((d.name, stamp(d / "SKILL.md")) for d in (SKILLS.iterdir() if SKILLS.exists() else [])
                if (d / "SKILL.md").exists() and recent(d / "SKILL.md"))

# root-level scripts + sidecars in _imports, PLUS one level of engine subdirs.
# 2026-07-27: root-only scanning was a blind spot -- engines live in subdirs
# (content-factory/, arch/, tasks/, namesearch/), so a retro that built one saw
# NOTHING in its own inventory. Measured that day: 7 root vs 26 subdir scripts
# touched in 24h, i.e. the digest reported ~21% of real script activity.
# Still skip pure noise: Syncthing versions, caches, drafts, generated output.
SKIP_DIRS = {".stversions", "__pycache__", ".git", "node_modules",
             "_drafts", "retro_candidates", "triage", "episode-seeds"}

def _sub_files(pattern):
    for p in IMP.glob(pattern):
        if p.parent.name in SKIP_DIRS or not recent(p):
            continue
        yield (f"{p.parent.name}/{p.name}", stamp(p))

scripts = sorted([(p.name, stamp(p)) for p in IMP.glob("*.py") if recent(p)] +
                 [(p.name, stamp(p)) for p in IMP.glob("*.json") if recent(p) and p.stat().st_size < 60000] +
                 list(_sub_files("*/*.py")))

# durable notes (the permanent homes — not day-ledgers/leads noise)
notes = []
for sub in ["05-Resources/Protocols", "06-Concepts"]:
    d = VAULT / sub
    if d.exists():
        notes += [(f"{sub}/{p.name}", stamp(p)) for p in d.glob("*.md") if recent(p)]
notes = sorted(notes)

# recent DESCRIPTIVE vault commits (skip the terse auto-backups)
commits = []
try:
    out = subprocess.run(["git", "-C", str(VAULT), "log", f"--since={DAYS} days ago", "--pretty=%h %s"],
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    commits = [ln for ln in (out.stdout or "").splitlines()
               if "pre-intervention" not in ln and "pre-drive-backup" not in ln]
except Exception:
    pass

count = len(skills) + len(scripts) + len(notes)
L = [f"# Retro inventory — last {DAYS} days (built/changed reusable artifacts)", ""]
L += [f"## New/changed skills ({len(skills)})"] + ([f"- {n}  ({t})" for n, t in skills] or ["- (none)"])
L += ["", f"## _imports scripts/sidecars ({len(scripts)})"] + ([f"- {n}  ({t})" for n, t in scripts] or ["- (none)"])
L += ["", f"## Durable notes — Protocols + Concepts ({len(notes)})"] + ([f"- {n}  ({t})" for n, t in notes] or ["- (none)"])
L += ["", f"## Recent descriptive vault commits ({len(commits)})"] + ([f"- {c}" for c in commits[:40]] or ["- (none)"])
(OUTDIR / "digest-latest.md").write_text("\n".join(L), encoding="utf-8")

print(f"BUILT_ARTIFACTS {count}")
print("digest " + str(OUTDIR / "digest-latest.md"))
