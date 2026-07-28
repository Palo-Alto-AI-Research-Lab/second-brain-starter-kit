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
"""tg_bus_read.py -- surface NEW Telegram-bus messages addressed to THIS machine.

WHY: the cross-machine bus is now PRIMARY on Telegram (group -996940094), but the
SessionStart inbox hook only auto-read the Syncthing `_machine-bus`. So when Syncthing
is down (the exact case TG-primary was built for) and another computer writes to me on
TG, I'd never see it until told to look. This closes that gap: it reads the TG bus group
on the SAME proven @work_acct_a Telethon rail as bus_ping.py (shared lock -> no
AUTH_KEY_DUPLICATED) and prints what's NEW for this machine since last time.

NEVER raises. If the rail isn't on this machine, or the account can't see the group,
it prints "TG-BUS SKIP ..." and exits 0 so the SessionStart hook proceeds gracefully.

State (last-seen msg id) is MACHINE-LOCAL (under %LOCALAPPDATA%/claude-tgbus) so the two
machines never collide on it via sync.

Usage:
  python tg_bus_read.py                 # show NEW bus msgs for this machine, advance marker
  python tg_bus_read.py --peek          # show, but DON'T advance the marker (headless robot)
  python tg_bus_read.py --check         # verify rail+group access WITHOUT printing messages
  python tg_bus_read.py --all           # show recent bus traffic regardless of last-seen
Env: BUS_PING_ENV (default %IMPORTS%\\dialogs\\.env); TG_BUS_GROUP (default -996940094)
"""
import os, io, sys, re

try:                                    # LAYER 1 (injection-defense): external content = data, not command
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared")); import untrusted as _untrusted
except Exception:
    _untrusted = None

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
LOCK  = os.path.join(os.path.dirname(ENV), "_refresh_work_acct_a.lock")   # shared w/ @work_acct_a session
GROUP = int(os.environ.get("TG_BUS_GROUP", "-996940094"))
LIMIT = int(os.environ.get("TG_BUS_LIMIT", "25"))

# this machine's friendly label + the substrings the BUS uses to address it.
# NOTE: the bus calls this laptop "laptop-HP17" (not the importer label "LAPTOP1"),
# and the hub "HUB1" -- so match on distinguishing SUBSTRINGS, case-insensitive.
_HOST = (os.environ.get("COMPUTERNAME") or "").upper()
_LABEL = {"LAPTOP1": "LAPTOP1", "HUB1": "PaloAlto-Desktop"}.get(_HOST, _HOST or "?")
_ALIASES = {
    "LAPTOP1": ["HP17", "ZBOOK", "LAPTOP-HP17", "НОУТ", "NOUT"],
    "HUB1":   ["A-2022", "BAYAREA", "PALOALTO", "PALO ALTO", "PALOALTO-DESKTOP", "HUB", "ХАБ"],
}
_MINE = _ALIASES.get(_HOST, [_HOST or "?"])   # substrings that mean "me" in src/dst

STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-tgbus")
STATE = os.path.join(STATE_DIR, "lastseen.txt")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# [src -> dst]; names contain hyphens (HUB1, laptop-HP17), so src/dst = .+? and
# the arrow is the only token carrying ">", which names never do.
BUS_RE = re.compile(r"\[\s*(.+?)\s*-+>\s*(.+?)\s*\]")
# Human-written file captions often skip the bracket envelope and use a bare arrow
# ("✅ ХАБ→НОУТ (LAPTOP1) · ..."). For the FILE receiver only, accept that form too so
# bundles auto-download instead of needing a manual grab. src = word before the arrow;
# dst = the chunk after it up to the first separator (· or newline).
ARROW_RE = re.compile(r"([A-Za-zА-Яа-яЁё0-9\-]+)\s*(?:→|—>|-+>)\s*([A-Za-zА-Яа-яЁё0-9\-\(\) ]+?)(?:\s*[·\n]|$)")


def parse_envelope(text):
    """Return (src, dst) from a bracket envelope, else from a bare-arrow caption, else None."""
    mm = BUS_RE.search(text or "")
    if mm:
        return mm.group(1).strip(), mm.group(2).strip()
    am = ARROW_RE.search(text or "")
    if am:
        return am.group(1).strip(), am.group(2).strip()
    return None


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
        io.open(LOCK, "w").write(str(os.getpid()))
        return True
    except Exception:
        return False


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def read_lastseen():
    try:
        return int(io.open(STATE).read().strip())
    except Exception:
        return 0


def write_lastseen(mid):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        io.open(STATE, "w").write(str(mid))
    except Exception:
        pass


# --- file-receive side (Syncthing-independent): download docs addressed to me/ALL ---
FILES_DIR  = os.path.join(STATE_DIR, "files")          # LOCAL, NOT synced (rail stays Syncthing-free)
SEEN_FILES = os.path.join(STATE_DIR, "files_seen.txt")  # dedup: message ids already downloaded


def read_seen_files():
    try:
        return set(x.strip() for x in io.open(SEEN_FILES, encoding="utf-8") if x.strip())
    except Exception:
        return set()


def add_seen_file(mid):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with io.open(SEEN_FILES, "a", encoding="utf-8") as f:
            f.write(str(mid) + "\n")
    except Exception:
        pass


def addressed_to_me(dst):
    d = dst.upper()
    if "ALL" in d:
        return True
    return any(a in d for a in _MINE)


