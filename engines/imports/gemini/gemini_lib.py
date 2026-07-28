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
r"""gemini_lib.py — Google Gemini Apps activity -> SQLite + Obsidian notes.

Stdlib only (AK-47). Adapter on the SAME Google "My Activity" JSON shape that
youtube/yt_lib.py already normalizes — Gemini chats export via Google Takeout:
  takeout.google.com -> Deselect all -> "My Activity" -> Gemini Apps -> JSON.

ONE normalized record schema, ONE source adapter (normalize_gemini). Everything
downstream (SQLite dedup store, day-notes, MOC) is reused verbatim in spirit
from the chatgpt/youtube importers so a non-engineer can reason about it.

Design choices grounded in the export's real shape (verified against Google's
documented My Activity structure; field-names to be reconfirmed on the first
real export — see _test_gemini.py for the fixture we build to):
  * My Activity is a FLAT list of per-prompt events, not threaded conversations.
    Each item ~= one user turn: {header, title:"Prompted ...", time, titleUrl?}.
  * Responses are NOT reliably present in My Activity, so we store the PROMPT as
    the primary signal and keep any response text when the export includes it.
  * Idempotency key = source|time|hash(title) — re-running never duplicates
    (the merge/upsert law of personal-data-warehouses: Dogsheep/HPI, data-eng).
  * We group prompts into ONE NOTE PER DAY (a "Gemini day"), because My Activity
    gives no stable conversation id. Day-notes are stable and re-buildable.

USAGE:
  python gemini_lib.py import <MyActivity.json|MyActivity.html|takeout.zip>  # -> DB + notes
  python gemini_lib.py stats                                                 # DB summary

REALITY CHECK (2026-07-25, hub): the first REAL Takeout (takeout-20260620T220849Z)
delivered My Activity as **HTML**, not JSON (HTML is Google's default; JSON only if
explicitly chosen at export time). Field shape confirmed against that real export via
browser-history/my_activity_to_db.py, which parsed it successfully on HP17:
one uniform MDL cell per prompt — head "Prompted <text>", then "Jun 20, 2026,
9:53:52 PM WEST", then detail (Gemini embeds the response text there).
So this lib now carries BOTH adapters: normalize_gemini (JSON rail, kept for a
future JSON-format export) and normalize_gemini_html (the rail real data uses).
"""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-07-20
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os, re, json, sqlite3, hashlib, sys, datetime
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
DB = HERE / "gemini_activity.db"

# Portable vault root: env first (Mac16 sets CLAUDE_VAULT_ROOT), then hub default.
VAULT = Path(os.environ.get("CLAUDE_VAULT_ROOT")
             or os.environ.get("OBSIDIAN_VAULT")
             or os.path.expanduser("~/Obsidian/Owner-Knowledge"))
