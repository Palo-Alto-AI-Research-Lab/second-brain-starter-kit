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
"""FAAA Phase 5 — render one CRM lead card per lead into staging.

Merges LLM synthesis (faaa/synth/*.json) with deterministic call data.
Raw call text is embedded here (single copy); ledgers will link, not re-embed.
Cards sharded by year of first contact. Emits call2slug.json for the ledger pass.
ASCII-only stdout.
"""
import json, io, re, os
from collections import OrderedDict, defaultdict, Counter
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

OUT = IMPORTS
STAGE = OUT + r"\staging"
LEADROOT = STAGE + r"\04-Projects\crypto\Platinum-CRM\leads"
DATE_ADDED = "2026-05-31"

rows = [json.loads(l) for l in io.open(OUT + r"\faaa-archive.jsonl", encoding="utf-8")]
id2row = {r["id"]: r for r in rows}
leads = json.load(io.open(OUT + r"\faaa-leads.json", encoding="utf-8"))

# ---- load synthesis (synth2: v2 batches + reused.json dict from v1) ----
synth = {}
bad_batches = []
sdir = OUT + r"\faaa\synth2"
for fn in sorted(os.listdir(sdir)):
    if not fn.endswith(".json"):
        continue
    try:
        data = json.load(io.open(os.path.join(sdir, fn), encoding="utf-8-sig"))
        objs = data.values() if isinstance(data, dict) else data   # reused.json is a dict
        for o in objs:
            if isinstance(o, dict) and "lead_id" in o:
                synth[int(o["lead_id"])] = o
    except Exception:
        bad_batches.append(fn)

TRANSLIT = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "abvgdeejziyklmnoprstufhccss y eya")
def slugify(text):
    if not text:
        return "lead"
    t = text.lower().translate(TRANSLIT)
    t = re.sub(r"['`’]", "", t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    t = re.sub(r"-+", "-", t)
    return (t[:48].strip("-")) or "lead"

def jstr(s):
    """YAML-safe double-quoted scalar (or empty)."""
    if s is None:
        return '""'
    return json.dumps(str(s).replace("\n", " ").strip(), ensure_ascii=False)

def jlist(xs):
    xs = [x for x in (xs or []) if x not in (None, "", "-")]
    if not xs:
        return "[]"
    return "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in xs) + "]"

def clean_tag(t):
    t = re.sub(r"[^\w\-]+", "-", str(t).strip().lower()).strip("-")
    return t

def neutralize(s):
    """Break every '[[' run in raw text so it isn't parsed as a wikilink
    (handles [[, [[[, ...). Renders identically; not a real edit of meaning."""
    return re.sub(r'(?<=\[)\[', r'\\[', s or "")

STATUS_RU = {
    "new": "новый", "negotiating": "в переговорах", "won": "закрыт+",
    "partner": "партнёр", "advisor": "эдвайзер", "lost": "потерян",
    "no-show": "не пришёл", "stale": "заглох", "refund": "рефанд",
    "unknown": "неизвестно",
}

# ---- assign final slugs (global dedup) ----
used = {}
def uniq(base):
    if base not in used:
        used[base] = 1; return base
    used[base] += 1; return "%s-%d" % (base, used[base])

leads_sorted = sorted(leads, key=lambda l: (l.get("first_date") or "9999"))
final = OrderedDict()   # lead_id -> dict(slug, year, title)
call2slug = {}
for l in leads_sorted:
    lid = l["lead_id"]
    s = synth.get(lid)
    name = (s.get("name") if s and s.get("name") else l["display_name"]) or "lead"
    slug = uniq(slugify(name))
    year = (l.get("first_date") or "0000")[:4]
    final[lid] = {"slug": slug, "year": year, "title": name}
    for cid in l["call_ids"]:
        call2slug[cid] = slug

