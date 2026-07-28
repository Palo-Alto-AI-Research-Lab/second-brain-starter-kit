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
"""Phase 7: selectively move ONLY the Personal-DMs import from staging into the vault.
Dry-run by default; set APPLY=1 to copy. Never clobbers existing vault files (reports + aborts).
Stdout ASCII-only."""
import os, json, shutil
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
my_person = {s for s in personslug.values() if s}   # 223 clean slugs

plan = []   # (src, dst)

# 1) Personal-DMs tree (conversations + MOC) -> vault
dm_src = STAGE / "01-Conversations" / "Telegram" / "Personal-DMs"
for p in dm_src.rglob("*.md"):
    rel = p.relative_to(STAGE)
    plan.append((p, VAULT / rel))

# 2) person notes (only my 223 slugs)
psrc = STAGE / "07-People"
staging_people = {p.stem for p in psrc.glob("person-*.md")}
extra = staging_people - my_person
missing = my_person - staging_people
for slug in sorted(my_person):
    f = psrc / (slug + ".md")
    if f.exists():
        plan.append((f, VAULT / "07-People" / (slug + ".md")))

# 3) the one new concept
csrc = STAGE / "06-Concepts" / "concept-crypto-exchange-listing.md"
if csrc.exists():
    plan.append((csrc, VAULT / "06-Concepts" / "concept-crypto-exchange-listing.md"))

# collision check: target already exists in vault?
collisions = [(s, d) for (s, d) in plan if d.exists()]

print("APPLY=%s" % APPLY)
print("planned copies: %d" % len(plan))
print("  Personal-DMs tree files: %d" % sum(1 for s,d in plan if 'Personal-DMs' in str(d)))
print("  person notes: %d (staging_people=%d, my=%d, stale_in_staging=%d, missing=%d)" % (
    sum(1 for s,d in plan if d.parent.name=='07-People'), len(staging_people), len(my_person), len(extra), len(missing)))
print("  concepts: %d" % sum(1 for s,d in plan if d.parent.name=='06-Concepts'))
if extra:
    print("  NOTE: %d staging 07-People files are NOT mine (skipped):" % len(extra), sorted(list(extra))[:5])
print("collisions (target exists in vault): %d" % len(collisions))
for s, d in collisions[:20]:
    print("  COLLIDE:", d.relative_to(VAULT))

if collisions and APPLY:
    print("ABORT: refusing to overwrite existing vault files."); raise SystemExit(1)

if APPLY:
    n = 0
    for s, d in plan:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        n += 1
    print("COPIED %d files into vault." % n)
else:
    print("(dry-run; set APPLY=1 to copy)")
