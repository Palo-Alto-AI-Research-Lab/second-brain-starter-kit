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
"""Phase 3: generate per-person conversation archive (Layer 2) into staging.
Deterministic, no LLM. One file per (person, year); month-split if a year > THRESH msgs.
Verbatim bodies, role-labelled, day-grouped. Stdout ASCII-only."""
import re, json
from pathlib import Path
from collections import defaultdict

import os
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"
ROOT = Path(os.path.join(_IROOT, "staging", "01-Conversations", "Telegram", "Personal-DMs", "conversations"))
ROOT.mkdir(parents=True, exist_ok=True)
THRESH = 1800   # per (pid, year): above this -> monthly files

rows = [json.loads(l) for l in open(os.path.join(_IROOT, "dm-archive.jsonl"), encoding='utf-8')]
idx = json.load(open(os.path.join(_IROOT, "dm-index.json"), encoding='utf-8'))
targets = json.load(open(os.path.join(_IROOT, "dm-person-targets.json"), encoding='utf-8'))
# authoritative clean slugs from synthesis (folder/stem + person-note link)
folder_slug = json.load(open(os.path.join(_IROOT, "dm-folderslug.json"), encoding='utf-8'))
person_slug = json.load(open(os.path.join(_IROOT, "dm-personslug.json"), encoding='utf-8'))
ACC = json.load(open(os.path.join(_IROOT, "dm-accounts.json"), encoding='utf-8'))
ID2H = ACC['id2handle']; PRIMARY = ACC['primary']; SELF = set(ACC['self_accounts'])
# wipe + recreate staging conversations so renamed (clean-slug) folders don't leave stale copies
import shutil
if ROOT.exists(): shutil.rmtree(ROOT)
ROOT.mkdir(parents=True, exist_ok=True)

MONTHS_RU = {1:'январь',2:'февраль',3:'март',4:'апрель',5:'май',6:'июнь',7:'июль',
             8:'август',9:'сентябрь',10:'октябрь',11:'ноябрь',12:'декабрь'}
WD_RU = ['пн','вт','ср','чт','пт','сб','вс']
import datetime
def weekday_ru(date):
    y,m,d = map(int, date.split('-'))
    return WD_RU[datetime.date(y,m,d).weekday()]

def first_token(name):
    base = re.sub(r'\s*\(tg:\d+\)\s*$', '', name).strip()
    if re.fullmatch(r'(?i)lead', base) or not base:
        return 'Контакт'
    return base.split()[0]

def blockquote(text):
    if not text.strip():
        return "> _[без текста]_"
    # neutralize verbatim [[...]] so message text isn't misread as a wikilink (phantom graph nodes)
    text = text.replace('[[', '[').replace(']]', ']')
    return '\n'.join('> ' + ln if ln.strip() else '>' for ln in text.split('\n'))

def yaml_escape(s):
    return (s or '').replace('"', "'")

# group rows by pid
by_pid = defaultdict(list)
for r in rows:
    by_pid[r['pid']].append(r)

files_index = {}   # pid -> dict(slug, has_note, target_slug, files=[...])
n_files = 0

