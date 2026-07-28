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
"""Recover ## CRM-данные via NON-team @handle found in the call-log body (exact, unambiguous)."""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import glob, io, re, json
from collections import Counter
V   = r"E:/Obsidian/Owner-Knowledge/04-Projects/crypto/Platinum-CRM/leads"
EXP = r"C:$HOME/!CLAUDE-HP17 May26/crm_export"
TIER_RU={"investor":"Инвестор","founder":"Фаундер / проект","kol":"KOL","b2b":"B2B","other":"—","not_investor":"Не инвестор"}
HANDLE=re.compile(r'@([A-Za-z][A-Za-z0-9_]{3,31})')

# enrichment by handle
enr={}
for line in io.open(EXP+"/enrichment.jsonl",encoding="utf-8"):
    o=json.loads(line); enr[o["handle_lc"]]=o

# team handles: high cross-card frequency + seeds
allcards=glob.glob(V+"/**/*.md",recursive=True)
hf=Counter()
for f in allcards:
    for h in set(x.lower() for x in HANDLE.findall(io.open(f,encoding="utf-8").read())): hf[h]+=1
TEAM={h for h,c in hf.items() if c>=12}
TEAM|={"corp_acct","corp_acct","owner_alt","owner_alt2","aowner_alt","work_acct_a","work_acct_b","helper_m",
       "zetaltd","lead_sc","azamweb3","azamshaghaghi","plainumvc","platinum1","ksplat","eventstodaybot","personal_acct"}

def section(rec):
    tier=rec["primary_tier"]; tags=[x.strip() for x in re.split(r"[;,|]",rec["tags_str"]) if x.strip()][:8]
    s=["\n## CRM-данные (entity export)",
       f'- **Квалификация:** {TIER_RU.get(tier,"—")}'+(" · теги: "+", ".join(tags) if tags else "")]
    if rec["operators"]: s.append("- **Оператор(ы) CRM:** "+", ".join(rec["operators"][:6]))
    s.append(f'- **DM-активность:** {rec["dm_msgs"]} сообщений'+(" · двусторонний диалог" if rec["dm_two_way"] else ""))
    if rec["bio"].strip(): s.append("- **Bio:** "+rec["bio"].strip().replace("\n"," ")[:400])
    if rec["link"].strip(): s.append("- **Ссылка:** "+rec["link"].strip())
    meta=[]
    if rec["created"]: meta.append("в CRM с "+rec["created"])
    if rec["last_activity"]: meta.append("посл. активность "+rec["last_activity"])
    if meta: s.append("- **"+" · ".join(meta)+"**")
    s.append("- _источник: crm_entities_export.csv (body-handle match)_")
    return s

matched=ambiguous=nomatch=0
for f in allcards:
    t=io.open(f,encoding="utf-8").read()
    if "## CRM-данные" in t: continue
    parts=t.split("---",2)
    if len(parts)<3 or "source: telegram-faaa" not in parts[1]: continue
    handles=set(h.lower() for h in HANDLE.findall(t)) - TEAM
    cand=[enr[h] for h in handles if h in enr]
    tids={c["telegram_id"] for c in cand}
    if len(tids)!=1: 
        if cand: ambiguous+=1
        else: nomatch+=1
        continue
    rec=cand[0]; fm=parts[1]
    fm_add=[]
    if "crm_telegram_id:" not in fm: fm_add.append(f'crm_telegram_id: "{rec["telegram_id"]}"')
    if "crm_tier:" not in fm: fm_add.append(f'crm_tier: "{rec["primary_tier"]}"')
    if "dm_msgs:" not in fm: fm_add.append(f'dm_msgs: {rec["dm_msgs"]}')
    if "crm_match:" not in fm: fm_add.append("crm_match: body-handle")
    new_fm=fm.rstrip("\n")+"\n"+"\n".join(fm_add)+"\n" if fm_add else fm
    body=parts[2]; ins="\n".join(section(rec))+"\n"
    body=body.replace("\n## Связи","\n"+ins+"\n## Связи",1) if "\n## Связи" in body else body.rstrip()+"\n"+ins
    io.open(f,"w",encoding="utf-8").write("---"+new_fm+"---"+body)
    matched+=1
print(f"body-handle recovery: matched={matched} ambiguous(>1 lead handle)={ambiguous} no_csv_handle={nomatch}")

# final coverage
n=crm=0
for f in glob.glob(V+"/**/*.md",recursive=True):
    n+=1
    if "## CRM-данные" in io.open(f,encoding="utf-8").read(): crm+=1
print(f"FINAL ## CRM-данные: {crm}/{n} ({100*crm/n:.1f}%)")
