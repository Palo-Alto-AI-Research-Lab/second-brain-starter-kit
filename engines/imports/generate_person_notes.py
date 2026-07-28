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
"""Phase 5: generate person notes (Layer 1) into staging/07-People, inject concept+tags
into conversation frontmatter, emit concept index. Only links concepts that EXIST (no broken
links). Stdout ASCII-only."""
import re, json
from pathlib import Path
from collections import defaultdict
import os
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

STAGE = Path(os.path.join(_IROOT, "staging"))
PDIR = STAGE / "07-People"
PDIR.mkdir(parents=True, exist_ok=True)
CONV = STAGE / r"01-Conversations\Telegram\Personal-DMs\conversations"

synth = json.load(open(os.path.join(_IROOT, "dm-synth-all.json"), encoding='utf-8'))
files_index = json.load(open(os.path.join(_IROOT, "dm-files-index.json"), encoding='utf-8'))
concept_cat = json.load(open(os.path.join(_IROOT, "concept_catalog.json"), encoding='utf-8'))
EXIST_CONCEPTS = {c['slug'] for c in concept_cat}
_PRIMARY = json.load(open(os.path.join(_IROOT, "dm-accounts.json"), encoding='utf-8'))['primary']
# include concepts created in staging (e.g. concept-crypto-exchange-listing)
for _p in (STAGE / "06-Concepts").glob("*.md"):
    EXIST_CONCEPTS.add(_p.stem)
# normalize agent-isms -> canonical concept slugs
CONCEPT_ALIASES = {'exchange-listing': 'concept-crypto-exchange-listing'}
def canon_concept(c):
    c = (c or '').strip()
    if c.startswith('NEW:'): c = c[4:]
    return CONCEPT_ALIASES.get(c, c)

def yesc(s): return (s or '').replace('"', "'").strip()
def yaml_list(items):
    items = [str(i).strip() for i in items if str(i).strip()]
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower()); out.append(i)
    return "[" + ", ".join('"%s"' % yesc(i) for i in out) + "]"

def valid_concepts(rec):
    cs = []
    for c in [rec.get('primary_concept','')] + (rec.get('concepts_secondary') or []):
        if not isinstance(c, str): continue
        c = canon_concept(c)
        if c in EXIST_CONCEPTS and c not in cs:
            cs.append(c)
    return cs

REL_RU = {
 'developer':'разработчик','cofounder':'сооснователь','colleague':'коллега','employee':'сотрудник',
 'investor':'инвестор','advisor':'эдвайзер','partner':'партнёр','vendor-contractor':'подрядчик',
 'client':'клиент','lead':'лид','peer-founder':'фаундер (равный)','friend':'друг',
 'personal-romantic':'личное','family':'семья','journalist-media':'медиа/журналист','unknown':'неизвестно'}

# org-mates for "see also" (person<->person edges)
def norm_org(o):
    o = (o or '').lower()
    o = re.sub(r'\s*/\s*', ' / ', o)
    return re.sub(r'[^a-zа-яё0-9 /]', '', o).strip()
org_members = defaultdict(list)
for pid, r in synth.items():
    if r.get('has_note') and norm_org(r.get('org')):
        org_members[norm_org(r['org'])].append(pid)

concept_index = defaultdict(list)   # concept -> [person_slug]
unknown_concepts = defaultdict(int)
n_notes = 0

