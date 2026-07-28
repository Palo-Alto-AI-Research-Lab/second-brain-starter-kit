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
"""Phase 4a: condense each >=20-msg person's DM into a compact transcript and pack into
synth batches for subagent person-note synthesis. Stdout ASCII-only."""
import re, json
from pathlib import Path
from collections import defaultdict
import os
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OUTDIR = Path(os.path.join(_IROOT, "dm", "synth_batches5"))
OUTDIR.mkdir(parents=True, exist_ok=True)
Path(os.path.join(_IROOT, "dm", "synth_out5")).mkdir(parents=True, exist_ok=True)

rows = [json.loads(l) for l in open(os.path.join(_IROOT, "dm-archive.jsonl"), encoding='utf-8')]
idx = json.load(open(os.path.join(_IROOT, "dm-index.json"), encoding='utf-8'))
targets = json.load(open(os.path.join(_IROOT, "dm-person-targets.json"), encoding='utf-8'))
needed = set(json.load(open(os.path.join(_IROOT, "dm-synth-needed.json"), encoding='utf-8')))

BATCH = 16
CHAR_BUDGET = 6500
MSG_CAP = 75
PER_MSG = 360

def first_token(name):
    base = re.sub(r'\s*\(tg:\d+\)\s*$', '', name).strip()
    if re.fullmatch(r'(?i)lead', base) or not base: return 'Контакт'
    return base.split()[0]

by_pid = defaultdict(list)
for r in rows:
    by_pid[r['pid']].append(r)

people = []
for pid in needed:
    m = idx[pid]
    prows = sorted(by_pid[pid], key=lambda r: r['ts'])
    fname = first_token(m['name'])
    # select messages: all 'post', sampled 'fragment', plus first 3 & last 2
    posts = [r for r in prows if r['cls'] == 'post']
    frags = [r for r in prows if r['cls'] == 'fragment']
    keep = {id(r) for r in posts}
    # even-sample fragments
    if frags:
        need = max(0, MSG_CAP - len(posts))
        if need and len(frags) > need:
            step = len(frags) / need
            sampled = [frags[int(i*step)] for i in range(need)]
        else:
            sampled = frags
        for r in sampled: keep.add(id(r))
    for r in prows[:3] + prows[-2:]:
        keep.add(id(r))
    sel = [r for r in prows if id(r) in keep]
    sel.sort(key=lambda r: r['ts'])
    # build transcript within budget
    lines, used = [], 0
    for r in sel:
        who = 'Антон' if r['role'] == 'account' else fname
        txt = re.sub(r'\s+', ' ', r['text']).strip()[:PER_MSG]
        line = f"{r['date']} [{who}]: {txt}"
        if used + len(line) > CHAR_BUDGET and lines:
            break
        lines.append(line); used += len(line)
    transcript = '\n'.join(lines)
    people.append(dict(
        pid=pid, target_slug=targets[pid]['slug'], name=m['name'],
        username=m['username'], tg_id=m['lead_id'], years=m['years'],
        total=m['total'], anton=m['acct'], contact=m['lead'],
        first=m['first_ts'][:10], last=m['last_ts'][:10],
        top_domains=m['top_domains'][:6], transcript=transcript))

# order by volume desc so early batches are the richest (good for test batch)
people.sort(key=lambda p: -p['total'])
batches = [people[i:i+BATCH] for i in range(0, len(people), BATCH)]
for bi, b in enumerate(batches, 1):
    Path(OUTDIR / f"batch_{bi:04d}.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=1), encoding='utf-8')

print("people_to_synth=%d  batches=%d  (size=%d)" % (len(people), len(batches), BATCH))
print("avg transcript chars:", sum(len(p['transcript']) for p in people)//max(1,len(people)))
print("batches ->", OUTDIR)
