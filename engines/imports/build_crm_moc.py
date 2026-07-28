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
"""FAAA Phase 7 — CRM status-board MOC + concept hub note.
ASCII-only stdout.
"""
import json, io, os
from collections import Counter, defaultdict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback

OUT = IMPORTS
STAGE = OUT + r"\staging"
CRMDIR = STAGE + r"\04-Projects\crypto\Platinum-CRM"
CONCDIR = STAGE + r"\06-Concepts"
VAULT_CONC = os.path.join(VAULT, "06-Concepts")
os.makedirs(CRMDIR, exist_ok=True)
os.makedirs(CONCDIR, exist_ok=True)

leads = json.load(io.open(OUT + r"\faaa-leads.json", encoding="utf-8"))
final = json.load(io.open(OUT + r"\faaa\final_slugs.json", encoding="utf-8"))
synth = {}
_sd = OUT + r"\faaa\synth2"
for fn in os.listdir(_sd):
    if fn.endswith(".json"):
        try:
            data = json.load(io.open(os.path.join(_sd, fn), encoding="utf-8-sig"))
            objs = data.values() if isinstance(data, dict) else data
            for o in objs:
                if isinstance(o, dict) and "lead_id" in o:
                    synth[int(o["lead_id"])] = o
        except Exception:
            pass

# enrich leads with synth + slug
L = []
for l in leads:
    lid = l["lead_id"]
    s = synth.get(lid, {})
    f = final.get(str(lid), {})
    L.append({
        "lid": lid, "slug": f.get("slug"), "title": f.get("title") or l["display_name"],
        "status": (s.get("status") or "unknown").lower(),
        "category": (s.get("category") or "other").lower(),
        "company": s.get("company"),
        "n": l["n_calls"], "year": (l.get("first_date") or "0000")[:4],
        "first": (l.get("first_date") or "")[:10], "last": (l.get("last_date") or "")[:10],
    })

status_c = Counter(x["status"] for x in L)
cat_c = Counter(x["category"] for x in L)
year_c = Counter(x["year"] for x in L)
STATUS_RU = {"new": "новые", "negotiating": "в переговорах", "won": "закрыты (+)",
             "partner": "партнёры", "advisor": "эдвайзеры", "lost": "потеряны",
             "no-show": "не пришли", "stale": "заглохли", "refund": "рефанды",
             "unknown": "неизвестно"}
STATUS_ORDER = ["won", "partner", "negotiating", "advisor", "new", "stale",
                "no-show", "lost", "refund", "unknown"]

def link(x):
    return "[[%s\\|%s]]" % (x["slug"], x["title"])

m = []
m.append("---")
m.append("type: moc")
m.append("title: \"Platinum CRM — карточки лидов\"")
m.append("source: telegram-faaa")
m.append("origin: mixed")
m.append("authored_by: hybrid")
m.append("date_added: 2026-05-31")
m.append("concept: \"[[concept-platinum-crm]]\"")
m.append("tags: [moc, crm, platinum-crm, crypto]")
m.append("---")
m.append("")
m.append("# Platinum CRM — лиды из звонков (FAAA)")
m.append("")
m.append("Синтезированные карточки лидов из follow-up звонков Platinum "
         "(Zoom/Google Meet). Дедуп по @хендлу + имени. "
         "Сырой архив: [[_FAAA-Follow-ups-MOC]].")
m.append("")
m.append("- Уникальных лидов: **%d** · звонков: **%d** · период: %s → %s" % (
    len(L), sum(x["n"] for x in L),
    min(x["first"] for x in L if x["first"]),
    max(x["last"] for x in L if x["last"])))
m.append("- С повторными касаниями (2+ звонка): **%d** · разовых: **%d**" % (
    sum(1 for x in L if x["n"] >= 2), sum(1 for x in L if x["n"] == 1)))
m.append("- Концепт-хаб: [[concept-platinum-crm]]")
m.append("")

m.append("## По статусу")
m.append("")
m.append("| Статус | Лидов |")
m.append("|---|---|")
for st in STATUS_ORDER:
    if status_c.get(st):
        m.append("| %s (`status-%s`) | %d |" % (STATUS_RU.get(st, st), st, status_c[st]))
m.append("")

