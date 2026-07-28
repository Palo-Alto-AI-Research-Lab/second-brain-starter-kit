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
"""Render Platinum CRM DM-leads (no-call) into cards. Rich if synth present, else thin.
Renders to staging_dm (NOT vault). Idempotent; slug-deduped vs existing FAAA cards."""
import json, io, os, re, glob
VL=r"E:/Obsidian/Owner-Knowledge/04-Projects/crypto/Platinum-CRM/leads"
ST=r"E:/Obsidian/_imports/staging_dm/04-Projects/crypto/Platinum-CRM/leads"
DMB=r"E:/Obsidian/_imports/faaa/dm_batches"; DMS=r"E:/Obsidian/_imports/faaa/dm_synth"
DATE="2026-06-01"
TIER_RU={"investor":"Инвестор","founder":"Фаундер / проект","kol":"KOL","b2b":"B2B","other":"—"}
TR=str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя","abvgdeejziyklmnoprstufhccss y eya")
def slugify(t):
    if not t: return "lead"
    t=t.lower().translate(TR); t=re.sub(r"['`’]","",t); t=re.sub(r"[^a-z0-9]+","-",t).strip("-")
    return (re.sub(r"-+","-",t)[:48].strip("-")) or "lead"
def ne1(s): return re.sub(r'(?<=\[)\[', r'\\[', s or "")  # break '[[' so it isn't a phantom wikilink
def jstr(s): return json.dumps((s or "").replace("\n"," ").strip(), ensure_ascii=False)

# synth by lead_id (tolerant)
synth={}
for f in glob.glob(DMS+"/batch_*.json"):
    try:
        t=io.open(f,encoding="utf-8-sig").read().strip(); t=re.sub(r'^```(json)?|```$','',t,flags=re.M).strip()
        for o in json.loads(t):
            if isinstance(o,dict) and o.get("lead_id"): synth[o["lead_id"]]=o
    except Exception: pass
# dedup vs AUTHORITATIVE staging FAAA card filenames (vault may be mid-rebuild)
FAAA_REF=r"E:/Obsidian/_imports/staging/04-Projects/crypto/Platinum-CRM/leads"
used={}
for f in glob.glob(FAAA_REF+"/**/*.md", recursive=True): used[os.path.basename(f)[:-3]]=1
def uniq(b):
    cand=b; i=1
    while cand in used:           # check EACH candidate is free (fixes -N collision w/ FAAA)
        i+=1; cand="%s-%d"%(b,i)
    used[cand]=1; return cand
# bundles
leads=[]
for f in glob.glob(DMB+"/batch_*.json"): leads+=json.load(io.open(f,encoding="utf-8"))["leads"]
# clear staging_dm
for f in glob.glob(ST+"/**/*.md", recursive=True): os.remove(f)

rich=thin=0
for b in leads:
    s=synth.get(b["lead_id"],{})
    name=(s.get("name") or b.get("name") or b.get("handle") or "lead").strip()
    slug=uniq(slugify(name)); year=(b.get("created") or "2025")[:4]
    if not re.match(r"20\d\d",year): year="2025"
    folder=os.path.join(ST,year); os.makedirs(folder,exist_ok=True)
    tier=b.get("tier","other"); company=s.get("company") or ""
    status=s.get("status") or "dm-only"; cat=s.get("category") or tier
    h=b.get("handle"); handles=["@"+h] if h and not h.startswith("@") else ([h] if h else [])
    fm=["---",f'title: {jstr(name)}',f'aliases: {json.dumps(handles,ensure_ascii=False)}',
        "type: crm-lead","source: telegram-dm","origin: mixed","authored_by: hybrid",
        f'status: {jstr(status)}',f'category: {jstr(cat)}',f'company: {jstr(company)}',
        f'role: {jstr(s.get("role"))}',f'country: {jstr(s.get("country"))}',
        f'handles: {json.dumps(handles,ensure_ascii=False)}',
        f'crm_tier: {jstr(tier)}',f'crm_telegram_id: {jstr(b.get("telegram_id"))}',
        f'dm_msgs: {len(b.get("dm",[]))}','dm_two_way: true',
        f'date_added: {DATE}','concept: "[[concept-platinum-crm]]"',
        f'lead_id: {jstr(b["lead_id"])}',
        f'tags: ["crm","lead","platinum-crm","platinum-dm","tier-{tier}","status-{re.sub(chr(95),chr(45),status)}"]',
        "---"]
    if b.get("operators"): fm.insert(-1, f'crm_operators: {json.dumps(b["operators"][:6],ensure_ascii=False)}')
    bd=[f"# {name}"+(f" — {company}" if company else ""),"",
        f"> [!info] CRM-лид Platinum (DM) · {TIER_RU.get(tier,'—')} · **{status}** · DM {len(b.get('dm',[]))} сообщ.",""]
    if s.get("summary"): bd+=["## Сводка",s["summary"],""]
    facts=[]
    for k,lab in (("what_they_do","Чем занимаются"),("what_they_want","Что хотят"),
                  ("what_we_offered","Что предложили"),("agreements","Договорённости"),("outcome","Итог")):
        if s.get(k): facts.append(f"- **{lab}:** {s[k]}")
    if facts: bd+=["## Ключевое"]+facts+[""]
    bd+=["## CRM-данные (entity export)",
         f"- **Квалификация:** {TIER_RU.get(tier,'—')}"+(" · теги: "+", ".join(b.get("tags",[])[:8]) if b.get("tags") else "")]
    if b.get("operators"): bd.append("- **Оператор(ы) CRM:** "+", ".join(b["operators"][:6]))
    if b.get("bio","").strip(): bd.append("- **Bio:** "+b["bio"].strip().replace("\n"," ")[:400])
    meta=[]
    if b.get("created"): meta.append("в CRM с "+b["created"])
    if b.get("last_activity"): meta.append("посл. активность "+b["last_activity"])
    if meta: bd.append("- **"+" · ".join(meta)+"**")
    bd.append("- _источник: crm_entities_export.csv (DM-лид без звонка)_")
    dm=b.get("dm",[])[:8]
    if dm:
        bd+=["","## Переписка (DM, выдержка)"]
        for m in dm:
            bd.append(f"- **{ne1(m.get('by','?'))}:** "+ne1(m.get("text","")).replace("\n"," ")[:300])
    bd+=["","## Связи","- [[_Platinum-CRM-MOC]] · [[concept-platinum-crm]]",""]
    io.open(os.path.join(folder,slug+".md"),"w",encoding="utf-8").write("\n".join(fm)+"\n\n"+"\n".join(bd))
    if s: rich+=1
    else: thin+=1
print("DM cards rendered:",rich+thin," rich(synth):",rich," thin(no synth yet):",thin)
print("staging_dm:",ST)
