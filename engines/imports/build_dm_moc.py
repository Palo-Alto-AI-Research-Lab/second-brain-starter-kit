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
"""Phase 8a: build _Personal-DMs-MOC.md in staging. Stdout ASCII-only."""
import re, json
from pathlib import Path
from collections import defaultdict, Counter

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

MOC = Path(IMPORTS) / "staging" / "01-Conversations" / "Telegram" / "Personal-DMs" / "_Personal-DMs-MOC.md"
idx = json.load(open(Path(IMPORTS) / "dm-index.json", encoding='utf-8'))
synth = json.load(open(Path(IMPORTS) / "dm-synth-all.json", encoding='utf-8'))
fidx = json.load(open(Path(IMPORTS) / "dm-files-index.json", encoding='utf-8'))
cidx = json.load(open(Path(IMPORTS) / "dm-concept-index.json", encoding='utf-8'))
concept_cat = {c['slug']: (c.get('title') or c['slug']) for c in json.load(open(Path(IMPORTS) / "concept_catalog.json", encoding='utf-8'))}
concept_cat['concept-crypto-exchange-listing'] = 'Листинг токенов на биржах'

def clean_name(pid):
    r = synth.get(pid, {})
    if r.get('display_name') and not re.match(r'(?i)^tg:', r['display_name']):
        return r['display_name']
    n = re.sub(r'\s*\(tg:\d+\)\s*$', '', idx[pid]['name']).strip()
    return n if n and not re.fullmatch(r'(?i)lead', n) else f"tg:{idx[pid]['lead_id']}"

REL_RU = {'developer':'Разработчики','cofounder':'Сооснователи','colleague':'Коллеги',
 'employee':'Сотрудники / команда','investor':'Инвесторы','advisor':'Эдвайзеры',
 'partner':'Партнёры','vendor-contractor':'Подрядчики','client':'Клиенты','lead':'Лиды',
 'peer-founder':'Фаундеры (равные)','friend':'Друзья','personal-romantic':'Личное',
 'family':'Семья','journalist-media':'Медиа / журналисты','unknown':'Не определено'}
REL_ORDER = ['employee','vendor-contractor','developer','colleague','cofounder','peer-founder',
 'partner','investor','advisor','client','lead','journalist-media','friend','personal-romantic','family','unknown']

# per-year aggregate
year_dialogs = Counter(); year_msgs = Counter(); year_anton = Counter(); year_lead = Counter()
for pid, m in idx.items():
    for y, n in m['per_year'].items():
        year_dialogs[y]+=1; year_msgs[y]+=n
tot_msgs = sum(m['total'] for m in idx.values())
tot_anton = sum(m['acct'] for m in idx.values())
tot_lead  = sum(m['lead'] for m in idx.values())
note_pids = [pid for pid in idx if synth.get(pid,{}).get('has_note')]
anon = [pid for pid in idx if re.fullmatch(r'(?i)lead', re.sub(r'\s*\(tg:\d+\)\s*$','',idx[pid]['name']).strip())]

L = []
L.append("---")
archived_pids = [pid for pid in idx if idx[pid]['total'] >= 5]
n_archived = len(archived_pids)
n_lt5 = len(idx) - n_archived
L.append("title: Личные переписки Telegram (2016–2026) — MOC")
L.append("type: moc")
L.append("source: telegram-personal-dm")
L.append("origin: mixed")
L.append("authored_by: hybrid")
L.append("created: 2026-05-31")
L.append("tags: [moc, telegram, personal-dm, network, ico-era, platinum, venture]")
L.append("---")
L.append("")
L.append("# 📇 Личные переписки Telegram — 2016–2026")
L.append("")
L.append("Личная сеть Антона за десятилетие: **ICO-эпоха** (MicroMoney/AMM, Ledger Pay, 2016–2018) → **Platinum** (Platinum Engineering / VC / Dev Incubator, листинги, 2019–2022) → **VC / AI-агенты / launchpad / Palo Alto** (2023–2026). Двусторонние переписки `origin: mixed`; реплики Антона — `authored_by: human`.")
L.append("")
L.append("## Сводка")
L.append("")
L.append(f"- **Контактов всего:** {len(idx):,}".replace(',', ' '))
L.append(f"- **Сообщений:** {tot_msgs:,}  (🟢 Антон: {tot_anton:,} · ⚪ контакты: {tot_lead:,})".replace(',', ' '))
L.append(f"- **Person-заметок (≥20 сообщений):** {len(note_pids):,}".replace(',', ' '))
L.append(f"- **Архив-переписок (≥5 сообщений):** {n_archived:,}".replace(',', ' '))
L.append(f"- **Контактов <5 сообщений (только в индексе, без файла):** {n_lt5:,}".replace(',', ' '))
L.append(f"- **Период:** 2016 → 2026  ·  пик активности — 2019–2021")
L.append(f"- **Неопознанных контактов:** {len(anon)} (имя в экспорте = «Lead»; где возможно — восстановлено по содержанию)")
L.append("- Экспорт **текстовый** (без медиа): голосовых/фото/файлов в исходнике нет — потерь голосовой расшифровки нет.")
L.append("")
L.append("## По годам")
L.append("")
L.append("| Год | Диалогов | Сообщений |")
L.append("|---|--:|--:|")
for y in sorted(year_dialogs):
    L.append(f"| {y} | {year_dialogs[y]} | {year_msgs[y]:,} |".replace(',', ' '))
L.append("")

