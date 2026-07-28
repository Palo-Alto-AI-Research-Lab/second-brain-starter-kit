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
"""A: generate 3 computed CRM dashboards from person notes (9718).
A1 Warm Stack (known but >90d cold), A2 Investors, A3 Intro matchmaking. TODAY=2026-06-01."""
import os, re
from pathlib import Path
from datetime import date
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
P = V / '07-People'
MOC = V / '90_MOCs'
TODAY = date(2026, 6, 1)

def f(fm, name):
    m = re.search(rf'^{name}:\s*["\']?(.+?)["\']?\s*$', fm, re.M)
    return m.group(1).strip().strip('"\'') if m else ''

def tags_of(fm):
    m = re.search(r'^tags:\s*\[(.+?)\]', fm, re.M)
    return [x.strip().strip('"\'') for x in m.group(1).split(',')] if m else []

def days_since(d):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', d or '')
    if not m: return None
    try: return (TODAY - date(int(m[1]), int(m[2]), int(m[3]))).days
    except Exception: return None

people = []
for fp in P.glob('person-*.md'):
    t = fp.read_text(encoding='utf-8', errors='ignore')
    fm = t.split('---')[1] if t.count('---') >= 2 else ''
    people.append(dict(
        stem=fp.stem, title=f(fm,'title') or fp.stem,
        rel=f(fm,'relationship'), tier=f(fm,'tier'), status=f(fm,'status'),
        role=f(fm,'role_title') or f(fm,'role'), org=f(fm,'org') or f(fm,'affiliation'),
        country=f(fm,'country'), dm=int(f(fm,'dm_msg_count') or 0),
        last=f(fm,'last_contact'), first=f(fm,'first_contact'), tags=tags_of(fm)))

DOMAINS = ['defi','ai-agents','web3','exchange-listing','launchpad','fundraising','longevity','otc','nft']

# ---------- A1: WARM STACK ----------
warm = []
for p in people:
    if not p['last'] or p['dm'] < 15: continue
    ds = days_since(p['last'])
    if ds is None or ds <= 90: continue
    rel_boost = {'partner':3,'peer-founder':2.5,'investor':3,'advisor':2,'friend':2,'colleague':1.5,'employee':1.5}.get(p['rel'],1)
    p['_score'] = p['dm'] * rel_boost
    p['_days'] = ds
    warm.append(p)
warm.sort(key=lambda x: -x['_score'])

A1 = ['---','title: "CRM — Тёплый стек (кому написать)"','type: moc','tags: [moc, crm, warm-stack]','concept: "[[concept-social-capital-crm]]"','---','',
      '# 🔥 Тёплый стек — кому написать',f'> Контакты с историей (≥15 сообщ.), которым ты НЕ писал >90 дней. Сегодня {TODAY}. Топ-50 по силе связи × давности.','',
      '| Кто | Связь | Роль | Не писал | Сообщ. |','|---|---|---|---|---|']
for p in warm[:50]:
    A1.append(f"| [[{p['stem']}\\|{p['title'][:38]}]] | {p['rel']} | {p['role'][:30]} | {p['_days']} дн | {p['dm']} |")
A1 += ['', f'_Всего тёплых-но-остывших: {len(warm)}._', '', '## Навигация', '- [[_CRM-MOC]] · [[_CRM-Investors]] · [[_CRM-Intros]] · [[belief-warm-connections]]']
(MOC/'_CRM-Warm-Stack.md').write_text('\n'.join(A1), encoding='utf-8')

# ---------- A2: INVESTORS ----------
inv = [p for p in people if p['tier'] in ('vc','fund','investor') or p['rel']=='investor']
status_order = {'partner':0,'negotiating':1,'qualifying':2,'new':3,'stale':4,'no-show':5,'lost':6}
inv.sort(key=lambda x:(status_order.get(x['status'],9), -x['dm']))
A2 = ['---','title: "CRM — Инвесторы"','type: moc','tags: [moc, crm, investors, fundraising]','concept: "[[concept-investor-taxonomy]]"','---','',
      '# 💼 Инвесторы',f'> {len(inv)} инвест-сущностей (tier: vc/fund/investor). Отсортированы по стадии сделки.','',
      '| Инвестор | Тип | Стадия | Орг | Страна |','|---|---|---|---|---|']
for p in inv[:80]:
    A2.append(f"| [[{p['stem']}\\|{p['title'][:36]}]] | {p['tier']} | {p['status']} | {p['org'][:26]} | {p['country'][:18]} |")
from collections import Counter
tc = Counter(p['tier'] for p in inv); sc = Counter(p['status'] for p in inv)
A2 += ['', f'_По типу: {dict(tc)}._', f'_По стадии: {dict(sc)}._','','## Навигация','- [[_CRM-MOC]] · [[_CRM-Warm-Stack]] · [[_CRM-Intros]] · [[concept-startup-fundraising]]']
(MOC/'_CRM-Investors.md').write_text('\n'.join(A2), encoding='utf-8')

# ---------- A3: INTRO MATCHMAKING ----------
A3 = ['---','title: "CRM — Интро-возможности (matchmaking)"','type: moc','tags: [moc, crm, intros, networking]','concept: "[[concept-social-capital-crm]]"','---','',
      '# 🤝 Интро-возможности',
      '> Сводишь людей = создаёшь ценность. Внутри домена: **фаундеры** (кому нужны деньги/связи) × **инвесторы/партнёры** (у кого они есть). Выбирай пары для тёплого интро.','',
      '> [!tip] Правило', '> Сделал интро — попроси встречное. → [[belief-warm-connections]]','']
def is_founder(p): return p['tier']=='founder' or p['rel']=='peer-founder'
def is_investor(p): return p['tier'] in ('vc','fund','investor') or p['rel']=='investor'
for dom in DOMAINS:
    grp = [p for p in people if dom in p['tags']]
    founders = sorted([p for p in grp if is_founder(p)], key=lambda x:-x['dm'])[:8]
    investors = sorted([p for p in grp if is_investor(p)], key=lambda x:-x['dm'])[:8]
    if not founders or not investors: continue
    A3.append(f'## {dom}  ({len(grp)} контактов)')
    A3.append('| 🚀 Фаундеры | 💰 Инвесторы/партнёры |')
    A3.append('|---|---|')
    for i in range(max(len(founders), len(investors))):
        fdr = f"[[{founders[i]['stem']}\\|{founders[i]['title'][:28]}]]" if i < len(founders) else ''
        ivr = f"[[{investors[i]['stem']}\\|{investors[i]['title'][:28]}]]" if i < len(investors) else ''
        A3.append(f'| {fdr} | {ivr} |')
    A3.append('')
A3 += ['## Навигация','- [[_CRM-MOC]] · [[_CRM-Warm-Stack]] · [[_CRM-Investors]] · [[concept-startup-lab-networking]]']
(MOC/'_CRM-Intros.md').write_text('\n'.join(A3), encoding='utf-8')

Path(os.path.join(_IROOT, "_crm_dash.txt")).write_text(
    f'warm_stack={len(warm)}\ninvestors={len(inv)}\npeople_scanned={len(people)}', encoding='utf-8')
print('CRM dashboards built')
