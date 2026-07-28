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
"""Generate staging notes for the Apple Notes import.

Consumes: notes_export.json + analysis.json + triage_results/*.json +
          concept_plan.json + secrets_verdict.json
Produces: %IMPORTS%\\staging\\apple-notes\\  (mirrors vault tree)
          %IMPORTS%\\apple-notes\\_quarantine\\   (secret notes — NEVER into vault)
          gen_report.json (counts for self-verification)
Deterministic, idempotent (re-run wipes and regenerates staging). 0 LLM tokens.
"""
import json, re, shutil, sys
from pathlib import Path
from collections import Counter, defaultdict

EXPORT = Path(r"E:\Google Drive on HP Palo Alto\!_Claude_Mac16\Apple Notes Export 2026-06-11")
OUT = Path(r"%IMPORTS%\apple-notes")
STAGING = Path(r"%IMPORTS%\staging\apple-notes")
VAULT = Path(r"%VAULT%")
QUAR = OUT / "_quarantine"
TODAY = "2026-06-12"

NOTES_DIR = STAGING / "01-Conversations" / "Apple-Notes" / "notes"
ATT_DIR = STAGING / "01-Conversations" / "Apple-Notes" / "attachments"
MOC_DIR = STAGING / "01-Conversations" / "Apple-Notes"
CONCEPTS_DIR = STAGING / "06-Concepts"

# ---------- load ----------
data = json.loads((EXPORT / "notes_export.json").read_text(encoding="utf-8"))
notes = data["notes"]
analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
recs = {r["idx"]: r for r in analysis["notes"]}

triage = {}
for f in sorted((OUT / "triage_results").glob("batch_*_result.json")):
    b = json.loads(f.read_text(encoding="utf-8"))
    for t in b["notes"]:
        triage[t["idx"]] = t

plan = json.loads((OUT / "concept_plan.json").read_text(encoding="utf-8"))
remap = {int(k): v for k, v in plan.get("remap", {}).items()}
new_concepts = {c["slug"]: c for c in plan.get("create", [])}

verdict = json.loads((OUT / "secrets_verdict.json").read_text(encoding="utf-8"))
secret_idx = {s["idx"]: s["kind"] for s in verdict["secrets"]}

existing_concepts = set(json.loads((OUT / "concepts_list.json").read_text(encoding="utf-8")))

missing = [i for i in range(len(notes)) if i not in triage]
if missing:
    print("FATAL: missing triage for idx:", missing[:20], "total", len(missing))
    sys.exit(1)

# ---------- reset staging ----------
if STAGING.exists():
    shutil.rmtree(STAGING)
