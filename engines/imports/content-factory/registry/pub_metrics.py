#!/usr/bin/env python
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
r"""pub_metrics.py - единый реестр ОПУБЛИКОВАННОГО контента + метрики + комменты.

Дополняет pub_registry.py (тот = очередь/лимиты ДО публикации; этот = факты ПОСЛЕ:
ссылка-пруф на каждый пост, снапшоты метрик во времени, комменты отвечено/нет,
топ-комментаторы). AK-47: один файл, stdlib, SQLite.

DB: pubmetrics.db (рядом). Таблицы:
  publications  - каждый опубликованный юнит (пост/статья/репо), url = пруф
  snapshots     - метрики по времени (views/likes/comments/shares), append-only
  comments      - каждый коммент; replied 0/1; авторы -> топ-комментаторы

USAGE:
  python pub_metrics.py init
  python pub_metrics.py add --platform fb_wall --url URL --title T [--date ISO] [--author anton] [--story ID]
  python pub_metrics.py import-ledger            # pub_ledger.jsonl (posted) -> publications
  python pub_metrics.py import-fb                # fb_teaser_ledger.json -> publications (без url, pfbid в extra)
  python pub_metrics.py snapshot-github [--org Palo-Alto-AI-Research-Lab]   # gh CLI: stars/forks/traffic
  python pub_metrics.py ingest-tg --in dump.json # [{url,title,date,views,reactions,replies,text?}]
  python pub_metrics.py ingest-fb-graph --in fb_metrics.json
                                                 # выход fb_posts_poll.py metrics; дедуп по
                                                 # стабильному graph_id (pfbid ротируется!)
  python pub_metrics.py snapshot --url URL --views N --likes N --comments N --shares N
  python pub_metrics.py comment --url URL --cid ID --author NAME [--author-id ID] [--text T] [--date ISO] [--replied]
  python pub_metrics.py mark-replied --cid ID
  python pub_metrics.py unanswered               # комменты без ответа
  python pub_metrics.py top-commenters [--n 15]
  python pub_metrics.py status
  python pub_metrics.py dashboard                # -> _Dashboards\Pub-Registry-Metrics.html
Exit: 0 ok | 2 bad args | 4 file missing
"""
import os, sys, json, sqlite3, argparse, subprocess, html
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "pubmetrics.db")
LEDGER = os.path.join(HERE, "pub_ledger.jsonl")
FB_LEDGER = os.path.normpath(os.path.join(HERE, "..", "fb_teaser_ledger.json"))
DASH = r"%VAULT%\_Dashboards\Pub-Registry-Metrics.html"

def now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")

def db():
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS publications(
      id INTEGER PRIMARY KEY,
      story_id TEXT DEFAULT '',
      platform TEXT NOT NULL,
      url TEXT DEFAULT '',
      title TEXT DEFAULT '',
      author TEXT DEFAULT 'anton',
      published_at TEXT DEFAULT '',
      source TEXT DEFAULT '',
      extra TEXT DEFAULT '',
      added_at TEXT NOT NULL,
      UNIQUE(platform, url, title)
    );
    CREATE TABLE IF NOT EXISTS snapshots(
      id INTEGER PRIMARY KEY,
      pub_id INTEGER NOT NULL,
      ts TEXT NOT NULL,
      views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER,
      extra TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS comments(
      id INTEGER PRIMARY KEY,
      pub_id INTEGER NOT NULL,
      platform TEXT NOT NULL,
      comment_id TEXT NOT NULL,
      author TEXT DEFAULT '',
      author_id TEXT DEFAULT '',
      text TEXT DEFAULT '',
      ts TEXT DEFAULT '',
      is_ours INTEGER DEFAULT 0,
      replied INTEGER DEFAULT 0,
      replied_at TEXT DEFAULT '',
      UNIQUE(platform, comment_id)
    );
    """)
    return c

def upsert_pub(c, platform, url="", title="", story="", author="anton",
               published_at="", source="", extra=""):
    row = None
    if url:
        row = c.execute("SELECT id FROM publications WHERE platform=? AND url=?",
                        (platform, url)).fetchone()
    if not row and title:
        row = c.execute("SELECT id FROM publications WHERE platform=? AND title=? AND url=''",
                        (platform, title)).fetchone()
        if row and url:  # у старой записи не было url, дозаполняем пруф
            c.execute("UPDATE publications SET url=? WHERE id=?", (url, row[0]))
    if row:
        return row[0], False
    c.execute("""INSERT INTO publications(story_id,platform,url,title,author,published_at,source,extra,added_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (story, platform, url, title, author, published_at, source, extra, now()))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0], True

