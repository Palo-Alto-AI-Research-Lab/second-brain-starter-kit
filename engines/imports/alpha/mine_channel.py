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
r"""mine_channel.py — GENERIC one-command miner for ANY Telegram channel/chat.
Generalises the proven promptdesign/foxpod/sostav pattern: scrape (0-token Telethon,
subscription path) -> build SQLite -> deterministic alpha DETECTOR shortlist.
The LLM judge + vault write are the next steps in the `/mine-channel` skill (Sonnet,
then obsidian-ingest) — kept OUT of here so this stays 0-token & idempotent.

  set PYTHONIOENCODING=utf-8
  python mine_channel.py --channel prompt_design --slug promptdesign
  python mine_channel.py --channel -1000800842092 --slug silmeshok --limit 500 --top 40
  python mine_channel.py --slug promptdesign --detect-only        # re-detect, no re-scrape

Output (under %IMPORTS%\alpha\<slug>\): <slug>.jsonl, <slug>.db
Shortlist -> %IMPORTS%\alpha\candidates\<slug>-report.md
Canon: memory alpha-extraction-engine; templates promptdesign_scrape/_alpha.
"""
import os, sys, re, json, sqlite3, asyncio
from pathlib import Path

ALPHA = Path(r"%IMPORTS%\alpha")
ENV = Path(r"C:/mcp/telegram-mcp/.env")
CAND = ALPHA / "candidates"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# generic tool/model/technique/deal/benchmark alpha keywords (RU+EN) — tune per channel later
KW = re.compile(
    r"(claude|cowork|chatgpt|gpt-?\d|deepseek|gemini|grok|llm|модел[ьи]|\bагент|mcp\b|n8n|"
    r"\bapi\b|github|репозитор|опенсорс|open\s?source|локальн|воркфлоу|workflow|автоматизац|"
    r"промпт|prompt|пайплайн|pipeline|скрипт|\bгайд|\.md\b|эмбеддинг|embedding|rag\b|вектор|"
    r"fine-?tune|дообуч|бесплатн|халяв|\bакци|кредит|лимит|free\b|деплой|deploy|vps\b|"
    r"окупа|профит|сэконом|в\s*\d+\s*раз|бенчмарк|метрик|инструмент|сервис|релиз|вышел|"
    r"выкатил|сделк|deal|раунд|инвест|оцен|valuation|выручк|revenue|стартап)", re.I)
PROMO = re.compile(
    r"(гоу к нам|к нам в|вступай|вступить|подписывайт|присоединяйт|мастермайнд|"
    r"наш[еа]\s*сообществ|наш чат|наш канал|закрыт[оаы].{0,15}клуб|реклам[аы]|по вопросам рекламы)", re.I)
BANTER = re.compile(r"^(спасибо|плюс|\+1|согласен|это|так|да|нет|лол|ахах|👍+|🔥+|❤+|спс)\W*$", re.I)


def load_env():
    d = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


async def scrape(channel, out, limit):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
    env = load_env()
    api_id = int(env["TELEGRAM_API_ID"]); api_hash = env["TELEGRAM_API_HASH"]
    session = env.get("TELEGRAM_SESSION_STRING_WORK_ACCT_A") or env["TELEGRAM_SESSION_STRING"]
    try:
        channel = int(channel)
    except (ValueError, TypeError):
        pass
    n = 0
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        ent = await client.get_entity(channel)
        with out.open("w", encoding="utf-8") as f:
            async for m in client.iter_messages(ent, limit=limit):
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
                f.write(json.dumps({
                    "id": m.id, "date": m.date.isoformat() if m.date else None,
                    "text": m.message or "", "views": getattr(m, "views", None),
                    "forwards": getattr(m, "forwards", None), "reactions": rx,
                    "reply_to": m.reply_to_msg_id if m.reply_to else None,
                    "file": fname, "urls": urls,
                }, ensure_ascii=False) + "\n")
                n += 1
                if n % 250 == 0:
                    print(f"  ...{n}", flush=True)
    print(f"scraped {n} posts -> {out}")
    return n


