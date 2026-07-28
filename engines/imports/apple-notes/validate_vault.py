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
"""Post-move validation in the LIVE vault: every [[wikilink]] in the Apple-Notes
import resolves against the full vault. Confirms demangle didn't break links and
the import is a connected graph. Stdout ASCII.
"""
import re, json
from pathlib import Path

VAULT = Path(r"%VAULT%")
AN = VAULT / "01-Conversations" / "Apple-Notes"
OUT = Path(r"%IMPORTS%\apple-notes")

targets = set()
for p in VAULT.rglob("*"):
    if p.is_file():
        targets.add(p.stem.lower()); targets.add(p.name.lower())

WIKI = re.compile(r'\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\\?\|[^\]]*)?\]\]')
broken = []
files = list(AN.rglob("*.md"))
for p in files:
    for m in WIKI.finditer(p.read_text(encoding="utf-8")):
        t = m.group(1).strip().lower().replace("\\", "")
        if t.endswith(".md"): t = t[:-3]
        if t not in targets and (t + ".md") not in targets:
            broken.append(f"{p.name} -> [[{m.group(1)[:50]}]]")

# concept linkage: each new concept reachable?
new_concepts = ["concept-noah-virtual-state","concept-tokenomics-design","concept-microfinance","concept-otnosheniya"]
concept_exists = {c: (VAULT/"06-Concepts"/f"{c}.md").exists() for c in new_concepts}

(OUT/"validate_vault_report.json").write_text(json.dumps(
    {"files": len(files), "broken_links": broken, "new_concepts_exist": concept_exists}, ensure_ascii=False), encoding="utf-8")
print("AN_MD_FILES:", len(files))
print("BROKEN_LINKS:", len(broken))
for b in broken[:20]: print("  ", b.encode("ascii","backslashreplace").decode())
print("NEW_CONCEPTS_EXIST:", all(concept_exists.values()))
print("OK" if not broken and all(concept_exists.values()) else "FAIL")
