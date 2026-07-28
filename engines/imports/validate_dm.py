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
"""Validate wikilinks in MY Personal-DMs staging files only (not other imports' staging leftovers),
resolving against vault stems + all staging stems. Require 0 broken. Stdout ASCII-only."""
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
personslug = json.load(open(Path(IMPORTS) / "dm-personslug.json", encoding='utf-8'))
my_person = {s for s in personslug.values() if s}

stems = set()
for base in (STAGE, VAULT):
    for p in base.rglob("*.md"):
        stems.add(p.stem)

targets = list((STAGE/"01-Conversations/Telegram/Personal-DMs").rglob("*.md"))
targets += [STAGE/"07-People"/(s+".md") for s in my_person]
targets += [STAGE/"06-Concepts"/"concept-crypto-exchange-listing.md"]

WIKI = re.compile(r'\[\[([^\]]+)\]\]')
broken = Counter(); where = defaultdict(list); total=0; scanned=0; missing_files=0
for p in targets:
    if not p.exists(): missing_files+=1; continue
    scanned+=1
    for m in WIKI.finditer(p.read_text(encoding='utf-8',errors='replace')):
        t = m.group(1).split('|')[0].rstrip('\\').split('#')[0].strip()
        if not t: continue
        total+=1
        if t not in stems:
            broken[t]+=1
            if len(where[t])<5: where[t].append(p.name)

print("scanned=%d  missing_target_files=%d  links=%d  broken=%d" % (scanned, missing_files, total, len(broken)))
if broken:
    for t,n in sorted(broken.items(), key=lambda kv:-kv[1])[:25]:
        print("  x%-4d %s  <- %s" % (n, t.encode('ascii','replace').decode(), where[t][0]))
else:
    print("ALL DM LINKS RESOLVE (0 broken)")
