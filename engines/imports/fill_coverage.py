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
"""C: fill concept: coverage for 02-Decisions & 03-Insights notes lacking concept AND part_of.
Deterministic: subfolder -> concept, else domain/topic field -> concept. Additive, idempotent."""
import os, re
from pathlib import Path
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

V = Path(_VROOT)

DEC_SUB = {
    'Business-Finance': 'concept-personal-finance', 'Cars': 'concept-cars',
    'Construction': 'concept-construction-renovation', 'Family-Kids': 'concept-parenting',
    'Home-Life': 'concept-life-observations', 'Portugal': 'concept-place-livability',
    'Travel': 'concept-travel-logistics',
}
INS_SUB = {
    'AI-Tech': 'concept-ai-agents', 'Alt-History': 'concept-alternative-history',
    'anton-voice': 'concept-graphomania-voice-first-writing', 'Crypto-Web3': 'concept-blockchain',
    'Games-Entertainment': 'concept-tap-to-earn-games', 'General-Tech': 'concept-tech-tools',
    'Operations': 'concept-business-strategy', 'Personal-Growth': 'concept-life-observations',
    'Translation': 'concept-language-learning',
}
DOMAIN = {
    'crypto': 'concept-blockchain', 'biohacking': 'concept-biohacking-nutrition',
    'health': 'concept-medicine-health', 'medicine': 'concept-medicine-health',
    'longevity': 'concept-longevity', 'business': 'concept-business-strategy',
    'finance': 'concept-personal-finance', 'cars': 'concept-cars',
    'construction': 'concept-construction-renovation', 'family': 'concept-parenting',
    'portugal': 'concept-place-livability', 'ai': 'concept-ai-agents',
}
CONCEPTS = {f.stem for f in (V/'06-Concepts').glob('concept-*.md')}

def fm_split(t):
    m = re.match(r'^(---\r?\n.*?\r?\n)(---\r?\n)(.*)$', t, re.S)
    return (m.group(1), m.group(2), m.group(3)) if m else (None, None, t)

def pick_concept(path, fm):
    rel = os.path.relpath(path, V).split(os.sep)
    top, sub = rel[0], (rel[1] if len(rel) > 1 else '')
    table = DEC_SUB if top == '02-Decisions' else INS_SUB
    if sub in table: return table[sub]
    dm = re.search(r'^domain:\s*["\']?(\w+)', fm, re.M)
    if dm and dm.group(1).lower() in DOMAIN: return DOMAIN[dm.group(1).lower()]
    tm = re.search(r'^topic:\s*["\']?[\d-]*([A-Za-z-]+)', fm, re.M)
    if tm and tm.group(1).lower() in DOMAIN: return DOMAIN[tm.group(1).lower()]
    return None

stats = {'scanned': 0, 'already': 0, 'mapped': 0, 'no_match': 0, 'meta_skip': 0}
for folder in ['02-Decisions', '03-Insights']:
    for f in (V/folder).glob('**/*.md'):
        if f.stem.startswith(('belief-', 'insight-worldview', 'insight-core', 'insight-contra',
                              'insight-decision', 'insight-prediction')):
            continue  # my hand-built identity notes — leave
        try:
            t = f.read_text(encoding='utf-8')
        except Exception:
            continue
        stats['scanned'] += 1
        head, sep, body = fm_split(t)
        if head is None:
            continue
        if re.search(r'^(concept|part_of):', head, re.M):
            stats['already'] += 1; continue
        # skip pure-meta session reports
        if re.search(r'^topic:\s*["\']?00-Meta', head, re.M) or 'session-report' in head or 'milestone' in head:
            stats['meta_skip'] += 1; continue
        c = pick_concept(f, head)
        if not c or c not in CONCEPTS:
            stats['no_match'] += 1; continue
        # insert concept after type: or origin: line
        line = f'concept: "[[{c}]]"\n'
        m = re.search(r'^(type:.*\n)', head, re.M) or re.search(r'^(origin:.*\n)', head, re.M)
        if m:
            head2 = head[:m.end()] + line + head[m.end():]
        else:
            head2 = head + line
        f.write_text(head2 + sep + body, encoding='utf-8')
        stats['mapped'] += 1

Path(os.path.join(_IROOT, "_coverage_fill.txt")).write_text(
    '\n'.join(f'{k}={v}' for k, v in stats.items()), encoding='utf-8')
print('coverage fill done')
