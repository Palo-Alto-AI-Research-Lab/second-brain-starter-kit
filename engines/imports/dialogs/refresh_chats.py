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
"""refresh_chats.py -- keep chats.db fresh from a DEDICATED read session.

Appends/updates LIVE dialogs of ONE of Anton's accounts into chats.db so newly
created/renamed chats appear without waiting for the next CRM export. Uses the
PROVEN pattern from refresh_dialogs.py: dedicated session (reused API_ID/HASH, own
authkey) + PID lock => never AUTH_KEY_DUPLICATED with the MCP; iter_dialogs() with
NO limit => all pages (not the list_chats 5000 cap).

Updates two tables (idempotent, this account only -- never nukes the CRM backbone):
  * chats         : upsert id/name/username/link/type/is_chat, source='live:<acct>'
                    (INSERT-or-UPDATE: keep CRM row's richer fields, refresh name/user)
  * chat_accounts : (chat_id, account_username, account_telegram_id) for this account

Config: dialogs/.env -> per account a trio
  <ACC>_API_ID / <ACC>_API_HASH / <ACC>_SESSION   (ACC = WORK_ACCT_A | CORP_ACCT)
Run: PYTHONUTF8=1 python refresh_chats.py <WORK_ACCT_A|CORP_ACCT>
ASCII-only stdout.
"""
import os, io, sys, time, sqlite3, asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
ENV = os.path.join(HERE, ".env")
CHAT_TYPES = ("group", "super_group", "channel")


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
                k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d


def lock_path(acc):
    return os.path.join(HERE, "_refresh_%s.lock" % acc.lower())


def acquire_lock(acc):
    LOCK = lock_path(acc)
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip())
        except Exception:
            pid = -1
        alive = _pid_alive(pid)
        if alive:
            print("ANOTHER REFRESH RUNNING (pid=%s) -- abort" % pid); return False
    io.open(LOCK, "w").write(str(os.getpid()))
    return True


def release_lock(acc):
    try:
        os.remove(lock_path(acc))
    except OSError:
        pass


def dtype(entity):
    from telethon.tl.types import User, Chat, Channel
    if isinstance(entity, User):
        return "user"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "super_group" if getattr(entity, "megagroup", False) else "channel"
    return "other"


async def run(acc):
    # FAIL-FAST: the CRM backbone table must exist. Without this guard the script crawls
    # ALL dialogs (~1h/account) and only THEN crashes on the first write (seen 2026-06-25,
    # empty chats.db after migration). Check first, abort in 1s with a clear message.
    if not os.path.exists(DB) or os.path.getsize(DB) == 0:
        print("chats.db missing or 0 bytes -- aborting BEFORE crawl. Rebuild chats.db first."); return
    _c = sqlite3.connect(DB)
    _has = _c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chats'").fetchone()
    _c.close()
    if not _has:
        print("chats.db has no 'chats' table -- aborting BEFORE crawl. Rebuild chats.db first."); return
    env = load_env(ENV)
    keys = ("%s_API_ID" % acc, "%s_API_HASH" % acc, "%s_SESSION" % acc)
    # back-compat: the original tg_login_step1/2 wrote REFRESH_* for @work_acct_a
    if acc == "WORK_ACCT_A" and not all(env.get(k) for k in keys):
        leg = ("REFRESH_API_ID", "REFRESH_API_HASH", "REFRESH_SESSION_STRING")
        if all(env.get(k) for k in leg):
            keys = leg
    if not all(env.get(k) for k in keys):
        print("NO DEDICATED SESSION for %s -- run tg_login for it first. Missing: %s"
              % (acc, ", ".join(k for k in keys if not env.get(k))))
        return
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(env[keys[2]]), int(env[keys[0]]), env[keys[1]],
                            catch_up=True, sequential_updates=True)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION NOT AUTHORIZED for %s -- re-run login" % acc); await client.disconnect(); return
    me = await client.get_me()
    acct_user = me.username or str(me.id)
    print("connected as @%s (id=%s)" % (acct_user, me.id)); sys.stdout.flush()

    rows, n, t0 = [], 0, time.time()
    try:
        async for d in client.iter_dialogs(ignore_migrated=True):
            ent = d.entity
            if getattr(ent, "is_self", False):
                continue
            cid = utils.get_peer_id(ent)
            typ = dtype(ent)
            uname = getattr(ent, "username", None) or ""
            rows.append((cid, utils.get_display_name(ent) or "", uname, typ))
            n += 1
            if n % 1000 == 0:
                print("  %d (%.0fs)" % (n, time.time() - t0)); sys.stdout.flush()
    except Exception as e:
        print("PARTIAL: %d before error: %s" % (n, str(e)[:140]))
    client.session.save()
    await client.disconnect()
    if not rows:
        print("NO ROWS -- aborting (kept chats.db)"); return

    con = sqlite3.connect(DB)
    cur = con.cursor()
    new_chats = upd = acc_rows = 0
    for cid, name, uname, typ in rows:
        is_chat = 1 if typ in CHAT_TYPES else 0
        link = ("https://t.me/%s" % uname) if uname else ""
        ex = cur.execute("SELECT 1 FROM chats WHERE telegram_id=?", (cid,)).fetchone()
        if ex:
            # refresh volatile fields; keep CRM-only columns intact
            cur.execute("UPDATE chats SET name=?, username=?, type=?, is_chat=? WHERE telegram_id=?",
                        (name, uname, typ, is_chat, cid))
            if uname:
                cur.execute("UPDATE chats SET link=? WHERE telegram_id=? AND (link='' OR link IS NULL)",
                            (link, cid))
            upd += 1
        else:
            cur.execute("""INSERT INTO chats(telegram_id,name,username,link,type,is_chat,
                           members_count,last_message_date,tags,source)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (cid, name, uname, link, typ, is_chat, None, "", "", "live:%s" % acct_user))
            new_chats += 1
        if is_chat:
            cur.execute("INSERT OR IGNORE INTO chat_accounts(chat_id,account_username,account_telegram_id) VALUES(?,?,?)",
                        (cid, acct_user, me.id))
            acc_rows += 1
    con.commit()
    con.close()
    print("CHATS REFRESH OK (%s) -> chats.db" % acct_user)
    print("  pulled=%d | new chats=%d | updated=%d | chat_accounts touched=%d | %.0fs"
          % (len(rows), new_chats, upd, acc_rows, time.time() - t0))


def main():
    if len(sys.argv) < 2:
        print("usage: python refresh_chats.py <WORK_ACCT_A|CORP_ACCT>"); return
    acc = sys.argv[1].upper()
    if not acquire_lock(acc):
        return
    try:
        asyncio.run(run(acc))
    finally:
        release_lock(acc)


if __name__ == "__main__":
    main()
