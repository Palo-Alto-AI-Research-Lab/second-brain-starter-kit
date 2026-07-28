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
r"""Daily fetch of recent messages from the SAFE Sostav topic-groups, for the
comment-suggestion routine (read summaries -> pick safe thread -> Reddit/Threads
answer -> propose to Anton, draft-first, never publish).

Reads the @personal_acct session from C:\mcp\telegram-mcp\.env (that account is the one
in the Sostav groups). 0-token: just pulls text + reaction counts so the LLM can
pick the most reaction-validated SAFE thread.

Usage (from C:\mcp\telegram-mcp so the venv telethon is importable):
  C:\mcp\telegram-mcp\.venv\Scripts\python.exe %IMPORTS%\sostav\daily_safe_fetch.py [days]
  days: how many days back to include (default 1 = "yesterday+today").

SAFE set only (health/travel/family/knowledge/lectures/general). Crypto,
Investments, Business, Requests, Girls, Flood, Real-estate are EXCLUDED.
"""
import os, sys, asyncio, datetime
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

ENV = r"C:\mcp\telegram-mcp\.env"
load_dotenv(ENV)
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SS = os.environ["TELEGRAM_SESSION_STRING_PERSONAL_ACCT"]

SAFE = [
    ("Puteshestviya", -1002223579022),
    ("Zdorovie",      -1002461212822),
    ("SemyaDom",      -1009770296131),
    ("Znaniya",       -1002598081473),
    ("Lekcii",        -1006879180176),
    ("Obshchiy",      -1003503054455),
]

async def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    today = datetime.datetime.now().date()
    mind = today - datetime.timedelta(days=days)
    c = TelegramClient(StringSession(SS), API_ID, API_HASH)
    await c.connect()
    me = await c.get_me()
    print("ME=@%s id=%s  window=%s..%s" % (me.username, me.id, mind, today))
    for label, gid in SAFE:
        rows = []
        async for m in c.iter_messages(gid, limit=400):
            d = m.date.date()
            if d < mind:
                break
            txt = (m.text or "").replace(chr(10), " ").strip()
            if not txt:
                continue
            rx = 0
            if m.reactions and m.reactions.results:
                rx = sum(r.count for r in m.reactions.results)
            try:
                snd = await m.get_sender()
                who = getattr(snd, "first_name", None) or getattr(snd, "username", "?") or "?"
            except Exception:
                who = "?"
            rows.append((m.date.strftime("%m-%d %H:%M"), rx, m.id, who, txt[:350]))
        print("\n==== %s (%s) : %d msgs ====" % (label, gid, len(rows)))
        for r in rows:
            print("[%s|rx%s|id%s|%s] %s" % r)
    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
