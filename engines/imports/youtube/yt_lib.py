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
"""
yt_lib.py — YouTube history normalizer + SQLite store (stdlib only, AK-47).

ONE normalized record schema, TWO source adapters:
  * normalize_scrape()  -> from myactivity.google.com scrape  {a,d,t,ti,ch,v}
  * normalize_takeout() -> from Google Takeout watch-/search-history.json

The big Takeout block reuses EVERYTHING downstream (SQLite, notes, dashboard);
only the adapter that feeds normalized records changes. That is the point of
the pilot: get the hard part (normalize -> store -> analyze) proven now.
"""
import os, re, json, sqlite3
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_history.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
  dedup_key  TEXT PRIMARY KEY,
  source     TEXT,   -- 'scrape' | 'takeout'
  action     TEXT,   -- 'watch'  | 'search'
  title      TEXT,   -- video title OR search query
  channel    TEXT,
  video_id   TEXT,
  query      TEXT,
  ts_utc     TEXT,   -- ISO 8601 if known (takeout); '' for scrape
  date_label TEXT,   -- raw label as shown ('Today'/'June 12'/...) or YYYY-MM-DD
  time_label TEXT,
  day        TEXT,   -- YYYY-MM-DD if resolvable else ''
  month      TEXT,   -- YYYY-MM    if resolvable else ''
  url        TEXT
);
"""

_MONTHS = {m: i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], start=1)}

def _clean(s):
    if s is None: return ""
    # strip narrow no-break space ( ) and normal nbsp Google injects into times
    return s.replace(" ", " ").replace(" ", " ").strip()

def _resolve_scrape_date(label, today):
    """'Today'/'Yesterday'/'June 12'/'June 12, 2025' -> YYYY-MM-DD (best effort)."""
    if not label: return ""
    lab = _clean(label)
    if lab == "Today":     return today.strftime("%Y-%m-%d")
    if lab == "Yesterday": return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.match(r"([A-Z][a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?$", lab)
    if m:
        mon = _MONTHS.get(m.group(1))
        if not mon: return ""
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            d = datetime(year, mon, day)
        except ValueError:
            return ""
        if not m.group(3) and d.date() > today.date():   # no year given & in future -> last year
            d = datetime(year - 1, mon, day)
        return d.strftime("%Y-%m-%d")
    return ""

def _vid(url):
    m = re.search(r"[?&]v=([^&]+)", url or "")
    return m.group(1) if m else None

# ---------------------------------------------------------------- adapters

def normalize_scrape(records, today=None):
    """records from the myactivity DOM scrape. Accepts either full keys
    (action/date/time/title/channel/videoId) or short keys (a/d/t/ti/ch/v)."""
    today = today or datetime.now()
    def g(r, full, short):
        return r.get(full, r.get(short))
    out = []
    for r in records:
        a = g(r, "action", "a") or ""
        action = "watch" if a == "Watched" else (
                 "search" if a.startswith("Searched") else None)
        if not action: continue
        title = _clean(g(r, "title", "ti"))
        chan  = _clean(g(r, "channel", "ch")) or None
        vid   = g(r, "videoId", "v") or None
        day   = _resolve_scrape_date(g(r, "date", "d"), today)
        time_label = _clean(g(r, "time", "t"))
        is_watch = action == "watch"
        url = (f"https://www.youtube.com/watch?v={vid}" if (is_watch and vid)
               else "")
        key = f"{action}|{vid or title}|{day}|{time_label}"
        out.append(dict(
            dedup_key=key, source="scrape", action=action,
            title=title, channel=(chan if is_watch else None),
            video_id=(vid if is_watch else None),
            query=(None if is_watch else title),
            ts_utc="", date_label=_clean(g(r, "date", "d")), time_label=time_label,
            day=day, month=(day[:7] if day else ""), url=url,
        ))
    return out

def normalize_takeout(items):
    """items: parsed list from Takeout watch-history.json / search-history.json
    (both share the same MyActivity JSON shape)."""
    out = []
    for it in items:
        title_raw = _clean(it.get("title"))
        url = it.get("titleUrl", "") or ""
        ts  = _clean(it.get("time"))            # ISO 8601, e.g. 2024-06-01T12:34:56.789Z
        day = month = ""
        if ts:
            try:
                d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                day, month = d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")
                time_label = d.strftime("%I:%M %p").lstrip("0")
            except ValueError:
                time_label = ""
        else:
            time_label = ""
        if title_raw.startswith("Watched "):
            action = "watch"; title = title_raw[len("Watched "):]
            subs = it.get("subtitles") or []
            chan = _clean(subs[0].get("name")) if subs else None
            vid = _vid(url)
            rec = dict(action=action, title=title, channel=chan, video_id=vid,
                       query=None, url=url)
            key = f"watch|{vid or title}|{ts}"
        elif title_raw.startswith("Searched for "):
            action = "search"; q = title_raw[len("Searched for "):]
            rec = dict(action=action, title=q, channel=None, video_id=None,
                       query=q, url=url)
            key = f"search|{q}|{ts}"
        else:
            continue  # 'Viewed', 'Visited', removed-video, etc. -> skip for now
        rec.update(dedup_key=key, source="takeout", ts_utc=ts,
                   date_label=day, time_label=time_label, day=day, month=month)
        out.append(rec)
    return out

# ---------------------------------------------------------------- store

def connect(db=DB):
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    return conn

def upsert(conn, recs):
    """Idempotent: INSERT OR IGNORE on dedup_key. Returns rows newly added."""
    before = conn.execute("SELECT count(*) FROM events").fetchone()[0]
    conn.executemany("""
      INSERT OR IGNORE INTO events
        (dedup_key,source,action,title,channel,video_id,query,ts_utc,
         date_label,time_label,day,month,url)
      VALUES (:dedup_key,:source,:action,:title,:channel,:video_id,:query,
              :ts_utc,:date_label,:time_label,:day,:month,:url)
    """, recs)
    conn.commit()
    after = conn.execute("SELECT count(*) FROM events").fetchone()[0]
    return after - before