# ---- render ----
counts = Counter()
status_counts = Counter()
for l in leads_sorted:
    lid = l["lead_id"]
    meta = final[lid]
    s = synth.get(lid) or {}
    slug, year, title = meta["slug"], meta["year"], meta["title"]
    folder = os.path.join(LEADROOT, year)
    os.makedirs(folder, exist_ok=True)

    status = (s.get("status") or "unknown").lower()
    status_counts[status] += 1
    category = (s.get("category") or "").lower() or None
    company = s.get("company")
    handles = l["handles"]
    pitchers = l["pitchers"][:8]
    first_c = (l.get("first_date") or "")[:10]
    last_c = (l.get("last_date") or "")[:10]
    n = l["n_calls"]
    lang = (s.get("lang") or "ru")

    tags = ["crm", "lead", "platinum-crm", "platinum-lead",
            "status-" + clean_tag(status)]
    if category:
        tags.append("cat-" + clean_tag(category))
    for t in (s.get("tags") or []):
        ct = clean_tag(t)
        if ct and ct not in tags:
            tags.append(ct)

    # aliases: other name variants + handles (dedup vs title)
    aliases = []
    for nv in l.get("name_variants", []):
        if nv and nv != title and nv not in aliases:
            aliases.append(nv)
    aliases = aliases[:6] + handles

    fm = []
    fm.append("---")
    fm.append("title: " + jstr(title))
    fm.append("aliases: " + jlist(aliases))
    fm.append("type: crm-lead")
    fm.append("source: telegram-faaa")
    fm.append("origin: mixed")
    fm.append("authored_by: hybrid")
    fm.append("status: " + jstr(status))
    if category: fm.append("category: " + jstr(category))
    fm.append("company: " + jstr(company))
    fm.append("role: " + jstr(s.get("role")))
    fm.append("country: " + jstr(s.get("country")))
    fm.append("handles: " + jlist(handles))
    fm.append("pitched_by: " + jlist(pitchers))
    fm.append("n_calls: %d" % n)
    fm.append("first_contact: " + jstr(first_c))
    fm.append("last_contact: " + jstr(last_c))
    fm.append("date_added: " + DATE_ADDED)
    fm.append("language: " + jstr(lang))
    fm.append("concept: \"[[concept-platinum-crm]]\"")
    fm.append("tags: " + jlist(tags))
    fm.append("lead_id: %d" % lid)
    fm.append("---")

    body = []
    head = title + (" — " + company if company else "")
    body.append("# " + head)
    body.append("")
    info = "> [!info] CRM-лид Platinum · **%s** (%s)%s · %d звонк(ов) · %s → %s" % (
        STATUS_RU.get(status, status), status,
        (" · " + category if category else ""), n, first_c or "?", last_c or "?")
    body.append(info)
    body.append("")
    if s.get("summary"):
        body.append("## Сводка")
        body.append(s["summary"])
        body.append("")
    # structured facts
    facts = []
    if s.get("what_they_do"):    facts.append("- **Чем занимаются:** " + s["what_they_do"])
    if s.get("what_they_want"):  facts.append("- **Что хотят:** " + s["what_they_want"])
    if s.get("what_we_offered"): facts.append("- **Что предложили:** " + s["what_we_offered"])
    if s.get("agreements"):      facts.append("- **Договорённости:** " + s["agreements"])
    if s.get("outcome"):         facts.append("- **Итог:** " + s["outcome"])
    if facts:
        body.append("## Ключевое")
        body.extend(facts)
        body.append("")
    # contacts
    body.append("## Контакты")
    if handles: body.append("- Telegram: " + " ".join(handles))
    if company: body.append("- Компания/проект: " + company)
    if s.get("role"): body.append("- Роль: " + s["role"])
    if s.get("country"): body.append("- Регион: " + s["country"])
    if pitchers: body.append("- Питчили со стороны Platinum: " + ", ".join(pitchers))
    body.append("")
    # call log (verbatim, single copy)
    body.append("## Лог звонков (%d)" % n)
    calls = [id2row[c] for c in l["call_ids"] if c in id2row]
    calls.sort(key=lambda r: (r.get("date") or ""))
    for r in calls:
        dt = (r.get("date") or "").replace("T", " ")[:16]
        hdr = r.get("call_name") or r.get("tema") or "звонок"
        by = r.get("sender") or "?"
        st = (" · " + r["status"]) if r.get("status") else ""
        body.append("### %s · %s" % (dt, hdr[:80]))
        body.append("*вёл: %s%s*" % (by, st))
        body.append("")
        txt = neutralize((r.get("text") or "").strip())  # neutralize stray wikilink-open
        for line in txt.split("\n"):
            body.append("> " + line if line.strip() else ">")
        body.append("")
    body.append("## Связи")
    body.append("- [[_Platinum-CRM-MOC]] · [[concept-platinum-crm]]")
    body.append("")

    path = os.path.join(folder, slug + ".md")
    io.open(path, "w", encoding="utf-8").write("\n".join(fm) + "\n\n" + "\n".join(body))
    counts["cards"] += 1
    if lid not in synth:
        counts["no_synth"] += 1

io.open(OUT + r"\faaa\call2slug.json", "w", encoding="utf-8").write(
    json.dumps(call2slug, ensure_ascii=False))
io.open(OUT + r"\faaa\final_slugs.json", "w", encoding="utf-8").write(
    json.dumps({str(k): v for k, v in final.items()}, ensure_ascii=False))

rep = io.open(OUT + r"\faaa\_render_report.txt", "w", encoding="utf-8")
rep.write("cards=%d  synth_loaded=%d  no_synth=%d  bad_batches=%s\n" % (
    counts["cards"], len(synth), counts["no_synth"], bad_batches))
rep.write("by status: %s\n" % dict(status_counts.most_common()))
rep.close()
print("DONE cards=%d synth=%d no_synth=%d bad_batches=%d"
      % (counts["cards"], len(synth), counts["no_synth"], len(bad_batches)))
