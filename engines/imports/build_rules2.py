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
"""
Build Layer-1 v2 into staging:
- 9 theme sub-concepts (children of concept-bible-platinum)
- 83 reglament-*.md re-pointed to their theme sub-concept (+ related_holybible flag)
- individual Trello rule-card notes in trello-cards/ (replacing the bare-link index)
- _Operations-Bible-MOC.md (theme groups link sub-concepts) + _Bible-Trello-Index.md (MOC of card notes)
Then re-validate & re-copy Operations + new sub-concepts into the vault.
"""
import json, re, hashlib, collections
from pathlib import Path
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OUT = Path(_IROOT)
STAGE = OUT / "staging"
OPS = STAGE / "03-Insights" / "Operations"
CARDS = OPS / "trello-cards"
CONC = STAGE / "06-Concepts"
LEDGER = STAGE / "01-Conversations" / "Telegram" / "Assistants-Ops" / "sessions"
for d in (OPS, CARDS, CONC): d.mkdir(parents=True, exist_ok=True)
# clear previous Operations md (fresh rebuild), keep ledgers intact
for p in OPS.glob("*.md"): p.unlink()
for p in CARDS.glob("*.md"): p.unlink()

_MAP={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i',
 'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
 'ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slugify(t,m=55):
    s="".join(_MAP.get(c,c) for c in (t or "").lower())
    s=re.sub(r"[^a-z0-9\s-]","",s); s=re.sub(r"[\s_-]+","-",s).strip("-")
    return s[:m].strip("-") or "x"
def yesc(s): return (s or "").replace('"',"'").replace("\n"," ").strip()

THEME = {  # key -> (concept-slug, RU name, tag)
 "communications-protocol":("concept-bible-communications","Коммуникации и протокол","коммуникации"),
 "child-education":("concept-bible-child-education","Дети и обучение","дети-обучение"),
 "procurement-vendors":("concept-bible-procurement","Закупки и подрядчики","закупки"),
 "travel-logistics":("concept-bible-travel","Поездки и логистика","поездки"),
 "access-security":("concept-bible-access-security","Доступы и безопасность","доступы"),
 "finance-payments":("concept-bible-finance","Финансы и платежи","финансы"),
 "social-media":("concept-bible-social-media","Соцсети и маркетинг","соцсети"),
 "staff-hr":("concept-bible-staff-hr","Персонал и найм","персонал"),
 "household-general":("concept-bible-household","Бытовое (общее)","быт"),
}
def th_of(k): return THEME.get(k, THEME["household-general"])

# ---- load curated + dedup -------------------------------------------------
cand={c["id"]:c for c in json.load(open(OUT/"rule_candidates.json",encoding="utf-8"))}
curated=[]
for i in range(8): curated+=json.load(open(OUT/"_rulebatch"/f"curated_{i:02d}.json",encoding="utf-8"))
rules=[c for c in curated if c.get("is_rule")]
dedup=json.load(open(OUT/"dedup_map.json",encoding="utf-8"))
tdedup=json.load(open(OUT/"trello_dedup.json",encoding="utf-8"))
# semantic-dedup decisions (persist across rebuilds; mirrors manual_rules.json pattern)
_suppath=OUT/"superseded_rules.json"
superseded=json.load(open(_suppath,encoding="utf-8")) if _suppath.exists() else {}

# manually-added rules (Anton-requested or clearly-needed) — reproducible append
mr_path=OUT/"manual_rules.json"
if mr_path.exists():
    for mr in json.load(open(mr_path,encoding="utf-8")):
        cand[mr["id"]]={"id":mr["id"],"date":mr.get("date"),
                        "sender":mr.get("posted_by"),"relayed_by":mr.get("relayed_by")}
        rules.append({"id":mr["id"],"is_rule":True,"statement":mr["statement"],
                      "theme":mr.get("theme","household-general"),"applies_to":mr.get("applies_to",""),
                      "origin":mr.get("origin","mixed"),"authored_by":mr.get("authored_by","hybrid"),
                      "tags":mr.get("tags",[]),"confidence":mr.get("confidence",1.0)})

# ---- 1. theme sub-concepts ------------------------------------------------
first_date=min((cand.get(r["id"],{}).get("date") or "9999") for r in rules)
for k,(slug,ru,tag) in THEME.items():
    f=CONC/f"{slug}.md"
    if f.exists() and "status: defined" in f.read_text(encoding="utf-8"):
        continue   # don't clobber a fleshed-out concept (flesh_concepts.py owns it)
    f.write_text("\n".join([
        "---", f"title: \"Библия — {ru}\"",
        f"aliases: [{ru}, регламенты {ru.lower()}]",
        "type: concept", "authored_by: hybrid", "origin: anton",
        f"created: {first_date}", "status: stub",
        'parent_concepts: ["[[concept-bible-platinum]]"]',
        f"tags: [concept, регламент, bible, {tag}]", "---", "",
        f"# Библия — {ru}", "",
        f"> Тематическая ветка «Библии»: бытовой/операционный слой регламентов из "
        f"рабочего чата с ассистентами. Родитель: [[concept-bible-platinum]] "
        f"(крипто/VC-плейбук + общий свод).", "",
        "## Регламенты этой темы", "",
        f"Полный список — [[_Operations-Bible-MOC]] · карточки Trello — [[_Bible-Trello-Index]].", "",
        "## Связанные", "", "- [[concept-bible-platinum]] — свод регламентов (Holy Bible)",
    ])+"\n", encoding="utf-8")

# ---- 2. reglament notes (re-pointed + dedup flag) -------------------------
seen={}; notes=[]; dups=0
for r in sorted(rules, key=lambda x:(cand.get(x["id"],{}).get("date") or "")):
    stmt=re.sub(r"\s+"," ",r["statement"]).strip()
    h=hashlib.md5(stmt.lower().encode()).hexdigest()[:10]
    if h in seen: dups+=1; continue
    seen[h]=True
    src=cand.get(r["id"],{}); origin=r.get("origin","mixed"); authored=r.get("authored_by","hybrid")
    tk=r.get("theme","household-general"); cslug,cru,ctag=th_of(tk)
    tags=list(dict.fromkeys(["регламент",ctag]+[t for t in r.get("tags",[]) if t]))
    if origin=="anton": tags.append("anton-original")
    if origin=="Alina": tags.append("origin-Alina")
    title=stmt[:80].rsplit(" ",1)[0] if len(stmt)>80 else stmt
    slug=slugify(stmt); fn=f"reglament-{slug}.md"
    if (OPS/fn).exists(): fn=f"reglament-{slug}-{h}.md"
    sid=str(r["id"]); _sup = sid in superseded
    status = "superseded" if _sup else "active"
    fm=["---", f'title: "{yesc(title)}"', "type: reglament",
        "source: telegram-assistants-ops", f"origin: {origin}", f"authored_by: {authored}",
        f'transcribed_by: "{yesc(src.get("relayed_by") or "—")}"',
        f'posted_by: "{yesc(src.get("sender") or "")}"',
        f"date_established: {src.get('date') or ''}", f"theme: {tk}",
        f'applies_to: "{yesc(r.get("applies_to",""))}"', f"status: {status}",
        f"tags: [{', '.join(tags)}]", f'concept: "[[{cslug}]]"', f"msg_id: {r['id']}",
        f"confidence: {r.get('confidence','')}"]
    if r["id"] in dedup:
        fm.append(f'related_holybible: "[[{dedup[r["id"]]["hb"]}]]"')
        fm.append(f"holybible_overlap: {dedup[r['id']]['score']}")
    if _sup:
        fm.append(f'superseded_by: "[[{superseded[sid]["by"]}]]"')
    fm+=["---","", f"**Правило:** {stmt}", ""]
    if r.get("applies_to"): fm.append(f"**Применяется к:** {r['applies_to']}")
    if src.get("date"): fm.append(f"**Источник:** [[Sessions-{src['date']}]] · чат Assistants-Ops")
    fm.append(f"**Тема:** [[{cslug}|Библия — {cru}]]  ·  **Свод:** [[concept-bible-platinum]]")
    if r["id"] in dedup: fm.append(f"**Перекликается с Holy Bible:** [[{dedup[r['id']]['hb']}]]")
    (OPS/fn).write_text("\n".join(fm)+"\n", encoding="utf-8")
    notes.append({"fn":fn[:-3],"title":title,"origin":origin,"theme":tk,"date":src.get("date"),"status":status})

# ---- 3. individual Trello rule-card notes ---------------------------------
def bucket(t):
    t=t.lower()
    table=[("урок","child-education"),("дет","child-education"),("нян","child-education"),("педагог","child-education"),
     ("подрядчик","procurement-vendors"),("отгруз","procurement-vendors"),("товар","procurement-vendors"),
     ("покупк","procurement-vendors"),("достав","procurement-vendors"),("поиск","procurement-vendors"),("возврат","procurement-vendors"),
     ("кален","travel-logistics"),("локац","travel-logistics"),("поезд","travel-logistics"),("брон","travel-logistics"),
     ("встреч","travel-logistics"),("виз","travel-logistics"),("рейс","travel-logistics"),("парков","travel-logistics"),
     ("iban","finance-payments"),("оплат","finance-payments"),("стоимост","finance-payments"),("расч","finance-payments"),("счет","finance-payments"),
     ("безопас","access-security"),("доступ","access-security"),("парол","access-security"),("админ","access-security"),
     ("gpt","communications-protocol"),("отчёт","communications-protocol"),("отчет","communications-protocol"),
     ("звон","communications-protocol"),("чат","communications-protocol"),("аудио","communications-protocol"),("дозвон","communications-protocol"),
     ("сотрудник","staff-hr"),("ассистент","staff-hr"),("найм","staff-hr"),("персонал","staff-hr"),("собеседов","staff-hr"),
     ("fb","social-media"),("фейсбук","social-media"),("инстаг","social-media"),("пост","social-media"),
     ("автомобил","household-general"),("авто","household-general")]
    for kw,th in table:
        if kw in t: return th
    return "household-general"

tcards=json.load(open(OUT/"trello_rules.json",encoding="utf-8"))
uniq={}
for c in tcards: uniq.setdefault(re.sub(r"\s+"," ",c["title"].lower()).strip(),c)
card_notes=[]; cseen={}
for key,c in uniq.items():
    title=c["title"].strip()
    if len(title)<8 or len(re.findall(r"[а-яёa-z]{3,}",title))<2: continue
    tk=bucket(title); cslug,cru,ctag=th_of(tk)
    slug=slugify(title); fn=f"reglament-card-{slug}.md"
    if fn in cseen: continue
    cseen[fn]=True
    tags=["регламент","trello","bible",ctag]
    fm=["---", f'title: "{yesc(title[:90])}"', "type: reglament-card",
        "source: trello-bible", "origin: anton", "authored_by: hybrid",
        "status: on-trello", f"theme: {tk}", f"tags: [{', '.join(tags)}]",
        f'concept: "[[{cslug}]]"', f'trello_url: "{c["url"]}"']
    if key in tdedup:
        fm.append(f'related_holybible: "[[{tdedup[key]["hb"]}]]"')
    fm+=["---","", f"# {title}", "",
        f"> Формализованный регламент из доски Trello. Тело правила — в карточке.", "",
        f"**Открыть в Trello:** [{title[:70]}]({c['url']})", "",
        f"**Тема:** [[{cslug}|Библия — {cru}]]  ·  **Свод:** [[concept-bible-platinum]]"]
    if key in tdedup: fm.append(f"**Перекликается с Holy Bible:** [[{tdedup[key]['hb']}]]")
    (CARDS/fn).write_text("\n".join(fm)+"\n", encoding="utf-8")
    card_notes.append({"fn":fn[:-3],"title":title,"theme":tk,"url":c["url"]})

# ---- 4. MOCs --------------------------------------------------------------
active=[n for n in notes if n.get("status")!="superseded"]
nsup=len(notes)-len(active)
oc=collections.Counter(n["origin"] for n in active)
byth=collections.defaultdict(list)
for n in active: byth[n["theme"]].append(n)
moc=["---","type: moc",'title: "Operations Bible — регламенты (рабочий чат)"',
     "tags: [moc, регламент, bible]", 'concept: "[[concept-bible-platinum]]"',"---","",
     "# 📖 Operations Bible — регламенты из рабочего чата","",
     f"> {len(active)} активных полнотекстовых правил · origin: {', '.join(f'{k}={v}' for k,v in oc.items())} · "
     f"дублей слито: {dups} · superseded скрыто: {nsup} · перекличек с Holy Bible: {len(dedup)}.","",
     "**Свод:** [[concept-bible-platinum]] · **Карточки Trello:** [[_Bible-Trello-Index]]","",
     "Полнотекстовые правила по темам (🟢 anton / ⚪ команда):",""]
for tk in sorted(byth, key=lambda x:-len(byth[x])):
    cslug,cru,_=th_of(tk)
    moc.append(f"## [[{cslug}\\|{cru}]]  ({len(byth[tk])})")
    for n in sorted(byth[tk], key=lambda x:x["date"] or ""):
        tag="🟢" if n["origin"]=="anton" else "⚪"
        moc.append(f"- {tag} [[{n['fn']}\\|{yesc(n['title'])[:75]}]]")
    moc.append("")

# ---- 4b. disk-scan: правила, живущие в ЖИВОМ волте вне корпуса этого импорта.
# Без этого перегенерация MOC теряла правила, добавленные напрямую (intake/машинный
# слой), и затирала ручные вставки — они становились MOC-сиротами (аудит
# rule_home_guard.py --moc-audit). Полный тематический каталог строит build_bible_moc.py.
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
_known={n["fn"].lower() for n in notes}
_extra=set()
for _d in (Path(_VROOT)/"03-Insights"/"Operations", Path(_VROOT)/"05-Resources"/"Protocols"):
    if not _d.is_dir(): continue
    for _p in _d.rglob("*.md"):
        if {".stversions","trello-cards"} & set(_p.parts): continue
        if not _p.name.startswith(("reglament-","protocol-")): continue
        if _p.stem.lower() not in _known: _extra.add(_p.stem)
moc+=["## Правила вне корпуса чата (автоскан живого волта)","",
      f"> {len(_extra)} правил, добавленных в волт напрямую (intake/машинный слой). "
      "Полный тематический каталог: [[_Bible-Rules-MOC]] (build_bible_moc.py).",""]
for _s in sorted(_extra): moc.append(f"- [[{_s}]]")
moc.append("")
(OPS/"_Operations-Bible-MOC.md").write_text("\n".join(moc)+"\n", encoding="utf-8")

cbyth=collections.defaultdict(list)
for n in card_notes: cbyth[n["theme"]].append(n)
idx=["---","type: moc",'title: "Bible — карточки Trello"',
     "tags: [moc, регламент, bible, trello]", 'concept: "[[concept-bible-platinum]]"',"---","",
     "# 📋 Bible — формализованные регламенты (Trello)","",
     f"> {len(card_notes)} карточек-регламентов (индивидуальные заметки). "
     f"Тело правил — в Trello. Свод: [[concept-bible-platinum]].",""]
for tk in sorted(cbyth, key=lambda x:-len(cbyth[x])):
    cslug,cru,_=th_of(tk)
    idx.append(f"## [[{cslug}\\|{cru}]]  ({len(cbyth[tk])})")
    for n in sorted(cbyth[tk], key=lambda x:x["title"].lower()):
        idx.append(f"- [[{n['fn']}\\|{yesc(n['title'])[:80]}]]")
    idx.append("")
(OPS/"_Bible-Trello-Index.md").write_text("\n".join(idx)+"\n", encoding="utf-8")

print("RULE_NOTES",len(notes),"DUPS",dups,"RULE_RELATED_HB",len(dedup))
print("SUBCONCEPTS",len(THEME))
print("TRELLO_CARD_NOTES",len(card_notes),"TRELLO_RELATED_HB",len(tdedup))
print("ORIGIN",dict(oc))
