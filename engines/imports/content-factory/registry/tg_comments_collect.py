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
r"""tg_comments_collect.py - комменты к нашим TG-постам -> pubmetrics.db (таблица comments).

Для каждой публикации tg_* из pubmetrics.db (url = t.me/<slug>/<msg_id>) тянет тред
ответов через MTProto (messages.GetReplies): работает и для мегагрупп (@ClawRus,
@ClawEng - реплаи прямо в группе), и для каналов с discussion-группой (@openclaw_lab,
@PaloAltoAi - комменты в привязанном чате). Каналы без discussion (@PaloAltoAiRu)
дают пусто - это норма, комментов там физически нет.

Правила:
  is_ours  = sender_id в OUR_IDS (наши аккаунты) или пост от имени самого канала
  replied  = после чужого коммента в том же треде есть НАШЕ сообщение новее (id больше)
Идемпотентно: INSERT OR IGNORE по (platform, comment_id); replied только повышаем.

Сессия = та же общая @work_acct_a Telethon-рельса, что bus_ping/tg_bus_read (общий лок ->
никогда AUTH_KEY_DUPLICATED).

USAGE:
  python tg_comments_collect.py            # собрать всё
  python tg_comments_collect.py --dry-run  # показать, ничего не писать
  python tg_comments_collect.py --platform tg_clawrus   # одна площадка
Exit: 0 ok | 3 rail busy/absent
"""
import os, io, sys, re, json, sqlite3, argparse, time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "pubmetrics.db")
ENV = os.environ.get("BUS_PING_ENV", r"%IMPORTS%\dialogs\.env")
LOCK = os.path.join(os.path.dirname(ENV), "_refresh_work_acct_a.lock")

# наши аккаунты (комменты от них = is_ours): work_acct_b, work_acct_a, personal_acct; corp_acct резолвим на лету
OUR_IDS = {265315838, 226258979, 5966672828}
OUR_USERNAMES = ["corp_acct"]  # id узнаём через get_entity при старте

# slug -> где живут комменты: сам чат (мегагруппа) или канал (GetReplies сам идёт в linked chat)
TG_URL = re.compile(r"https://t\.me/([A-Za-z0-9_]+)/(\d+)")