for d in (NOTES_DIR, ATT_DIR, CONCEPTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
QUAR.mkdir(exist_ok=True)

def yaml_str(s):
    s = (s or "").replace('"', "'").replace("\n", " ").strip()
    return '"' + s + '"'

def concept_for(idx, t):
    c = (t.get("concept") or "").strip()
    if idx in remap:
        c = remap[idx]
    if c.startswith("NEW:"):
        # unresolved NEW that synthesis didn't remap -> try to extract slug
        m = re.search(r'concept-[a-z0-9-]+', c)
        c = m.group(0) if m else ""
    if c and c not in existing_concepts and c not in new_concepts:
        return c, False  # invented slug -> flag
    return c, True

# ---------- generate ----------
skipped_dups, quarantined, junk_lines, created_files = [], [], [], []
bad_slugs = Counter()
by_year = defaultdict(list)
by_cat = defaultdict(list)
by_concept = defaultdict(list)
att_to_copy = set()
persons_links = 0

# person matching: existing person-* slugs (translit match on full name)
TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
    'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}
def translit(s):
    import unicodedata
    out = ''.join(TRANSLIT.get(ch, ch) for ch in s.lower())
    out = unicodedata.normalize('NFKD', out)
    out = ''.join(c for c in out if ord(c) < 128)
    out = re.sub(r'[^a-z0-9]+', '-', out).strip('-')
    return re.sub(r'-{2,}', '-', out)

person_slugs = {p.stem for p in (VAULT / "07-People").glob("person-*.md")}
new_person_candidates = Counter()

def person_links(t):
    links, news = [], []
    for name in (t.get("persons") or []):
        sl = "person-" + translit(name)[:50].strip('-')
        if sl in person_slugs:
            links.append(f"[[{sl}]]")
        else:
            news.append(name)
    return links, news

for i, n in enumerate(notes):
    r, t = recs[i], triage[i]
    title = (n.get("title") or "Untitled").strip()
    md = n.get("markdown") or ""
    cat = t.get("category") or "thought"
    # 1) secrets -> quarantine (outside vault)
    if i in secret_idx or cat == "credential":
        kind = secret_idx.get(i, t.get("secret_kind") or "credential")
        qf = QUAR / f"{r['slug']}.md"
        qf.write_text(f"<!-- QUARANTINED from Apple Notes import {TODAY}: {kind} -->\n\n" + md, encoding="utf-8")
        quarantined.append({"idx": i, "title": title, "kind": kind, "file": qf.name})
        continue
    # 2) exact dups -> skip (keep first occurrence)
    if r["dup_of"] is not None:
        skipped_dups.append({"idx": i, "title": title, "kept_idx": r["dup_of"]})
        continue
    # 3) junk -> one collector ledger
    if cat == "junk":
        body_one = re.sub(r'\s+', ' ', md)
        body_one = re.sub(r'!?\[\[([^\]]*)\]?\]?', r'(вложение: \1)', body_one)
        body_one = body_one.replace("[[", "").replace("]]", "")[:200]
        junk_lines.append(f"- `{r['created']}` **{title[:80]}** — {body_one}")
        continue
    # 4) normal note
    concept, ok_slug = concept_for(i, t)
    if concept and not ok_slug:
        bad_slugs[concept] += 1
        concept = ""
    tags = ["apple-notes"]
    origin = t.get("origin") or "anton"
    if origin == "anton":
        tags.append("anton-original")
    for tg in (t.get("tags") or [])[:4]:
        tg = tg.strip().lower().replace(" ", "-")
        if tg and tg not in tags:
            tags.append(tg)
    plinks, pnews = person_links(t)
    for nm in pnews:
        new_person_candidates[nm] += 1
    fm = ["---"]
    fm.append(f"title: {yaml_str(title)}")
    fm.append(f"aliases: [{yaml_str(title[:120])}]")
    fm.append("type: apple-note")
    fm.append(f"category: {cat}")
    fm.append("source: apple-notes")
    fm.append(f"apple_note_id: {yaml_str(n.get('apple_note_id') or '')}")
    fm.append("authored_by: human" if origin != "external" else "authored_by: human")
    fm.append(f"origin: {origin}")
    if origin == "external" and (t.get("external_author") or "").strip():
        fm.append(f"author: {yaml_str(t['external_author'])}")
    fm.append(f"date_created: {r['created']}")
    fm.append(f"date_modified: {r['modified']}")
    fm.append(f"date_added: {TODAY}")
    fm.append(f"valid_as_of: {r['modified'] or r['created']}")
    fm.append("volatility: slow" if cat in ("operational",) else "volatility: durable")
    fm.append(f"language: {r['lang']}")
    fm.append(f"value_score: {t.get('value', 0.5)}")
    if concept:
        fm.append(f'concept: "[[{concept}]]"')
    if t.get("deep_extract"):
        fm.append("deep_extract_candidate: true")
    fm.append(f"tags: [{', '.join(tags)}]")
    fm.append("---")
    body = md
    see = []
    if plinks:
        see.append("\n\n## См. также\n\n" + " · ".join(plinks))
        persons_links += len(plinks)
    out_md = "\n".join(fm) + "\n\n" + body + ("".join(see)) + "\n"
    f = NOTES_DIR / f"{r['slug']}.md"
    f.write_text(out_md, encoding="utf-8")
    created_files.append(r["slug"])
    yr = (r["created"] or "0000")[:4]
    by_year[yr].append((i, r["slug"], title, t.get("value", 0.5)))
    by_cat[cat].append((i, r["slug"], title))
    if concept:
        by_concept[concept].append((i, r["slug"], title))
    for a in (n.get("attachments") or []):
        att_to_copy.add(a["file"])

# ---------- junk ledger ----------
if junk_lines:
    jf = MOC_DIR / "Apple-Notes-junk-stubs.md"
    jf.write_text(
        "---\ntitle: \"Apple Notes — мусорные обрывки (коллектор)\"\ntype: apple-note\ncategory: junk-ledger\n"
        f"source: apple-notes\norigin: anton\nauthored_by: human\ndate_added: {TODAY}\ntags: [apple-notes]\n---\n\n"
        "# Мусорные обрывки из Apple Notes\n\nОбрывки без самостоятельной ценности — собраны в один файл, чтобы не плодить шум. Полные оригиналы: `%VAULT_ROOT%\_originals\\apple-notes\\`.\n\n"
        + "\n".join(junk_lines) + "\n", encoding="utf-8")

# ---------- attachments ----------
copied_att = 0
for a in sorted(att_to_copy):
    src = EXPORT / "attachments" / a
    if src.exists():
        shutil.copy2(src, ATT_DIR / a)
        copied_att += 1

# ---------- new concept notes ----------
for slug, c in new_concepts.items():
    body = ["---"]
    body.append(f"title: {yaml_str(c.get('title_ru') or slug.replace('concept-', '').replace('-', ' '))}")
    body.append("type: concept")
    body.append("authored_by: human")
    body.append("origin: anton")
    body.append(f"created: {TODAY}")
    body.append("source: apple-notes-import")
    body.append("tags: [concept, apple-notes]")
    body.append("---")
    body.append("")
    body.append(f"# {c.get('title_ru') or slug}")
    body.append("")
    body.append(c.get("description") or "")
    body.append("")
    body.append("## Заметки-источники (Apple Notes)")
    body.append("")
    for i in c.get("note_idxs", []):
        if i in recs and recs[i]["slug"] in created_files:
            body.append(f"- [[{recs[i]['slug']}]] — {triage[i].get('title_fix') or notes[i]['title'][:70]}")
    (CONCEPTS_DIR / f"{slug}.md").write_text("\n".join(body) + "\n", encoding="utf-8")

# ---------- MOC ----------
moc = ["---", 'title: "Apple Notes — MOC"', "type: moc", "source: apple-notes",
       f"date_added: {TODAY}", "tags: [moc, apple-notes]", "---", "",
       "# Apple Notes (iCloud, 2012–2026) — карта импорта", "",
       f"Экспорт с Mac **2026-06-11**, импортирован **{TODAY}**. Всего в экспорте 649 заметок; импортировано **{len(created_files)}** + 1 коллектор обрывков; {len(quarantined)} в карантине (секреты, НЕ в волте), {len(skipped_dups)} точных дублей пропущено.",
       "Оригинал (верный байт-в-байт): `%VAULT_ROOT%\_originals\\apple-notes\\2026-06-12__Apple Notes Export 2026-06-11\\`.", ""]
moc.append("## По категориям\n")
CAT_RU = {"thought": "Мысли и рефлексия", "idea": "Бизнес-идеи и схемы", "diary": "Дневниковое",
          "operational": "Операционное (задачи, списки, логистика)", "reference-external": "Внешние материалы (сохранённое чужое)",
          "prompt-draft": "Промпты и AI-черновики", "outreach-draft": "Письма и питчи (черновики)",
          "person": "Про людей", "stub": "Заглушки (только заголовок)"}
for cat in ["thought", "idea", "diary", "outreach-draft", "person", "operational", "prompt-draft", "reference-external", "stub"]:
    items = by_cat.get(cat, [])
    if not items:
        continue
    moc.append(f"### {CAT_RU.get(cat, cat)} ({len(items)})\n")
    for i, slug, title in sorted(items, key=lambda x: -(triage[x[0]].get("value", 0))):
        v = triage[i].get("value", 0)
        star = " ⭐" if v >= 0.8 else ""
        moc.append(f"- [[{slug}\\|{title[:70]}]]{star}")
    moc.append("")
moc.append("## По годам\n")
for yr in sorted(by_year):
    moc.append(f"- **{yr}** — {len(by_year[yr])} заметок")
moc.append("")
moc.append("## По концептам\n")
for c in sorted(by_concept, key=lambda c: -len(by_concept[c])):
    moc.append(f"- [[{c}]] — {len(by_concept[c])}")
moc.append("")
if junk_lines:
    moc.append(f"Обрывки без ценности: [[Apple-Notes-junk-stubs]] ({len(junk_lines)})")
moc.append("")
(MOC_DIR / "_Apple-Notes-MOC.md").write_text("\n".join(moc), encoding="utf-8")

# ---------- report ----------
report = {
    "input_notes": len(notes),
    "created_files": len(created_files),
    "junk_collected": len(junk_lines),
    "quarantined": quarantined,
    "skipped_dups": skipped_dups,
    "attachments_copied": copied_att,
    "attachments_expected": len(att_to_copy),
    "new_concepts": sorted(new_concepts),
    "bad_concept_slugs": dict(bad_slugs),
    "person_links": persons_links,
    "new_person_candidates_top": new_person_candidates.most_common(40),
    "by_year": {y: len(v) for y, v in sorted(by_year.items())},
    "by_cat": {c: len(v) for c, v in by_cat.items()},
}
(OUT / "gen_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
total_accounted = len(created_files) + len(junk_lines) + len(quarantined) + len(skipped_dups)
print("CREATED:", len(created_files), " JUNK:", len(junk_lines), " QUAR:", len(quarantined), " DUPS:", len(skipped_dups))
print("ACCOUNTED:", total_accounted, "of", len(notes))
print("ATTACH:", copied_att, "/", len(att_to_copy))
print("NEW_CONCEPTS:", len(new_concepts), " BAD_SLUGS:", sum(bad_slugs.values()))
print("OK" if total_accounted == len(notes) else "MISMATCH")
