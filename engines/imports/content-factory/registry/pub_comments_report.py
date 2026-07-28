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
r"""pub_comments_report.py - утренний дайджест неотвеченных комментов -> чат 03.

Читает pubmetrics.db (таблица comments), составляет короткий дайджест:
  сколько без ответа всего / по площадкам / 8 самых свежих (автор + кусочек + ссылка).
Подозреваемые спам-боты (author_id в spam_authors.txt) помечаются 🤖 и НЕ считаются
кандидатами на ответ. Ничего не отвечает сам - только докладывает.

USAGE:
  python pub_comments_report.py            # напечатать дайджест
  python pub_comments_report.py --post     # напечатать + отправить в чат 03 (bus_ping --post)
Пусто (0 неотвеченных) -> в 03 не шлём (без шума), печатаем "все отвечены".
"""
import os, sys, sqlite3, subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "pubmetrics.db")
SPAM = os.path.join(HERE, "spam_authors.txt")
BUS_PING = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"),
                        ".claude", "scripts", "bus_ping.py")


def spam_ids():
    ids = set()
    if os.path.exists(SPAM):
        for line in open(SPAM, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line:
                ids.add(line)
    return ids


def main():
    post = "--post" in sys.argv[1:]
    bots = spam_ids()
    c = sqlite3.connect(DB)
    rows = c.execute("""SELECT cm.author, cm.author_id, cm.text, cm.ts, cm.platform,
                               cm.comment_id, p.title
                        FROM comments cm JOIN publications p ON p.id=cm.pub_id
                        WHERE cm.replied=0 AND cm.is_ours=0 ORDER BY cm.ts DESC""").fetchall()
    c.close()
    human = [r for r in rows if r[1] not in bots]
    bot_n = len(rows) - len(human)
    if not human:
        print("все комменты отвечены" + (f" (спам-ботов в стороне: {bot_n})" if bot_n else ""))
        return
    plat = {}
    for r in human:
        plat[r[4]] = plat.get(r[4], 0) + 1
    lines = [f"💬 Комменты без ответа: {len(human)}"
             + (f" (+{bot_n} 🤖 спам, не отвечаем)" if bot_n else ""),
             " · ".join(f"{k}:{v}" for k, v in sorted(plat.items(), key=lambda x: -x[1])),
             ""]
    for a, aid, t, ts, pl, cid, title in human[:8]:
        link = "https://t.me/" + cid.replace("/", "/")  # cid = slug/msg_id в discussion/группе
        lines.append(f"• {a} [{ts[5:16]}]: {(t or '').strip()[:90]}")
        lines.append(f"  под «{(title or '')[:50]}» → {link}")
    if len(human) > 8:
        lines.append(f"…и ещё {len(human) - 8} (дашборд Pub-Registry-Metrics.html)")
    lines.append("")
    lines.append("Ответить: скажи мне «ответь на комменты» - подготовлю по правилам "
                 "(TG=осмысленно с контекстом) и покажу перед отправкой.")
    text = "\n".join(lines)
    print(text)
    if post:
        r = subprocess.run([sys.executable, BUS_PING, "--post", text],
                           capture_output=True, text=True)
        print("post:", (r.stdout or r.stderr or "").strip()[:200])


if __name__ == "__main__":
    main()
