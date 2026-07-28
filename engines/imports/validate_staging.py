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
"""Phase 6: wikilink integrity over staging (resolving against staging + vault basenames).
Require 0 broken. Stdout ASCII-only; details to a UTF-8 report."""
import re, json
from pathlib import Path
from collections import Counter, defaultdict

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
STAGE = Path(IMPORTS) / "staging"
VAULT = Path(VAULT)

stems = set()
for base in (STAGE, VAULT):
    for p in base.rglob("*.md"):
        stems.add(p.stem)

WIKI = re.compile(r'\[\[([^\]]+)\]\]')
broken = Counter()
broken_where = defaultdict(list)
total_links = 0
files_scanned = 0

for p in STAGE.rglob("*.md"):
    files_scanned += 1
    txt = p.read_text(encoding='utf-8', errors='replace')
    for m in WIKI.finditer(txt):
        inner = m.group(1)
        target = inner.split('|')[0].rstrip('\\').split('#')[0].strip()
        if not target:        # self-heading link [[#sec]]
            continue
        total_links += 1
        if target not in stems:
            broken[target] += 1
            if len(broken_where[target]) < 5:
                broken_where[target].append(p.name)

rep = ["# Staging link validation", ""]
rep.append(f"files_scanned: {files_scanned}")
rep.append(f"total_wikilinks: {total_links}")
rep.append(f"distinct_broken_targets: {len(broken)}")
rep.append("")
if broken:
    rep.append("## Broken targets (count — sample files)")
    for t, n in sorted(broken.items(), key=lambda kv:-kv[1]):
        rep.append(f"- [[{t}]] x{n}  <- {', '.join(broken_where[t])}")
(Path(IMPORTS) / "dm_link_report.md").write_text('\n'.join(rep), encoding='utf-8')

print("files=%d links=%d broken_targets=%d broken_total=%d" % (
    files_scanned, total_links, len(broken), sum(broken.values())))
if broken:
    print("TOP BROKEN:")
    for t, n in sorted(broken.items(), key=lambda kv:-kv[1])[:20]:
        # ascii-safe: show repr
        print("  x%-4d %s" % (n, t.encode('ascii','replace').decode()))
else:
    print("ALL LINKS RESOLVE (0 broken)")
