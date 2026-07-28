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
r"""intention_mine.py - the "intention lane" of the content-factory.

WHAT (Anton's rule 2026-07-02): every pain / question / "how do I X" the user
raises across the DAY's sessions is an INTENTION. Mine them from ALL sessions
(all machines) like fb_diary_collect does, drop them into a never-losing POOL
("копилка намерений" = intentions.db), then the LLM judge/writer turns 2-3+ per
day into detailed build-in-public "ask" posts (X / Telegram / Indie Hackers /
Ask HN), draft-first. See decision-intention-lane-content-factory-2026-07-02.

This file = the DETERMINISTIC half (0 tokens):
  mine [DAY]   : scan the day's sessions -> candidate digest md + ensure DB.
  add ...      : the judge inserts a finished intention (dedup by content hash).
  list ...     : show the pool.
  pending      : count intentions still needing a post.
  mark ...     : update status / record a channel it was posted to.

The JUDGE+WRITER (cluster candidates -> distinct intentions with journey+ask,
write the posts) is the in-session LLM step (Opus for author voice) or the
/intention skill - NOT here. Prints are ASCII-only (Windows cp1252 safe).
"""
import os, sys, io, json, re, hashlib, sqlite3, argparse, datetime, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
IMPORTS = os.path.dirname(os.path.dirname(HERE))          # %IMPORTS%
sys.path.insert(0, IMPORTS)
import vault_sessions                                     # shared corpus reader
import fb_diary_collect as fdc                            # reuse surviving primitives (noise/extract/date)

# Local same-day session fill (root-cause fix 2026-07-15): fb_diary_collect was
# refactored into a script-only form and dropped its old reusable helper
# `local_sessions_for_day` + `THIS_MACHINE`, which this miner imported -> mine
# crashed with AttributeError. We rebuild the tiny grouping loop here on top of
# fdc's SURVIVING primitives (extract_text / line_local_date / is_noise /
# PROJECTS / FILE_WINDOW_HOURS), so the intention lane no longer depends on
# fb_diary's private internals. vault_sessions is the primary (nightly) source;
# this fills TODAY's live sessions that the archive pool hasn't ingested yet.
THIS_MACHINE = vault_sessions.this_machine_label()
_AUTORUN_SENTINELS = ("FACEBOOK_DIARY_AUTORUN", "INTENTION_LANE_AUTORUN", "<scheduled-task")


