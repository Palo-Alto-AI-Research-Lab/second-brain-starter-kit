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
"""FAAA Phase 8 — wikilink integrity over staging (vs staging+vault basenames).
ASCII-only stdout; details to _validate.txt.
"""
import re, io, os
from collections import Counter
from pathlib import Path

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
STAGE = Path(IMPORTS) / "staging"
VAULT = Path(VAULT)

names = set()
for base in (STAGE, VAULT):
    if base.exists():
        for p in base.rglob("*.md"):
            names.add(p.stem)

LINK = re.compile(r'\[\[([^\]\|#]+)')
broken = Counter()
total = 0
files_with_broken = set()
nfiles = 0
for p in STAGE.rglob("*.md"):
    nfiles += 1
    t = io.open(p, encoding="utf-8").read()
    for mm in LINK.finditer(t):
        tgt = mm.group(1).rstrip('\\').strip()
        if not tgt:
            continue
        total += 1
        if tgt not in names:
            broken[tgt] += 1
            files_with_broken.add(str(p))

r = io.open(Path(IMPORTS) / "faaa" / "_validate.txt", "w", encoding="utf-8")
r.write("staging files: %d\n" % nfiles)
r.write("total wikilinks: %d\n" % total)
r.write("distinct broken targets: %d\n" % len(broken))
r.write("total broken links: %d\n" % sum(broken.values()))
r.write("files containing broken links: %d\n\n" % len(files_with_broken))
r.write("=== top broken targets ===\n")
for t, c in broken.most_common(60):
    r.write("  %4d  %s\n" % (c, t))
r.close()
print("DONE files=%d links=%d broken_distinct=%d broken_total=%d"
      % (nfiles, total, len(broken), sum(broken.values())))
