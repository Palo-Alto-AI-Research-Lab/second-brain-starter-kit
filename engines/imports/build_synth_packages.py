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
"""Step 3a: one vault pass -> per-concept synthesis material packages.
For each of the 86 concept-*.md, gather all linked notes (year-sampled, anton-original
prioritized, with stems for citation). Write _synth/<slug>.json packages."""
import os, re, json
from pathlib import Path
from collections import defaultdict
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

V = Path(_VROOT)
CONCEPTS = V / '06-Concepts'
OUT = Path(os.path.join(_IROOT, "_synth")); OUT.mkdir(exist_ok=True)

concept_slugs = {f.stem for f in CONCEPTS.glob('concept-*.md')}

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

# catalog (slug+title) for agents to pick related concepts
catalog = []
titles = {}
for f in sorted(CONCEPTS.glob('concept-*.md')):
    t = f.read_text(encoding='utf-8', errors='ignore')
    fm, _ = fm_body(t)
    tm = re.search(r'^title:\s*[\'"]?(.+?)[\'"]?\s*$', fm, re.M)
    title = tm.group(1).strip() if tm else f.stem
    titles[f.stem] = title
    catalog.append({'slug': f.stem, 'title': title})

# one pass: collect notes per concept
by_concept = defaultdict(list)
for dp, dirs, fs in os.walk(V):
    if '.obsidian' in dp or '06-Concepts' in dp: continue
    for fn in fs:
        if not fn.endswith('.md'): continue
        p = Path(dp) / fn
        t = p.read_text(encoding='utf-8', errors='ignore')
        fm, body = fm_body(t)
        cm = re.search(r'^concept:\s*"?\[\[([^\]\|]+)', fm, re.M)
        if not cm: continue
        slug = cm.group(1).strip()
        if slug not in concept_slugs: continue
        if 'fb-duplicate' in fm or 'fb-repost' in fm: continue  # skip dups/reposts
        ao = bool(re.search(r'^\s*-\s*anton-original\s*$', fm, re.M)) or ('#anton-original' in t) or bool(re.search(r'^origin:\s*anton\b', fm, re.M))
        dm = re.search(r'^date:?\s*[\'"]?(\d{4}-\d{2}-\d{2})', fm, re.M) or re.search(r'(\d{4}-\d{2}-\d{2})', fn)
        date = dm.group(1) if dm else '0000-00-00'
        snip = ' '.join(re.split(r'## See Also|## Legacy', body)[0].split())[:200]
        wc = len(snip)
        by_concept[slug].append({'date': date, 'stem': p.stem, 'snip': snip, 'ao': ao, 'wc': wc})

# build packages
summary = []
for slug in sorted(concept_slugs):
    notes = by_concept.get(slug, [])
    ao_notes = [n for n in notes if n['ao']]
    # sample per year: prefer anton-original, then richest, up to 10/yr
    by_year = defaultdict(list)
    for n in notes:
        by_year[n['date'][:4]].append(n)
    material = []
    for yr in sorted(by_year):
        yrnotes = sorted(by_year[yr], key=lambda n: (not n['ao'], -n['wc']))[:10]
        for n in sorted(yrnotes, key=lambda n: n['date']):
            material.append({'date': n['date'], 'stem': n['stem'], 'snip': n['snip'], 'ao': n['ao']})
    pkg = {
        'slug': slug, 'title': titles.get(slug, slug),
        'total_notes': len(notes), 'anton_original_notes': len(ao_notes),
        'catalog': catalog, 'material': material,
    }
    (OUT / f'{slug}.json').write_text(json.dumps(pkg, ensure_ascii=False), encoding='utf-8')
    summary.append((slug, len(notes), len(ao_notes), len(material)))

summary.sort(key=lambda x: -x[1])
lines = [f'concepts={len(concept_slugs)}', 'slug | total | anton_orig | sampled', '']
for s, tot, ao, mat in summary:
    lines.append(f'{s} | {tot} | {ao} | {mat}')
Path(os.path.join(_IROOT, "_synth_summary.txt")).write_text('\n'.join(lines), encoding='utf-8')
print('packages built:', len(concept_slugs))
