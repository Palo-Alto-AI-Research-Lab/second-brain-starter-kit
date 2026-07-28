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
"""bus_ping.py -- one-shot Telegram ping to Anton's Saved Messages.

Tiny, dependency-light notifier reused by the cross-machine PLAN-MODE robot
(robot_inbox_prompt.md). Sends `text` to Anton's own Saved Messages via the
dedicated @work_acct_a Telethon session. NEVER raises -- if the session env is not
on this machine (the laptop has it; other machines may not, since _imports does
NOT sync), it prints "PING SKIP" and exits 0 so the caller proceeds gracefully.

This is the SAME proven rail as cowork_loop.send_saved (shared @work_acct_a session,
shared lock so it never collides with refresh_chats / the Telegram MCP ->
never AUTH_KEY_DUPLICATED). Copied standalone (not imported) so it works even
where cowork_loop's E:\\_imports paths are absent.

Usage:
  python bus_ping.py "your message text"     -> send (Cyrillic OK, UTF-8)
  python bus_ping.py --check                 -> verify the rail WITHOUT sending
                                                (prints PING READY / PING SKIP, exit 0)

Env override: BUS_PING_ENV = path to a .env carrying REFRESH_API_ID /
REFRESH_API_HASH / REFRESH_SESSION_STRING. Default = %IMPORTS%\\dialogs\\.env
"""
import os, io, sys, json, time, argparse

# env resolution ladder (canon-proposal NAT1-Nina #61582f29, same as bus_group_post):
# BUS_PING_ENV -> machine.env's BUS_PING_ENV -> %LOCALAPPDATA%\claude-tgbus\session.env -> hub default E:\...
# machine.env rung (ANCHOR1 audit 2026-07-16 #ee1aa4bd): the hub hardcode made ping silently SKIP on
# nodes whose session lives elsewhere (ANCHOR1: ~/secrets/dialogs.env) and whose cron lacks the env
# var -- ~/.claude/machine.env already carries the right path per machine, so read it here.
def _menv_ping_env():
    p = os.path.join(os.path.expanduser("~"), ".claude", "machine.env")
    try:
        if os.path.exists(p):
            for _l in io.open(p, encoding="utf-8"):
                _l = _l.strip()
                if _l.startswith("BUS_PING_ENV=") and _l.split("=", 1)[1].strip():
                    return os.path.expandvars(os.path.expanduser(_l.split("=", 1)[1].strip()))
    except Exception:
        pass
    return None

_LOCAL = os.path.join(os.environ.get("LOCALAPPDATA", ""), "claude-tgbus", "session.env")
ENV = (os.environ.get("BUS_PING_ENV") or _menv_ping_env()
       or (_LOCAL if os.path.exists(_LOCAL) else r"%IMPORTS%\dialogs\.env"))
LOCK = os.path.join(os.path.dirname(ENV), "_refresh_work_acct_a.lock")  # shared w/ @work_acct_a session
SAVED = "me"   # Telethon alias for own Saved Messages
GROUP = int(os.environ.get("TG_BUS_GROUP", "-996940094"))   # machine-bus mirror group "03"
BUS_GROUP = GROUP  # compat alias: hub-side ack_watchdog.py imports bus_ping.BUS_GROUP (2026-07-03)

def _machine_tag():
    host = (os.environ.get("COMPUTERNAME") or "?").strip()
    return {"LAPTOP1": "laptop-HP17", "HUB1": "hub-PaloAlto"}.get(host, host)

# Windows console is cp1252 -> force UTF-8 so status lines print safely.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_env(path):
    d = {}
    if os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def rail_ready():
    env = load_env(ENV)
    return all(env.get(k) for k in ("REFRESH_API_ID", "REFRESH_API_HASH", "REFRESH_SESSION_STRING"))