for pid, r in synth.items():
    if not r.get('has_note'): continue
    fi = files_index[pid]
    pfirst = min(f['first'] for f in fi['files'])
    plast = max(f['last'] for f in fi['files'])
    slug = r['person_slug']
    name = r.get('display_name') or fi['name']
    rel = r.get('relationship','unknown')
    cs = valid_concepts(r)
    # track unknowns
    for c in [r.get('primary_concept','')] + (r.get('concepts_secondary') or []):
        if isinstance(c,str):
            cc = canon_concept(c)
            if cc and cc not in EXIST_CONCEPTS: unknown_concepts[cc]+=1
    primary = cs[0] if cs else None
    for c in cs: concept_index[c].append(slug)

    aliases = list(r.get('aliases') or [])
    if fi.get('username'): aliases.append('@'+fi['username'])
    base_tags = ['person','personal-dm', rel]
    tags = base_tags + [t for t in (r.get('tags') or []) if t]

    fm = ["---",
          f'title: "{yesc(name)}"',
          f'aliases: {yaml_list(aliases)}',
          "type: person",
          "source: telegram-personal-dm",
          "origin: mixed",
          "authored_by: hybrid",
          "summarized_by: claude-cowork",
          "created: 2026-05-31",
          f'relationship: {rel}']
    if yesc(r.get('org')):        fm.append(f'org: "{yesc(r.get("org"))}"')
    if yesc(r.get('role_title')): fm.append(f'role_title: "{yesc(r.get("role_title"))}"')
    if yesc(r.get('country_city')): fm.append(f'location: "{yesc(r.get("country_city"))}"')
    if fi.get('username'):        fm.append(f'tg_username: "@{fi["username"]}"')
    if fi.get('lead_id'):         fm.append(f'tg_id: {fi["lead_id"]}')
    fm.append(f'identified: {str(bool(r.get("identified"))).lower()}')
    fm.append(f'first_contact: "{pfirst}"')
    fm.append(f'last_contact: "{plast}"')
    fm.append(f'dm_msg_count: {fi.get("total",0)}')
    fm.append(f'dm_years: {sorted({int(f["year"]) for f in fi["files"]})}')
    if primary: fm.append(f'concept: "[[{primary}]]"')
    fm.append(f'tags: {yaml_list(tags)}')
    if r.get('confidence') is not None:
        try: fm.append(f'confidence: {float(r.get("confidence")):.2f}')
        except: pass
    fm.append("import_batch: 2026-05-31")
    fm.append("---")
    fm.append("")

    body = [f"# {name}", ""]
    sub = " · ".join([x for x in [REL_RU.get(rel,rel), yesc(r.get('org')), yesc(r.get('role_title')), yesc(r.get('country_city'))] if x])
    body.append(f"> ⚪ {sub}")
    body.append(f"> 🗓 {pfirst} – {plast} · 💬 {fi.get('total',0)} сообщений (DM) · {r.get('timeframe','')}")
    if not r.get('identified'):
        body.append(">")
        body.append("> ⚠️ личность не подтверждена — восстановлено по содержанию переписки")
    body.append("")
    if yesc(r.get('who_they_are')):
        body += ["## Кто это", r.get('who_they_are').strip(), ""]
    if r.get('worked_on'):
        body.append("## Что делали вместе")
        body += [f"- {w.strip()}" for w in r['worked_on'] if str(w).strip()]
        body.append("")
    if r.get('key_threads'):
        body.append("## Ключевые треды")
        body += [f"- {k.strip()}" for k in r['key_threads'] if str(k).strip()]
        body.append("")
    if yesc(r.get('notable_anton_reasoning')):
        body += ["## Заметная мысль Антона", f"> {r['notable_anton_reasoning'].strip()}", ""]
    # conversations
    body.append("## Переписка")
    for f in sorted(fi['files'], key=lambda x: (x.get('account',''), x['period'])):
        acc_lbl = f" · @{f['ahandle']}" if f.get('account') and f.get('account') != _PRIMARY else ""
        body.append(f"- [[{f['stem']}|{f['period']}]]{acc_lbl} — {f['msgs']} сообщений ({f['first']}–{f['last']})")
    body.append("")
    # concepts
    if cs:
        body.append("## Концепты")
        body += [f"- [[{c}]]" for c in cs]
        body.append("")
    # see also (org-mates)
    mates = [m for m in org_members.get(norm_org(r.get('org')), []) if m != pid]
    if mates:
        body.append("## См. также")
        for m in mates[:6]:
            mr = synth[m]
            body.append(f"- [[{mr['person_slug']}|{mr.get('display_name') or files_index[m]['name']}]]" +
                        (f" — {REL_RU.get(mr.get('relationship','unknown'), mr.get('relationship'))}" if mr.get('relationship') else ""))
        body.append("")

    (PDIR / (slug + ".md")).write_text('\n'.join(fm + body) + '\n', encoding='utf-8')
    n_notes += 1

    # ---- inject concept + tags into this person's conversation files ----
    cdir = CONV / fi['slug']
    inject_tags = [t for t in (r.get('tags') or []) if t][:6]
    for f in fi['files']:
        fp = cdir / (f['stem'] + ".md")
        if not fp.exists(): continue
        txt = fp.read_text(encoding='utf-8')
        def repl_tags(mm):
            cur = [t.strip() for t in mm.group(1).split(',') if t.strip()]
            for t in inject_tags:
                if t not in cur: cur.append(t)
            return f"tags: [{', '.join(cur)}]"
        txt2 = re.sub(r'tags: \[([^\]]*)\]', repl_tags, txt, count=1)
        if primary and 'concept:' not in txt2.split('---')[1]:
            txt2 = txt2.replace("import_batch: 2026-05-31\n---",
                                f'concept: "[[{primary}]]"\nimport_batch: 2026-05-31\n---', 1)
        fp.write_text(txt2, encoding='utf-8')

Path(os.path.join(_IROOT, "dm-concept-index.json")).write_text(
    json.dumps({k: v for k,v in concept_index.items()}, ensure_ascii=False, indent=1), encoding='utf-8')

print("person notes written: %d" % n_notes)
print("concepts used: %d ; unknown(non-existing) concept refs: %d" % (len(concept_index), len(unknown_concepts)))
for c,n in sorted(unknown_concepts.items(), key=lambda kv:-kv[1])[:30]:
    print("   unknown %2d  %s" % (n, c))