def build_db(jsonl, db):
    rows = []
    for line in jsonl.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line); d = r.get("date") or ""
        rows.append((r.get("id"), d, d[:10], r.get("text") or "", r.get("views") or 0,
                     r.get("forwards") or 0, r.get("reactions") or 0, r.get("file"),
                     " ".join(r.get("urls") or [])))
    con = sqlite3.connect(db)
    con.executescript("DROP TABLE IF EXISTS messages; CREATE TABLE messages("
                      "id INTEGER,date TEXT,day TEXT,text TEXT,views INTEGER,forwards INTEGER,"
                      "reactions INTEGER,file TEXT,urls TEXT);")
    con.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit(); con.close()
    return len(rows)


def score(text, views, fwd, rx, file, urls):
    nl = len([u for u in (urls or "").split() if u.startswith("http")])
    s = (fwd or 0) * 1.0 + (rx or 0) * 0.25 + min((views or 0) / 1000.0, 15) + nl * 6
    if file and re.search(r"\.(md|pdf|txt|csv|json|zip)$", file, re.I):
        s += 20
    if KW.search(text or ""):
        s += 10
    if len(text or "") >= 400:
        s += 4
    if PROMO.search(text or ""):
        s -= 15
    if BANTER.match((text or "").strip()):
        s -= 25
    return s, nl


def detect(slug, channel, db, since, until, top):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id,date,day,text,views,forwards,reactions,file,urls FROM messages "
                       "WHERE day>=? AND day<? AND length(text)>=60 ORDER BY date", (since, until)).fetchall()
    con.close()
    scored = sorted(((score(r[3], r[4], r[5], r[6], r[7], r[8]), r) for r in rows), key=lambda x: -x[0][0])
    seen, picks = set(), []
    for (sc, nl), r in scored:
        if sc <= 6:
            break
        k = re.sub(r"\s+", " ", (r[3] or "").lower())[:120]
        if k in seen:
            continue
        seen.add(k); picks.append((sc, nl, r))
        if len(picks) >= top:
            break
    ref = str(channel).lstrip("-") if str(channel).lstrip("-").isdigit() else channel
    lines = [f"# 🛰 {slug} — alpha DETECTOR shortlist", "",
             f"_0-token detector over `{slug}.db` ({since}…{until}). {len(rows)} substantive posts → top {len(picks)} by signal._",
             f"_Next: LLM-judge keeps only REAL alpha FOR ANTON (tool/model/deal · technique · proof-point), drops promo. Verdict ✅/🟡/🗑._", "", "---", ""]
    for i, (sc, nl, r) in enumerate(picks, 1):
        mid, date, day, text, views, fwd, rx, file, urls = r
        lines.append(f"### #{i} ({day} · {fwd or 0}fwd · {rx or 0}rx · {views or 0}v · score {int(sc)})")
        if str(channel).startswith("@") or not str(channel).lstrip("-").isdigit():
            lines.append(f"- **Link:** https://t.me/{str(channel).lstrip('@')}/{mid}")
        if file:
            lines.append(f"- **Guide:** {file}")
        body = re.sub(r"\s+", " ", text or "").strip()
        lines.append(f"- **Text:** {body[:600]}")
        lines.append("")
    CAND.mkdir(parents=True, exist_ok=True)
    out = CAND / f"{slug}-report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"scanned {len(rows)} substantive · shortlisted {len(picks)} -> {out}")
    return str(out)


def main():
    a = sys.argv
    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    slug = opt("--slug")
    if not slug:
        sys.exit("need --slug <name>")
    channel = opt("--channel")
    limit = int(opt("--limit")) if "--limit" in a else None
    top = int(opt("--top", "40"))
    since = opt("--since", "2000-01-01"); until = opt("--until", "2099-01-01")
    home = ALPHA / slug; home.mkdir(parents=True, exist_ok=True)
    jsonl = home / f"{slug}.jsonl"; db = home / f"{slug}.db"

    if "--detect-only" not in a:
        if not channel:
            sys.exit("need --channel <username|id> (or use --detect-only on existing jsonl)")
        asyncio.run(scrape(channel, jsonl, limit))
    if not jsonl.exists():
        sys.exit(f"no jsonl: {jsonl}")
    n = build_db(jsonl, db)
    print(f"db: {n} posts")
    detect(slug, channel or slug, db, since, until, top)


if __name__ == "__main__":
    main()
