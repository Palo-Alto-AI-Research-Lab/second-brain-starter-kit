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
"""Rebuild _Platinum-CRM-MOC over the COMBINED vault leads (FAAA calls + DM leads).
Source-agnostic: scans the live vault cards' frontmatter. ASCII-only stdout."""
import re, io, glob, os
from collections import Counter, defaultdict

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback

VL = os.path.join(VAULT, "04-Projects", "crypto", "Platinum-CRM", "leads")
MOC = os.path.join(VAULT, "04-Projects", "crypto", "Platinum-CRM", "_Platinum-CRM-MOC.md")

def fm(t, key):
    m = re.search(r'^%s:\s*"?([^"\n]*)"?\s*$' % re.escape(key), t, re.M)
    return (m.group(1).strip() if m else "") or ""

cards = []
for f in glob.glob(VL + r"\**\*.md", recursive=True):
    try: t = io.open(f, encoding="utf-8").read(1400)
    except Exception: continue
    if "type: crm-lead" not in t: continue
    slug = os.path.basename(f)[:-3]
    nc = fm(t, "n_calls"); dm = fm(t, "dm_msgs")
    cards.append({
        "slug": slug, "title": fm(t, "title") or slug,
        "source": fm(t, "source"), "status": fm(t, "status").lower(),
        "category": fm(t, "category").lower(), "tier": fm(t, "crm_tier").lower(),
        "company": fm(t, "company"),
        "n_calls": int(nc) if nc.isdigit() else 0,
        "dm_msgs": int(dm) if dm.isdigit() else 0,
        "last": fm(t, "last_contact"), "first": fm(t, "first_contact"),
        "year": (fm(t, "first_contact") or "")[:4],
    })

call = [c for c in cards if c["source"] == "telegram-faaa"]
dm = [c for c in cards if c["source"] == "telegram-dm"]
status_c = Counter(c["status"] for c in cards)
cat_c = Counter(c["category"] for c in cards if c["category"])
tier_c = Counter(c["tier"] for c in dm if c["tier"])
year_c = Counter(c["year"] for c in cards if c["year"])

def link(c): return "[[%s\\|%s]]" % (c["slug"], (c["title"] or c["slug"])[:40])

m = []
m += ["---", "type: moc", 'title: "Platinum CRM — карточки лидов"',
      "source: telegram-faaa+dm", "origin: mixed", "authored_by: hybrid",
      "date_added: 2026-06-01", 'concept: "[[concept-platinum-crm]]"',
      "tags: [moc, crm, platinum-crm, crypto]", "---", ""]
m += ["# Platinum CRM — единый слой лидов", "",
      "Карточки лидов Platinum из ДВУХ источников: **звонки** (FAAA follow-ups, Zoom/Meet) "
      "и **личка** (DM из CRM entity-export, инвесторы/фаундеры без звонка). "
      "Дедуп по @хендлу+имени. Сырой архив звонков: [[_FAAA-Follow-ups-MOC]].", ""]
m += ["- **Всего лидов: %d**  ·  из звонков: **%d**  ·  из DM: **%d**" % (len(cards), len(call), len(dm)),
      "- 🔝 Топ-лиды (вовлечённые: ≥1 звонок / ≥20 DM): [[_Platinum-Top-Leads-MOC]]",
      "- Концепт-хаб: [[concept-platinum-crm]]", ""]

m += ["## По статусу", "", "| Статус | Лидов |", "|---|---|"]
for s, c in status_c.most_common():
    m.append("| %s | %d |" % (s or "—", c))
m.append("")

m += ["## По источнику и квалификации (CRM tier, DM-лиды)", "", "| Tier | DM-лидов |", "|---|---|"]
for t, c in tier_c.most_common():
    m.append("| %s | %d |" % (t, c))
m.append("")

m += ["## По категории", "", "| Категория | Лидов |", "|---|---|"]
for c, n in cat_c.most_common(20):
    m.append("| %s | %d |" % (c, n))
m.append("")

m += ["## По годам (первый контакт)", ""]
for y in sorted(year_c):
    if y: m.append("- **%s** — %d" % (y, year_c[y]))
m.append("")

m += ["## Самые активные лиды по звонкам (топ-50)", "", "| Звонков | Лид | Статус | Период |", "|---|---|---|---|"]
for c in sorted(call, key=lambda z: -z["n_calls"])[:50]:
    m.append("| %d | %s | %s | %s→%s |" % (c["n_calls"], link(c), c["status"], c["first"], c["last"]))
m.append("")

m += ["## Приоритетные (won / partner / negotiating / interested)", ""]
hot = [c for c in cards if c["status"] in ("won", "partner", "negotiating", "interested")]
hot.sort(key=lambda z: (-(z["n_calls"] + z["dm_msgs"])))
for c in hot[:80]:
    tag = ("%d зв." % c["n_calls"]) if c["source"] == "telegram-faaa" else ("DM %d" % c["dm_msgs"])
    m.append("- %s — %s · %s · %s" % (link(c), c["status"], tag, c["company"]))
m.append("")

comp = defaultdict(list)
for c in cards:
    if c["company"]: comp[c["company"].strip()].append(c)
multi = {k: v for k, v in comp.items() if len(v) >= 2}
if multi:
    m += ["## Компании с несколькими контактами", ""]
    for k in sorted(multi, key=lambda k: -len(multi[k]))[:50]:
        m.append("- **%s** (%d): %s" % (k, len(multi[k]), ", ".join(link(x) for x in multi[k][:8])))
    m.append("")

m += ["```dataview", "TABLE source, status, crm_tier, company, n_calls, dm_msgs",
      'FROM "04-Projects/crypto/Platinum-CRM/leads"', 'WHERE type = "crm-lead"',
      "SORT n_calls DESC", "```", ""]

io.open(MOC, "w", encoding="utf-8").write("\n".join(m) + "\n")
print("DONE moc: total=%d call=%d dm=%d statuses=%d" % (len(cards), len(call), len(dm), len(status_c)))
