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
"""Phase 8b: append concept->person backlink rosters to referenced concept files (vault).
Idempotent (replaces a marked block). Stdout ASCII-only."""
import os, re, json
from pathlib import Path

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
VAULT = Path(VAULT)
CDIR = VAULT / "06-Concepts"
cidx = json.load(open(os.path.join(IMPORTS, "dm-concept-index.json"), encoding='utf-8'))
synth = json.load(open(os.path.join(IMPORTS, "dm-synth-all.json"), encoding='utf-8'))
idx = json.load(open(os.path.join(IMPORTS, "dm-index.json"), encoding='utf-8'))
slug2pid = {r['person_slug']: pid for pid, r in synth.items() if r.get('person_slug')}

REL_RU = {'developer':'разработчик','cofounder':'сооснователь','colleague':'коллега','employee':'сотрудник',
 'investor':'инвестор','advisor':'эдвайзер','partner':'партнёр','vendor-contractor':'подрядчик',
 'client':'клиент','lead':'лид','peer-founder':'фаундер','friend':'друг','personal-romantic':'личное',
 'family':'семья','journalist-media':'медиа','unknown':'?'}
START = "<!-- dm-backlinks:start -->"
END = "<!-- dm-backlinks:end -->"
CAP = 40
edited = 0; missing = []

for concept, pids in cidx.items():
    cf = CDIR / (concept + ".md")
    if not cf.exists():
        missing.append(concept); continue
    pids = [slug2pid[s] for s in pids if s in slug2pid]
    pids = sorted(pids, key=lambda pid: -idx[pid]['total'])
    lines = [f"## 📇 Контакты из личных переписок (2016–2018)", START]
    for pid in pids[:CAP]:
        r = synth[pid]
        nm = r.get('display_name') or idx[pid]['name']
        rel = REL_RU.get(r.get('relationship',''), '')
        org = f", {r.get('org')}" if r.get('org') else ""
        lines.append(f"- [[{r['person_slug']}|{nm}]] — {rel}{org} · {idx[pid]['total']} сообщ.")
    if len(pids) > CAP:
        lines.append(f"- …и ещё {len(pids)-CAP} — см. [[_Personal-DMs-MOC]]")
    lines.append(END)
    block = '\n'.join(lines)

    txt = cf.read_text(encoding='utf-8')
    if START in txt and END in txt:
        txt = re.sub(re.escape(START) + r'.*?' + re.escape(END),
                     START + '\n' + '\n'.join(lines[2:-1]) + '\n' + END, txt, flags=re.DOTALL)
        # also ensure heading present right before START (it is, from prior run)
    else:
        if not txt.endswith('\n'): txt += '\n'
        txt += '\n' + block + '\n'
    cf.write_text(txt, encoding='utf-8')
    edited += 1

print("concept files edited: %d" % edited)
print("concepts referenced but file missing: %d %s" % (len(missing), missing[:10]))
