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
r"""sostav_alpha.py — COMMUNITY-alpha detector over the СОСТАВ club (sostav.db).

Sibling of `..\lobster\lobster_alpha.py`, adapted for a RU entrepreneurs/finance club:
  - sostav.db schema (rx, reply_count, topic, authors.rx_recv) instead of lobster's.
  - RU business/finance/dealflow alpha keywords (not DeFi-English).
  - PENALISE intro posts — in СОСТАВ the top-reacted substantive msgs are member
    self-intros ("меня зовут… 57 лет, женат, бизнес…"); those are DOSSIER material
    (already covered by 54 person-notes), NOT actionable alpha. Deprioritise them.
  - TOPIC weighting: business topics (Крипта/Инвестиции/Запросы/Бизнес/Знания/Лекции/
    Недвижимость) up; social (Девушки/Флудильня/Семья) down.

⛔ HIGH SENSITIVITY (grey-finance, real names, arrests/scams) → PRIVATE layer only.
   Output stays in the local review screen / private vault. NEVER outbound/public.

  set PYTHONIOENCODING=utf-8
  python sostav_alpha.py                       # default May 2026
  python sostav_alpha.py --since 2026-05-01 --until 2026-06-01 --top 40

0 LLM tokens, 0 GPU. Idempotent (pure read of sostav.db).
"""
import sqlite3, re, sys, os

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB = r"%IMPORTS%\sostav\sostav.db"
OUT = r"%IMPORTS%\alpha\candidates"

# business / finance / dealflow / reputation alpha keywords (RU + a little EN)
KW = re.compile(
    r"(сделк|инвест|раунд|оценк[аи]|\bдоля\b|экзит|выход из|привлек|привлеч|фонд[ае]?\b|"
    r"\bOTC\b|кэшаут|кэш-аут|обнал|нал\b|перевод|платёж|юрисдикц|релокац|релокат|"
    r"\bвиз[аыу]\b|\bвнж\b|гражданств|юрист|юрлиц|налог|оптимизац|схем[аы]|"
    r"скам|кинул|кидал|развод|мошен|обман|долг\b|долж|\bсуд\b|арест|заморозк|санкц|"
    r"продаю|куплю|\bищу\b|\bнужен\b|\bнужна\b|посоветуй|рекоменд|контакт|познаком|интро\b|"
    r"стартап|выручк|оборот|маржа|прибыл|убыт|\bнайм\b|оффер|зарплат|"
    r"USDT|крипт|биткоин|btc\b|eth\b|кошел|биржа|листинг|токен|due\s?dil|дью-дил|питч|"
    r"недвиж|аренд|ипотек|сделал|запуст|масштаб|клиент|продаж|воронк|конверс)", re.I)

# intro / self-presentation posts -> dossier material, not alpha. Penalise hard.
# CLASS-FIX 2026-07-05: the club tags intros with a HASHTAG (#интро/#резюме/#знакомство/
# #о себе). The prose-only markers below missed them, so a "#интро Всем привет!…" post
# (with KW like "продал доли/выручка") topped the alpha shortlist. Hashtag forms close
# the whole class; "представлюсь" (future tense) was also slipping past "представля".
INTRO = re.compile(
    r"(#\s?интро|#\s?резюме|#\s?знакомств|#\s?о\s?себе|"
    r"меня зовут|о себе|представля|представлюсь|расскажу о себе|коктабчане|паровозы и вагончики|"
    r"приветству.{0,30}состав|^\s*(привет|всем привет|добрый|здравству)|"
    r"\b\d{2}\s*(?:лет|года|год)\b.{0,80}(?:женат|замужем|детей|ребён|родил|живу|прожива))",
    re.I | re.S)

# low-signal banter one-liners
BANTER = re.compile(r"^(спасибо|плюс|\+1|согласен|это|так|да|нет|лол|ахах|"
                    r"👍+|🔥+|❤+|спс|пасиб|topic|оф+топ)\W*$", re.I)

