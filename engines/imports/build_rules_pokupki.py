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
"""Build reglament-pokupki-*.md from curated purchase rules; link to the existing
   Operations Bible concepts; write a Pokupki-rules index. ASCII stdout."""
import re, json
from collections import Counter
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
OUT = Path(r"E:/Obsidian/_imports")
OPS = VAULT / "03-Insights/Operations"
POK = VAULT / "01-Conversations/Telegram/Pokupki"

cands = {c["id"]: c for c in json.loads((OUT / "pokupki_rule_cands.json").read_text(encoding="utf-8"))}
rules = json.loads((OUT / "pokupki_rules_curated.json").read_text(encoding="utf-8"))

_MAP = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i',
 'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
 'ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slug(t, n=55):
    s = "".join(_MAP.get(c, c) for c in (t or "").lower())
    s = re.sub(r"https?://\S+", "", s); s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"[\s_-]+", "-", s).strip("-")[:n].strip("-") or "rule"
def esc(s): return (s or "").replace('"', "'").replace("\n", " ").strip()

THEME = {
 "procurement-vendors": ("concept-bible-procurement", "Закупки и подрядчики"),
 "finance-payments": ("concept-bible-finance", "Финансы и платежи"),
 "communications-protocol": ("concept-bible-communications", "Коммуникации"),
 "travel-logistics": ("concept-bible-travel", "Путешествия"),
 "household-general": ("concept-bible-household", "Быт"),
 "staff-hr": ("concept-bible-staff-hr", "Персонал и HR"),
}

used = set(); index = []
by_theme = Counter(); by_origin = Counter()
for r in rules:
    rid = r.get("id"); cand = cands.get(rid, {})
    stmt = r.get("statement", "").strip()
    if not stmt:
        continue
    theme = r.get("theme", "procurement-vendors")
    sub, subtitle = THEME.get(theme, THEME["procurement-vendors"])
    origin = r.get("origin", "mixed")
    date = cand.get("date", "")
    auth = "human" if origin == "anton" else "hybrid"
    tags = ["регламент", "покупки"] + [t for t in r.get("tags", []) if t][:5]
    stem = f"reglament-pokupki-{slug(stmt)}"; k = 2
    while stem in used:
        stem = f"reglament-pokupki-{slug(stmt)}-{k}"; k += 1
    used.add(stem)
    body = [
      "---", f'title: "{esc(stmt[:70])}"', "type: reglament", "source: telegram-pokupki",
      f"origin: {origin}", f"authored_by: {auth}",
      f"date_established: {date}", f"theme: {theme}",
      f'applies_to: "{esc(r.get("applies_to","ассистенты"))}"', "status: active",
      f"tags: [{', '.join(tags)}]", f'concept: "[[{sub}]]"',
      f"msg_id: {rid}", f"confidence: {r.get('confidence',0.7)}",
      "---", "",
      f"**Правило:** {stmt}", "",
      f"**Применяется к:** {esc(r.get('applies_to','ассистенты'))}",
      f"**Источник:** [[Sessions-{date}]] · чат «Покупки»" if date else "**Источник:** чат «Покупки»",
      f"**Тема:** [[{sub}\\|Библия — {subtitle}]]  ·  **Свод:** [[concept-bible-platinum]]",
      f"**Лента-MOC:** [[_Pokupki-MOC]]",
    ]
    (OPS / f"{stem}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    index.append((theme, origin, stem, stmt))
    by_theme[theme] += 1; by_origin[origin] += 1

# Pokupki rules index note
idx = ["---", "type: moc", 'title: "Покупки — правила закупок"',
       "tags: [moc, pokupki, регламент, покупки]", "---", "",
       "# 🛒📖 Покупки — правила закупок", "",
       f"> {len(index)} правил из чата «Покупки», влиты в [[concept-bible-platinum|Библию регламентов]]. "
       "Сиблинг: [[_Operations-Bible-MOC]].", ""]
for theme in sorted(set(t for t, *_ in index)):
    sub, subtitle = THEME.get(theme, THEME["procurement-vendors"])
    idx.append(f"## {subtitle} ([[{sub}]])")
    for t, origin, stem, stmt in sorted(index):
        if t == theme:
            mark = "🟢" if origin == "anton" else "⚪"
            idx.append(f"- {mark} [[{stem}\\|{esc(stmt[:90])}]]")
    idx.append("")
(POK / "_Pokupki-Rules.md").write_text("\n".join(idx), encoding="utf-8")

print("rules written", len(index), "| by_theme", dict(by_theme), "| by_origin", dict(by_origin))
