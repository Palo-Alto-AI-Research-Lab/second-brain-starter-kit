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
"""Phase 4 gate: every [[wikilink]] in staging must resolve to a staging or vault file."""
import re
from collections import Counter
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
STAGE = Path(r"E:/Obsidian/_imports/staging_pokupki")

vault_stems = {p.stem for p in VAULT.rglob("*.md")}
stage_files = list(STAGE.rglob("*.md"))
stage_stems = {p.stem for p in stage_files}
resolvable = vault_stems | stage_stems

LINK = re.compile(r"\[\[([^\]|#]+)")
broken = Counter()
total = 0
for p in stage_files:
    for m in LINK.finditer(p.read_text(encoding="utf-8")):
        tgt = m.group(1).strip().rstrip("\\")
        if not tgt:
            continue
        total += 1
        if tgt not in resolvable:
            broken[tgt] += 1

print(f"staging files {len(stage_files)} | vault stems {len(vault_stems)} | links {total} | BROKEN {len(broken)}")
for t, c in broken.most_common(25):
    print("  ", c, "->", t.encode("ascii", "replace").decode())
