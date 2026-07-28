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
"""Phase 4b: validate + aggregate synth outputs; build authoritative clean slugs.
Stdout ASCII-only. Reports any missing pids per batch."""
import re, json
from pathlib import Path
from collections import defaultdict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

BDIR = Path(IMPORTS) / "dm" / "synth_batches"
ODIR = Path(IMPORTS) / "dm" / "synth_out"
idx = json.load(open(Path(IMPORTS) / "dm-index.json", encoding='utf-8'))
targets = json.load(open(Path(IMPORTS) / "dm-person-targets.json", encoding='utf-8'))
people_cat = json.load(open(Path(IMPORTS) / "people_catalog.json", encoding='utf-8'))

TRANSLIT = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i',
 'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
 'ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def translit(s): return ''.join(TRANSLIT.get(c.lower(), c) for c in s)
def slugify(s):
    s = translit(s or '').lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    return s[:50]

# ---- validate + collect ----
records = {}
problems = []
n_batches = len(list(BDIR.glob('batch_*.json')))
for bi in range(1, n_batches+1):
    inp = json.load(open(BDIR / f"batch_{bi:04d}.json", encoding='utf-8'))
    in_pids = [p['pid'] for p in inp]
    of = ODIR / f"batch_{bi:04d}.json"
    if not of.exists():
        problems.append(f"batch {bi}: OUTPUT MISSING"); continue
    try:
        out = json.load(open(of, encoding='utf-8'))
    except Exception as e:
        problems.append(f"batch {bi}: JSON ERROR {e}"); continue
    out_by_pid = {str(r.get('pid')): r for r in out}
    missing = [p for p in in_pids if p not in out_by_pid]
    extra = [p for p in out_by_pid if p not in set(in_pids)]
    if missing: problems.append(f"batch {bi}: missing {len(missing)} pids: {missing}")
    if extra: problems.append(f"batch {bi}: {len(extra)} extra pids: {extra}")
    for r in out:
        records[str(r.get('pid'))] = r

# ---- authoritative clean slugs (folder + person), collision-safe ----
reserved = set()
for p in people_cat:
    s = p['slug']
    reserved.add(s[7:] if s.startswith('person-') else s.lower())

order = sorted(idx.keys(), key=lambda pid: -idx[pid]['total'])  # bigger relationships pick first
folder_slug = {}
used = set()
for pid in order:
    has_note = targets[pid]['has_note']
    rec = records.get(pid)
    if has_note and rec and rec.get('display_name') and not re.match(r'(?i)^tg:', rec['display_name'].strip()):
        base = slugify(rec['display_name']) or idx[pid]['slug']
    else:
        base = idx[pid]['slug']            # keep deterministic (anonymous / non-synth)
    cand = base; k = 2
    while cand in used or cand in reserved:
        cand = f"{base}-{k}"; k += 1
    used.add(cand)
    folder_slug[pid] = cand

person_slug = {pid: (f"person-{folder_slug[pid]}" if targets[pid]['has_note'] else None)
               for pid in idx}

# ---- collect NEW concept proposals ----
new_concepts = defaultdict(int)
for r in records.values():
    for key in ['primary_concept'] + (r.get('concepts_secondary') or []):
        pass
    pc = r.get('primary_concept','')
    if isinstance(pc,str) and pc.startswith('NEW:'): new_concepts[pc[4:]] += 1
    for c in (r.get('concepts_secondary') or []):
        if isinstance(c,str) and c.startswith('NEW:'): new_concepts[c[4:]] += 1

# ---- write outputs ----
all_out = {}
for pid in idx:
    r = dict(records.get(pid, {}))
    r['pid'] = pid
    r['folder_slug'] = folder_slug[pid]
    r['person_slug'] = person_slug[pid]
    r['has_note'] = targets[pid]['has_note']
    all_out[pid] = r
(Path(IMPORTS) / "dm-synth-all.json").write_text(json.dumps(all_out, ensure_ascii=False, indent=1), encoding='utf-8')
(Path(IMPORTS) / "dm-folderslug.json").write_text(json.dumps(folder_slug, ensure_ascii=False, indent=1), encoding='utf-8')
(Path(IMPORTS) / "dm-personslug.json").write_text(json.dumps(person_slug, ensure_ascii=False, indent=1), encoding='utf-8')
(Path(IMPORTS) / "dm-new-concepts.json").write_text(json.dumps(dict(new_concepts), ensure_ascii=False, indent=1), encoding='utf-8')

print("synth records collected: %d / %d people-with-notes" % (len(records), sum(1 for t in targets.values() if t['has_note'])))
print("PROBLEMS: %d" % len(problems))
for p in problems: print("  -", p)
print("NEW concept proposals (%d distinct):" % len(new_concepts))
for c,n in sorted(new_concepts.items(), key=lambda kv:-kv[1]): print("   %2d  %s" % (n, c))
