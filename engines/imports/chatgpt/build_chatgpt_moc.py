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
r"""build_chatgpt_moc.py — regenerate _ChatGPT-MOC.md from the enriched notes,
primary view BY TOPIC (harvested), secondary index BY MONTH. Reads frontmatter
only. Run after harvest + concept pass."""
import glob, re
from pathlib import Path
import datetime

CG = Path(r"%VAULT%\01-Conversations\ChatGPT")
NEW = CG / "conversations"
TOPIC_NAMES = {
    "01-AI-Tech": "AI и технологии", "02-Crypto-Web3": "Крипто / Web3",
    "03-Biohacking": "Биохакинг", "04-Translation": "Переводы",
    "05-Medicine": "Медицина", "06-Cars": "Авто", "08-Family-Kids": "Семья и дети",
    "11-Portugal": "Португалия", "12-Construction": "Стройка",
    "13-General-Tech": "Тех общее", "14-Business-Finance": "Бизнес и финансы",
    "15-Personal-Growth": "Личностный рост", "16-Travel": "Путешествия",
    "17-Home-Life": "Дом и быт", "18-Games-Entertainment": "Игры и развлечения",
}


def fmget(fm, key):
    m = re.search(r"(?m)^%s:\s*(.+?)\s*$" % key, fm)
    return m.group(1).strip().strip('"\'') if m else ""


rows = []
for p in glob.glob(str(NEW / "*.md")):
    t = Path(p).read_text(encoding="utf-8", errors="ignore")
    fm = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
    fm = fm.group(1) if fm else ""
    stub = Path(p).stem
    rows.append({
        "stub": stub,
        "title": fmget(fm, "title") or stub,
        "date": fmget(fm, "date_recorded"),
        "topic": fmget(fm, "topic"),
        "model": fmget(fm, "model"),
        "mc": fmget(fm, "msg_count"),
        "has_c": bool(re.search(r"(?m)^related_concepts:\s*\n\s*-\s*\[\[", fm)),
        "arch": fmget(fm, "archived") == "true",
    })

today = datetime.date.today().isoformat()
total = len(rows)
linked = sum(1 for r in rows if r["has_c"])
out = [
    "---", 'title: "ChatGPT — все разговоры (MOC)"', "type: moc", "source: chatgpt",
    "date_added: %s" % today, "tags: [chatgpt, moc]", "---", "",
    "# ChatGPT — карта всех разговоров", "",
    "> Официальный экспорт · **%d** чатов · %d с концептами (%d%%) · спрашивай через `/ask`. "
    "Старый тематический рендер заархивирован в `_originals\\chatgpt-topic-folders-2026-06-16`."
    % (total, linked, 100 * linked // total if total else 0),
    "",
    "## По темам", "",
]

by_topic = {}
for r in rows:
    by_topic.setdefault(r["topic"] or "_Без темы (новые)", []).append(r)


def line(r):
    tag = " · %s" % r["mc"] if r["mc"] else ""
    tag += " · 🏷" if r["has_c"] else ""
    tag += " · 🗄" if r["arch"] else ""
    return "- [[%s|%s]] (%s%s)" % (r["stub"], r["title"].replace("|", "/")[:80], r["date"], tag)


for key in sorted(by_topic, key=lambda k: (k.startswith("_"), k)):
    rs = sorted(by_topic[key], key=lambda r: r["date"], reverse=True)
    name = TOPIC_NAMES.get(key, key)
    out.append("### %s (%d)" % (name, len(rs)))
    out.append("")
    out += [line(r) for r in rs]
    out.append("")

# secondary: by month (compact index, count only)
out += ["## По месяцам (индекс)", ""]
by_m = {}
for r in rows:
    by_m.setdefault((r["date"] or "0000-00")[:7], 0)
    by_m[(r["date"] or "0000-00")[:7]] += 1
for m in sorted(by_m, reverse=True):
    out.append("- **%s** — %d" % (m, by_m[m]))

(CG / "_ChatGPT-MOC.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("MOC rebuilt: %d chats, %d topics, %d linked" % (total, len(by_topic), linked))
