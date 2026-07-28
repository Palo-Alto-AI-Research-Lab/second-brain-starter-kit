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
"""Phase 2: fingerprint existing vault people + concepts for dedup/reuse.
Outputs people_catalog.json, concept_catalog.json. Stdout ASCII-only."""
import re, json
from pathlib import Path
import os
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

VAULT = Path(_VROOT)
PEOPLE = VAULT / "07-People"
CONCEPTS = VAULT / "06-Concepts"

def frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m: return {}, text[ : 400]
    fm = {}
    for line in m.group(1).split('\n'):
        mm = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if mm:
            fm[mm.group(1).strip()] = mm.group(2).strip()
    return fm, text[m.end(): m.end()+400]

def norm_name(s):
    s = s.lower()
    s = re.sub(r'\(tg:\d+\)', '', s)
    s = re.sub(r'[^a-zа-яё0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

people = []
if PEOPLE.exists():
    for p in sorted(PEOPLE.glob("*.md")):
        text = p.read_text(encoding='utf-8', errors='replace')
        fm, _ = frontmatter(text)
        title = fm.get('title', '').strip('"\'')
        aliases = fm.get('aliases', '')
        # collect any telegram handles mentioned
        handles = set(re.findall(r'@([A-Za-z0-9_]{3,32})', text))
        people.append(dict(
            file=p.name, slug=p.stem, title=title, aliases=aliases,
            norm_title=norm_name(title or p.stem.replace('person-','').replace('-',' ')),
            handles=sorted(handles)[:10],
        ))

concepts = []
if CONCEPTS.exists():
    for p in sorted(CONCEPTS.glob("*.md")):
        text = p.read_text(encoding='utf-8', errors='replace')
        fm, body = frontmatter(text)
        title = fm.get('title', '').strip('"\'')
        # first non-empty body line as one-line def
        deftext = ''
        for ln in body.split('\n'):
            ln = ln.strip()
            if ln and not ln.startswith('#') and not ln.startswith('---'):
                deftext = ln[:160]; break
        concepts.append(dict(file=p.name, slug=p.stem, title=title, tags=fm.get('tags',''), one_line=deftext))

Path(os.path.join(_IROOT, "people_catalog.json")).write_text(
    json.dumps(people, ensure_ascii=False, indent=1), encoding='utf-8')
Path(os.path.join(_IROOT, "concept_catalog.json")).write_text(
    json.dumps(concepts, ensure_ascii=False, indent=1), encoding='utf-8')

# crypto/business-relevant concept slugs (quick ASCII preview)
crypto = [c['slug'] for c in concepts if re.search(r'crypto|blockchain|token|ico|defi|dex|wallet|web3|venture|startup|fundrais|invest|payment|stablecoin', c['slug'])]
print("existing_people=%d existing_concepts=%d" % (len(people), len(concepts)))
print("crypto/biz concepts (%d):" % len(crypto))
print(" ".join(crypto[:80]))
print("people_catalog -> people_catalog.json ; concept_catalog -> concept_catalog.json")
