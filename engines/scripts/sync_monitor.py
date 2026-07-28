#!/usr/bin/env python3
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
# sync_monitor.py -- DEAD-MAN-SWITCH for Syncthing peer connectivity (runs on the always-on hub).
#
# WHY (reglament-chp-poterya-sinka-mezhdu-mashinami, root C): when sync silently dies, machines go
# mute and nobody notices for hours. This monitor watches the hub's live peer connections and PINGS
# the clan bus group chat 03 (via bus_ping --post, canon cc-alerts-to-chat-03) the MOMENT a peer drops -- so recovery
# starts in minutes, not after half a day. It is QUIET: it pings ONLY on a state CHANGE
# (connected->disconnected or back), never on every run. 0 LLM tokens (pure Python + Syncthing REST).
#
# Run every ~20 min via a scheduled task (continuous safety monitor -- exempt from the night-window
# rule, same as the 15-min config git backup). State in ~/.claude/sync_monitor_state.json (local).
import os, sys, json, time, subprocess, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".claude", "sync_monitor_state.json")
LOG = os.path.join(HOME, ".claude", "scripts", "_sync_monitor.log")


def _log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg + "\n")
    except Exception:
        pass


PING = os.path.join(HOME, ".claude", "scripts", "bus_ping.py")
# On a peer reconnect, divergent edits from the split surface as .sync-conflict files ->
# fire the loss-free sweeper (SAFE-only, archive-first) so they self-heal, not pile up.
SWEEPER = r"%IMPORTS%\sync\conflict_sweeper.py"
API = "http://127.0.0.1:8384/rest"
REPING_AFTER = 3 * 3600        # if a peer stays down, re-nag Anton at most every 3h
APIKEY = (os.environ.get("STGUIAPIKEY") or "").strip()
# --- Layer-2 self-heal: auto-nudge a disconnected peer's robot to restart its Syncthing ---
GROUP_POST = os.path.join(HOME, ".claude", "scripts", "_shared", "bus_group_post.py")  # 83  # 0-LLM post to the bus GROUP
BUS_DIR = os.environ.get("MACHINE_BUS_DIR", r"%VAULT%\_machine-bus")
ME_HUB = "HUB1"       # this (hub) machine's bus key -> nudge sender label
NUDGE_EVERY = 30 * 60          # space auto group-nudges >= 30 min apart
NUDGE_MAX = 3                  # ... and at most 3 per down-episode, then rely on the 3h Anton re-ping -> bounded noise


