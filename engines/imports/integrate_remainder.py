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
"""Final pass: handle transcript-parent files in collection folders and
Telegram sessions missing concept:. Never touches files that already have concept:."""
import re
from pathlib import Path

V = Path("E:/Obsidian/Owner-Knowledge")
concept_files = {f.stem for f in (V / "06-Concepts").glob("*.md")}

# Collection folder → (concept, origin, authored_by)
COLLECTION_MAP = {
    "Crypto": ("concept-blockchain", "external", "ai"),
    "Foerster-and-AltHistory": ("concept-alternative-history", "external", "ai"),
    "Longevity-Biohacking": ("concept-longevity", "external", "ai"),
}

applied = 0; log = []

conv = V / "01-Conversations"

# 1. Handle collection folders
for coll_name, (prim, origin, authored_by) in COLLECTION_MAP.items():
    coll_dirs = [p for p in conv.rglob(coll_name) if p.is_dir()]
    for coll_dir in coll_dirs:
        # Only touch files directly in this folder (transcript-parent files),
        # not nested episode files (those were handled by integrate_transcripts2.py)
        for fpath in list(coll_dir.glob("*.md")) + list(coll_dir.rglob("*.md")):
            try:
                t = open(fpath, encoding="utf-8", errors="ignore").read()
            except: continue
            m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
            if not m: continue
            h, fm, e, body = m.groups()
            if re.search(r"^concept:\s", fm, re.M): continue
            # Add fields
            if not re.search(r"^origin:", fm, re.M):
                fm = fm.rstrip() + f"\norigin: {origin}"
            if not re.search(r"^authored_by:", fm, re.M):
                fm = fm.rstrip() + f"\nauthored_by: {authored_by}"
            if prim in concept_files:
                fm = fm.rstrip() + f'\nconcept: "[[{prim}]]"'
                open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
                applied += 1

# 2. Handle Telegram sessions missing concept: (origin: anton already set)
sessions_path = conv / "Telegram" / "Arhiv-Golosa" / "sessions"
if sessions_path.exists():
    for fpath in sessions_path.glob("*.md"):
        try:
            t = open(fpath, encoding="utf-8", errors="ignore").read()
        except: continue
        m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
        if not m: continue
        h, fm, e, body = m.groups()
        if re.search(r"^concept:\s", fm, re.M): continue
        # Sessions = life-observations (mixed topics)
        prim = "concept-life-observations"
        if prim in concept_files:
            fm = fm.rstrip() + f'\nconcept: "[[{prim}]]"'
            open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
            applied += 1

# 3. Handle Other subfolder
other_dirs = [p for p in conv.rglob("Other") if p.is_dir()]
for other_dir in other_dirs:
    for fpath in other_dir.rglob("*.md"):
        try:
            t = open(fpath, encoding="utf-8", errors="ignore").read()
        except: continue
        m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
        if not m: continue
        h, fm, e, body = m.groups()
        if re.search(r"^concept:\s", fm, re.M): continue
        prim = "concept-life-observations"
        if not re.search(r"^origin:", fm, re.M):
            fm = fm.rstrip() + "\norigin: external"
        if not re.search(r"^authored_by:", fm, re.M):
            fm = fm.rstrip() + "\nauthored_by: ai"
        fm = fm.rstrip() + f'\nconcept: "[[{prim}]]"'
        open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
        applied += 1

log.append(f"applied={applied}")
open("E:/Obsidian/_imports/_integrate_remainder_log.txt", "w", encoding="utf-8").write("\n".join(log))
