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
"""bus_send.py -- the ONE entry point for every machine->machine message. DUAL-SEND BY
CONSTRUCTION: posts to BOTH rails (Telegram group 03 + Syncthing _machine-bus) in a single
call, so an actor can NEVER send on one rail only.

WHY (грабли 2026-06-28): a task went out only on _machine-bus (via `machine_bus.py send`) and
Anton did not see it in TG-03. Root: DUAL-SEND was a PROSE rule with no enforcement -> the
human/LLM had to remember to call both rails, and forgot. This gate removes the choice.

CANON (Anton 2026-06-28): Telegram is ALWAYS the mirror channel of ALL machine<->machine comms
-- never optional, never "fallback only". If one rail fails, the message STILL goes on the
other AND a failure SIGNAL is raised (a dead rail is a signal to Anton, not a reason to send
silently on one). The 4 extra rails (GDrive/email/WhatsApp/Telethon) stay as deeper fallbacks
behind these two primaries.

Usage: python bus_send.py [<target>] "<message>"
       target defaults to ALL (broadcast).
         python bus_send.py "hello clan"
         python bus_send.py LAPTOP1 "task for the laptop"
         python bus_send.py --to LAPTOP1 --sign "TASK: ..."
       ⚠️ argparse contract (wave-1 2026-07-21): a message whose FIRST word starts with "-"
       needs the "--" separator (bus_send.py --to HUB -- "--literal text"); unknown flags and
       --help now exit 2/0 BEFORE any send (the publish_canon "--help fired" class).
Exit: 0 = both rails OK; 1 = degraded (one rail down, other delivered + signalled); 3 = both down.
  "both rails" = (A) Syncthing/_machine-bus and (B) TG group 03. Rail B is reached by EITHER the
  user-session transport (bus_ping) OR, as a FALLBACK, the fleet BOT (tg_bot_send, @fleet_bus_bot,
  stdlib Bot API). The bot fires ONLY when the user transport did not deliver, so a healthy send
  never double-posts into 03. The 0/1/3 contract is UNCHANGED -- it still turns on the two logical
  rails (A, B); the bot only makes rail B resilient / decoupled from Anton's personal account
  (DR26-07-11-ANCHOR1-01). Optional knob: BUS_TG_PRIMARY=user (default) | bot = which TG transport
  is tried first.
Test hook (non-destructive): env BUS_SEND_FAIL forces rail(s) to fail. Accepts one name or a
  comma/plus list -- syncthing | tg | bot (e.g. BUS_SEND_FAIL=tg,bot fails the WHOLE TG rail).

PORTABILITY (linux fleet nodes, 2026-07-10 ANCHOR1): the hub is Windows (COMPUTERNAME + the
Windows E: bus dir); its behaviour is UNCHANGED. On a linux node those Windows values are absent, so
the soft-detect block below derives the equivalents from the env the node already carries
(MACHINE_KEY + BUS_PING_ENV + a local bus dir). EVERY line in that block is a pure FALLBACK --
it fires only when the Windows value is missing, so it can never alter hub behaviour.
"""
import os, re, sys, argparse, subprocess

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPTS, "_shared"))  # 83: ack_watchdog moved to _shared
sys.path.insert(0, SCRIPTS)
FLAG = os.path.join(SCRIPTS, "_BUS_RAIL_DOWN.flag")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# --- portable soft-detect (linux fleet nodes; hub Windows untouched) ---------
# Trigger = the Windows bus dir does NOT exist (i.e. we are not on the hub) AND the node
# carries BUS_PING_ENV (its Telethon rail config). Both conditions true == a configured
# linux node. On the hub the E:\ dir exists -> this whole block is skipped.
_WIN_BUS = r"%VAULT%\_machine-bus"
if not os.path.exists(_WIN_BUS) and os.environ.get("BUS_PING_ENV"):
    # 1) TG rail tag: bus_ping._machine_tag() reads COMPUTERNAME; unset on linux -> tag "[?]".
    #    Feed it MACHINE_KEY so posts are tagged with the real node name (e.g. [ANCHOR1]).
    if not os.environ.get("COMPUTERNAME") and os.environ.get("MACHINE_KEY"):
        os.environ["COMPUTERNAME"] = os.environ["MACHINE_KEY"]
    # 2) Syncthing rail dir: machine_bus.py honours MACHINE_BUS_DIR (default = the E:\ path).
    #    If the caller did not set it, point it at the node's local bus dir when present.
    if not os.environ.get("MACHINE_BUS_DIR"):
        for _cand in ("/root/machine-bus",):
            if os.path.isdir(_cand):
                os.environ["MACHINE_BUS_DIR"] = _cand
                break


def _fail(rail):
    """Test hook: BUS_SEND_FAIL forces one or more rails to fail. Back-compatible with the old
    single-value form (BUS_SEND_FAIL=syncthing); also accepts a comma/plus list so the whole TG
    rail can be exercised (BUS_SEND_FAIL=tg,bot)."""
    raw = os.environ.get("BUS_SEND_FAIL", "")
    parts = {p.strip() for p in raw.replace("+", ",").split(",") if p.strip()}
    return rail in parts