TOPIC_W = {"Крипта": 1.5, "Инвестиции": 1.5, "Запросы": 1.6, "Бизнес": 1.5,
           "Знания": 1.4, "Лекции": 1.3, "Недвижимость": 1.3, "Здоровье и спорт": 1.0,
           "Путешествия": 0.9, "Общий": 0.85, "Семья, дом, хобби": 0.7,
           "Девушки": 0.4, "Флудильня": 0.4}


def fetch(since, until):
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT m.topic, m.msg_id, m.from_name, m.from_id, m.date, m.text,
               m.rx, m.reply_count, m.n_links,
               (SELECT a.rx_recv FROM authors a WHERE a.from_id = m.from_id) AS infl
        FROM messages m
        WHERE m.date >= ? AND m.date < ? AND length(m.text) >= 80
        ORDER BY m.unixtime""", (since, until)).fetchall()
    links = {}
    for top, mid, url, dom in con.execute(
            "SELECT topic, msg_id, url, domain FROM links WHERE msg_id IN "
            "(SELECT msg_id FROM messages WHERE date>=? AND date<?)", (since, until)):
        links.setdefault((top, mid), []).append((url, dom))
    con.close()
    return rows, links


def score(r):
    (topic, _mid, _fn, _fid, _date, text, rx, rc, nlinks, infl) = r
    tw = TOPIC_W.get(topic, 0.85)
    s = ((rx or 0) * 1.5 + (nlinks or 0) * 6 + min(rc or 0, 12) * 2) * tw
    if KW.search(text or ""):
        s += 9
    if (infl or 0) >= 1500:
        s += 3
    if len(text or "") >= 220:
        s += 3
    if INTRO.search(text or ""):
        s -= 30                      # intro posts = dossier material, not alpha
    if BANTER.match((text or "").strip()):
        s -= 20
    return s


def norm(t):
    return re.sub(r"\s+", " ", (t or "").lower())[:120]


def run(since, until, top, tag):
    rows, links = fetch(since, until)
    scored = sorted(((score(r), r) for r in rows), key=lambda x: -x[0])
    seen, picks = set(), []
    for sc, r in scored:
        if sc <= 4:
            break
        k = norm(r[5])
        if k in seen:
            continue
        seen.add(k)
        picks.append((sc, r))
        if len(picks) >= top:
            break

    lines = [f"# 🔒 СОСТАВ community-alpha — DETECTOR shortlist ({tag})", "",
             "⛔ HIGH SENSITIVITY — приватный слой, НИКОГДА не наружу/публично.", "",
             f"_Deterministic 0-token detector over `sostav.db` ({since} … {until}). "
             f"{len(rows)} substantive msgs scanned → top {len(picks)} candidates by "
             f"signal (reactions×topic-weight + links + reply-threads + RU-alpha-keywords + "
             f"author influence; intro/banter penalised)._",
             "_Next: LLM-judge keeps only REAL business alpha (сделка/дилфлоу/рекомендация/"
             "предупреждение/рыночный сигнал/запрос), drops intros & banter. "
             "Verdict: ✅ alpha · 🟡 watch · 🗑 шум._",
             "", "---", ""]
    for i, (sc, r) in enumerate(picks, 1):
        (topic, mid, fn, _fid, date, text, rx, rc, nlinks, infl) = r
        urls = links.get((topic, mid), [])
        doms = ", ".join(sorted({d for _, d in urls})) if urls else ""
        body = re.sub(r"\s+", " ", text).strip()
        lines.append(f"### #{i}  ({date[:10]} · {topic} · {rx or 0}rx · {rc or 0} rep · score {int(sc)})")
        lines.append(f"- **Author:** {fn}")
        if doms:
            lines.append(f"- **Links:** {doms}")
        lines.append(f"- **Text:** {body[:600]}")
        lines.append("")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"sostav-{tag}-report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"scanned {len(rows)} substantive · shortlisted {len(picks)} → {path}")
    return path


if __name__ == "__main__":
    a = sys.argv
    since = a[a.index("--since") + 1] if "--since" in a else "2026-05-01"
    until = a[a.index("--until") + 1] if "--until" in a else "2026-06-01"
    top = int(a[a.index("--top") + 1]) if "--top" in a else 35
    tag = a[a.index("--tag") + 1] if "--tag" in a else "may2026"
    run(since, until, top, tag)
