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
"""tg_channels_check.py -- per-machine self-test of BOTH Telegram channels.

Anton (2026-06-27): "каждый комп проверяет РАБОТАЕТ ли у него ОБА канала телеграм MCP / telethon".

This is the LOCAL, per-machine self-test (every computer checks ITS OWN two TG rails).
Distinct from the hub-only `connector-health-daily` watchdog (centralized).

Two channels:
  A) Telegram MCP (chigwell, C:\\mcp\\telegram-mcp) -- the rich connector.
     A script CANNOT truly test the MCP (it's a harness-owned stdio server, only reachable
     by the LLM in-session). So here we give the DETERMINISTIC best-effort signal:
        - is a telegram-mcp python process alive right now?
        - what does the MCP error log say -- most recent FATAL (AuthKeyDuplicated = the root,
          or "Could not find a matching"/TypeNotFound = stale telethon), and how fresh?
     The TRUE MCP verdict is added by the /tg-check SKILL (it calls a cheap MCP tool in-session).
  B) Telethon rail (@work_acct_a REFRESH session) -- the MCP-INDEPENDENT bus rail.
     This CAN be tested deterministically & SAFELY: we shell out to tg_bus_read.py --check,
     which uses the SHARED lock `_refresh_work_acct_a.lock` -> no AUTH_KEY_DUPLICATED.

Exit code: 0 if rail GREEN and no FRESH MCP fatal; 1 if anything is RED (for nightly --notify).

Usage:
  python tg_channels_check.py            # print the per-machine 2-channel matrix
  python tg_channels_check.py --notify   # on RED, also ping the bus (tg_bus_send.py) -- for cron
  python tg_channels_check.py --json      # machine-readable
Env: TG_MCP_LOG (default C:\\mcp\\telegram-mcp\\mcp_errors.log); BUS_PING_ENV (rail .env)
"""
import os, io, sys, json, subprocess, datetime, re, time

_HOME   = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".claude")
SCRIPTS = os.path.join(_HOME, "scripts")
_HOST   = (os.environ.get("COMPUTERNAME") or "").upper()
_LABEL  = {"LAPTOP1": "laptop-HP17", "HUB1": "HUB1"}.get(_HOST, _HOST or "?")

MCP_LOG = os.environ.get("TG_MCP_LOG", r"C:\mcp\telegram-mcp\mcp_errors.log")
# a fatal log entry younger than this many hours = the MCP is (or was just) actively broken.
FRESH_H = float(os.environ.get("TG_MCP_FRESH_HOURS", "48"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_TS = re.compile(r'"asctime":\s*"([0-9T:+\-]+)"')


def _parse_ts(line):
    m = _TS.search(line)
    if not m:
        return None
    try:
        return datetime.datetime.fromisoformat(m.group(1))
    except Exception:
        return None


def _hours_ago(dt):
    if dt is None:
        return None
    now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
    return (now - dt).total_seconds() / 3600.0


def mcp_process_alive():
    """Windows: is a telegram-mcp python process running? Returns True/False/None(unknown)."""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, timeout=15).stdout
    except Exception:
        return None  # not Windows / tasklist absent
    # tasklist gives names+PIDs but not cmdline; use WMIC-free CIM via powershell only if needed.
    # Cheap heuristic: any python.exe AND the MCP marker via a 2nd narrow query.
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*telegram-mcp*' -or $_.CommandLine -like '*TG-Media*' } | "
             "Measure-Object).Count"],
            capture_output=True, text=True, timeout=25).stdout.strip()
        return int(ps) > 0
    except Exception:
        return None


def check_mcp():
    """Deterministic best-effort MCP signal. Returns dict {state, detail}."""
    d = {"channel": "MCP", "state": "UNKNOWN", "detail": "", "last_fatal": None, "process": None}
    # 1) process presence (informational -- MCP only runs while a Claude session loads it)
    alive = mcp_process_alive()
    d["process"] = alive

    # 2) log forensics: newest line + freshest fatal of each kind
    if not os.path.exists(MCP_LOG):
        d["state"] = "NO-LOG"
        d["detail"] = "MCP log not found here (%s) -- MCP may not be installed on this machine" % MCP_LOG
        return d
    try:
        lines = io.open(MCP_LOG, encoding="utf-8", errors="replace").readlines()[-400:]
    except Exception as e:
        d["state"] = "UNKNOWN"; d["detail"] = "cannot read log: %s" % str(e)[:80]; return d

    fatal_dt, fatal_kind = None, None
    for ln in lines:
        kind = None
        if "AuthKeyDuplicated" in ln:
            kind = "AuthKeyDuplicated (ROOT: same TG session on 2+ machines)"
        elif "Could not find a matching" in ln or "TypeNotFound" in ln:
            kind = "TypeNotFound (stale telethon in MCP venv)"
        if kind:
            ts = _parse_ts(ln)
            if ts and (fatal_dt is None or ts > fatal_dt):
                fatal_dt, fatal_kind = ts, kind
    if fatal_dt:
        d["last_fatal"] = {"when": fatal_dt.isoformat(), "kind": fatal_kind,
                           "hours_ago": round(_hours_ago(fatal_dt), 1)}

    ha = _hours_ago(fatal_dt) if fatal_dt else None
    if ha is not None and ha <= FRESH_H:
        d["state"] = "RED"
        d["detail"] = "FRESH fatal %.1fh ago: %s" % (ha, fatal_kind)
    elif alive is True:
        d["state"] = "LIKELY-UP"
        d["detail"] = "process running, no fatal in last %gh -- confirm in-session (call an MCP tool)" % FRESH_H
    elif alive is False:
        d["state"] = "NOT-LOADED"
        d["detail"] = "no MCP process now (normal if no Claude session is open) -- confirm in-session"
    else:
        d["state"] = "UNKNOWN"
        d["detail"] = "process state unknown -- confirm in-session"
    return d