def _lbl(ok, info):
    """Compact per-transport label for the status line: OK / SKIP / - (not attempted) / FAIL."""
    if ok:
        return "OK"
    info = info or ""
    if info.startswith("not needed"):
        return "-"
    if "skip" in info.lower() or "no token" in info.lower() or "no refresh" in info.lower():
        return "SKIP"
    return "FAIL"


def _send_syncthing(target, msg):
    if _fail("syncthing"):
        return False, "forced-test-fail"
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "machine_bus.py"), "send", target, msg],
            capture_output=True, text=True, timeout=60)
        info = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        return r.returncode == 0, (info[-1] if info else "")
    except Exception as e:
        return False, str(e)


def _send_tg(target, msg):
    if _fail("tg"):
        return False, "forced-test-fail"
    try:
        import bus_ping
        text = msg if str(target).upper() == "ALL" else "[-> %s] %s" % (target, msg)
        ok = bus_ping.post(text)
        return bool(ok), "PING OK" if ok else "post returned False"
    except Exception as e:
        return False, str(e)


def _send_bot(target, msg):
    """FALLBACK TG transport: post to group 03 via the fleet bot (tg_bot_send, stdlib Bot API).
    Returns (ok, info). Absent token -> (False, 'skip ...') so it degrades like bus_ping and is
    never a hard failure by itself. Called only when the user-session TG transport missed."""
    if _fail("bot"):
        return False, "forced-test-fail"
    try:
        import tg_bot_send
        text = msg if str(target).upper() == "ALL" else "[-> %s] %s" % (target, msg)
        ok = tg_bot_send.post(text)
        return bool(ok), "BOT OK" if ok else "bot skip/False (no token or post failed)"
    except Exception as e:
        return False, str(e)


def _build_parser():
    """argparse front door (wave-1 2026-07-21). Successor of the old hand parser `_parse` +
    the ad-hoc -h/--help guard (#a1c59688) + the manual --sign strip: unknown flags exit 2 and
    --help exits 0 BEFORE any rail is touched (the publish_canon "--help fired" class). The BUG A
    forever-fix (flag-as-target) is inherited: option-like tokens are now rejected by argparse
    itself, and anything smuggled past `--` still hits _valid_target's flag rejection."""
    p = argparse.ArgumentParser(
        prog="bus_send.py",
        usage='bus_send.py [--to MACHINE] [--sign] [--] [<target>] "<message>"',
        description="DUAL-SEND one machine->machine message on BOTH rails "
                    "(Syncthing _machine-bus + Telegram group 03). Target defaults to ALL.",
        epilog='A message whose first word starts with "-" needs the "--" separator: '
               'bus_send.py --to HUB -- "--literal text". Exit: 0 both rails, 1 degraded, '
               '2 refused/usage, 3 both rails down.')
    p.add_argument("--to", "-t", dest="to", metavar="MACHINE",
                   help="target machine (alternative to the first positional word)")
    p.add_argument("--sign", action="store_true",
                   help="Layer-2: attach the fleet signature so receivers treat this as a real command")
    p.add_argument("words", nargs="*", metavar="[target] message",
                   help="optional target (machine | ALL | @capability), then the message text")
    return p


def _valid_target(target):
    """(ok, reason). Single source of truth = ack_watchdog.valid_target (known machines / ALL /
    @cap; flags rejected). Defensive fallback if the watchdog module is somehow unimportable:
    still block flags/empty so `--to`/`-t`/garbage never sends silently."""
    try:
        import ack_watchdog
        return ack_watchdog.valid_target(target)
    except Exception:
        t = ("" if target is None else str(target)).strip()
        if not t or t.startswith("-"):
            return False, "invalid target (flag/empty) and registry unavailable"
        return True, ""


def _maybe_register(target, msg, delivered):
    """Register a DIRECT order with the ACK-watchdog so silence gets chased.
    Skips: broadcasts (ALL), undelivered, the watchdog's own re-pings (BUS_NO_TRACK),
    and non-orders (ACKs / heartbeats / rail-down signals)."""
    if not delivered or str(target).upper() == "ALL":
        return
    if os.environ.get("BUS_NO_TRACK"):
        return
    head = (msg or "").lstrip()[:24]
    if any(s in head for s in ("✅", "💓", "\U0001F534", "RECEIVED", "принял")):
        return
    try:
        import ack_watchdog
        ack_watchdog.register(target, msg)
    except Exception:
        pass  # watchdog optional -- never break a send


