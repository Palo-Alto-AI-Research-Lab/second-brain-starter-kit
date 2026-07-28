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
"""tg_bus_send.py -- post a message to the clan Telegram bus WITHOUT the Telegram MCP.

WHY: the chigwell Telegram-MCP drops under load (big get_history payloads) / idle, taking
posting with it. The bus must not depend on a flaky connector. This sends straight over the
same @work_acct_a Telethon rail that tg_bus_read.py / bus_ping.py use (shared lock -> no
AUTH_KEY_DUPLICATED). Pairs with tg_bus_read.py to make the bus fully MCP-independent.

It auto-wraps your text in the bus envelope `🤖 [<this-machine> -> <dst>] text` unless your
text already starts with `🤖 [`. Default dst = ALL.

Usage:
  python tg_bus_send.py "кто живой?"                 # -> 🤖 [laptop-HP17 -> ALL] кто живой?
  python tg_bus_send.py --to HUB1 "текст"   # direct to the hub
  python tg_bus_send.py --raw "🤖 [x -> y] ..."      # send verbatim (no auto-envelope)
Env: BUS_PING_ENV (default %IMPORTS%\\dialogs\\.env); TG_BUS_GROUP (default -996940094)
"""
import os, io, sys, argparse

# machine.env rung (ANCHOR1 audit 2026-07-16 #ee1aa4bd): same ladder as bus_ping -- the hub hardcode
# made the rail silently SKIP on nodes whose @work_acct_a session lives elsewhere (ANCHOR1:
# ~/secrets/dialogs.env). Explicit BUS_PING_ENV still wins; hub default unchanged.
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

ENV   = os.environ.get("BUS_PING_ENV") or _menv_ping_env() or r"%IMPORTS%\dialogs\.env"
LOCK  = os.path.join(os.path.dirname(ENV), "_refresh_work_acct_a.lock")
GROUP = int(os.environ.get("TG_BUS_GROUP", "-996940094"))
_HOST = (os.environ.get("COMPUTERNAME") or "").upper()
_LABEL = {"LAPTOP1": "laptop-HP17", "HUB1": "HUB1"}.get(_HOST, _HOST or "?")

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


def acquire_lock():
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip())
        except Exception:
            pid = -1
        if _pid_alive(pid):
            return False
    try:
        io.open(LOCK, "w").write(str(os.getpid())); return True
    except Exception:
        return False


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--to", default="ALL")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--file", default=None, help="path to a file to attach as a document (Syncthing-independent rail)")
    a = ap.parse_args()
    if a.file and not a.text:
        a.text = f"FILE: {os.path.basename(a.file)}"
    if a.file and not os.path.exists(a.file):
        print("BUS-SEND SKIP: file not found:", a.file); return
    msg = a.text if (a.raw or a.text.startswith("🤖 [")) else f"🤖 [{_LABEL} -> {a.to}] {a.text}"

    env = load_env(ENV)
    # FIX B: a machine-LOCAL session override (own auth-key) beats the synced .env -> no AuthKeyDuplicated.
    _LOCAL = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-tgbus", "session.env")
    env.update({k: v for k, v in load_env(_LOCAL).items() if v})
    if not all(env.get(k) for k in ("REFRESH_API_ID", "REFRESH_API_HASH", "REFRESH_SESSION_STRING")):
        print("BUS-SEND SKIP: no REFRESH_* session on this machine"); return
    if not acquire_lock():
        print("BUS-SEND SKIP: @work_acct_a session busy (lock held) -- retry"); return
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        async def _go():
            client = TelegramClient(StringSession(env["REFRESH_SESSION_STRING"]),
                                    int(env["REFRESH_API_ID"]), env["REFRESH_API_HASH"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect(); raise RuntimeError("session not authorized")
            if a.file:
                await client.send_file(GROUP, a.file, caption=msg, force_document=True)
            else:
                await client.send_message(GROUP, msg)
            await client.disconnect()

        asyncio.run(_go())
        print("BUS-SEND OK ->", msg[:80])
    except Exception as e:
        print("BUS-SEND FAIL:", str(e)[:160])
    finally:
        release_lock()


if __name__ == "__main__":
    main()
