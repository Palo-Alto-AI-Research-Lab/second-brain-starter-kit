#!/usr/bin/env python3
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
"""tailnet_guard.py -- nightly check: EVERY fleet peer must be in the tailnet.

Rule (origin: anton, 2026-07-16, emphatic): all peers live inside Tailscale.
Syncthing + the TG bus work fine WITHOUT tailnet, so an absent node is
invisible in daily work (MAC1 lived outside the net unnoticed until
the hub SSH door -- tailnet-only -- exposed it). This guard makes the gap loud.

Checks `tailscale status --json` (Self + Peers) against
~/.claude/scripts/tailnet_expected.json. Missing/offline-daemon => alert to
the bus (dual rail via bus_send.py).

Anti-fake-incident (memory deterministic-script-gotchas): --test / env
TAILNET_GUARD_MUTE=1 prints but never sends; a state file dedups repeat
alerts for the same missing-set within 24h.

Exit: 0 = all present, 1 = alert condition, 2 = guard itself broken.
"""
import json, os, subprocess, sys, time

HOME = os.path.expanduser("~")
EXPECTED = os.path.join(HOME, ".claude", "scripts", "tailnet_expected.json")
STATE = os.path.join(HOME, ".claude", "scripts", "tailnet_guard_state.json")
BUS_SEND = os.path.join(HOME, ".claude", "scripts", "bus_send.py")
MUTE = ("--test" in sys.argv) or os.environ.get("TAILNET_GUARD_MUTE") == "1"


def alert(msg):
    print("ALERT:", msg)
    if MUTE:
        print("(muted: not sent to bus)")
        return
    # dedup: same alert fingerprint within 24h => skip send
    fp = str(hash(msg))
    st = {}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE))
        except Exception:
            st = {}
    if st.get("fp") == fp and time.time() - st.get("ts", 0) < 24 * 3600:
        print("(dedup: same alert sent <24h ago, skipping)")
        return
    subprocess.run([sys.executable, BUS_SEND, "⚠️ TAILNET GUARD [hub]: " + msg],
                   timeout=180)
    json.dump({"fp": fp, "ts": time.time()}, open(STATE, "w"))


def main():
    try:
        exp = json.load(open(EXPECTED))["expected"]
    except Exception as e:
        alert("guard broken: cannot read tailnet_expected.json: %s" % e)
        return 2
    try:
        out = subprocess.run(["tailscale", "status", "--json"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            alert("tailscale daemon not answering on hub: %s" % out.stderr.strip()[:200])
            return 1
        st = json.loads(out.stdout)
    except Exception as e:
        alert("guard broken: tailscale status failed: %s" % e)
        return 2

    present = set()
    nodes = [st.get("Self") or {}] + list((st.get("Peer") or {}).values())
    for node in nodes:
        # HostName can be a human label ("Rita's MacBook Pro"); the DNSName
        # first label is the canonical machine name -- collect both.
        hn = (node.get("HostName") or "").lower()
        dns = (node.get("DNSName") or "").split(".")[0].lower()
        for name in (hn, dns):
            if name:
                present.add(name)

    missing = {h: note for h, note in exp.items() if h.lower() not in present}
    if missing:
        lines = ["%s (%s)" % (h, note) for h, note in missing.items()]
        alert("узлы ВНЕ tailnet: " + "; ".join(lines) +
              ". Правило: все пиры внутри Tailscale. Онбординг узла = follower-onboard Step 6b.")
        return 1
    print("OK: all %d expected nodes present in tailnet" % len(exp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
