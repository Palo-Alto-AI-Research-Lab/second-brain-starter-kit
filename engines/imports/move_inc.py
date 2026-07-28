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
"""Phase 14: incremental move of Personal-DMs from staging -> vault.
Overwrites MY OWN prior import (Personal-DMs tree + my person slugs + my concept), then removes
orphaned vault conversation files no longer in staging. Dry-run unless APPLY=1. Stdout ASCII-only."""
import os, json, shutil, re
from pathlib import Path

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"

APPLY = os.environ.get('APPLY') == '1'
STAGE = Path(os.path.join(IMPORTS, "staging"))
VAULT = Path(VAULT)
personslug = json.load(open(os.path.join(IMPORTS, "dm-personslug.json"), encoding='utf-8'))
my_person = {s for s in personslug.values() if s}

stage_dm = STAGE/"01-Conversations"/"Telegram"/"Personal-DMs"
vault_dm = VAULT/"01-Conversations"/"Telegram"/"Personal-DMs"

plan = []
for p in stage_dm.rglob("*.md"):
    plan.append((p, VAULT/ p.relative_to(STAGE)))
psrc = STAGE/"07-People"
for slug in sorted(my_person):
    f = psrc/(slug+".md")
    if f.exists(): plan.append((f, VAULT/"07-People"/(slug+".md")))
for _cn in ('concept-crypto-exchange-listing.md', 'concept-defi.md'):
    csrc = STAGE/"06-Concepts"/_cn; cdst = VAULT/"06-Concepts"/_cn
    if csrc.exists() and not cdst.exists():   # only NEW concepts; never overwrite a vault concept
        plan.append((csrc, cdst))

new = sum(1 for s,d in plan if not d.exists())
overwrite = sum(1 for s,d in plan if d.exists())

# orphan detection: vault Personal-DMs files not present in staging tree
stage_rel = {p.relative_to(stage_dm) for p in stage_dm.rglob("*.md")}
orphans = []
if vault_dm.exists():
    for p in vault_dm.rglob("*.md"):
        if p.relative_to(vault_dm) not in stage_rel:
            orphans.append(p)
# orphan person notes (DM-source notes whose slug no longer in my_person)
orphan_notes = []
for p in (VAULT/"07-People").glob("person-*.md"):
    if p.stem in my_person: continue
    t = p.read_text(encoding='utf-8', errors='replace')[:400]
    if 'telegram-personal-dm' in t:
        orphan_notes.append(p)

print("APPLY=%s" % APPLY)
print("plan copies: %d  (new=%d, overwrite-own-prior=%d)" % (len(plan), new, overwrite))
print("  Personal-DMs tree: %d  person notes: %d  concepts: %d" % (
    sum(1 for s,d in plan if 'Personal-DMs' in str(d)),
    sum(1 for s,d in plan if d.parent.name=='07-People'),
    sum(1 for s,d in plan if d.parent.name=='06-Concepts')))
print("orphan conversation files to delete: %d" % len(orphans))
for p in orphans[:10]: print("   orphan:", p.relative_to(vault_dm))
print("orphan DM person notes: %d" % len(orphan_notes))
for p in orphan_notes[:10]: print("   orphan-note:", p.name)

if APPLY:
    n=0
    for s,d in plan:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s,d); n+=1
    dele=0
    for p in orphans+orphan_notes:
        try: p.unlink(); dele+=1
        except Exception as e: print("  del-fail:", p.name, e)
    # prune empty dirs under vault_dm/conversations
    for d in sorted(vault_dm.rglob("*"), reverse=True):
        if d.is_dir():
            try: d.rmdir()
            except OSError: pass
    print("COPIED %d ; DELETED %d orphans." % (n, dele))
else:
    print("(dry-run; APPLY=1 to copy)")