def _pid_alive(pid):
    # cross-platform stale-lock check; `tasklist ... 2>NUL` on Linux/macOS
    # created a literal NUL file in cwd and treated every lock as stale
    if pid <= 0:
        return False
    if os.name == "nt":
        # utf-8 guard (canon-proposal NAT1-Nina #3637084a): os.popen on localized
        # Windows emits cp866 bytes that crash under PYTHONUTF8=1 -> subprocess+errors=replace
        import subprocess
        try:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=15).stdout or ""
        except Exception:
            return False
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(wait_s=0):
    """Take the shared @work_acct_a lock. `wait_s` > 0 = keep trying for that long.

    The lock is held for the duration of ONE send (a couple of seconds), so a caller that
    gives up instantly loses its message to a collision that would have cleared on its own.
    Loop callers can afford `wait_s=0` ("retry next cycle"); ONE-SHOT callers cannot -- for
    them there is no next cycle. Default stays 0 so existing callers are untouched."""
    deadline = time.time() + max(0, wait_s)
    while True:
        if os.path.exists(LOCK):
            try:
                pid = int(io.open(LOCK).read().strip())
            except Exception:
                pid = -1
            if _pid_alive(pid):
                if time.time() >= deadline:
                    return False
                time.sleep(1.5)
                continue
        try:
            io.open(LOCK, "w").write(str(os.getpid()))
            return True
        except Exception:
            if time.time() >= deadline:
                return False
            time.sleep(1.5)


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def send(text):
    """Return True on success. Never raises. Prints PING OK / PING SKIP / PING FAIL."""
    env = load_env(ENV)
    api_id = env.get("REFRESH_API_ID")
    api_hash = env.get("REFRESH_API_HASH")
    sess = env.get("REFRESH_SESSION_STRING")
    if not (api_id and api_hash and sess):
        print("PING SKIP: no REFRESH_* session in %s (rail not on this machine)" % ENV)
        return False
    if not acquire_lock():
        print("PING SKIP: @work_acct_a session busy (lock held) -- caller may retry next cycle")
        return False
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        async def _go():
            client = TelegramClient(StringSession(sess), int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise RuntimeError("session not authorized")
            await client.send_message(SAVED, text)
            await client.disconnect()

        asyncio.run(_go())
        print("PING OK")
        return True
    except Exception as e:
        print("PING FAIL: %s" % str(e)[:160])
        return False
    finally:
        release_lock()


def post(text):
    """Post a machine<->machine message to TG GROUP 03 (canonical mirror rail), tagged with
    this machine. Used by bus_send.py's dual-send. Returns True/False, never raises.
    Distinct from send() which targets own Saved Messages."""
    env = load_env(ENV)
    api_id = env.get("REFRESH_API_ID"); api_hash = env.get("REFRESH_API_HASH"); sess = env.get("REFRESH_SESSION_STRING")
    if not (api_id and api_hash and sess):
        print("PING SKIP: no REFRESH_* session in %s (rail not on this machine)" % ENV)
        return False
    if not acquire_lock():
        print("PING SKIP: @work_acct_a session busy (lock held) -- caller may retry next cycle")
        return False
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        tagged = "\U0001F916 [%s] %s" % (_machine_tag(), text)

        async def _go():
            client = TelegramClient(StringSession(sess), int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise RuntimeError("session not authorized")
            await client.send_message(GROUP, tagged)
            await client.disconnect()

        asyncio.run(_go())
        print("PING OK -> group 03")
        return True
    except Exception as e:
        print("PING FAIL: %s" % str(e)[:160])
        return False
    finally:
        release_lock()


SPOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_outbox_undelivered.jsonl")
POST_TO_LOCK_WAIT_S = int(os.environ.get("BUS_PING_LOCK_WAIT", "25"))


def spool_depth():
    """How many outbound messages this machine failed to deliver and still owes."""
    try:
        with io.open(SPOOL, encoding="utf-8") as fh:
            return sum(1 for l in fh if l.strip())
    except Exception:
        return 0


def _spool_add(chat_id, text, tag, reason):
    """Last rung: park an undelivered message on disk instead of dropping it.

    The spool IS the failure counter -- one artifact, not two: depth > 0 means this node owes
    somebody a message, and `--check` reports it."""
    try:
        with io.open(SPOOL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"chat_id": str(chat_id), "text": text, "tag": bool(tag),
                                 "reason": str(reason)[:200],
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                                ensure_ascii=False) + "\n")
    except Exception:
        pass


def _spool_drain(max_n=10):
    """Self-heal: a SUCCESSFUL send proves the rail is back, so flush what we owe -- no new
    cron, no watchdog to forget. Drains over the BOT rail (stdlib HTTP, no Telethon lock, so
    draining can never collide with the send that just succeeded).

    Deliberately at-least-once: if we deliver and then die before rewriting the file, the
    entry is retried later. A duplicate alert to Anton is strictly better than a lost one.

    Fully guarded: draining is a side-errand of a send that ALREADY succeeded, so it must not
    be able to raise into the caller and make a delivered message look failed."""
    try:
        _spool_drain_inner(max_n)
    except Exception as e:
        sys.stderr.write("PING SPOOL: drain skipped (%s)\n" % str(e)[:120])


def _spool_append(rows):
    """Put rows (back) on the spool. Append, never overwrite: a concurrent sender may have
    parked something new while we were draining."""
    if not rows:
        return
    with io.open(SPOOL, "a", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")


def _spool_reclaim_orphans():
    """A drainer that died mid-flight leaves its claim file behind. Give those messages back
    to the spool (the pid check is the same one the send-lock uses)."""
    d = os.path.dirname(SPOOL)
    base = os.path.basename(SPOOL) + ".draining-"
    try:
        names = [n for n in os.listdir(d) if n.startswith(base)]
    except Exception:
        return
    for n in names:
        try:
            pid = int(n[len(base):])
        except ValueError:
            continue
        if pid == os.getpid() or _pid_alive(pid):
            continue
        p = os.path.join(d, n)
        try:
            with io.open(p, encoding="utf-8") as fh:
                rows = [l for l in fh.read().splitlines() if l.strip()]
            _spool_append(rows)
            os.remove(p)
            print("PING SPOOL: reclaimed %d message(s) from a dead drainer (pid %d)" % (len(rows), pid))
        except Exception:
            pass


def _spool_drain_inner(max_n):
    _spool_reclaim_orphans()
    if not os.path.exists(SPOOL):
        return
    try:
        import tg_bot_send
    except Exception:
        return
    # ATOMIC CLAIM (Codex T3, 21.07): two drainers running at once (live session + robot) would
    # both read the same rows and deliver them twice. os.replace is atomic -- exactly one process
    # can win the rename, and it alone owns those rows. No lock file, nothing to go stale.
    claim = "%s.draining-%d" % (SPOOL, os.getpid())
    try:
        os.replace(SPOOL, claim)
    except Exception:
        return  # another drainer already took the file (or it vanished) -- nothing owed to us
    try:
        with io.open(claim, encoding="utf-8") as fh:
            rows = [l for l in fh.read().splitlines() if l.strip()]
    except Exception:
        return
    left, sent, bad = [], 0, 0
    for line in rows:
        if sent >= max_n:
            left.append(line)
            continue
        try:
            d = json.loads(line)
        except Exception:
            # torn/corrupt row: KEEP it. Dropping it would be the very silent loss this whole
            # ladder exists to prevent -- it stays visible in --check until a human looks.
            bad += 1
            left.append(line)
            continue
        try:
            ok = tg_bot_send.post_to(d.get("chat_id"), d.get("text") or "", tag=d.get("tag", True))
        except Exception:
            ok = False
        if ok:
            sent += 1
        else:
            left.append(line)
    # survivors first, claim removed second: a crash in between re-delivers, never loses
    _spool_append(left)
    try:
        os.remove(claim)
    except Exception:
        pass
    if sent or bad:
        print("PING SPOOL: delivered %d parked message(s), %d left%s"
              % (sent, len(left), (" (%d unparseable -- inspect %s)" % (bad, SPOOL)) if bad else ""))


def _post_to_bot(chat_id, text, tag):
    """Rung 2: the fleet bot (stdlib Bot API). No Telethon session, so no lock to lose."""
    try:
        import tg_bot_send
    except Exception as e:
        return False, "tg_bot_send unimportable: %s" % str(e)[:80]
    try:
        ok = bool(tg_bot_send.post_to(chat_id, text, tag=tag))
        # a bare "False" in the spool's reason field tells a 3am reader nothing; name the
        # usual cause so the fix ("add the bot to that chat") is obvious from the record
        return ok, "ok" if ok else "bot refused (not a member of that chat? token? see BOT FAIL above)"
    except Exception as e:
        return False, "bot raised: %s" % str(e)[:80]


def post_to(chat_id, text, tag=True):
    """Post `text` to an ARBITRARY chat id (e.g. 02 POLICE -6491142604, or an operator's
    personal id). Used by the F1-F4 silent-peer escalators (ack_watchdog second-reping, robot
    3-consecutive-fail), post_police(), and the secondop 04-mirror. Never raises.

    LADDER (2026-07-20, after a silent drop): user session -> fleet bot -> disk spool.
    Root it fixes: this function had NO fallback while its sibling post() got one via
    bus_send -- so a momentarily busy @work_acct_a lock silently ate one-shot messages, INCLUDING
    Tier-2 escalations to Anton in 02 POLICE. Caught because a Codex second-opinion exchange
    never reached chat 04 and nothing said a word. Canon: Telegram mirror is never optional,
    and a dead rail is a SIGNAL, not a reason to give up quietly."""
    # PULSE write-side tap: mirror 02-POLICE sends into a local log the pulse window tails, so the
    # pulse never has to PARSE Telegram (Anton 2026-07-05 "parsing TG is dumb, log it when you send").
    # Pure side-effect, runs BEFORE the send, wrapped so it can never affect delivery.
    try:
        if str(chat_id) == str(POLICE_GROUP):
            _pl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pulse_police.log")
            with io.open(_pl, "a", encoding="utf-8") as _pf:
                _pf.write((text or "").replace("\r", " ").replace("\n", " / ") + "\n")
    except Exception:
        pass
    env = load_env(ENV)
    api_id = env.get("REFRESH_API_ID"); api_hash = env.get("REFRESH_API_HASH"); sess = env.get("REFRESH_SESSION_STRING")
    reason = None
    got_lock = False
    delivered = False
    if not (api_id and api_hash and sess):
        reason = "no REFRESH_* session in %s" % ENV
        print("PING SKIP: %s" % reason)
    else:
        # Wait out a collision instead of dropping the message (see acquire_lock).
        got_lock = acquire_lock(POST_TO_LOCK_WAIT_S)
        if not got_lock:
            reason = "@work_acct_a session busy for %ds" % POST_TO_LOCK_WAIT_S
            print("PING SKIP: %s -> falling back to bot rail" % reason)
    if got_lock:
        try:
            import asyncio
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            body = ("\U0001F916 [%s] %s" % (_machine_tag(), text)) if tag else text
            try:
                target = int(chat_id)
            except (TypeError, ValueError):
                target = chat_id

            async def _go():
                client = TelegramClient(StringSession(sess), int(api_id), api_hash)
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    raise RuntimeError("session not authorized")
                await client.send_message(target, body)
                await client.disconnect()

            asyncio.run(_go())
            print("PING OK -> %s" % chat_id)
            delivered = True
        except Exception as e:
            reason = str(e)[:160]
            print("PING FAIL: %s -> falling back to bot rail" % reason)
        finally:
            release_lock()
        # Drain OUTSIDE the try: a hiccup while flushing the spool must never be mistaken for a
        # failed send and push us onto the bot rung -- that would deliver this message TWICE.
        if delivered:
            _spool_drain()
            return True
    # RUNG 2: the bot (no lock, different transport, survives a busy/dead user session).
    ok, info = _post_to_bot(chat_id, text, tag)
    if ok:
        _spool_drain()
        return True
    # RUNG 3: park it. A message we cannot send must never just vanish.
    _spool_add(chat_id, text, tag, "user:%s | bot:%s" % (reason, info))
    sys.stderr.write("⚠️ OUTBOUND UNDELIVERED -> chat %s (user rail: %s; bot rail: %s). "
                     "PARKED in %s (depth=%d) -- it will be retried on the next successful "
                     "send from this machine.\n" % (chat_id, reason, info, SPOOL, spool_depth()))
    return False


# 02 POLICE = the "needs Anton's attention" clean channel (canon: approval.json targets.tg_police).
POLICE_GROUP = int(os.environ.get("TG_POLICE_GROUP", "-6491142604"))


def post_police(text):
    """Escalate to 02 POLICE (-6491142604), the clean 'requires Anton' channel."""
    return post_to(POLICE_GROUP, text)


def main():
    # argparse (wave-1 2026-07-21): unknown flag / --help -> exit BEFORE any Telegram send
    # (the publish_canon "--help fired" class). Text starting with "-" needs the "--" separator.
    p = argparse.ArgumentParser(
        prog="bus_ping.py",
        description="One-shot Telegram ping to Anton's Saved Messages (default), or to group 03 "
                    "with --post. Never raises; prints PING OK / SKIP / FAIL.",
        epilog='Text whose first word starts with "-" needs the "--" separator: '
               'bus_ping.py -- "--literal text".')
    p.add_argument("--check", action="store_true", help="verify the rail + spool WITHOUT sending")
    p.add_argument("--drain", action="store_true", help="manually flush the undelivered spool")
    p.add_argument("--post", action="store_true", help="post to TG GROUP 03 instead of Saved Messages")
    p.add_argument("text", nargs="*", help="message text")
    ns = p.parse_args()
    if ns.check:
        print("PING READY (rail present)" if rail_ready()
              else "PING SKIP (no REFRESH_* session on this machine -> pings will be skipped gracefully)")
        d = spool_depth()
        print("SPOOL: %d undelivered message(s) parked in %s%s" % (
            d, SPOOL, " -- both rails were down; they retry on the next successful send" if d else ""))
        return 1 if d else 0
    if ns.drain:
        # manual flush of the spool (the automatic one rides on the next successful send)
        _spool_drain(max_n=50)
        print("SPOOL: %d left" % spool_depth())
        return 0
    if ns.post:
        # CLI access to post() -> TG GROUP 03 (canonical alert channel per cc-alerts-to-chat-03).
        post(" ".join(ns.text))
        return
    if not ns.text:
        print("usage: bus_ping.py \"text\"  |  bus_ping.py --check")
        return
    send(" ".join(ns.text))


if __name__ == "__main__":
    main()