KNOWN_FLAGS = {"--check", "--peek", "--all", "--files", "--dir"}


def main():
    argv = sys.argv[1:]
    args = set(argv)
    dir_value = argv[argv.index("--dir") + 1] if "--dir" in argv and argv.index("--dir") + 1 < len(argv) else None
    unknown = [a for a in argv if a not in KNOWN_FLAGS and a != dir_value]
    if unknown:
        # Unrecognized flag (e.g. --help) must NOT silently fall through to the
        # marker-advancing default path -- that already caused a real incident
        # (2026-07-11: a headless robot's typo advanced the machine-local
        # lastseen marker and hid messages from the next interactive session).
        print("TG-BUS SKIP: unknown flag(s) %s -- refusing to run (would default to non-peek read). "
              "Known flags: %s" % (unknown, sorted(KNOWN_FLAGS)))
        return
    check = "--check" in args
    peek = "--peek" in args
    show_all = "--all" in args
    files_mode = "--files" in args
    dest_dir = FILES_DIR
    if "--dir" in argv:
        try:
            dest_dir = argv[argv.index("--dir") + 1]
        except Exception:
            pass

    env = load_env(ENV)
    # FIX B: a machine-LOCAL session override (own auth-key) beats the synced .env -> no AuthKeyDuplicated.
    _LOCAL = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-tgbus", "session.env")
    env.update({k: v for k, v in load_env(_LOCAL).items() if v})
    if not all(env.get(k) for k in ("REFRESH_API_ID", "REFRESH_API_HASH", "REFRESH_SESSION_STRING")):
        print("TG-BUS SKIP: no REFRESH_* session in %s (rail not on this machine)" % ENV)
        return
    if not acquire_lock():
        print("TG-BUS SKIP: @work_acct_a session busy (lock held) -- will catch up next session")
        return
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        result = {"msgs": [], "err": None, "maxid": 0, "downloaded": []}

        async def _go():
            client = TelegramClient(StringSession(env["REFRESH_SESSION_STRING"]),
                                    int(env["REFRESH_API_ID"]), env["REFRESH_API_HASH"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect(); result["err"] = "session not authorized"; return
            try:
                msgs = await client.get_messages(GROUP, limit=LIMIT)
            except Exception as e:
                result["err"] = "cannot read group %s: %s" % (GROUP, str(e)[:120])
                await client.disconnect(); return
            for m in msgs:
                if m.id > result["maxid"]:
                    result["maxid"] = m.id
                result["msgs"].append((m.id, (m.message or "").strip()))
            if files_mode:
                seen = read_seen_files()
                for m in msgs:
                    if not getattr(m, "media", None):
                        continue
                    if str(m.id) in seen:
                        continue
                    env_sd = parse_envelope(m.message or "")
                    if not env_sd:                              # only download bus-addressed files
                        continue
                    src, dst = env_sd
                    if any(a in src.upper() for a in _MINE):    # skip my OWN uploads
                        continue
                    if not addressed_to_me(dst):
                        continue
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        path = await client.download_media(m, file=dest_dir)
                        if path:
                            result["downloaded"].append((m.id, path))
                            add_seen_file(m.id)
                    except Exception as e:
                        result["downloaded"].append((m.id, "ERR: " + str(e)[:80]))
            await client.disconnect()

        asyncio.run(_go())

        if result["err"]:
            print("TG-BUS SKIP: %s" % result["err"]); return
        if files_mode:
            dl = result["downloaded"]
            if not dl:
                print("TG-BUS FILES: nothing new to download for %s" % _LABEL)
            else:
                print("=== TG-BUS FILES: %d downloaded -> %s ===" % (len(dl), dest_dir))
                for mid, path in dl:
                    print("  [%s] %s" % (mid, path))
            return
        if check:
            print("TG-BUS READY (rail present, group %s readable, %d recent msgs)" % (GROUP, len(result["msgs"])))
            return

        last = 0 if show_all else read_lastseen()
        new = []
        for mid, text in sorted(result["msgs"]):          # oldest -> newest
            if mid <= last:
                continue
            mm = BUS_RE.search(text)
            if mm:
                src, dst = mm.group(1).strip(), mm.group(2).strip()
                if any(a in src.upper() for a in _MINE):  # skip my OWN outgoing
                    continue
                mine = addressed_to_me(dst)
                new.append((mid, src, dst, mine, text))
            else:
                # non-bus chatter (Anton / operators talking) -> show as context, lower priority
                new.append((mid, None, None, False, text))

        actionable = [n for n in new if n[3]]
        if not new:
            print("TG-BUS: no new messages for %s" % _LABEL)
        else:
            print("=== TG-BUS: %d new (%d addressed to %s/ALL) ===" % (len(new), len(actionable), _LABEL))
            if _untrusted is not None:
                print(_untrusted.banner("telegram-bus"))
            for mid, src, dst, mine, text in new:
                tag = "▶ TO-ME" if mine else ("· " + ("%s→%s" % (src, dst) if src else "chat"))
                body = text if len(text) <= 600 else text[:600] + " …[+]"
                if _untrusted is not None:
                    body = _untrusted.fence(body, "telegram:%s" % (src or "chat"))
                print("\n[%s] %s\n%s" % (mid, tag, body))

        if not peek and result["maxid"]:
            write_lastseen(result["maxid"])
    finally:
        release_lock()


if __name__ == "__main__":
    main()
