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
"""Incremental planning: resolve person-note targets with slug stability by tg_id,
decide synth-needed (new + grown) vs reuse-prior-synth. Stdout ASCII-only.
Thresholds: NOTE >=20 total msgs; ARCHIVE >=5 total msgs."""
import re, json, glob, os
from pathlib import Path
try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"

NOTE_THR = 20
ARCH_THR = 5
GROWN_NEW_MSGS = 20   # existing-noted person with >= this many msgs in >=2019 -> re-synth

idx = json.load(open(os.path.join(IMPORTS, "dm-index.json"), encoding='utf-8'))
old_synth = json.load(open(os.path.join(IMPORTS, "_bak_2018", "dm-synth-all.json"), encoding='utf-8'))
PEOPLE = Path(os.path.join(VAULT, "07-People"))

def norm_name(s):
    s=(s or '').lower(); s=re.sub(r'\(tg:\d+\)','',s); s=re.sub(r'[^a-zа-яё0-9 ]',' ',s)
    return re.sub(r'\s+',' ',s).strip()

# scan vault person notes
tgid2slug={}; handle2slug={}; name2slug_orig={}; dm_note_slugs=set()
for f in glob.glob(str(PEOPLE/'person-*.md')):
    p=Path(f); txt=p.read_text(encoding='utf-8',errors='replace')
    fm=txt.split('---',2)[1] if txt.startswith('---') else ''
    src=re.search(r'^source:\s*(.+)$',fm,re.M)
    is_dm = bool(src and 'telegram-personal-dm' in src.group(1))
    if is_dm: dm_note_slugs.add(p.stem)
    tg=re.search(r'^tg_id:\s*(\d+)',fm,re.M)
    if tg: tgid2slug[tg.group(1)]=p.stem
    for h in re.findall(r'@([A-Za-z0-9_]{3,32})', txt): handle2slug.setdefault(h.lower(),p.stem)
    title=re.search(r'^title:\s*"?(.+?)"?\s*$',fm,re.M)
    nt=norm_name(title.group(1)) if title else norm_name(p.stem.replace('person-','').replace('-',' '))
    if not is_dm and len(nt.split())>=2: name2slug_orig.setdefault(nt,p.stem)

targets={}; synth_needed=[]; reuse=[]; n_new=0; n_existing=0; n_grown=0
for pid,m in idx.items():
    total=m['total']
    has_note = total>=NOTE_THR
    has_arch = total>=ARCH_THR
    uname=(m['username'] or '').lower()
    nn=norm_name(m['name'])
    new_msgs = sum(n for y,n in m['per_year'].items() if int(y)>=2019)
    # resolve existing
    existing_slug=None
    if pid in tgid2slug: existing_slug=tgid2slug[pid]
    elif uname and uname in handle2slug: existing_slug=handle2slug[uname]
    elif len(nn.split())>=2 and nn in name2slug_orig: existing_slug=name2slug_orig[nn]
    existing = existing_slug is not None
    reuse_synth = False
    if has_note:
        if existing and existing_slug in dm_note_slugs and pid in old_synth and old_synth[pid].get('has_note') and new_msgs < GROWN_NEW_MSGS:
            reuse_synth = True; reuse.append(pid)
        else:
            synth_needed.append(pid)
            if existing: n_grown += 1
            else: n_new += 1
    if existing: n_existing += 1
    targets[pid]=dict(slug=existing_slug, has_note=has_note, has_archive=has_arch,
                      existing=existing, existing_slug=existing_slug, reuse_synth=reuse_synth,
                      name=m['name'], username=m['username'], dmslug=m['slug'], total=total,
                      new_msgs=new_msgs)

Path(os.path.join(IMPORTS,"dm-person-targets.json")).write_text(json.dumps(targets,ensure_ascii=False,indent=1),encoding='utf-8')
Path(os.path.join(IMPORTS,"dm-synth-needed.json")).write_text(json.dumps(synth_needed,ensure_ascii=False),encoding='utf-8')

print("NOTE_THR=%d ARCH_THR=%d" % (NOTE_THR,ARCH_THR))
print("people total: %d" % len(idx))
print("with note (>=20): %d" % sum(1 for t in targets.values() if t['has_note']))
print("with archive (>=5): %d" % sum(1 for t in targets.values() if t['has_archive']))
print("synth_needed: %d  (new=%d, grown-existing=%d)" % (len(synth_needed), n_new, n_grown))
print("reuse prior synth (static existing): %d" % len(reuse))
print("existing-note matches total: %d (dm tg_id reuse drives most)" % n_existing)