m.append("## По категории")
m.append("")
m.append("| Категория | Лидов |")
m.append("|---|---|")
for cat, c in cat_c.most_common():
    m.append("| %s (`cat-%s`) | %d |" % (cat, cat, c))
m.append("")

m.append("## По годам")
m.append("")
for y in sorted(year_c):
    m.append("- **%s** — %d лидов" % (y, year_c[y]))
m.append("")

# top-touched
m.append("## Самые активные лиды (по числу звонков)")
m.append("")
m.append("| Звонков | Лид | Статус | Период |")
m.append("|---|---|---|---|")
for x in sorted(L, key=lambda z: -z["n"])[:60]:
    m.append("| %d | %s | %s | %s→%s |" % (
        x["n"], link(x), x["status"], x["first"], x["last"]))
m.append("")

# by company (>=2 leads)
comp = defaultdict(list)
for x in L:
    if x["company"]:
        comp[x["company"].strip()].append(x)
multi_comp = {k: v for k, v in comp.items() if len(v) >= 2}
if multi_comp:
    m.append("## Компании с несколькими контактами")
    m.append("")
    for k in sorted(multi_comp, key=lambda k: -len(multi_comp[k]))[:50]:
        names = ", ".join(link(x) for x in multi_comp[k][:8])
        m.append("- **%s** (%d): %s" % (k, len(multi_comp[k]), names))
    m.append("")

m.append("## Приоритетные (won / negotiating / partner)")
m.append("")
hot = [x for x in L if x["status"] in ("won", "negotiating", "partner")]
hot.sort(key=lambda z: (-z["n"], z["last"]))
for x in hot[:80]:
    m.append("- %s — %s · %d звонк. · %s" % (
        link(x), x["status"], x["n"], x["company"] or ""))
m.append("")
m.append("```dataview")
m.append("TABLE status, company, n_calls, last_contact")
m.append("FROM \"04-Projects/crypto/Platinum-CRM/leads\"")
m.append("WHERE type = \"crm-lead\"")
m.append("SORT n_calls DESC")
m.append("```")
io.open(CRMDIR + r"\_Platinum-CRM-MOC.md", "w", encoding="utf-8").write("\n".join(m) + "\n")

# ---- concept hub ----
existing = set()
if os.path.isdir(VAULT_CONC):
    existing = {f[:-3] for f in os.listdir(VAULT_CONC) if f.endswith(".md")}
neighbours = [c for c in ["concept-blockchain", "concept-crypto", "concept-web3",
              "concept-defi", "concept-tokenomics", "concept-venture-capital",
              "concept-fundraising", "concept-crm"] if c in existing]
c = []
c.append("---")
c.append("title: \"Platinum CRM / dealflow\"")
c.append("aliases: [Platinum CRM, Platinum dealflow, FAAA follow-ups, лиды Platinum]")
c.append("type: concept")
c.append("authored_by: hybrid")
c.append("origin: mixed")
c.append("created: 2026-05-31")
c.append("status: defined")
c.append("tags: [concept, crm, platinum-crm, crypto, venture-capital]")
c.append("---")
c.append("")
c.append("# Platinum CRM / dealflow")
c.append("")
c.append("> [!abstract] Концепт-хаб")
c.append("> Воронка лидов Platinum (крипто VC / dev-incubator Антона Дзятковского) "
         "из follow-up звонков 2022–2026: фонды, инвесторы, проекты, эдвайзеры, KOL-ы.")
c.append("")
c.append("Связывает все карточки лидов и архив звонков в единый граф.")
c.append("")
c.append("## Точки входа")
c.append("- [[_Platinum-CRM-MOC]] — доска лидов по статусам/категориям/компаниям")
c.append("- [[_FAAA-Follow-ups-MOC]] — сырой хронологический архив звонков")
c.append("")
if neighbours:
    c.append("## Связанные концепты")
    for n in neighbours:
        c.append("- [[%s]]" % n)
    c.append("")
io.open(CONCDIR + r"\concept-platinum-crm.md", "w", encoding="utf-8").write("\n".join(c) + "\n")

print("DONE moc + concept; leads=%d statuses=%s neighbours=%s"
      % (len(L), dict(status_c), neighbours))