def add_snapshot(c, pub_id, views=None, likes=None, comments=None, shares=None, extra=""):
    c.execute("INSERT INTO snapshots(pub_id,ts,views,likes,comments,shares,extra) VALUES(?,?,?,?,?,?,?)",
              (pub_id, now(), views, likes, comments, shares, extra))

# ---------- importers ----------

def import_ledger(c):
    if not os.path.exists(LEDGER):
        print("нет pub_ledger.jsonl"); return 0
    n = 0
    for line in open(LEDGER, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event") != "posted":
            continue
        _, new = upsert_pub(c, e.get("platform", "?"), e.get("url", ""),
                            e.get("title", ""), e.get("id", ""),
                            published_at=e.get("at", ""), source="pub_ledger")
        n += new
    return n

def import_fb(c):
    if not os.path.exists(FB_LEDGER):
        print("нет fb_teaser_ledger.json"); return 0
    d = json.load(open(FB_LEDGER, encoding="utf-8"))
    n = 0
    for pfbid, meta in (d.get("posts") or {}).items():
        _, new = upsert_pub(c, "fb_wall", f"https://www.facebook.com/OwnerProfile/posts/{pfbid}",
                            f"FB post {pfbid[:24]}…",
                            published_at=meta.get("first_seen", ""),
                            source="fb_teaser_ledger",
                            extra=json.dumps({"pfbid": pfbid}))
        n += new
    return n

TRACKER = r"%VAULT%\_Dashboards\content-distribution-tracker.html"

def _plat_norm(p):
    q = p.lower()
    table = [("x / twitter", "x"), ("claweng", "tg_claweng"), ("clawrus", "tg_clawrus"),
             ("paloaltoairu", "tg_paloaltoairu"), ("paloaltoai", "tg_paloaltoai"),
             ("medium", "medium"), ("facebook", "fb_wall"), ("fb", "fb_wall"),
             ("github", "github"), ("threads", "threads"), ("vc.ru", "vcru"),
             ("хабр", "habr"), ("habr", "habr"), ("reddit", "reddit")]
    for k, v in table:
        if k in q:
            return v
    return p.strip().lower().replace(" ", "_")[:24]

def import_tracker(c):
    """content-distribution-tracker.html (JS initPosts) -> publications."""
    import re
    if not os.path.exists(TRACKER):
        print("нет трекера:", TRACKER); return 0
    h = open(TRACKER, encoding="utf-8").read()
    m = re.search(r"initPosts\s*=\s*(\[.*?\]);", h, re.S)
    if not m:
        print("initPosts не найден"); return 0
    n = 0
    for obj in re.findall(r"\{[^{}]*\}", m.group(1)):
        d = dict(re.findall(r"(\w+)\s*:\s*'((?:[^'\\]|\\.)*)'", obj))
        if "Запощен" not in d.get("status", ""):
            continue
        title = f"{d.get('post','')} · {d.get('tier','')} · {d.get('lang','')}".strip(" ·")
        pub_id, new = upsert_pub(c, _plat_norm(d.get("platform", "?")), d.get("url", ""),
                                 title, story=d.get("post", ""),
                                 published_at=d.get("date", ""), source="dist-tracker",
                                 extra=json.dumps({"tracker_id": d.get("id", ""),
                                                   "note": d.get("note", "")}, ensure_ascii=False))
        n += new
        vals = {}
        for k, col in (("r", "likes"), ("c", "comments"), ("s", "shares"), ("f", "views")):
            v = d.get(k, "")
            if v.strip().isdigit():
                vals[col] = int(v)
        if vals:
            add_snapshot(c, pub_id, views=vals.get("views"), likes=vals.get("likes"),
                         comments=vals.get("comments"), shares=vals.get("shares"))
    return n

def snapshot_github(c, org):
    out = subprocess.run(["gh", "repo", "list", org, "--json",
                          "name,stargazerCount,forkCount,url,description,createdAt"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print("gh error:", out.stderr[:300]); return 0
    n = 0
    for r in json.loads(out.stdout):
        pub_id, _ = upsert_pub(c, "github", r["url"], r["name"],
                               published_at=r.get("createdAt", "")[:16],
                               source="gh")
        views = None
        tr = subprocess.run(["gh", "api", f"repos/{org}/{r['name']}/traffic/views"],
                            capture_output=True, text=True)
        uniq = None
        if tr.returncode == 0:
            try:
                t = json.loads(tr.stdout)
                views = t.get("count"); uniq = t.get("uniques")
            except Exception:
                pass
        add_snapshot(c, pub_id, views=views, likes=r["stargazerCount"],
                     shares=r["forkCount"],
                     extra=json.dumps({"uniques_14d": uniq, "views_window": "14d"}))
        n += 1
    return n

def ingest_tg(c, path):
    rows = json.load(open(path, encoding="utf-8"))
    n = 0
    for r in rows:
        pub_id, _ = upsert_pub(c, r.get("platform", "tg_channel"), r.get("url", ""),
                               r.get("title", "")[:120],
                               published_at=r.get("date", ""), source="tg")
        add_snapshot(c, pub_id, views=r.get("views"), likes=r.get("reactions"),
                     comments=r.get("replies"))
        n += 1
    return n

def ingest_fb_graph(c, path):
    """Выход fb_posts_poll.py metrics -> publications + snapshots + comments.

    Дедуп постов по СТАБИЛЬНОМУ численному graph_id (extra JSON): pfbid в permalink
    ротируется, из-за этого dedup по url ломался (грабли fb-watch-pfbid-rotation).
    Порядок матча: graph_id -> точный url -> pfbid из permalink внутри старых url.
    """
    d = json.load(open(path, encoding="utf-8"))
    me_id = str((d.get("me") or {}).get("id", ""))
    n_posts = n_snaps = n_comments = 0
    import re
    for p in d.get("posts", []):
        gid = p.get("id") or ""
        url = p.get("permalink") or ""
        pub_id = None
        row = c.execute("SELECT id FROM publications WHERE platform='fb_wall' AND extra LIKE ?",
                        ('%"graph_id": "' + gid + '"%',)).fetchone()
        if row:
            pub_id = row[0]
        if pub_id is None and url:
            row = c.execute("SELECT id FROM publications WHERE platform='fb_wall' AND url=?",
                            (url,)).fetchone()
            if row:
                pub_id = row[0]
        if pub_id is None and url:
            m = re.search(r"(pfbid\w+)", url)
            if m:
                row = c.execute("SELECT id FROM publications WHERE platform='fb_wall' AND url LIKE ?",
                                ("%" + m.group(1) + "%",)).fetchone()
                if row:
                    pub_id = row[0]
        if pub_id is None:
            pub_id, new = upsert_pub(c, "fb_wall", url, (p.get("text") or "")[:80] or f"FB post {gid}",
                                     published_at=(p.get("ts") or "")[:16], source="fb_graph",
                                     extra=json.dumps({"graph_id": gid}))
            n_posts += new
        else:  # дозаполняем graph_id и свежий permalink у найденной записи
            old = c.execute("SELECT extra FROM publications WHERE id=?", (pub_id,)).fetchone()[0]
            try:
                ex = json.loads(old) if old else {}
            except Exception:
                ex = {"legacy_extra": old}
            if ex.get("graph_id") != gid:
                ex["graph_id"] = gid
                c.execute("UPDATE publications SET extra=? WHERE id=?", (json.dumps(ex), pub_id))
            if url:
                c.execute("UPDATE publications SET url=? WHERE id=? AND url!=?", (url, pub_id, url))
        add_snapshot(c, pub_id, likes=p.get("reactions"), comments=p.get("comments_count"),
                     shares=p.get("shares"), extra=json.dumps({"graph_id": gid}))
        n_snaps += 1
        for cm in p.get("comments", []):
            ours = 1 if (me_id and str(cm.get("author_id", "")) == me_id) else 0
            c.execute("""INSERT OR IGNORE INTO comments(pub_id,platform,comment_id,author,author_id,text,ts,is_ours,replied)
                         VALUES(?,?,?,?,?,?,?,?,0)""",
                      (pub_id, "fb_wall", cm.get("cid", ""), cm.get("author", ""),
                       str(cm.get("author_id", "")), cm.get("text", ""), cm.get("ts", ""), ours))
            n_comments += c.execute("SELECT changes()").fetchone()[0]
    return n_posts, n_snaps, n_comments

# ---------- reports ----------

LATEST = """
SELECT p.id,p.platform,p.title,p.url,p.published_at,
  (SELECT views FROM snapshots s WHERE s.pub_id=p.id ORDER BY ts DESC LIMIT 1),
  (SELECT likes FROM snapshots s WHERE s.pub_id=p.id ORDER BY ts DESC LIMIT 1),
  (SELECT comments FROM snapshots s WHERE s.pub_id=p.id ORDER BY ts DESC LIMIT 1),
  (SELECT shares FROM snapshots s WHERE s.pub_id=p.id ORDER BY ts DESC LIMIT 1),
  (SELECT COUNT(*) FROM comments cm WHERE cm.pub_id=p.id AND cm.replied=0 AND cm.is_ours=0)
FROM publications p ORDER BY p.platform, p.published_at DESC
"""

def status(c):
    total = c.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
    withurl = c.execute("SELECT COUNT(*) FROM publications WHERE url!=''").fetchone()[0]
    snaps = c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    unans = c.execute("SELECT COUNT(*) FROM comments WHERE replied=0 AND is_ours=0").fetchone()[0]
    print(f"публикаций: {total} (с пруф-ссылкой: {withurl}) · снапшотов метрик: {snaps} · комментов без ответа: {unans}")
    for p, n in c.execute("SELECT platform, COUNT(*) FROM publications GROUP BY platform ORDER BY 2 DESC"):
        print(f"  {p}: {n}")

def dashboard(c):
    rows = c.execute(LATEST).fetchall()
    unans = c.execute("""SELECT cm.author, cm.text, cm.ts, p.title, p.url FROM comments cm
                         JOIN publications p ON p.id=cm.pub_id
                         WHERE cm.replied=0 AND cm.is_ours=0 ORDER BY cm.ts DESC""").fetchall()
    tops = c.execute("""SELECT author, COUNT(*) n FROM comments WHERE is_ours=0 AND author!=''
                        GROUP BY author ORDER BY n DESC LIMIT 15""").fetchall()
    plats = {}
    for r in rows:
        plats.setdefault(r[1], []).append(r)
    def esc(x):
        return html.escape(str(x)) if x is not None else ""
    parts = ["""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Реестр публикаций и метрик</title><style>
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#fafafa;color:#222}
h1{font-size:22px} h2{font-size:17px;margin-top:28px;border-bottom:2px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
th,td{border:1px solid #e0e0e0;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f0f0f0} .num{text-align:right} .warn{background:#fff3cd}
.badge{display:inline-block;background:#e8f0fe;border-radius:10px;padding:1px 8px;font-size:12px;margin-right:6px}
a{color:#1a56db;text-decoration:none} a:hover{text-decoration:underline}
.miss{color:#b00;font-size:12px}</style></head><body>"""]
    total = len(rows); withurl = sum(1 for r in rows if r[3])
    parts.append(f"<h1>📚 Реестр публикаций и метрик</h1><p>Обновлено: {now()} · "
                 f"<span class='badge'>публикаций: {total}</span>"
                 f"<span class='badge'>с пруф-ссылкой: {withurl}</span>"
                 f"<span class='badge'>без ответа: {len(unans)} комм.</span></p>")
    for plat in sorted(plats):
        rs = plats[plat]
        parts.append(f"<h2>{esc(plat)} ({len(rs)})</h2><table><tr><th>дата</th><th>заголовок</th>"
                     "<th>пруф</th><th class=num>👁</th><th class=num>👍</th><th class=num>💬</th>"
                     "<th class=num>↗</th><th class=num>без ответа</th></tr>")
        for (pid, _, title, url, pub_at, v, l, cm, sh, un) in rs:
            link = f"<a href='{esc(url)}' target=_blank>ссылка</a>" if url else "<span class=miss>нет ссылки!</span>"
            cls = " class=warn" if un else ""
            parts.append(f"<tr{cls}><td>{esc(pub_at[:10])}</td><td>{esc(title)}</td><td>{link}</td>"
                         f"<td class=num>{esc(v)}</td><td class=num>{esc(l)}</td><td class=num>{esc(cm)}</td>"
                         f"<td class=num>{esc(sh)}</td><td class=num>{un or ''}</td></tr>")
        parts.append("</table>")
    parts.append(f"<h2>💬 Комменты без ответа ({len(unans)})</h2>")
    if unans:
        parts.append("<table><tr><th>автор</th><th>коммент</th><th>когда</th><th>под чем</th></tr>")
        for a, t, ts, title, url in unans:
            parts.append(f"<tr class=warn><td>{esc(a)}</td><td>{esc((t or '')[:200])}</td><td>{esc(ts[:16])}</td>"
                         f"<td><a href='{esc(url)}' target=_blank>{esc(title[:60])}</a></td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>пусто (или комменты ещё не собраны)</p>")
    parts.append("<h2>🏆 Топ-комментаторы</h2>")
    if tops:
        parts.append("<table><tr><th>человек</th><th class=num>комментов</th></tr>")
        for a, n in tops:
            parts.append(f"<tr><td>{esc(a)}</td><td class=num>{n}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>комменты ещё не собраны</p>")
    parts.append("</body></html>")
    os.makedirs(os.path.dirname(DASH), exist_ok=True)
    open(DASH, "w", encoding="utf-8").write("".join(parts))
    print("dashboard ->", DASH)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init"); sub.add_parser("status"); sub.add_parser("dashboard")
    sub.add_parser("import-ledger"); sub.add_parser("import-fb"); sub.add_parser("import-tracker")
    sub.add_parser("unanswered")
    g = sub.add_parser("snapshot-github"); g.add_argument("--org", default="Palo-Alto-AI-Research-Lab")
    t = sub.add_parser("ingest-tg"); t.add_argument("--in", dest="inp", required=True)
    fbg = sub.add_parser("ingest-fb-graph"); fbg.add_argument("--in", dest="inp", required=True)
    a = sub.add_parser("add")
    for f in ("platform", "url", "title"):
        a.add_argument("--" + f, required=(f == "platform"), default="")
    a.add_argument("--date", default=""); a.add_argument("--author", default="anton")
    a.add_argument("--story", default="")
    s = sub.add_parser("snapshot"); s.add_argument("--url", required=True)
    for f in ("views", "likes", "comments", "shares"):
        s.add_argument("--" + f, type=int, default=None)
    cmt = sub.add_parser("comment")
    cmt.add_argument("--url", required=True); cmt.add_argument("--cid", required=True)
    cmt.add_argument("--author", default=""); cmt.add_argument("--author-id", default="")
    cmt.add_argument("--text", default=""); cmt.add_argument("--date", default="")
    cmt.add_argument("--replied", action="store_true"); cmt.add_argument("--ours", action="store_true")
    mr = sub.add_parser("mark-replied"); mr.add_argument("--cid", required=True)
    tc = sub.add_parser("top-commenters"); tc.add_argument("--n", type=int, default=15)
    args = ap.parse_args()
    c = db()
    if args.cmd == "init":
        print("ok:", DB)
    elif args.cmd == "import-ledger":
        print("новых из pub_ledger:", import_ledger(c))
    elif args.cmd == "import-fb":
        print("новых из fb_teaser_ledger:", import_fb(c))
    elif args.cmd == "import-tracker":
        print("новых из dist-tracker:", import_tracker(c))
    elif args.cmd == "snapshot-github":
        print("репо снапшотнуто:", snapshot_github(c, args.org))
    elif args.cmd == "ingest-tg":
        print("tg-постов принято:", ingest_tg(c, args.inp))
    elif args.cmd == "ingest-fb-graph":
        if not os.path.exists(args.inp):
            print("нет файла:", args.inp); sys.exit(4)
        np_, ns_, nc_ = ingest_fb_graph(c, args.inp)
        print(f"fb-graph: новых постов {np_} · снапшотов {ns_} · новых комментов {nc_}")
    elif args.cmd == "add":
        pid, new = upsert_pub(c, args.platform, args.url, args.title, args.story,
                              args.author, args.date, "manual")
        print(("added" if new else "exists"), "pub_id:", pid)
    elif args.cmd == "snapshot":
        row = c.execute("SELECT id FROM publications WHERE url=?", (args.url,)).fetchone()
        if not row:
            print("нет публикации с таким url; сперва add"); sys.exit(2)
        add_snapshot(c, row[0], args.views, args.likes, args.comments, args.shares)
        print("ok")
    elif args.cmd == "comment":
        row = c.execute("SELECT id,platform FROM publications WHERE url=?", (args.url,)).fetchone()
        if not row:
            print("нет публикации с таким url; сперва add"); sys.exit(2)
        c.execute("""INSERT OR IGNORE INTO comments(pub_id,platform,comment_id,author,author_id,text,ts,is_ours,replied,replied_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (row[0], row[1], args.cid, args.author, args.author_id, args.text,
                   args.date, int(args.ours), int(args.replied), now() if args.replied else ""))
        print("ok")
    elif args.cmd == "mark-replied":
        c.execute("UPDATE comments SET replied=1, replied_at=? WHERE comment_id=?", (now(), args.cid))
        print("ok")
    elif args.cmd == "unanswered":
        for a, t, ts, title in c.execute("""SELECT cm.author,cm.text,cm.ts,p.title FROM comments cm
                JOIN publications p ON p.id=cm.pub_id WHERE cm.replied=0 AND cm.is_ours=0 ORDER BY cm.ts"""):
            print(f"[{ts[:16]}] {a}: {(t or '')[:120]}  <- {title[:50]}")
    elif args.cmd == "top-commenters":
        for a, n in c.execute("SELECT author,COUNT(*) FROM comments WHERE is_ours=0 AND author!='' GROUP BY author ORDER BY 2 DESC LIMIT ?", (args.n,)):
            print(f"{n:4d}  {a}")
    elif args.cmd == "status":
        status(c)
    elif args.cmd == "dashboard":
        dashboard(c)
    c.commit(); c.close()

if __name__ == "__main__":
    main()
