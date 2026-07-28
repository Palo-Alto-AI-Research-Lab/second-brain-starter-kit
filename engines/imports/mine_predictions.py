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
"""Mine Anton's OWN notes for forward-looking statements (prediction candidates).
Deterministic first-pass: sentences with predictive markers + a time horizon.
Output sorted-by-date candidates for curation into a prediction ledger."""
import os, re, json
from pathlib import Path

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"

V = Path(VAULT)

# predictive markers (ru + en)
MARKERS = re.compile(
    r'(предсказ|прогноз|я (?:думаю|уверен|считаю|верю|ставлю)|'
    r'через \d+\s*(?:лет|год|года|месяц)|к 20\d\d|до 20\d\d|в 20\d\d\s*(?:году)?\s*(?:будет|станет)|'
    r'\bбудет\b|\bстанет\b|\bпроизойд|\bслучится|\bожидаю|\bскоро\b|'
    r'\bwill\b|\bgonna\b|in \d+ years?|by 20\d\d|\bpredict|\bexpect|\bbet that)',
    re.I)
HORIZON = re.compile(r'(через \d+\s*(?:лет|год|года|месяц)|к 20\d\d|до 20\d\d|by 20\d\d|in \d+ years?|20\d\d)', re.I)

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

cands = []
for dp, dirs, fs in os.walk(V):
    if '.obsidian' in dp or '06-Concepts' in dp: continue
    for fn in fs:
        if not fn.endswith('.md'): continue
        p = Path(dp)/fn
        t = p.read_text(encoding='utf-8', errors='ignore')
        if 'anton-original' not in t: continue
        if 'fb-duplicate' in t or 'fb-repost' in t: continue
        fm, body = fm_body(t)
        dm = re.search(r'^date:?\s*[\'"]?(\d{4}-\d{2}-\d{2})', fm, re.M) or re.search(r'(\d{4}-\d{2}-\d{2})', fn)
        date = dm.group(1) if dm else None
        if not date: continue
        cm = re.search(r'^concept:\s*"?\[\[([^\]\|]+)', fm, re.M)
        concept = cm.group(1) if cm else ''
        # split into sentences
        body = re.split(r'## See Also|## Legacy', body)[0]
        for sent in re.split(r'(?<=[.!?\n])\s+', body):
            sent = sent.strip()
            if len(sent) < 25 or len(sent) > 320: continue
            if MARKERS.search(sent) and HORIZON.search(sent):
                cands.append({'date': date, 'concept': concept, 'stem': p.stem,
                              'text': ' '.join(sent.split())[:300]})

# dedup by text
seen = set(); uniq = []
for c in sorted(cands, key=lambda x: x['date']):
    k = c['text'][:80]
    if k in seen: continue
    seen.add(k); uniq.append(c)

Path(os.path.join(IMPORTS, '_predictions_raw.json')).write_text(
    json.dumps(uniq, ensure_ascii=False), encoding='utf-8')
# readable dump
lines = [f'candidates={len(uniq)}', '']
for c in uniq:
    lines.append(f"[{c['date']}] ({c['concept'].replace('concept-','')}) {c['text']}")
Path(os.path.join(IMPORTS, '_predictions_raw.txt')).write_text('\n'.join(lines), encoding='utf-8')
print('prediction candidates:', len(uniq))
