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
"""Integrate new transcript-episode subfolders under 01-Conversations.
Sets: origin, authored_by (if missing), concept: primary wikilink.
External content (podcasts, lectures): origin: external, authored_by: ai
Dialogues (Anton + others): origin: mixed, authored_by: hybrid
Never deletes existing fields."""
import re, os, glob
from pathlib import Path

V = Path("E:/Obsidian/Owner-Knowledge")
CONC = V / "06-Concepts"
concept_files = {f.stem for f in CONC.glob("*.md")}

# Subfolder → (concept, origin, authored_by)
# external = podcasts/lectures not by Anton
# mixed = dialogues involving Anton
SUBFOLDER_MAP = {
    "Huberman": ("concept-biohacking-nutrition", "external", "ai"),
    "Huberman112": ("concept-biohacking-nutrition", "external", "ai"),
    "Huberman1p": ("concept-biohacking-nutrition", "external", "ai"),
    "Huberman2p": ("concept-biohacking-nutrition", "external", "ai"),
    "beloveshkin": ("concept-biomarkers", "external", "ai"),
    "beloveshkin_clean": ("concept-biomarkers", "external", "ai"),
    "vita dao": ("concept-vitadao", "external", "ai"),
    "Lifespan Research Institute": ("concept-longevity", "external", "ai"),
    "The Randall Carlson 45video": ("concept-alternative-history", "external", "ai"),
    "Old World Exploration": ("concept-alternative-history", "external", "ai"),
    "Mind unveiled": ("concept-simulation-hypothesis", "external", "ai"),
    "dialogues_work_acct_b_12_months": ("concept-life-observations", "mixed", "hybrid"),
    "dialogues_work_acct_b_before_2023": ("concept-life-observations", "mixed", "hybrid"),
    "Председатель СНТ_1": ("concept-construction-renovation", "external", "ai"),
    "Председатель СНТ_2": ("concept-construction-renovation", "external", "ai"),
}

SME = "## Смежные концепты"
applied = 0; skipped = 0
log = []

conv_path = V / "01-Conversations"

# Find all transcript-episode files in mapped subfolders
for subfolder_name, (prim_concept, origin, authored_by) in SUBFOLDER_MAP.items():
    # Find the subfolder anywhere under 01-Conversations
    matches = list(conv_path.rglob(subfolder_name))
    sub_dirs = [p for p in matches if p.is_dir()]
    if not sub_dirs:
        log.append(f"MISSING subfolder: {subfolder_name}")
        continue

    for sub_dir in sub_dirs:
        files = [f for f in sub_dir.rglob("*.md")]
        for fpath in files:
            try:
                t = open(fpath, encoding="utf-8", errors="ignore").read()
            except:
                skipped += 1; continue
            m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
            if not m:
                skipped += 1; continue
            h, fm, e, body = m.groups()

            has_origin = bool(re.search(r"^origin:", fm, re.M))
            has_concept = bool(re.search(r"^concept:\s", fm, re.M))
            has_authored = bool(re.search(r"^authored_by:", fm, re.M))
            if has_origin and has_concept:
                skipped += 1; continue

            changed = False

            if not has_origin:
                fm = fm.rstrip() + f"\norigin: {origin}"
                changed = True
            if not has_authored:
                fm = fm.rstrip() + f"\nauthored_by: {authored_by}"
                changed = True
            if not has_concept and prim_concept in concept_files:
                fm = fm.rstrip() + f'\nconcept: "[[{prim_concept}]]"'
                changed = True

            if changed:
                open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
                applied += 1
            else:
                skipped += 1

log.insert(0, f"TOTAL applied={applied} skipped={skipped}")
open("E:/Obsidian/_imports/_integrate_transcripts_log.txt", "w", encoding="utf-8").write("\n".join(log))
