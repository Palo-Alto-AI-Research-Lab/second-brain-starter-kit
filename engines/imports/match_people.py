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
"""Phase 2b: resolve each DM person -> person-note target (dedup vs existing 07-People).
Match by exact @handle or by FULL multi-token normalized name only (never single first-name).
Outputs dm-person-targets.json. Stdout ASCII-only."""
import os, re, json
from pathlib import Path

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

idx = json.load(open(os.path.join(IMPORTS, "dm-index.json"), encoding='utf-8'))
people = json.load(open(os.path.join(IMPORTS, "people_catalog.json"), encoding='utf-8'))

def norm_name(s):
    s = (s or '').lower()
    s = re.sub(r'\(tg:\d+\)', '', s)
    s = re.sub(r'[^a-zа-яё0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

# existing lookups
existing_slugs = {p['slug'] for p in people}
name_to_slug = {}
handle_to_slug = {}
for p in people:
    nt = p['norm_title']
    if nt and len(nt.split()) >= 2:      # full names only
        name_to_slug.setdefault(nt, p['slug'])
    for h in p.get('handles', []):
        handle_to_slug[h.lower()] = p['slug']
    # aliases may contain full names
    al = p.get('aliases') or ''
    for a in re.findall(r'"([^"]+)"', al):
        na = norm_name(a)
        if len(na.split()) >= 2:
            name_to_slug.setdefault(na, p['slug'])

targets = {}
used_new = set()
n_match_existing = 0
for pid, m in idx.items():
    name = m['name']
    uname = (m['username'] or '').lower()
    dmslug = m['slug']
    nn = norm_name(name)
    matched = None
    if uname and uname in handle_to_slug:
        matched = handle_to_slug[uname]
    elif len(nn.split()) >= 2 and nn in name_to_slug:
        matched = name_to_slug[nn]
    if matched:
        n_match_existing += 1
        targets[pid] = dict(slug=matched, has_note=True, existing=True,
                            name=name, username=m['username'], dmslug=dmslug,
                            total=m['total'])
        continue
    has_note = m['total'] >= 20
    new_slug = 'person-' + dmslug
    # collision-avoid against existing notes and other new ones
    if has_note:
        base = new_slug; k = 2
        while new_slug in existing_slugs or new_slug in used_new:
            new_slug = f"{base}-{k}"; k += 1
        used_new.add(new_slug)
    targets[pid] = dict(slug=(new_slug if has_note else None), has_note=has_note,
                        existing=False, name=name, username=m['username'],
                        dmslug=dmslug, total=m['total'])

Path(os.path.join(IMPORTS, "dm-person-targets.json")).write_text(
    json.dumps(targets, ensure_ascii=False, indent=1), encoding='utf-8')

n_notes = sum(1 for t in targets.values() if t['has_note'])
n_new = sum(1 for t in targets.values() if t['has_note'] and not t['existing'])
print("people=%d  will_have_note=%d  new=%d  matched_existing=%d" % (
    len(targets), n_notes, n_new, n_match_existing))
if n_match_existing:
    print("matched-existing examples:")
    for pid,t in list(targets.items()):
        if t['existing']:
            print("  %s  ->  %s" % (t['name'][:30], t['slug']))
