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
"""Incremental aggregate: validate synth_out2, merge reused prior synth, assign STABLE slugs
(existing contacts reuse their vault slug by tg_id; new get clean slugs). Stdout ASCII-only."""
import re, json, glob
from pathlib import Path
from collections import defaultdict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

BDIR = Path(IMPORTS) / "dm" / "synth_batches2"
ODIR = Path(IMPORTS) / "dm" / "synth_out2"
idx = json.load(open(Path(IMPORTS) / "dm-index.json", encoding='utf-8'))
targets = json.load(open(Path(IMPORTS) / "dm-person-targets.json", encoding='utf-8'))
old_synth = json.load(open(Path(IMPORTS) / "_bak_2018" / "dm-synth-all.json", encoding='utf-8'))
people_cat = json.load(open(Path(IMPORTS) / "people_catalog.json", encoding='utf-8'))

TRANSLIT={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
 'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
 'ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def translit(s): return ''.join(TRANSLIT.get(c.lower(),c) for c in s)
def slugify(s):
    s=translit(s or '').lower(); s=re.sub(r'[^a-z0-9\s-]','',s); s=re.sub(r'[\s_-]+','-',s).strip('-')
    return s[:50]

# ---- validate + collect new synth ----
records={}; problems=[]
nb=len(list(BDIR.glob('batch_*.json')))
for bi in range(1,nb+1):
    inp=json.load(open(BDIR/f"batch_{bi:04d}.json",encoding='utf-8'))
    in_pids=[p['pid'] for p in inp]
    of=ODIR/f"batch_{bi:04d}.json"
    if not of.exists(): problems.append(f"batch {bi}: OUTPUT MISSING ({in_pids})"); continue
    try: out=json.load(open(of,encoding='utf-8'))
    except Exception as e: problems.append(f"batch {bi}: JSON ERR {e}"); continue
    obp={str(r.get('pid')):r for r in out}
    miss=[p for p in in_pids if p not in obp]
    if miss: problems.append(f"batch {bi}: missing {len(miss)}: {miss}")
    for r in out: records[str(r.get('pid'))]=r

# merge reused prior synth for reuse pids
n_reuse=0
for pid,t in targets.items():
    if t['has_note'] and t.get('reuse_synth') and pid not in records and pid in old_synth:
        records[pid]=old_synth[pid]; n_reuse+=1

# missing has_note people (need patch)
missing_note=[pid for pid,t in targets.items() if t['has_note'] and pid not in records]

# ---- stable slug assignment ----
reserved=set()
for p in people_cat:
    s=p['slug']; reserved.add((s[7:] if s.startswith('person-') else s).lower())
order=sorted(idx.keys(), key=lambda pid:-idx[pid]['total'])
folder_slug={}; person_slug={}; used=set()
for pid in order:
    t=targets[pid]; total=idx[pid]['total']
    if total < 5:
        folder_slug[pid]=None; person_slug[pid]=None; continue
    if t['has_note'] and t.get('existing') and t.get('existing_slug'):
        es=t['existing_slug']
        bare=es[7:] if es.startswith('person-') else es
        folder_slug[pid]=bare; person_slug[pid]=es; used.add(bare); continue
    # new note OR archive-only -> need a base slug
    rec=records.get(pid)
    if t['has_note'] and rec and rec.get('display_name') and not re.match(r'(?i)^tg:',rec['display_name'].strip()):
        base=slugify(rec['display_name']) or idx[pid]['slug']
    else:
        base=idx[pid]['slug']
    cand=base; k=2
    while cand in used or cand in reserved:
        cand=f"{base}-{k}"; k+=1
    used.add(cand); folder_slug[pid]=cand
    person_slug[pid]=(f"person-{cand}" if t['has_note'] else None)

# new concept proposals
new_concepts=defaultdict(int)
for r in records.values():
    for c in [r.get('primary_concept','')]+(r.get('concepts_secondary') or []):
        if isinstance(c,str) and c.startswith('NEW:'): new_concepts[c[4:]]+=1

# ---- write outputs ----
all_out={}
for pid,t in targets.items():
    if not t['has_note']: continue
    r=dict(records.get(pid,{})); r['pid']=pid
    r['folder_slug']=folder_slug.get(pid); r['person_slug']=person_slug.get(pid); r['has_note']=True
    r['existing']=t.get('existing',False)
    all_out[pid]=r
(Path(IMPORTS) / "dm-synth-all.json").write_text(json.dumps(all_out,ensure_ascii=False,indent=1),encoding='utf-8')
(Path(IMPORTS) / "dm-folderslug.json").write_text(json.dumps(folder_slug,ensure_ascii=False,indent=1),encoding='utf-8')
(Path(IMPORTS) / "dm-personslug.json").write_text(json.dumps(person_slug,ensure_ascii=False,indent=1),encoding='utf-8')
(Path(IMPORTS) / "dm-new-concepts.json").write_text(json.dumps(dict(new_concepts),ensure_ascii=False,indent=1),encoding='utf-8')

n_notes=sum(1 for t in targets.values() if t['has_note'])
print("synth records: %d (new+reuse)  reuse_merged=%d" % (len(records), n_reuse))
print("has_note people: %d  | records present: %d  | MISSING(need patch): %d" % (
    n_notes, sum(1 for pid in all_out), len(missing_note)))
print("archive folders (>=5): %d" % sum(1 for v in folder_slug.values() if v))
print("PROBLEMS: %d" % len(problems))
for p in problems[:40]: print("  -",p)
if missing_note: print("MISSING NOTE PIDS:", missing_note[:40])
print("NEW concept proposals:", dict(new_concepts))
