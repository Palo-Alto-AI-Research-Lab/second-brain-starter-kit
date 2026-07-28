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
"""Compute calibration scoring for insight-prediction-ledger.md.
Parses prediction tables, tallies status by domain (section) and by prediction year,
and injects a scorecard between <!--CALIB:START--> / <!--CALIB:END--> markers (idempotent).
Re-run after editing the ledger: python %IMPORTS%\\ledger_calibration.py
"""
import os
import re
from collections import defaultdict
from pathlib import Path

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"

P = Path(os.path.join(VAULT, '03-Insights', 'insight-prediction-ledger.md'))
YES, NO, PART, WAIT = '✅', '❌', '\U0001f7e1', '⏳'  # checkmark, X, yellow, hourglass
STAT = {YES: 'yes', NO: 'no', PART: 'part', WAIT: 'wait'}

def strip_block(s):
    return re.sub(r'\n?<!--CALIB:START-->.*?<!--CALIB:END-->\n?', '\n', s, flags=re.S)

def newrec():
    return {'yes': 0, 'no': 0, 'part': 0, 'wait': 0}

raw = P.read_text(encoding='utf-8')
body = strip_block(raw)

bydom = defaultdict(newrec)
byyear = defaultdict(newrec)
overall = newrec()
cur = None
rows = 0
for ln in body.split('\n'):
    s = ln.strip()
    if s.startswith('## '):
        cur = s[3:].strip()
        continue
    if not s.startswith('|'):
        continue
    cells = re.split(r'(?<!\\)\|', ln)  # split on UNescaped pipes (keep [[a\|b]] intact)
    if len(cells) < 6:
        continue
    statcell = cells[4]
    st = None
    for ch, name in STAT.items():
        if ch in statcell:
            st = name
            break
    if not st:
        continue
    ym = re.search(r'(20\d\d)', cells[1])
    yr = ym.group(1) if ym else '????'
    bydom[cur][st] += 1
    byyear[yr][st] += 1
    overall[st] += 1
    rows += 1

def resolved(r):
    return r['yes'] + r['no'] + r['part']

def pct(n, d):
    return round(100 * n / d) if d else 0

def strict(r):
    return pct(r['yes'], resolved(r))

def direction(r):
    return pct(r['yes'] + r['part'], resolved(r))

# --- build markdown ---
o = overall
res = resolved(o)
md = []
md.append('## 📊 Калибровка (скоринг)')
md.append('> Авто-счёт из таблиц ниже. Пересобрать: `python %IMPORTS%\\ledger_calibration.py`. '
          '*Резолвед = всё, кроме ⏳. Строгая точность = ✅/резолвед. Направление = (✅+🟡)/резолвед.*')
md.append('')
md.append(f'**Итого:** {rows} прогнозов · {res} резолвед · {YES}{o["yes"]} {PART}{o["part"]} {NO}{o["no"]} {WAIT}{o["wait"]}')
md.append('')
md.append(f'**Строгая точность:** **{strict(o)}%** · **Направление (✅+🟡):** **{direction(o)}%** · **Промах (❌):** **{pct(o["no"], res)}%**')
md.append('')
md.append('### По доменам')
md.append(f'| Домен | Резолвед | {YES} | {PART} | {NO} | {WAIT} | Строго | Направление |')
md.append('|---|---|---|---|---|---|---|---|')
for name, r in sorted(bydom.items(), key=lambda kv: -resolved(kv[1])):
    if rows and (resolved(r) + r['wait']) == 0:
        continue
    md.append(f'| {name} | {resolved(r)} | {r["yes"]} | {r["part"]} | {r["no"]} | {r["wait"]} | {strict(r)}% | {direction(r)}% |')
md.append('')
md.append('### По году прогноза')
md.append(f'| Год | Резолвед | {YES} | {PART} | {NO} | {WAIT} | Строго |')
md.append('|---|---|---|---|---|---|---|')
for yr in sorted(byyear):
    r = byyear[yr]
    md.append(f'| {yr} | {resolved(r)} | {r["yes"]} | {r["part"]} | {r["no"]} | {r["wait"]} | {strict(r)}% |')
md.append('')

# --- data-driven highlights ---
hl = []
# euphoria (2017) vs sober (2019+2020)
euph = byyear.get('2017', newrec())
sober = newrec()
for y in ('2019', '2020'):
    for k in sober:
        sober[k] += byyear.get(y, newrec())[k]
if resolved(euph):
    hl.append(f'**ICO-эйфория 2017:** {strict(euph)}% строгой точности ({resolved(euph)} резолвед) — худший год.')
if resolved(sober):
    hl.append(f'**Отрезвление 2019–2020:** {strict(sober)}% — лучший период (трезвые прогнозы после краха).')
# best/worst domain with >=3 resolved
elig = [(n, r) for n, r in bydom.items() if resolved(r) >= 3]
if elig:
    best = max(elig, key=lambda kv: strict(kv[1]))
    worst = min(elig, key=lambda kv: strict(kv[1]))
    hl.append(f'**Сильнейший домен:** {best[0]} — {strict(best[1])}% строго.')
    hl.append(f'**Слабейший домен:** {worst[0]} — {strict(worst[1])}% строго.')
if hl:
    md.append('> [!insight] Что показывают числа')
    for h in hl:
        md.append('> - ' + h)
    md.append('> - Подробная качественная интерпретация — в разделе **«Паттерны»** ниже.')
    md.append('')

block = '<!--CALIB:START-->\n' + '\n'.join(md).rstrip() + '\n<!--CALIB:END-->'

idx = body.index('\n## ')
out = body[:idx + 1] + block + '\n\n' + body[idx + 1:]
P.write_text(out, encoding='utf-8')
print('OK rows=%d resolved=%d strict=%d%% dir=%d%% domains=%d years=%d'
      % (rows, res, strict(o), direction(o), len(bydom), len(byyear)))