def _pid_alive(pid):
    # cross-platform stale-lock check; `tasklist ... 2>NUL` on Linux/macOS
    # created a literal NUL file in cwd and treated every lock as stale
    if pid <= 0:
        return False
    if os.name == "nt":
        return str(pid) in os.popen('tasklist /FI "PID eq %d" /NH 2>NUL' % pid).read()
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def load_env(path):
    d = {}
    if os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def acquire_lock():
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip())
        except Exception:
            pid = -1
        alive = _pid_alive(pid)
        if alive:
            return False
    try:
        io.open(LOCK, "w").write(str(os.getpid()))
        return True
    except Exception:
        return False


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--platform", default="")
    ap.add_argument("--sleep", type=float, default=0.5)
    a = ap.parse_args()

    env = load_env(ENV)
    local = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                         "claude-tgbus", "session.env")
    env.update({k: v for k, v in load_env(local).items() if v})
    if not all(env.get(k) for k in ("REFRESH_API_ID", "REFRESH_API_HASH", "REFRESH_SESSION_STRING")):
        print("SKIP: нет REFRESH_* сессии в", ENV); sys.exit(3)

    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    # GetReplies отдаёт полный профиль отправителя - сохраняем @username сразу.
    # Иначе за ним потом приходится идти в get_full_user по голому id, а он виснет.
    if "author_username" not in [r[1] for r in c.execute("PRAGMA table_info(comments)")]:
        c.execute("ALTER TABLE comments ADD COLUMN author_username TEXT DEFAULT ''")
        c.commit()
    q = "SELECT id, platform, url FROM publications WHERE url LIKE 'https://t.me/%/%'"
    if a.platform:
        q += " AND platform=?"
        pubs = c.execute(q, (a.platform,)).fetchall()
    else:
        pubs = c.execute(q).fetchall()
    targets = []
    for pid, plat, url in pubs:
        m = TG_URL.match(url)
        if m:
            targets.append((pid, plat, m.group(1), int(m.group(2)), url))
    print(f"публикаций с t.me-ссылкой: {len(targets)}")

    if not acquire_lock():
        print("SKIP: @work_acct_a сессия занята (лок) - повтори позже"); sys.exit(3)

    stats = {"threads": 0, "empty": 0, "comments_new": 0, "ours": 0, "replied_upd": 0, "errors": 0}
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.functions.messages import GetRepliesRequest

        async def _go():
            client = TelegramClient(StringSession(env["REFRESH_SESSION_STRING"]),
                                    int(env["REFRESH_API_ID"]), env["REFRESH_API_HASH"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect(); print("ERR: session not authorized"); return
            ours = set(OUR_IDS)
            for un in OUR_USERNAMES:
                try:
                    e = await client.get_entity(un)
                    ours.add(e.id)
                except Exception:
                    pass
            ents = {}   # slug -> entity
            for pid, plat, slug, mid, url in targets:
                if slug not in ents:
                    try:
                        ents[slug] = await client.get_entity(slug)
                    except Exception as ex:
                        print(f"ERR entity {slug}: {ex}"); ents[slug] = None
                ent = ents[slug]
                if ent is None:
                    stats["errors"] += 1; continue
                try:
                    r = await client(GetRepliesRequest(peer=ent, msg_id=mid, offset_id=0,
                                                       offset_date=None, add_offset=0, limit=100,
                                                       max_id=0, min_id=0, hash=0))
                except Exception as ex:
                    name = type(ex).__name__
                    # MsgIdInvalid = нет треда; PeerIdInvalid = пост сам реплай (не корень треда)
                    if name in ("MsgIdInvalidError", "PeerIdInvalidError"):
                        stats["empty"] += 1
                    else:
                        print(f"ERR replies {slug}/{mid}: {name}: {ex}"); stats["errors"] += 1
                    await asyncio.sleep(a.sleep); continue
                msgs = [m for m in r.messages if getattr(m, "message", None) is not None]
                if not msgs:
                    stats["empty"] += 1
                    await asyncio.sleep(a.sleep); continue
                stats["threads"] += 1
                msgs.sort(key=lambda m: m.id)
                users = {u.id: u for u in getattr(r, "users", [])}
                # комменты к посту КАНАЛА живут в discussion-группе: slug для ссылки =
                # username чата, где реально лежит сообщение (иначе t.me-ссылка битая)
                chat_un = {ch.id: getattr(ch, "username", None) for ch in getattr(r, "chats", [])}
                def live_slug(m):
                    chid = getattr(getattr(m, "peer_id", None), "channel_id", None)
                    return chat_un.get(chid) or slug

                def sender_of(m):
                    sid = None
                    if m.from_id is not None:
                        sid = getattr(m.from_id, "user_id", None) or getattr(m.from_id, "channel_id", None)
                    return sid

                def uname_of(sid):
                    u = users.get(sid)
                    return (getattr(u, "username", None) or "") if u is not None else ""

                def name_of(sid, m):
                    u = users.get(sid)
                    if u is not None:
                        nm = " ".join(x for x in [getattr(u, "first_name", None),
                                                  getattr(u, "last_name", None)] if x)
                        return nm or (getattr(u, "username", None) or str(sid))
                    if getattr(m, "post_author", None):
                        return m.post_author
                    return str(sid or "channel")

                our_msg_ids = [m.id for m in msgs
                               if (sender_of(m) in ours) or
                                  (m.from_id is not None and getattr(m.from_id, "channel_id", None))]
                for m in msgs:
                    sid = sender_of(m)
                    is_ours = 1 if ((sid in ours) or
                                    (m.from_id is not None and getattr(m.from_id, "channel_id", None))) else 0
                    replied = 0
                    if not is_ours:
                        replied = 1 if any(oid > m.id for oid in our_msg_ids) else 0
                    cid = f"{live_slug(m)}/{m.id}"
                    txt = (m.message or "")[:1000]
                    ts = m.date.strftime("%Y-%m-%dT%H:%M") if m.date else ""
                    if a.dry_run:
                        flag = "OURS" if is_ours else ("OK" if replied else "UNANSWERED")
                        print(f"  [{plat} {slug}/{mid}] {flag} {name_of(sid, m)}: {txt[:80]!r}")
                        continue
                    uname = uname_of(sid)
                    cur = c.execute("""INSERT OR IGNORE INTO comments
                        (pub_id,platform,comment_id,author,author_id,text,ts,is_ours,replied,replied_at,author_username)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid, plat, cid, name_of(sid, m), str(sid or ""), txt, ts,
                         is_ours, replied, ts if replied else "", uname))
                    if uname:
                        c.execute("""UPDATE comments SET author_username=?
                                     WHERE author_id=? AND COALESCE(author_username,'')=''""",
                                  (uname, str(sid or "")))
                    if cur.rowcount:
                        stats["comments_new"] += 1
                        stats["ours"] += is_ours
                    elif replied:
                        u = c.execute("""UPDATE comments SET replied=1,
                                         replied_at=CASE WHEN replied_at='' THEN ? ELSE replied_at END
                                         WHERE platform=? AND comment_id=? AND replied=0""",
                                      (ts, plat, cid))
                        stats["replied_upd"] += u.rowcount
                await asyncio.sleep(a.sleep)
            await client.disconnect()

        asyncio.get_event_loop().run_until_complete(_go())
    finally:
        release_lock()
        if not a.dry_run:
            c.commit()
        c.close()
    print("итог:", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
