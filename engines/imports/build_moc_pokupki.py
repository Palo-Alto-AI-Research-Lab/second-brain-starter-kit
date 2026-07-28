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
"""Build _Pokupki-MOC.md: stats, participants, concept index, month/day index,
   voice-gap note, graph bridges. Data-driven from JSONL + backlinks."""
import json
from collections import Counter, defaultdict
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
OUT = Path(r"E:/Obsidian/_imports")
POK = VAULT / "01-Conversations/Telegram/Pokupki"
rows = [json.loads(l) for l in (OUT / "pokupki-archive.jsonl").read_text(encoding="utf-8").splitlines()]
backlinks = json.loads((OUT / "pokupki_backlinks.json").read_text(encoding="utf-8"))

days = sorted(set(r["date"] for r in rows if r["date"]))
months = sorted(set(d[:7] for d in days))
by_month = defaultdict(list)
for d in days:
    by_month[d[:7]].append(d)
voice = sum(1 for r in rows if r["media_kind"] == "voice")
photos = sum(1 for r in rows if r["media_kind"] == "photo")
pdfs = sum(1 for r in rows if r["media_kind"] == "pdf")
know = sum(len(v) for v in backlinks.values())   # actual note files (post-dedup)
origin_c = Counter(r["origin"] for r in rows)

# participants (by display name) with role guess
name_c = Counter(r["from"] for r in rows if r["from"])
ROLE = {"anton": "🟢 Антон (принципал)", "Alina": "🔵 Алина (принципал)",
        "mixed": "⚪ ассистент", "external": "⚫ внешний"}
name_origin = {}
for r in rows:
    if r["from"]:
        name_origin.setdefault(r["from"], r["origin"])

CONC_TITLE = {
 "concept-construction-renovation":"Стройка и ремонт","concept-home-goods":"Товары для дома",
 "concept-procurement-vendors":"Закупки и поставщики","concept-tech-tools":"Гаджеты и техника",
 "concept-cars":"Авто","concept-garden-landscaping":"Сад и ландшафт",
 "concept-parenting":"Детям","concept-groceries-food":"Продукты и еда",
 "concept-personal-finance":"Платежи и финансы","concept-travel-logistics":"Путешествия",
 "concept-place-livability":"Жизнь в Португалии"}

L = []
L += ["---", "type: moc", 'title: "Покупки — чат закупок"',
      "source: telegram-pokupki", "tags: [moc, pokupki, telegram, покупки]",
      f"created: 2026-05-30", "---", ""]
L += ["# 🛒 Покупки — MOC", "",
      f"> **{len(rows):,} сообщений** · {len(days)} дней · {len(months)} месяцев "
      f"({months[0]} → {months[-1]}) · **{know:,} заметок-знаний** · "
      f"🎤 {voice:,} голосовых · 🖼 {photos:,} фото · 📄 {pdfs} PDF".replace(",", " "), "",
      "Чат одобрения закупок Антона с командой ассистентов — товарный ресёрч, "
      "директивы-голосовые Антона (транскрибированы ассистентами) и тред-одобрения. "
      "Сиблинг чата [[_Assistants-Ops-MOC|Assistants-Ops]]; правила закупок сведены в "
      "[[concept-bible-procurement|Библию регламентов]].", ""]

# voice gap  (format the number with a thin space; keep prose commas intact)
voice_s = f"{voice:,}".replace(",", " ")
L += ["> [!warning] Пробел: голос не выгружен",
      f"> Большая часть рассуждений Антона — это **{voice_s} голосовых сообщений**, которые "
      "в этом экспорте **не выгружены** (только аудио-метка, без расшифровки). "
      "Восстановлено то, что ассистенты транскрибировали текстом (директивы-relay). "
      "Чтобы добрать остальное: переэкспорт *с медиа* → Whisper-расшифровка `.ogg` → "
      "обогащение лент/заметок по `msg_id` (идемпотентно).", ""]

# concept index
L += ["## 🧭 По темам (концепты)", "",
      "| Концепт | Заметок |", "|---|---|"]
for slug, n in sorted(backlinks.items(), key=lambda kv: -len(kv[1])):
    title = CONC_TITLE.get(slug, slug)
    L.append(f"| [[{slug}\\|{title}]] | {len(backlinks[slug])} |")
L.append("")
L += ["```dataview", "TABLE length(rows) AS Заметок",
      'FROM "01-Conversations/Telegram/Pokupki/posts"',
      "GROUP BY concept SORT length(rows) DESC", "```", ""]

# participants
L += ["## 👥 Участники", ""]
for nm, c in name_c.most_common(18):
    L.append(f"- {ROLE.get(name_origin.get(nm,'external'),'⚫')} **{nm}** — {c} сообщ.")
L.append("")

# month/day index
L += ["## 🗓 Ленты по месяцам", ""]
for mo in months:
    ds = sorted(by_month[mo])
    cnt = sum(1 for r in rows if r["date"][:7] == mo)
    links = " · ".join(f"[[Sessions-{d}\\|{d[8:]}]]" for d in ds)
    L.append(f"**{mo}** — {len(ds)} дн., {cnt} сообщ.: {links}")
    L.append("")

# bridges
L += ["## 🔗 Связи с остальным графом",
      "- [[concept-bible-procurement]] — правила закупок (Библия регламентов)",
      "- [[_Assistants-Ops-MOC]] — операционный чат-сиблинг",
      "- [[concept-construction-renovation]] · [[concept-home-goods]] · "
      "[[concept-procurement-vendors]] · [[concept-cars]] · [[concept-garden-landscaping]] · "
      "[[concept-tech-tools]] · [[concept-parenting]] · [[concept-groceries-food]] · "
      "[[concept-travel-logistics]] · [[concept-personal-finance]] · [[concept-place-livability]]",
      ""]

(POK / "_Pokupki-MOC.md").write_text("\n".join(L), encoding="utf-8")
print("MOC written. months", len(months), "days", len(days), "voice", voice, "know", know)