for pid, prows in by_pid.items():
    if pid in SELF:                        # Anton's own accounts: no archive/note
        continue
    if folder_slug.get(pid) is None:      # < ARCH_THR msgs: not archived
        continue
    prows.sort(key=lambda r: r['ts'])
    m = idx[pid]
    t = targets[pid]
    name = m['name']
    uname = m['username']
    lead_id = m['lead_id']
    dmslug = folder_slug[pid]          # authoritative clean slug
    psl = person_slug[pid]             # person-note link target (None if no note)
    has_note = psl is not None
    fname = first_token(name)
    pdir = ROOT / dmslug
    pdir.mkdir(parents=True, exist_ok=True)
    files_index[pid] = dict(slug=dmslug, has_note=has_note,
                            target_slug=psl, name=name, username=uname,
                            lead_id=lead_id, total=m['total'], files=[])

    # group by (account, year), decide split
    by_ay = defaultdict(list)
    for r in prows:
        by_ay[(r.get('account', PRIMARY), r['year'])].append(r)

    for (acct, year), yrows in sorted(by_ay.items()):
        monthly = len(yrows) > THRESH
        # bucket: key -> rows  (key = year or year-MM)
        buckets = defaultdict(list)
        for r in yrows:
            key = r['date'][:7] if monthly else year
            buckets[key].append(r)
        ahandle = ID2H.get(acct, acct)
        for key, brows in sorted(buckets.items()):
            brows.sort(key=lambda r: r['ts'])
            period = key
            stem = f"{dmslug}-{period}" if acct == PRIMARY else f"{dmslug}-{ahandle}-{period}"
            a = sum(1 for r in brows if r['role'] == 'account')
            c = len(brows) - a
            first_d, last_d = brows[0]['date'], brows[-1]['date']
            # build body
            out = []
            disp_un = f" @{uname}" if uname else ""
            title = f"{name} — DM {period}" if not re.fullmatch(r'(?i)lead', re.sub(r'\\s*\\(tg:\\d+\\)\\s*$','',name).strip()) else f"tg:{lead_id} — DM {period}"
            fm = [
                "---",
                f'title: "{yaml_escape(title)}"',
                "type: dm-conversation",
                "source: telegram-personal-dm",
                f'chat: "Личка с {yaml_escape(name)}"',
                f'contact_name: "{yaml_escape(name)}"',
            ]
            if uname: fm.append(f'contact_username: "@{uname}"')
            if lead_id: fm.append(f"contact_tg_id: {lead_id}")
            fm.append(f'account: "@{ahandle}"')
            fm.append(f"account_id: {acct}")
            if has_note:
                fm.append(f'person: "[[{psl}]]"')
            fm += [
                "origin: mixed",
                "authored_by: human",
                "language: ru",
                f"year: {year}",
                f'period: "{period}"',
                f'date_range: "{first_d} .. {last_d}"',
                f"msg_count: {len(brows)}",
                f"anton_msgs: {a}",
                f"contact_msgs: {c}",
                f'participants: ["Антон Дзятковский", "{yaml_escape(name)}"]',
                f"tags: [telegram, personal-dm, dm-{year}]",
                f"import_batch: 2026-05-31",
                "---",
                "",
                f"# Личка с {name} — {period}",
                "",
                f"> 🟢 **Антон**  ·  ⚪ **{fname}**{disp_un}  ·  {len(brows)} сообщений  ·  {first_d} – {last_d}",
                "",
            ]
            if has_note:
                fm.append(f"Контакт: [[{psl}|{name}]]" + (f" · @{uname}" if uname else "") + (f" · tg `{lead_id}`" if lead_id else ""))
                fm.append("")
            out = fm
            cur_month = None
            cur_day = None
            for r in brows:
                mo = r['date'][:7]
                if mo != cur_month:
                    mm = int(mo[5:7])
                    out.append("")
                    out.append(f"## {mo} · {MONTHS_RU[mm]}")
                    cur_month = mo
                    cur_day = None
                if r['date'] != cur_day:
                    out.append("")
                    out.append(f"### {r['date']} · {weekday_ru(r['date'])}")
                    cur_day = r['date']
                hhmm = r['ts'][11:16]
                icon = '🟢' if r['role'] == 'account' else '⚪'
                who = 'Антон' if r['role'] == 'account' else fname
                ed = " _(ред.)_" if r.get('edited') else ""
                out.append("")
                out.append(f"**{hhmm}** {icon} **{who}**{ed}")
                out.append(blockquote(r['text']))
            (pdir / (stem + ".md")).write_text('\n'.join(out) + '\n', encoding='utf-8')
            n_files += 1
            files_index[pid]['files'].append(dict(
                stem=stem, period=period, year=year, msgs=len(brows),
                anton=a, contact=c, first=first_d, last=last_d,
                account=acct, ahandle=ahandle))

Path(os.path.join(_IROOT, "dm-files-index.json")).write_text(
    json.dumps(files_index, ensure_ascii=False, indent=1), encoding='utf-8')
print("archive files written: %d  (people=%d)" % (n_files, len(files_index)))
print("root ->", ROOT)
