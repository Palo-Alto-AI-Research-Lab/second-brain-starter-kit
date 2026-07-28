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
"""Promote ALL Platinum-CRM leads with >=1 call (incl no-show) OR >=20 DM msgs to 07-People.
New -> create; mine(context:platinum-crm) -> overwrite; others(Personal-DM/orig) -> enrich (append)."""
import glob, io, os, re
LV=r"E:/Obsidian/Owner-Knowledge/04-Projects/crypto/Platinum-CRM/leads"
PPL=r"E:/Obsidian/Owner-Knowledge/07-People"
TR=str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя","abvgdeejziyklmnoprstufhccss y eya")
def slugify(t):
    t=(t or "").lower().translate(TR); t=re.sub(r"['`’]","",t); t=re.sub(r"[^a-z0-9]+","-",t).strip("-")
    return re.sub(r"-+","-",t)[:46].strip("-") or "lead"
def fv(fm,k):
    m=re.search(r'%s:\s*"?([^"\n]*)"?'%k,fm); return (m.group(1).strip() if m else "")
TIER_RU={"investor":"Инвестор","founder":"Фаундер/проект","kol":"KOL","b2b":"B2B","other":"—","not_investor":"Не инвестор"}

# existing people index
exist={}
for f in glob.glob(PPL+"/*.md"):
    b=os.path.basename(f)[:-3]
    try: c=io.open(f,encoding="utf-8").read()
    except: c=""
    exist[b.lower()]=(f, "context: platinum-crm" in c)
used=set(exist.keys())

created=overwritten=enriched=skipped=0
for f in glob.glob(LV+"/**/*.md",recursive=True):
    t=io.open(f,encoding="utf-8").read(); fm=t.split("---",2)[1] if t.count("---")>=2 else t
    src=fv(fm,"source"); dm=int(fv(fm,"dm_msgs") or 0); ncalls=int(fv(fm,"n_calls") or 0)
    has_call=(src=="telegram-faaa") or ncalls>=1
    if not (has_call or dm>=20): continue
    name=fv(fm,"title")
    if not name: continue
    card=os.path.basename(f)[:-3]
    org=fv(fm,"company"); role=fv(fm,"role"); country=fv(fm,"country")
    tier=fv(fm,"crm_tier") or fv(fm,"category"); status=fv(fm,"status")
    _hm=re.search(r'handles:\s*\[(.*?)\]', fm)
    _hl=[x.strip().strip('"').strip("'") for x in (_hm.group(1).split(",") if _hm else []) if x.strip()]
    handle=_hl[0] if _hl else ""
    sm=re.search(r"## Сводка\s*\n+([^\n]+)",t); summary=sm.group(1).strip() if sm else ""
    base="person-"+slugify(name)
    key=base.lower()
    # content for a full note
    def full_note():
        fmn=["---",f'title: "{name}"',"type: person","context: platinum-crm",
             f'org: "{org}"',f'role: "{role}"',f'country: "{country}"',f'tier: "{tier}"',
             f'status: "{status}"',"relationship: lead",f'telegram: "{handle}"',
             f'n_calls: {ncalls}',f'dm_msgs: {dm}',f'lead_card: "[[{card}]]"',
             "origin: mixed","authored_by: hybrid",
             f'tags: [person, platinum-crm, crm-lead, status-{re.sub(chr(95),chr(45),status or "unknown")}]',"---"]
        body=[f"# {name}","",
              f"> [!info] Platinum CRM · {org or '—'} · {TIER_RU.get(tier,tier or '—')} · {status or '—'}","",
              "## Кто это", summary or " · ".join([x for x in (role,org,country) if x]) or "CRM-лид Platinum.","",
              "## Связи",f"- Лид-карточка: [[{card}]]",
              "- [[concept-platinum-crm]] · [[_Platinum-CRM-MOC]] · [[_People-MOC]]",""]
        return "\n".join(fmn)+"\n\n"+"\n".join(body)
    if key in exist:
        path,is_mine=exist[key]
        if is_mine:
            io.open(path,"w",encoding="utf-8").write(full_note()); overwritten+=1
        else:
            c=io.open(path,encoding="utf-8").read()
            if "## Platinum CRM" in c: skipped+=1
            else:
                add=f"\n\n## Platinum CRM\n- Лид-карточка: [[{card}]] · {org or '—'} · {TIER_RU.get(tier,tier or '')} · {status or '—'}\n- [[_Platinum-CRM-MOC]]\n"
                io.open(path,"a",encoding="utf-8").write(add); enriched+=1
    else:
        s=base; k=2
        while s.lower() in used: s=base+"-"+str(k); k+=1
        used.add(s.lower())
        io.open(os.path.join(PPL,s+".md"),"w",encoding="utf-8").write(full_note()); created+=1

# MOC: replace static section with a Dataview-driven one
moc=PPL+"/_People-MOC.md"; txt=io.open(moc,encoding="utf-8").read()
txt=re.sub(r"\n## Platinum-CRM —.*$","",txt,flags=re.S)
total=created+overwritten
dv=("\n## Platinum-CRM — контакты ("+str(total)+" person-notes + "+str(enriched)+" обогащено)\n\n"
    "_Все лиды с ≥1 звонком или ≥20 DM-сообщениями. Полный слой: [[_Platinum-CRM-MOC]]._\n\n"
    "```dataview\nTABLE org AS \"Где работает\", tier AS \"Тир\", status AS \"Статус\", lead_card AS \"Карточка\"\n"
    "FROM \"07-People\"\nWHERE context = \"platinum-crm\"\nSORT status ASC, tier ASC\n```\n")
io.open(moc,"w",encoding="utf-8").write(txt.rstrip()+"\n"+dv)
print(f"created={created} overwritten={overwritten} enriched={enriched} skipped(already)={skipped}")
print("07-People total:", len(glob.glob(PPL+"/*.md")))
