# -*- coding: utf-8 -*-
"""Phase 4: build _Telegram-MOC.md directly in the vault, data-driven."""
import json, re
from pathlib import Path
from collections import Counter, defaultdict

IMP = Path(r"E:/Obsidian/_imports")
VAULT = Path(r"E:/Obsidian/Anton-Knowledge")
BASE = VAULT / "01-Conversations/Telegram/Arhiv-Golosa"
recs = [json.loads(l) for l in (IMP / "telegram-archive-classified.jsonl").open(encoding="utf-8")]
posts = [r for r in recs if r["cls"] == "post"]

by_month = defaultdict(list)
for r in recs:
    if r.get("month"):
        by_month[r["month"]].append(r)

# map month -> session file links
def month_links(month):
    if month == "2025-02":
        days = sorted({(r.get("ts") or "")[:10] for r in by_month[month] if r.get("ts")})
        return ", ".join(f"[[Sessions-{d}]]" for d in days)
    return f"[[Sessions-{month}]]"

# top hashtags
tags = Counter()
for r in posts:
    for h in re.findall(r'#(\w+)', r["text"]):
        tags[h.lower()] += 1

# transcripts (Anton's voice) — list the longest as notable
transcripts = sorted([r for r in posts if r.get("sender") == "Personal Audio Summary"],
                     key=lambda r: -r["len"])

# build slug index the same way generator did, to link notable posts
def translit(s):
    M={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',' ':'-'}
    s=s.lower(); out=[]
    for ch in s:
        if ch in M: out.append(M[ch])
        elif ch.isalnum() and ch.isascii(): out.append(ch)
        else: out.append('-')
    return re.sub(r'-+','-',''.join(out)).strip('-')
def slug_of(r):
    fl=r['text'].strip().splitlines()[0] if r['text'].strip() else 'post'
    fl=re.sub(r'\[@[^\]]+\]\([^)]+\)','',fl); fl=re.sub(r'https?://\S+','',fl)
    return f"{(r.get('ts') or '')[:10]}-{translit(fl)[:48].strip('-')}"

L = []
L += [
    "---",
    'title: "Telegram — Архив ГОЛОСА (MOC)"',
    "type: moc",
    "source: telegram-archive",
    "tags: [moc, telegram, telegram-archive]",
    "---",
    "",
    "# Telegram — Архив ГОЛОСА Content (Map of Content)",
    "",
    "> Импорт группового чата контент-команды (сентябрь 2023 → май 2026). "
    "Голосовые уже переведены в текст. Аудио/фото/видео в импорт не включались.",
    "",
    "## Сводка",
    "",
    "| Метрика | Значение |",
    "|---|---|",
    f"| Текстовых сообщений | {len(recs)} |",
    f"| Длинных постов (отд. файлы) | {len(posts)} |",
    f"| Транскриптов (Personal Audio Summary) | {sum(1 for r in posts if r.get('sender')=='Personal Audio Summary')} |",
    f"| Сессий (30-мин) | {len({r.get('session') for r in recs})} |",
    f"| Месяцев активности | {len(by_month)} |",
    "",
    "## Структура",
    "- `posts/` — каждый длинный пост отдельным файлом (654)",
    "- `sessions/` — лента разговора: помесячно, февраль-2025 по дням",
    "- Участники: см. раздел ниже",
    "",
    "## Индекс по месяцам",
    "",
    "| Месяц | Сообщений | Постов | Лента |",
    "|---|---|---|---|",
]
for m in sorted(by_month):
    msgs = by_month[m]
    pc = sum(1 for r in msgs if r["cls"] == "post")
    L.append(f"| {m} | {len(msgs)} | {pc} | {month_links(m)} |")

L += ["", "## Участники (контент-команда)", ""]
vol = Counter(r.get("sender") for r in recs if r.get("sender"))
for s, n in vol.most_common():
    if not s or s == "Personal Audio Summary":
        continue
    slug = translit(s)
    pf = VAULT / "07-People" / f"person-{slug}.md"
    name = f"[[person-{slug}|{s}]]" if pf.exists() else s
    L.append(f"- {name} — {n} сообщений")

L += ["", "## Топ-хэштеги", "", " ".join(f"#{t}" for t, _ in tags.most_common(25)), ""]

L += ["", "## Заметные транскрипты (самые длинные голосовые)", ""]
for r in transcripts[:25]:
    title = re.sub(r'\s+', ' ', r['text'].strip())[:70]
    L.append(f"- [[{slug_of(r)}|{title}]] ({(r.get('ts') or '')[:10]}, {r['len']} симв.)")

L += ["", "## Извлечённые концепты и инсайты", "",
      "_(заполняется по мере ручного разбора лучших постов)_", ""]

(BASE / "_Telegram-MOC.md").write_text("\n".join(L), encoding="utf-8")
print("MOC written:", (BASE / "_Telegram-MOC.md"))
print("transcripts:", len(transcripts), "| top hashtags:", [t for t,_ in tags.most_common(8)])
