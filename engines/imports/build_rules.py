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
Build Layer-1 (the Bible) from curated rules + Trello rule-cards into staging.
- 83 inline rules -> reglament-*.md (full body, provenance, theme, tags)
- ~200 unique Trello rule-cards -> _Bible-Trello-Index.md (title + link)
- _Operations-Bible-MOC.md grouping inline rules by theme, linking the index
  and the existing concept [[concept-bible-platinum]]
- appends "Регламенты этого дня" backlinks into the relevant day-ledgers
Dedup inline rules by normalized statement hash (covers the dedup phase).
"""
import json, re, hashlib, collections
from pathlib import Path
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OUT = Path(_IROOT)
STAGE = OUT / "staging"
RULES_DIR = STAGE / "03-Insights" / "Operations"
LEDGER_DIR = STAGE / "01-Conversations" / "Telegram" / "Assistants-Ops" / "sessions"
RULES_DIR.mkdir(parents=True, exist_ok=True)

_MAP = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z',
 'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s',
 'т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'',
 'ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slugify(text, maxlen=55):
    s="".join(_MAP.get(c,c) for c in (text or "").lower())
    s=re.sub(r"[^a-z0-9\s-]","",s); s=re.sub(r"[\s_-]+","-",s).strip("-")
    return s[:maxlen].strip("-") or "rule"
def yesc(s): return (s or "").replace('"',"'").replace("\n"," ").strip()

# ---- load curated rules + candidate context -------------------------------
cand = {c["id"]: c for c in json.load(open(OUT/"rule_candidates.json", encoding="utf-8"))}
curated = []
for i in range(8):
    curated += json.load(open(OUT/"_rulebatch"/f"curated_{i:02d}.json", encoding="utf-8"))
rules = [c for c in curated if c.get("is_rule")]

THEME_RU = {
 "child-education":"Дети и обучение","communications-protocol":"Коммуникации и протокол",
 "procurement-vendors":"Закупки и подрядчики","travel-logistics":"Поездки и логистика",
 "access-security":"Доступы и безопасность","finance-payments":"Финансы и платежи",
 "social-media":"Соцсети и маркетинг","staff-hr":"Персонал и найм",
 "household-general":"Бытовое (общее)"}

# ---- generate reglament notes (dedup by statement hash) -------------------
seen={}; notes=[]; dups=0
for r in sorted(rules, key=lambda x: (cand.get(x["id"],{}).get("date") or "")):
    stmt=re.sub(r"\s+"," ",r["statement"]).strip()
    h=hashlib.md5(stmt.lower().encode("utf-8")).hexdigest()[:10]
    if h in seen: dups+=1; continue
    seen[h]=True
    src=cand.get(r["id"],{})
    origin=r.get("origin","mixed"); authored=r.get("authored_by","hybrid")
    theme=r.get("theme","household-general")
    tags=list(dict.fromkeys(["регламент"]+[t for t in r.get("tags",[]) if t]))
    if origin=="anton": tags.append("anton-original")
    if origin=="Alina":  tags.append("origin-Alina")
    title=stmt[:80].rsplit(" ",1)[0] if len(stmt)>80 else stmt
    slug=slugify(stmt); fn=f"reglament-{slug}.md"
    if (RULES_DIR/fn).exists(): fn=f"reglament-{slug}-{h}.md"
    fm=["---", f'title: "{yesc(title)}"', "type: reglament",
        "source: telegram-assistants-ops", f"origin: {origin}",
        f"authored_by: {authored}",
        f'transcribed_by: "{yesc(src.get("relayed_by") or "—")}"',
        f'posted_by: "{yesc(src.get("sender") or "")}"',
        f"date_established: {src.get('date') or ''}",
        f"theme: {theme}", f'applies_to: "{yesc(r.get("applies_to",""))}"',
        "status: active", f"tags: [{', '.join(tags)}]",
        'concept: "[[concept-bible-platinum]]"', f"msg_id: {r['id']}",
        f"confidence: {r.get('confidence','')}", "---", "",
        f"**Правило:** {stmt}", ""]
    if r.get("applies_to"): fm.append(f"**Применяется к:** {r['applies_to']}")
    if src.get("date"): fm.append(f"**Источник:** [[Sessions-{src['date']}]] · чат Assistants-Ops")
    fm.append("**Свод:** [[concept-bible-platinum|Holy Bible — свод регламентов]]")
    (RULES_DIR/fn).write_text("\n".join(fm)+"\n", encoding="utf-8")
    notes.append({"fn":fn[:-3],"title":title,"origin":origin,"theme":theme,"date":src.get("date")})

# ---- Trello rule-card index (unique by normalized title) ------------------
tcards=json.load(open(OUT/"trello_rules.json", encoding="utf-8"))
uniq={}
for c in tcards:
    key=re.sub(r"\s+"," ",c["title"].lower()).strip()
    if key not in uniq: uniq[key]=c
def bucket(t):
    t=t.lower()
    for kw,th in [("урок","Дети и обучение"),("дет","Дети и обучение"),("нян","Дети и обучение"),
        ("подрядчик","Закупки и подрядчики"),("отгруз","Закупки и подрядчики"),("товар","Закупки и подрядчики"),
        ("покупк","Закупки и подрядчики"),("достав","Закупки и подрядчики"),("поиск","Закупки и подрядчики"),
        ("кален","Поездки и логистика"),("локац","Поездки и логистика"),("поезд","Поездки и логистика"),
        ("брон","Поездки и логистика"),("встреч","Поездки и логистика"),("виз","Поездки и логистика"),
        ("iban","Финансы и платежи"),("оплат","Финансы и платежи"),("стоимост","Финансы и платежи"),("расч","Финансы и платежи"),
        ("безопас","Доступы и безопасность"),("доступ","Доступы и безопасность"),("парол","Доступы и безопасность"),
        ("gpt","Коммуникации и протокол"),("отчёт","Коммуникации и протокол"),("отчет","Коммуникации и протокол"),
        ("звон","Коммуникации и протокол"),("чат","Коммуникации и протокол"),("аудио","Коммуникации и протокол"),
        ("сотрудник","Персонал и найм"),("ассистент","Персонал и найм"),("найм","Персонал и найм"),("персонал","Персонал и найм"),
        ("автомобил","Бытовое (общее)"),("авто","Бытовое (общее)")]:
        if kw in t: return th
    return "Прочее"
tg=collections.defaultdict(list)
for c in uniq.values(): tg[bucket(c["title"])].append(c)
idx=["---","type: reference","title: \"Bible — индекс карточек Trello\"",
     "tags: [регламент, bible, trello, index]",
     'concept: "[[concept-bible-platinum]]"',"---","",
     "# 📋 Bible — формализованные регламенты (Trello)","",
     f"> {len(uniq)} уникальных карточек-регламентов. Тело правил живёт в Trello; "
     "здесь — навигационный индекс. Свод: [[concept-bible-platinum]].",""]
for th in sorted(tg):
    idx.append(f"## {th}")
    for c in sorted(tg[th], key=lambda x:x["title"]):
        idx.append(f"- [{yesc(c['title'])[:90]}]({c['url']})")
    idx.append("")
(RULES_DIR/"_Bible-Trello-Index.md").write_text("\n".join(idx)+"\n", encoding="utf-8")

# ---- Operations Bible MOC -------------------------------------------------
oc=collections.Counter(n["origin"] for n in notes)
byth=collections.defaultdict(list)
for n in notes: byth[n["theme"]].append(n)
moc=["---","type: moc",'title: "Operations Bible — регламенты (рабочий чат)"',
     "tags: [moc, регламент, bible]", 'concept: "[[concept-bible-platinum]]"',"---","",
     "# 📖 Operations Bible — регламенты из рабочего чата","",
     f"> {len(notes)} правил с полным текстом (из переписки) · "
     f"origin: {', '.join(f'{k}={v}' for k,v in oc.items())}. "
     f"Дубликатов слито: {dups}.","",
     "**Свод-концепт:** [[concept-bible-platinum]] (Holy Bible Platinum)  ",
     "**Формализованные карточки:** [[_Bible-Trello-Index]] (≈" f"{len(uniq)} на Trello)","",
     "Полнотекстовые правила (из чата), по темам:",""]
for th in sorted(byth, key=lambda x:-len(byth[x])):
    moc.append(f"## {THEME_RU.get(th,th)}  ({len(byth[th])})")
    for n in sorted(byth[th], key=lambda x:x["date"] or ""):
        tag="🟢" if n["origin"]=="anton" else "⚪"
        moc.append(f"- {tag} [[{n['fn']}\\|{yesc(n['title'])[:75]}]]")
    moc.append("")
moc+=["---","🟢 = origin: anton (#anton-original) · ⚪ = origin: mixed (SOP команды)"]
(RULES_DIR/"_Operations-Bible-MOC.md").write_text("\n".join(moc)+"\n", encoding="utf-8")

# ---- append rule backlinks into day-ledgers -------------------------------
rules_by_day=collections.defaultdict(list)
for n in notes:
    if n["date"]: rules_by_day[n["date"]].append(n)
patched=0
for day,ns in rules_by_day.items():
    f=LEDGER_DIR/f"Sessions-{day}.md"
    if not f.exists(): continue
    txt=f.read_text(encoding="utf-8")
    if "**Регламенты этого дня:**" in txt: continue
    links=", ".join(f"[[{n['fn']}]]" for n in ns)
    txt=re.sub(r"(\n> .*?потоки:.*?\n)", r"\1\n**Регламенты этого дня:** "+links+"\n",
               txt, count=1, flags=re.S)
    f.write_text(txt, encoding="utf-8"); patched+=1

print("RULE_NOTES", len(notes), "DUPS", dups)
print("TRELLO_INDEX_CARDS", len(uniq))
print("LEDGERS_PATCHED", patched)
print("ORIGIN", dict(oc))