# Top contacts
L.append("## Топ-контакты по объёму")
L.append("")
L.append("| # | Контакт | Сообщений | Годы | Роль | Орг / проект |")
L.append("|--:|---|--:|---|---|---|")
ranked = [p for p in sorted(idx.keys(), key=lambda pid: -idx[pid]['total']) if not idx[p].get('is_self') and p in fidx]
for i, pid in enumerate(ranked[:60], 1):
    r = synth.get(pid, {})
    nm = clean_name(pid)
    yrs = ','.join(sorted(idx[pid]['years']))
    rel = REL_RU.get(r.get('relationship',''), r.get('relationship','')) if r.get('has_note') else 'архив'
    org = (r.get('org') or '').replace('|','/')
    if r.get('has_note'):
        link = f"[[{r['person_slug']}\\|{nm}]]"
    else:
        f0 = sorted(fidx[pid]['files'], key=lambda x:x['period'])[0]['stem']
        link = f"[[{f0}\\|{nm}]]"
    L.append(f"| {i} | {link} | {idx[pid]['total']} | {yrs} | {rel} | {org} |")
L.append("")

# By relationship
L.append("## По типу отношений")
L.append("")
by_rel = defaultdict(list)
for pid in note_pids:
    by_rel[synth[pid].get('relationship','unknown')].append(pid)
for rel in REL_ORDER:
    if rel not in by_rel: continue
    members = sorted(by_rel[rel], key=lambda pid: -idx[pid]['total'])
    L.append(f"### {REL_RU.get(rel, rel)} ({len(members)})")
    L.append("")
    for pid in members:
        r = synth[pid]; nm = clean_name(pid)
        org = f" — {r.get('org')}" if r.get('org') else ""
        L.append(f"- [[{r['person_slug']}|{nm}]]{org}  · {idx[pid]['total']} сообщ.")
    L.append("")

# Concept index
L.append("## Индекс концептов")
L.append("")
L.append("Концепты, к которым привязаны контакты этой сети (по числу людей):")
L.append("")
for c, pids in sorted(cidx.items(), key=lambda kv: -len(kv[1])):
    title = concept_cat.get(c, c)
    L.append(f"- [[{c}|{title}]] — {len(pids)} чел.")
L.append("")

# Org rosters (top orgs)
L.append("## Команды и организации")
L.append("")
def norm_org(o):
    o=(o or '').lower(); return re.sub(r'[^a-zа-яё0-9 ]','',o).strip()
org_members = defaultdict(list)
for pid in note_pids:
    o = synth[pid].get('org')
    if o and norm_org(o): org_members[o].append(pid)
for org, pids in sorted(org_members.items(), key=lambda kv:-len(kv[1])):
    if len(pids) < 2: continue
    L.append(f"### {org} ({len(pids)})")
    for pid in sorted(pids, key=lambda pid:-idx[pid]['total']):
        r = synth[pid]; nm = clean_name(pid)
        rt = f" — {r.get('role_title')}" if r.get('role_title') else ""
        L.append(f"- [[{r['person_slug']}|{nm}]]{rt}")
    L.append("")

# Minor contacts (archive-only, 5-19 msgs) -> separate aux file
minor = [pid for pid in idx if idx[pid]['total']>=5 and not synth.get(pid,{}).get('has_note') and not idx[pid].get('is_self') and pid in fidx]
minor.sort(key=lambda pid:-idx[pid]['total'])
L.append("## Прочие контакты")
L.append("")
L.append(f"- **{len(minor)}** контактов с 5–19 сообщениями — только архив-переписки (без person-заметки): [[_Personal-DMs-Minor-Contacts]]")
L.append(f"- **{n_lt5}** контактов с <5 сообщениями — только в индексе экспорта (отдельные файлы не создавались).")
L.append("")
ML = ["---","title: Personal-DMs — прочие контакты (5–19 сообщений)","type: moc-aux",
      "source: telegram-personal-dm","origin: mixed","authored_by: hybrid","created: 2026-05-31",
      "tags: [telegram, personal-dm, network]","---","",
      f"# Прочие контакты — архив, 5–19 сообщений ({len(minor)})","",
      "Только архив-переписки, без person-заметки. ← [[_Personal-DMs-MOC]]",""]
for pid in minor:
    nm = clean_name(pid)
    yrs = ','.join(sorted(idx[pid]['years']))
    f0 = sorted(fidx[pid]['files'], key=lambda x:x['period'])[0]['stem']
    ML.append(f"- [[{f0}|{nm}]] · {idx[pid]['total']} сообщ. · {yrs}")
(MOC.parent / "_Personal-DMs-Minor-Contacts.md").write_text('\n'.join(ML)+'\n', encoding='utf-8')
L.append("")

L.append("## Структура")
L.append("")
L.append("- `conversations/<контакт>/<контакт>-<год>[-месяц].md` — полный текст переписки (🟢 Антон / ⚪ контакт), по дням; крупные годы разбиты по месяцам.")
L.append("- `07-People/person-<контакт>.md` — заметка о человеке (кто это, что делали вместе, ключевые треды, концепты).")
L.append("- Концепты — в `06-Concepts/`; провенанс: `origin: mixed`, реплики Антона `authored_by: human`.")
L.append("")
L.append("## Дозагрузка новых лет")
L.append("")
L.append("Новые годовые экспорты добавляются инкрементально: парсер дедуплицирует по (контакт+текст), достраивает только новые годо-/месяц-файлы и новые person-заметки (идемпотентно по `tg_id`). См. адаптер «Telegram — Personal DMs» в `source-adapters.md`.")

MOC.write_text('\n'.join(L) + '\n', encoding='utf-8')
print("MOC written:", MOC.name, "| lines:", len(L))
print("note_people=%d minor=%d concepts=%d orgs>=2=%d" % (
    len(note_pids), len(minor), len(cidx), sum(1 for v in org_members.values() if len(v)>=2)))