def main():
    a = sys.argv[1:]
    # bare-word help forms of the old guard (#a1c59688): without this, "help" would broadcast
    # the literal word into chat 03 as a message. -h/--help themselves are argparse's now.
    if a and a[0].lower() in ("help", "/?"):
        print(__doc__)
        return 2
    ns = _build_parser().parse_args(a)   # unknown flag -> exit 2 HERE, before any send
    want_sign = ns.sign
    if ns.to is not None:
        target, msg = ns.to, " ".join(ns.words)
    elif not ns.words:
        print("usage: bus_send.py [--to <machine>] \"<message>\"")
        return 2
    elif len(ns.words) == 1:
        target, msg = "ALL", ns.words[0]
    else:
        target, msg = ns.words[0], " ".join(ns.words[1:])
    if not (msg or "").strip():
        print("refusing to send an empty message")
        return 2
    _auto = os.environ.get("FLEET_AUTOSIGN") == "1" and msg.lstrip().upper().startswith(
        ("TASK:", "ORDER:", "ACK-REQ:"))
    if want_sign or _auto:
        try:
            import fleet_hmac
            signed = fleet_hmac.sign_message(msg)
            if signed != msg:
                msg = signed
                print("[layer2] fleet-signed this command (both rails carry the signature).")
            else:
                print("[layer2] WARNING: no fleet secret on this node -> sent UNSIGNED "
                      "(receiver treats it as data). Add secrets/fleet_hmac.env to sign.")
        except Exception as e:
            print("[layer2] sign skipped (fleet_hmac error, sent as-is): %s" % str(e)[:120])
    # BUG A forever-fix: refuse a flag/stray-verb/garbage target LOUDLY before sending, so it can
    # never become a phantom ACK-watchdog row nor drop the real message.
    ok, why = _valid_target(target)
    if not ok:
        print("REFUSING TO SEND: %s" % why)
        return 2
    # robot-invisible gate (ZBOOK #128 class-fix, hub-ratified 2026-07-14): peer inbox-robots
    # only ACT on bodies STARTING with TASK:/ORDER:/ACK-REQ: -- any prefix makes the message
    # human-visible but robot-invisible (bit twice: 26h on 07-10 + 7 days on the laptop).
    # WARN loudly, do not block: FYI/status posts are legitimately robot-invisible.
    # 2026-07-21 class-fix (MacBook-Rita root-cause report #3e35ad00): the `target != ALL`
    # carve-out silently exempted BROADCASTS from this gate -- exactly the messages that hit every
    # peer at once. Two real work items ("TASK [env-audit...", "UPDATE к #...") went out fleet-wide
    # with no warning and no peer robot ever saw them. Broadcasts are now checked like any target.
    if not re.match(r"^(TASK:|ORDER:|ACK-REQ:|ACK\b|✅|🤝|💓)", msg.strip()):
        print("⚠️ robot-invisible: body does not start with TASK:/ORDER:/ACK-REQ: -- "
              "the target's inbox-robot will NOT act on it (fine for FYI, wrong for work items)")

    st_ok, st_info = _send_syncthing(target, msg)

    # --- TG-03 rail: user-session transport + fleet BOT fallback (never both on a healthy send) --
    # BUS_TG_PRIMARY=bot flips the order (bot first, user fallback) so the fleet can decouple the TG
    # rail from Anton's personal account without another engine change. Default = user (unchanged).
    # Whichever is tried first, the OTHER fires ONLY if the first did not deliver -> lands in 03 once.
    primary = (os.environ.get("BUS_TG_PRIMARY") or "user").strip().lower()
    if primary == "bot":
        bot_ok, bot_info = _send_bot(target, msg)
        if bot_ok:
            tgu_ok, tgu_info = False, "not needed (bot ok)"
        else:
            tgu_ok, tgu_info = _send_tg(target, msg)
    else:
        tgu_ok, tgu_info = _send_tg(target, msg)
        if tgu_ok:
            bot_ok, bot_info = False, "not needed (tg-user ok)"
        else:
            bot_ok, bot_info = _send_bot(target, msg)
    tg_ok = tgu_ok or bot_ok   # rail B reached by EITHER TG transport
    print("DUAL-SEND -> syncthing:%s(%s)  tg-03:%s [user:%s bot:%s]" % (
        "OK" if st_ok else "FAIL", st_info,
        "OK" if tg_ok else "FAIL", _lbl(tgu_ok, tgu_info), _lbl(bot_ok, bot_info)))

    _maybe_register(target, msg, st_ok or tg_ok)

    if st_ok and tg_ok:
        if os.path.exists(FLAG):
            os.remove(FLAG)
        return 0

    down = ([] if st_ok else ["syncthing/_machine-bus"]) + ([] if tg_ok else ["telegram-03"])
    sig = "\U0001F534 BUS RAIL DOWN: %s -- msg still delivered on the surviving rail: '%s'" % (
        ", ".join(down), msg[:60])
    open(FLAG, "w", encoding="utf-8").write(sig)
    # raise the signal on whichever rail IS up (can't signal via a dead rail). The TG signal goes
    # via whichever TG transport is alive -- user session if it worked, else the fleet bot.
    if tg_ok and not st_ok:
        try:
            if tgu_ok:
                import bus_ping
                bus_ping.post(sig)
            else:
                import tg_bot_send
                tg_bot_send.post(sig)
        except Exception:
            pass
    if st_ok and not tg_ok:
        try:
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "machine_bus.py"), "send", "ALL", sig], timeout=60)
        except Exception:
            pass
    print(sig)
    return 1 if (st_ok or tg_ok) else 3


if __name__ == "__main__":
    sys.exit(main())
