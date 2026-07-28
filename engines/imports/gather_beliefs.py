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
"""Harvest distilled beliefs from the 62 concept-synthesis notes:
Тезис + Ключевые повороты/уроки + Открытые вопросы. Output compact material for
deriving belief notes + throughlines."""
import re
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
CONCEPTS = Path(os.path.join(_VROOT, "06-Concepts"))

def delink(s):
    s = re.sub(r'\[\[[^\]\|]*\|([^\]]+)\]\]', r'\1', s)   # [[x|alias]] -> alias
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)             # [[x]] -> x
    return s

out = []
n = 0
for f in sorted(CONCEPTS.glob('concept-*.md')):
    t = f.read_text(encoding='utf-8', errors='ignore')
    if 'synthesis_built:' not in t:
        continue
    # cut off Legacy
    t = t.split('## Legacy')[0]
    n += 1
    title_m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', t, re.M)
    title = title_m.group(1) if title_m else f.stem
    # thesis: lines of the [!abstract] callout
    thesis = ''
    am = re.search(r'>\s*\[!abstract\][^\n]*\n((?:>.*\n?)+)', t)
    if am:
        thesis = ' '.join(re.sub(r'^>\s?', '', l).strip() for l in am.group(1).splitlines())
    # turns/lessons section
    def section(name):
        m = re.search(rf'##\s*{name}\s*\n(.+?)(?=\n##|\Z)', t, re.S)
        return m.group(1).strip() if m else ''
    turns = section(r'Ключевые повороты и уроки')
    openq = section(r'Открытые вопросы[^\n]*')
    out.append(f'### {f.stem} — {title}')
    if thesis: out.append('ТЕЗИС: ' + delink(thesis)[:600])
    if turns: out.append('ПОВОРОТЫ/УРОКИ:\n' + delink(turns)[:900])
    if openq: out.append('ОТКРЫТЫЕ ВОПРОСЫ: ' + delink(openq)[:400])
    out.append('')

Path(os.path.join(_IROOT, "_beliefs_material.txt")).write_text('\n'.join(out), encoding='utf-8')
print(f'harvested from {n} synthesis notes;', sum(len(x) for x in out), 'chars')