def check_rail():
    """Telethon rail via the existing safe tg_bus_read.py --check (shared lock)."""
    d = {"channel": "Telethon-rail", "state": "UNKNOWN", "detail": ""}
    script = os.path.join(SCRIPTS, "tg_bus_read.py")
    if not os.path.exists(script):
        d["state"] = "NO-SCRIPT"; d["detail"] = "tg_bus_read.py not on this machine"; return d
    try:
        r = subprocess.run([sys.executable, script, "--check"],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        d["state"] = "RED"; d["detail"] = "check crashed: %s" % str(e)[:100]; return d
    out1 = out.strip().splitlines()[-1] if out.strip() else ""
    if "TG-BUS READY" in out:
        d["state"] = "GREEN"; d["detail"] = out1
    elif "no REFRESH_* session" in out:
        d["state"] = "NO-RAIL"; d["detail"] = "REFRESH_* session not configured on this machine"
    elif "session busy (lock held)" in out:
        d["state"] = "BUSY"; d["detail"] = "rail locked by another process -- retry (not a failure)"
    else:
        d["state"] = "RED"; d["detail"] = out1 or "rail check returned no READY"
    return d


def main():
    args = set(sys.argv[1:])
    mcp, rail = check_mcp(), check_rail()

    red = (mcp["state"] == "RED") or (rail["state"] == "RED")
    payload = {"machine": _LABEL, "host": _HOST, "mcp": mcp, "rail": rail, "red": red}

    if "--json" in args:
        print(json.dumps(payload, ensure_ascii=False, indent=2));
    else:
        icon = {"GREEN": "🟢", "LIKELY-UP": "🟡", "BUSY": "🟡", "NOT-LOADED": "🟠",
                "RED": "🔴", "NO-LOG": "⚪", "NO-RAIL": "⚪", "NO-SCRIPT": "⚪", "UNKNOWN": "⚪"}
        print("=== TG channels self-test @ %s ===" % _LABEL)
        print("%s  MCP (chigwell)   : %-11s %s" % (icon.get(mcp["state"], "⚪"), mcp["state"], mcp["detail"]))
        print("%s  Telethon rail    : %-11s %s" % (icon.get(rail["state"], "⚪"), rail["state"], rail["detail"]))
        if mcp.get("last_fatal"):
            print("   last MCP fatal: %s (%sh ago)" % (mcp["last_fatal"]["kind"], mcp["last_fatal"]["hours_ago"]))
        print("   NOTE: a script can't truly test the MCP -- /tg-check confirms it with an in-session tool call.")

    if "--notify" in args:
        _notify_on_change(payload)

    sys.exit(1 if red else 0)


# --- change-only alarm (so an HOURLY cadence isn't spammy) -----------------
# Posts to the bus ONLY when status FLIPS (broke or recovered), stays silent while
# stable, and re-pings a still-RED state at most once per REMIND_SEC (persistent
# outage gets a daily nudge, not an hourly one). State is machine-local.
NSTATE    = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-tgbus", "tgcheck_state.txt")
REMIND_SEC = float(os.environ.get("TG_CHECK_REMIND_SEC", str(12 * 3600)))


def _notify_on_change(payload):
    sig = "%s|%s" % (payload["mcp"]["state"], payload["rail"]["state"])
    red = bool(payload["red"])
    last_sig, last_t, last_red = "", 0.0, False
    try:
        # field sep = TAB (sig itself contains "|", e.g. "RED|GREEN", so "|" can't be the sep)
        raw = io.open(NSTATE).read().strip().split("\t")
        last_sig = raw[0]
        last_t = float(raw[1]) if len(raw) > 1 else 0.0
        last_red = (len(raw) > 2 and raw[2] == "1")
    except Exception:
        pass
    now = time.time()
    changed = sig != last_sig
    stale_red = red and (now - last_t) > REMIND_SEC
    if not (changed or stale_red):
        return  # stable -> silent (this is what makes hourly cheap & quiet)

    if not red and last_red and changed:
        msg = "%s ✅ TG self-test RECOVERED: MCP=%s rail=%s" % (payload["machine"], payload["mcp"]["state"], payload["rail"]["state"])
    elif red:
        why = payload["mcp"].get("detail", "") if payload["mcp"]["state"] == "RED" else payload["rail"].get("detail", "")
        msg = "%s 🔴 TG self-test RED: MCP=%s rail=%s (%s)" % (payload["machine"], payload["mcp"]["state"], payload["rail"]["state"], why[:80])
    else:
        # green and wasn't red before -> nothing worth posting; just record baseline
        _write_nstate(sig, now, red); return

    send = os.path.join(SCRIPTS, "tg_bus_send.py")
    if os.path.exists(send):
        try:
            subprocess.run([sys.executable, send, "--to", "ALL", msg], timeout=60)
        except Exception:
            pass
    _write_nstate(sig, now, red)


def _write_nstate(sig, now, red):
    try:
        os.makedirs(os.path.dirname(NSTATE), exist_ok=True)
        io.open(NSTATE, "w").write("%s\t%f\t%s" % (sig, now, "1" if red else "0"))
    except Exception:
        pass


if __name__ == "__main__":
    main()