NOTES_DIR = VAULT / "01-Conversations" / "Gemini" / "days"
MOC = VAULT / "01-Conversations" / "Gemini" / "_Gemini-MOC.md"
FRESHNESS = HERE / "_freshness.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns(
  dedup_key  TEXT PRIMARY KEY,
  source     TEXT,            -- 'takeout-myactivity'
  prompt     TEXT,            -- user's prompt text
  response   TEXT,            -- model response if the export carried it, else ''
  ts_utc     TEXT,            -- ISO 8601
  day        TEXT,            -- YYYY-MM-DD
  month      TEXT,            -- YYYY-MM
  url        TEXT             -- conversation/app link if present
);
"""

_PROMPT_PREFIXES = ("Prompted ", "Prompt: ", "Asked ", "You said: ")


def _clean(s):
    if s is None:
        return ""
    return s.replace(" ", " ").replace("\xa0", " ").strip()


def _strip_prompt_prefix(title):
    t = _clean(title)
    for p in _PROMPT_PREFIXES:
        if t.startswith(p):
            return t[len(p):].strip()
    return t


def normalize_gemini(items):
    """items: parsed list from a Gemini Apps 'My Activity' JSON export.

    Returns normalized turn dicts ready for the SQLite store. Skips non-Gemini
    rows defensively (a mixed My Activity export can carry other products)."""
    out = []
    for it in items:
        header = _clean(it.get("header"))
        # Keep Gemini/Bard rows; if header missing, fall back on titleUrl host.
        url = it.get("titleUrl", "") or ""
        looks_gemini = ("gemini" in header.lower() or "bard" in header.lower()
                        or "gemini.google.com" in url or "bard.google.com" in url)
        if header and not looks_gemini:
            continue

        title_raw = _clean(it.get("title"))
        if not title_raw:
            continue
        prompt = _strip_prompt_prefix(title_raw)

        # Response: some exports nest it; try common shapes, else ''.
        response = ""
        for k in ("description", "response"):
            if it.get(k):
                response = _clean(it.get(k))
                break
        subs = it.get("subtitles") or []
        if not response and subs and isinstance(subs, list):
            cand = _clean(subs[0].get("name") if isinstance(subs[0], dict) else subs[0])
            # subtitles often just repeat the product name; ignore that case
            if cand and cand.lower() not in ("gemini apps", "bard"):
                response = cand

        ts = _clean(it.get("time"))
        day = month = ""
        if ts:
            try:
                d = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                day, month = d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")
            except ValueError:
                pass

        key = "gemini|%s|%s" % (ts, hashlib.sha1(title_raw.encode("utf-8")).hexdigest()[:12])
        out.append(dict(dedup_key=key, source="takeout-myactivity", prompt=prompt,
                        response=response, ts_utc=ts, day=day, month=month, url=url))
    return out


# ---------------------------------------------------------- html adapter
# Regex set proven on the real export by browser-history/my_activity_to_db.py.
_CELL_RX = re.compile(
    r'<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">(.*?)</div>',
    re.S)
_DATE_RX = re.compile(r'([A-Z][a-z]{2}) (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}):(\d{2})\s*([AP]M)')
_LINK_RX = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_BR_RX = re.compile(r'<br\s*/?>', re.I)
_TAG_RX = re.compile(r'<[^>]+>')
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
RESPONSE_CAP = 2000  # detail carries the model's reply = exposure, not Anton's voice; cap it


def _parse_dt_html(line):
    m = _DATE_RX.search(line)
    if not m:
        return None
    mon, day, year, hh, mm, ss, ap = m.groups()
    if mon not in _MONTHS:
        return None
    h = int(hh) % 12 + (12 if ap == "PM" else 0)
    try:
        return datetime.datetime(int(year), _MONTHS[mon], int(day), h, int(mm), int(ss))
    except ValueError:
        return None


def normalize_gemini_html(html_text):
    """Adapter for the REAL export shape: Takeout/My Activity/Gemini Apps/MyActivity.html.

    The per-product HTML file is already Gemini-only, so no product filtering is
    needed. Yields the SAME normalized row dicts as normalize_gemini."""
    import html as _html
    out = []
    for m in _CELL_RX.finditer(html_text):
        cell = m.group(1)
        plain = _html.unescape(_TAG_RX.sub("", _BR_RX.sub("\n", cell)))
        lines = [l.strip() for l in plain.split("\n") if l.strip()]
        di = dt = None
        for i, l in enumerate(lines):
            d = _parse_dt_html(l)
            if d:
                di, dt = i, d
                break
        if dt is None:
            continue  # caption/header cell, not an activity cell
        head = _clean(" ".join(lines[:di]))
        if not head:
            continue
        response = _clean(" ".join(lines[di + 1:]))[:RESPONSE_CAP]
        url = ""
        lk = _LINK_RX.search(cell)
        if lk:
            url = _html.unescape(lk.group(1)).strip()
        ts = dt.strftime("%Y-%m-%dT%H:%M:%S")
        key = "gemini|%s|%s" % (ts, hashlib.sha1(head.encode("utf-8")).hexdigest()[:12])
        out.append(dict(dedup_key=key, source="takeout-myactivity-html",
                        prompt=_strip_prompt_prefix(head), response=response,
                        ts_utc=ts, day=dt.strftime("%Y-%m-%d"),
                        month=dt.strftime("%Y-%m"), url=url))
    return out


_ZIP_GEMINI_RX = re.compile(r"My Activity/(Gemini|Bard)[^/]*/MyActivity\.html$")


def load_rows(path):
    """Auto-detect input rail: Takeout .zip / MyActivity .html / My Activity .json.
    Returns normalized rows ready for upsert."""
    p = str(path).lower()
    if p.endswith(".zip"):
        import zipfile
        rows = []
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if _ZIP_GEMINI_RX.search(n)]
            for n in names:
                rows.extend(normalize_gemini_html(z.read(n).decode("utf-8", "replace")))
        if not names:
            print(f"[warn] no 'My Activity/Gemini*/MyActivity.html' inside {path} "
                  "(was Gemini Apps ticked in the export?)")
        return rows
    if p.endswith((".html", ".htm")):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return normalize_gemini_html(f.read())
    return normalize_gemini(_load_json(path))


# ------------------------------------------------------------------ store

def connect(db=None):
    # Late-bind to the module global so tests/callers can reassign DB at runtime
    # (a default arg `db=DB` would freeze the original path at def-time).
    con = sqlite3.connect(str(db or DB))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def upsert(con, rows):
    """Idempotent merge. Returns (inserted, seen).

    Counts real inserts via con.total_changes delta — NOT per-statement
    cur.rowcount, which is unreliable for INSERT OR IGNORE under WAL (may
    report -1/0 for a row that was actually inserted)."""
    before = con.total_changes
    for r in rows:
        con.execute(
            "INSERT OR IGNORE INTO turns"
            "(dedup_key,source,prompt,response,ts_utc,day,month,url)"
            " VALUES(:dedup_key,:source,:prompt,:response,:ts_utc,:day,:month,:url)", r)
    con.commit()
    return con.total_changes - before, len(rows)


# ------------------------------------------------------------------ notes

def _fm_escape(s):
    return (s or "").replace('"', "'").replace("\n", " ").strip()


def build_day_notes(con):
    """One note per Gemini day. Idempotent: rewrites the day file from the DB
    (the DB is the source of truth), never clobbers a concept-enriched note —
    we only own files under 01-Conversations/Gemini/days/."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT day FROM turns WHERE day<>'' ORDER BY day")]
    written = 0
    for day in days:
        turns = con.execute(
            "SELECT ts_utc,prompt,response,url FROM turns WHERE day=? ORDER BY ts_utc", (day,)
        ).fetchall()
        first_prompt = turns[0][1] if turns else ""
        slug = re.sub(r"[^a-z0-9]+", "-", first_prompt.lower())[:40].strip("-") or "gemini"
        path = NOTES_DIR / f"{day}-{slug}.md"
        lines = [
            "---",
            f'title: "Gemini {day} — {_fm_escape(first_prompt)[:60]}"',
            "type: ai-conversation",
            "stage: raw",
            "source: gemini",
            "origin: mixed",
            "authored_by: hybrid",
            f"date_recorded: {day}",
            f"date_added: {datetime.date.today().isoformat()}",
            "language: ru",
            "tags: [ai-conversation, archive, gemini]",
            f"msg_count: {len(turns)}",
            "related_concepts: []",
            "---",
            "",
            f"# Gemini — {day}",
            "",
        ]
        for ts, prompt, response, url in turns:
            tm = ts[11:16] if len(ts) >= 16 else ""
            lines.append(f"### {tm} — {prompt}".rstrip())
            if url:
                lines.append(f"[open in Gemini]({url})")
            if response:
                lines.append("")
                lines.append(f"> {response}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        written += 1
    return written, len(days)


def write_freshness(con):
    row = con.execute("SELECT MAX(day) FROM turns WHERE day<>''").fetchone()
    newest = row[0] if row and row[0] else None
    total = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    stale_days = None
    if newest:
        try:
            nd = datetime.date.fromisoformat(newest)
            stale_days = (datetime.date.today() - nd).days
        except ValueError:
            pass
    FRESHNESS.write_text(json.dumps({
        "checked_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "newest_day": newest, "total_turns": total, "stale_days": stale_days,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return newest, total, stale_days


# ------------------------------------------------------------------ cli

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("items", data)


def do_import(path):
    rows = load_rows(path)
    con = connect()
    ins, seen = upsert(con, rows)
    nw, nd = build_day_notes(con)
    newest, total, stale = write_freshness(con)
    print(f"gemini import: +{ins} new / {seen} parsed | day-notes: {nw} written "
          f"({nd} days) | DB total {total} | newest {newest} (stale {stale}d)")
    return ins


def do_stats():
    con = connect()
    total = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    days = con.execute("SELECT COUNT(DISTINCT day) FROM turns WHERE day<>''").fetchone()[0]
    print(f"gemini DB: {total} turns across {days} days | {DB}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "import":
        if len(sys.argv) < 3:
            print("usage: gemini_lib.py import <MyActivity.json|MyActivity.html|takeout.zip>")
            sys.exit(2)
        do_import(sys.argv[2])
    elif cmd == "stats":
        do_stats()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