def local_sessions_for_day(day):
    """sid -> [(role,text)] for TODAY's local ~/.claude/projects sessions.

    Mirrors fb_diary_collect.main()'s reader but returns per-session turns and
    excludes automated cron/scheduled-task self-runs (incl. this miner's own).
    """
    out = {}
    now = datetime.datetime.now().timestamp()
    files = glob.glob(os.path.join(fdc.PROJECTS, "**", "*.jsonl"), recursive=True)
    for f in sorted(files, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0):
        if os.sep + "subagents" + os.sep in f:            # skip verbose subagent grind
            continue
        try:
            if now - os.path.getmtime(f) > fdc.FILE_WINDOW_HOURS * 3600:
                continue
        except OSError:
            continue
        turns, skip = [], False
        try:
            with io.open(f, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    d = fdc.line_local_date(o)
                    if d is not None and d != day:
                        continue
                    msg = o.get("message") or {}
                    typ = o.get("type")
                    role = msg.get("role") or (typ if typ in ("user", "assistant") else None)
                    if role not in ("user", "assistant"):
                        continue
                    for s in fdc.extract_text(msg.get("content")):
                        if any(mark in s for mark in _AUTORUN_SENTINELS):
                            skip = True                    # automated run, not a real chat
                        if fdc.is_noise(s):
                            continue
                        turns.append((role, s))
        except OSError:
            continue
        if skip or not turns:
            continue
        out[os.path.basename(f)] = turns
    return out

DB = os.path.join(HERE, "intentions.db")
CANDDIR = os.path.join(HERE, "candidates")

# --- intention markers (high-recall prefilter; the LLM judge removes noise) ----
MARKERS = [
    # questions / how-to
    "как ", "как,", "как?", "как-то", "каким образом", "почему", "зачем",
    "что если", "как лучше", "как сделать", "как нам", "как мне", "как это",
    "где найти", "где взять", "чем лучше", "стоит ли", "можно ли", "надо ли",
    # need / want / seek
    "нужен", "нужна", "нужно", "надо ", "надо,", "хочу ", "хочу,", "хотим",
    "хотелось", "ищу ", "ищем", "мне нужен", "нам нужен", "давай ", "давайте",
    # stuck / pain
    "проблема", "не могу", "не знаю", "не получается", "не понимаю", "затык",
    "уперся", "упёрся", "уперлись", "сложно", "боль", "мешает", "не работает",
    "фейл", "факап", "тупик", "затрудня", "не хватает",
    # realized / changed mind
    "понял", "поняла", "осознал", "оказалось", "зря ", "ошиб", "передумал",
    "пришел к", "пришёл к",
    # explicit
    "intention", "намерен", "intent",
]
SIGNALS = {"+", "?", "qqq", "no", "да", "ок", "ok", "нет", "плюс", "."}  # not intentions
MIN_LEN, MAX_STORE = 20, 700


def ensure_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS intentions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        title TEXT,
        pain TEXT,
        journey TEXT,
        ask TEXT,
        status TEXT DEFAULT 'new',
        channels TEXT DEFAULT '[]',
        source_sessions TEXT DEFAULT '[]',
        chash TEXT UNIQUE,
        created_at TEXT,
        updated_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS responders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intention_id INTEGER,
        who TEXT,
        channel TEXT,
        note TEXT,
        promoted_to_crm INTEGER DEFAULT 0,
        created_at TEXT)""")
    con.commit()
    return con


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def is_intention(text):
    low = _norm(text)
    if len(low) < MIN_LEN or low in SIGNALS:
        return False
    # skip pure paths / tool dumps / injected skill headers
    if low.startswith(("c:\\", "e:\\", "http", "```", "<", "/")):
        return False
    if "base directory for this skill" in low[:80]:
        return False
    return any(m in low for m in MARKERS)


def excerpt(s):
    s = re.sub(r"\s+", " ", s.strip())
    if len(s) <= MAX_STORE:
        return s
    return s[: MAX_STORE * 2 // 3] + " [...] " + s[-MAX_STORE // 3:]


def day_sessions(day):
    """sid -> (machine, [(role,text)]) for `day`, vault corpus + this-machine fill."""
    by_sid = {}
    for rec in vault_sessions.recent_sessions(day=day):
        if vault_sessions.is_cron_session(rec) or not rec["turns"]:
            continue
        sid = rec["session_id"] or os.path.basename(rec["path"])
        by_sid[sid] = (rec["machine"] or "?", rec["turns"])
    for sid, turns in local_sessions_for_day(day).items():
        if sid not in by_sid:
            by_sid[sid] = (THIS_MACHINE, turns)
    return by_sid


def cmd_mine(args):
    day = args.day or datetime.date.today().strftime("%Y-%m-%d")
    ensure_db().close()
    if not os.path.isdir(CANDDIR):
        os.makedirs(CANDDIR)
    by_sid = day_sessions(day)
    seen, blocks, n_cand, n_sess = set(), [], 0, 0
    for sid, (machine, turns) in by_sid.items():
        hits = []
        for role, s in turns:
            if role != "user" or fdc.is_noise(s) or not is_intention(s):
                continue
            key = _norm(s)[:160]
            if key in seen:
                continue
            seen.add(key)
            hits.append(excerpt(s))
        if hits:
            n_sess += 1
            n_cand += len(hits)
            head = "### session %s  [%s]" % (sid[:8], machine)
            blocks.append(head + "\n" + "\n".join("- " + h for h in hits))
    out = os.path.join(CANDDIR, "cand-%s.md" % day)
    body = ("# Intention candidates %s\n\n" % day) + "\n\n".join(blocks) + "\n"
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    print("DAY", day)
    print("SESSIONS_WITH_HITS", n_sess)
    print("CANDIDATES", n_cand)
    print("OUT", out)


def cmd_add(args):
    con = ensure_db()
    chash = hashlib.sha1(_norm((args.title or "") + "|" + (args.pain or "")).encode("utf-8")).hexdigest()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sessions = json.dumps([x for x in (args.sessions or "").split(",") if x], ensure_ascii=False)
    try:
        cur = con.execute(
            "INSERT INTO intentions(day,title,pain,journey,ask,status,source_sessions,chash,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (args.day or datetime.date.today().strftime("%Y-%m-%d"), args.title, args.pain,
             args.journey, args.ask, "new", sessions, chash, now, now))
        con.commit()
        print("ADDED id=%d" % cur.lastrowid)
    except sqlite3.IntegrityError:
        row = con.execute("SELECT id FROM intentions WHERE chash=?", (chash,)).fetchone()
        print("DUP existing id=%s (skipped)" % (row[0] if row else "?"))
    con.close()


def cmd_list(args):
    con = ensure_db()
    q, p = "SELECT id,day,status,title FROM intentions", []
    where = []
    if args.status:
        where.append("status=?"); p.append(args.status)
    if args.day:
        where.append("day=?"); p.append(args.day)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC LIMIT %d" % (args.limit or 50)
    rows = con.execute(q, p).fetchall()
    for r in rows:
        title = (r[3] or "")[:70].encode("ascii", "replace").decode("ascii")
        print("#%-4d %s  [%-8s] %s" % (r[0], r[1], r[2], title))
    print("COUNT", len(rows))
    con.close()


def cmd_pending(args):
    con = ensure_db()
    n = con.execute("SELECT COUNT(*) FROM intentions WHERE status IN('new','drafted')").fetchone()[0]
    print("PENDING", n)
    con.close()


def cmd_mark(args):
    con = ensure_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    row = con.execute("SELECT channels FROM intentions WHERE id=?", (args.id,)).fetchone()
    if not row:
        print("NOT_FOUND id=%s" % args.id); con.close(); return
    chans = json.loads(row[0] or "[]")
    if args.channel and args.channel not in chans:
        chans.append(args.channel)
    con.execute("UPDATE intentions SET status=COALESCE(?,status),channels=?,updated_at=? WHERE id=?",
                (args.status, json.dumps(chans, ensure_ascii=False), now, args.id))
    con.commit()
    print("OK id=%s status=%s channels=%s" % (args.id, args.status, ",".join(chans)))
    con.close()


def cmd_respond(args):
    """Record someone who replied to an intention post (ALPHA). Isolated table;
    promotion into the production leads.db is a separate reviewed step."""
    con = ensure_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur = con.execute(
        "INSERT INTO responders(intention_id,who,channel,note,created_at) VALUES(?,?,?,?,?)",
        (args.id, args.who, args.channel, args.note, now))
    con.commit()
    who = (args.who or "")[:40].encode("ascii", "replace").decode("ascii")
    print("RESPONDER id=%d -> intention #%s  who=%s  (promote to CRM = reviewed step)"
          % (cur.lastrowid, args.id, who))
    con.close()


def cmd_responders(args):
    con = ensure_db()
    q = "SELECT id,intention_id,channel,who,promoted_to_crm FROM responders"
    if args.pending:
        q += " WHERE promoted_to_crm=0"
    q += " ORDER BY id DESC LIMIT %d" % (args.limit or 50)
    rows = con.execute(q).fetchall()
    for r in rows:
        who = (r[3] or "")[:50].encode("ascii", "replace").decode("ascii")
        print("#%-3d intent#%s [%-10s] crm=%d  %s" % (r[0], r[1], r[2], r[4], who))
    print("COUNT", len(rows))
    con.close()


ADAPTER = os.path.join(os.path.dirname(HERE), "episode_adapter.py")
EPI = os.path.join(os.path.dirname(HERE), "episodes")


def cmd_episode(args):
    """Bridge: promote a pooled intention into a reality-show EPISODE (longread +
    dev-log on GitHub, per tier contract). Includes phase-2 (Хабр as a longread
    channel). The intention's context becomes the episode's writer seed."""
    con = ensure_db()
    row = con.execute("SELECT title,pain,journey,ask,channels FROM intentions WHERE id=?",
                      (args.id,)).fetchone()
    if not row:
        print("NOT_FOUND id=%s" % args.id); con.close(); return
    title, pain, journey, ask, chans = row
    day = datetime.date.today().strftime("%Y-%m-%d")
    slug = "intention-%d-%s" % (args.id, day)             # ascii-safe, unique
    cmd = [sys.executable, ADAPTER, "new", "--slug", slug,
           "--title", title or ("intention %d" % args.id),
           "--source", "intention#%d" % args.id]
    if not args.no_phase2:
        cmd.append("--with-phase2")
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        print("EPISODE_BRIDGE_FAILED (slug may already exist)"); con.close(); return
    # writer seed = the intention's context, dropped into the bundle
    seed = os.path.join(EPI, slug, "intention-seed.md")
    with io.open(seed, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Intention seed for episode %s\n\n" % slug)
        fh.write("**Title:** %s\n\n**Pain:** %s\n\n**Journey (how Anton got here):** %s\n\n**Ask:** %s\n"
                 % (title or "", pain or "", journey or "", ask or ""))
    lst = json.loads(chans or "[]")
    tag = "episode:%s" % slug
    if tag not in lst:
        lst.append(tag)
    con.execute("UPDATE intentions SET status='episode',channels=?,updated_at=? WHERE id=?",
                (json.dumps(lst, ensure_ascii=False), datetime.datetime.now().isoformat(timespec="seconds"), args.id))
    con.commit(); con.close()
    print("SEED", seed)
    print("NEXT: write each tier draft (voice=Opus) in episodes/%s/, then "
          "`python episode_adapter.py check --slug %s`" % (slug, slug))


def main():
    ap = argparse.ArgumentParser(description="intention lane miner + pool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine"); m.add_argument("day", nargs="?"); m.set_defaults(f=cmd_mine)
    a = sub.add_parser("add")
    for opt in ("day", "title", "pain", "journey", "ask", "sessions"):
        a.add_argument("--" + opt)
    a.set_defaults(f=cmd_add)
    l = sub.add_parser("list"); l.add_argument("--status"); l.add_argument("--day"); l.add_argument("--limit", type=int); l.set_defaults(f=cmd_list)
    sub.add_parser("pending").set_defaults(f=cmd_pending)
    mk = sub.add_parser("mark"); mk.add_argument("--id", type=int, required=True); mk.add_argument("--status"); mk.add_argument("--channel"); mk.set_defaults(f=cmd_mark)
    rp = sub.add_parser("respond"); rp.add_argument("--id", type=int, required=True); rp.add_argument("--who", required=True); rp.add_argument("--channel"); rp.add_argument("--note"); rp.set_defaults(f=cmd_respond)
    rs = sub.add_parser("responders"); rs.add_argument("--pending", action="store_true"); rs.add_argument("--limit", type=int); rs.set_defaults(f=cmd_responders)
    ep = sub.add_parser("episode"); ep.add_argument("--id", type=int, required=True); ep.add_argument("--no-phase2", action="store_true"); ep.set_defaults(f=cmd_episode)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