def _api(path):
    req = urllib.request.Request(API + path, headers={"X-API-Key": APIKEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(s):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def _ping(text):
    # ALL CC alerts go to chat 03 (the bus group), NOT Saved -- canon cc-alerts-to-chat-03 (Anton 2026-06-27).
    try:
        subprocess.run([sys.executable, PING, "--post", text], timeout=60)
    except Exception as e:
        print("ping failed:", e)


def _sweep_conflicts():
    # detached, non-blocking; loss-free (sweeper only clears subset-of-newer-base conflicts + archives)
    try:
        if os.path.exists(SWEEPER):
            subprocess.Popen([sys.executable, SWEEPER, "--apply"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _log("triggered conflict_sweeper on peer reconnect")
    except Exception as e:
        _log(f"sweep trigger failed: {e}")


def _buskeys():
    """deviceID -> bus key (the COMPUTERNAME-style name the peer's robot answers to), from machines.json.
    A nudge must address the peer by THIS, not the Syncthing device name, or its tg_bus filter won't match."""
    try:
        with open(os.path.join(BUS_DIR, "machines.json"), encoding="utf-8") as fh:
            reg = json.load(fh)
        return {v.get("deviceID"): k for k, v in reg.get("machines", {}).items() if v.get("deviceID")}
    except Exception:
        return {}


def _group_nudge(buskey, down_min):
    """Layer-2 self-heal: post a 0-LLM group line telling a disconnected peer to restart its Syncthing.
    Best-effort -- rail may be absent on a peer, never blocks the monitor."""
    mid = os.urandom(4).hex()
    text = ("\U0001F916 [%s -> %s] AUTO sync-link down ~%dmin -- your Syncthing is NOT connected to the hub "
            "(EEAETB6, hub healthy). Restart your Syncthing via your watchdog task, then it self-reconnects. #%s"
            % (ME_HUB, buskey, down_min, mid))
    try:
        subprocess.run([sys.executable, GROUP_POST, text], timeout=90)
        _log(f"group_nudge -> {buskey} (~{down_min}min)")
    except Exception as e:
        _log(f"group_nudge failed for {buskey}: {e}")


def main():
    if not APIKEY:
        print("STGUIAPIKEY not set -> cannot query Syncthing; skip"); _log("SKIP: STGUIAPIKEY not set"); return
    try:
        names = {d["deviceID"]: d.get("name", d["deviceID"][:7]) for d in _api("/config/devices")}
        conns = _api("/system/connections").get("connections", {})
        myid = _api("/system/status").get("myID", "")
    except Exception as e:
        print("Syncthing API unreachable:", e)
        # The daemon itself may be down -> that's its own watchdog's job; we only watch PEERS here.
        return

    state = _load_state()
    buskeys = _buskeys()
    now = int(time.time())
    changed = []
    for dev, c in conns.items():
        if dev == myid:
            continue
        name = names.get(dev, dev[:7])
        bk = buskeys.get(dev)
        cur = bool(c.get("connected"))
        prev = state.get(dev)
        if prev is None:
            # first time we see this peer -> record baseline, do NOT alert (avoid spurious first-run ping).
            # last_alert=now (not 0) so a peer that is ALREADY down at baseline doesn't instantly re-nag.
            state[dev] = {"connected": cur, "since": now, "last_alert": now if not cur else 0, "nudges": 0, "last_nudge": 0}
            continue
        was = prev.get("connected")
        if cur != was:
            # transition
            if cur:
                _ping(f"✅ SYNC OK: {name} переподключился к хабу (Syncthing). Полный состав восстанавливается.")
                _sweep_conflicts()  # peer back -> auto-clear any conflicts the split produced
                state[dev] = {"connected": True, "since": now, "last_alert": 0, "nudges": 0, "last_nudge": 0}
            else:
                _ping(f"🔌 SYNC ALERT: {name} ОТВАЛИЛСЯ от хаба (Syncthing). Возможна потеря синка — runbook: reglament-chp-poterya-sinka. Координация в /bus.")
                nud, lastn = 0, 0
                if bk:  # Layer-2: first auto-nudge to the peer's robot to restart its Syncthing
                    _group_nudge(bk, 1); nud, lastn = 1, now
                state[dev] = {"connected": False, "since": now, "last_alert": now, "nudges": nud, "last_nudge": lastn}
            changed.append((name, cur))
        elif not cur:
            # still down: (a) bounded auto-nudges every NUDGE_EVERY up to NUDGE_MAX, (b) Anton re-nag every REPING_AFTER
            since = prev.get("since", now)
            if bk and prev.get("nudges", 0) < NUDGE_MAX and now - prev.get("last_nudge", 0) >= NUDGE_EVERY:
                _group_nudge(bk, max(1, round((now - since) / 60)))
                prev["nudges"] = prev.get("nudges", 0) + 1
                prev["last_nudge"] = now
            if now - prev.get("last_alert", 0) >= REPING_AFTER:
                down_h = round((now - since) / 3600, 1)
                _ping(f"⏳ SYNC всё ещё лежит: {name} офлайн ~{down_h}ч. Подними по runbook reglament-chp-poterya-sinka.")
                prev["last_alert"] = now
            state[dev] = prev
        else:
            state[dev] = {"connected": True, "since": prev.get("since", now), "last_alert": 0, "nudges": 0, "last_nudge": 0}

    _save_state(state)
    online = sum(1 for d, c in conns.items() if d != myid and c.get("connected"))
    total = sum(1 for d in conns if d != myid)
    print(f"sync_monitor: {online}/{total} peers connected; changes this run: {changed or 'none'}")
    _log(f"{online}/{total} peers connected; changes: {changed or 'none'}")


if __name__ == "__main__":
    main()
