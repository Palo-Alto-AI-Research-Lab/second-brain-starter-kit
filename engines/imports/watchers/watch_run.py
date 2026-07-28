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
r"""watch_run.py - the /watch-channel nightly runner (ONE task, many channels).

Reads watchers.json and for each ACTIVE watcher, SEQUENTIALLY:
  1) live INCREMENTAL fetch (Telethon min_id, idempotent) into _imports\alpha\<slug>\<slug>.db
  2) the SHARED 0-token detector (mine_channel.detect) over the last <window_days> days
     -> _imports\alpha\candidates\<slug>-report.md   (PRIVATE Second-Brain layer only)

This is the "turn /mine-channel into a nightly routine" engine. It REUSES
mine_channel.detect (the alpha brain) so detector logic never drifts, and adds only a
pinned-session INCREMENTAL fetch (mine_channel.scrape full-rescrapes; nightly must not).
All watchers run sequentially under ONE session -> no AuthKeyDuplicated risk
(see memory deterministic-script-gotchas: 1 session = 1 IP = 1 process).

0 LLM tokens, 0 GPU. LLM-judge stays on-demand (/alpha-judge, /mine-channel step 3).
Output is PRIVATE only - anti-leak is at OUTPUT, never outbound/public.
Lives on the always-on HUB (consolidated automations).

Run:  python watch_run.py [slug]      (no slug = all active watchers)
"""
import sys, re, json, sqlite3, asyncio, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(r"%IMPORTS%\watchers")
ALPHA = Path(r"%IMPORTS%\alpha")
ENV = Path(r"C:/mcp/telegram-mcp/.env")
REGISTRY = HERE / "watchers.json"
sys.path.insert(0, str(ALPHA))          # reuse the shared detector
import mine_channel                       # detect(), build_db(), KW/PROMO/BANTER


def log(m):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)


def load_env():
    d = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def ensure_schema(con):
    # EXACT columns mine_channel.detect expects, so we can call it directly on this db.
    con.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER, date TEXT, day TEXT, text TEXT, views INTEGER,
        forwards INTEGER, reactions INTEGER, file TEXT, urls TEXT)""")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_watch_id ON messages(id)")
    con.commit()


async def fetch_incremental(w, env):
    """Append only messages newer than the last stored id. Idempotent; a missed night
    auto-backfills. Returns count inserted."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

    api_id = int(env["TELEGRAM_API_ID"]); api_hash = env["TELEGRAM_API_HASH"]
    skey = w.get("session_key", "TELEGRAM_SESSION_STRING_WORK_ACCT_A")
    session = env.get(skey) or env.get("TELEGRAM_SESSION_STRING")
    if not session:
        raise RuntimeError(f"no session string for key {skey}")
    chat = w["chat_id"]
    try:
        chat = int(chat)
    except (ValueError, TypeError):
        pass

    home = ALPHA / w["slug"]; home.mkdir(parents=True, exist_ok=True)
    db = home / f"{w['slug']}.db"
    con = sqlite3.connect(db); ensure_schema(con)
    last_id = con.execute("SELECT COALESCE(MAX(id),0) FROM messages").fetchone()[0] or 0

    inserted = 0
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        try:
            ent = await client.get_entity(chat)
        except (ValueError, TypeError):
            # numeric id resolves only for chats in this session's dialog cache
            # (i.e. joined). Public channels we are NOT a member of (left=True)
            # need the @username resolve path instead. Class-fix 2026-07-04.
            uname = w.get("username")
            if not uname:
                raise
            ent = await client.get_entity(uname)
        async for m in client.iter_messages(ent, min_id=last_id, limit=w.get("scan_limit", 1500)):
            if m.id <= last_id:
                continue
            txt = m.message or ""
            rx = sum(r.count for r in m.reactions.results) if getattr(m, "reactions", None) and m.reactions.results else 0
            urls = []
            for e in (m.entities or []):
                if isinstance(e, MessageEntityTextUrl):
                    urls.append(e.url)
                elif isinstance(e, MessageEntityUrl) and m.message:
                    urls.append(m.message[e.offset:e.offset + e.length])
            fname = None
            if m.media is not None:
                doc = getattr(m.media, "document", None)
                if doc:
                    for at in getattr(doc, "attributes", []):
                        if getattr(at, "file_name", None):
                            fname = at.file_name
            d = m.date.isoformat() if m.date else ""
            con.execute("INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?,?,?)",
                        (m.id, d, d[:10], txt, getattr(m, "views", 0) or 0,
                         getattr(m, "forwards", 0) or 0, rx, fname, " ".join(urls)))
            inserted += 1
            if inserted % 500 == 0:
                con.commit(); log(f"  ...{inserted}")
    con.commit(); con.close()
    return str(db), last_id, inserted


def run_one(w, env):
    slug = w["slug"]
    log(f"[{slug}] start (chat={w['chat_id']})")
    db, last_id, n = asyncio.run(fetch_incremental(w, env))
    log(f"[{slug}] +{n} new (from id>{last_id})")
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=int(w.get("window_days", 3)))).isoformat()
    until = (today + datetime.timedelta(days=1)).isoformat()
    # prefer @username as the report ref so detect() emits clickable t.me links;
    # chat_id stays the STABLE fetch key (usernames can change, ids can't).
    ref = w.get("username") or w["chat_id"]
    out = mine_channel.detect(slug, ref, db, since, until, int(w.get("top", 25)))
    log(f"[{slug}] report -> {out}  (PRIVATE layer; sensitivity={w.get('sensitivity','private')})")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if not REGISTRY.exists():
        sys.exit(f"no registry: {REGISTRY}  (add channels via /watch-channel)")
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    env = load_env()
    active = [w for w in reg.get("watchers", []) if w.get("active") and (not only or w["slug"] == only)]
    if not active:
        log("no active watchers" + (f" matching '{only}'" if only else "")); return
    log(f"running {len(active)} watcher(s): {', '.join(w['slug'] for w in active)}")
    for w in active:                      # SEQUENTIAL = one session at a time, no AuthKey clash
        try:
            run_one(w, env)
        except Exception as e:
            log(f"[{w.get('slug','?')}] ERROR: {e}")
    log("DONE")


if __name__ == "__main__":
    main()
