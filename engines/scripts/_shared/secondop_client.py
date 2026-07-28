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
"""secondop_client.py -- peer-side client for the Codex second-opinion broker (Phase 1.5).

For fleet machines WITHOUT a local Codex login: write a request onto the Syncthing bus
(_machine-bus/_secondop/), the HUB broker (secondop.py serve-once, schtasks every 5 min)
answers over the same rail and mirrors the exchange to chat 04 "AI-DUO".

ДО: the peer's live session decides it wants a second opinion (SessionStart hook reminds it).
ПОСЛЕ: this client polls for the answer file and prints it -- the session acts on it.

Usage:
  python secondop_client.py t1|t2|t3 --task <id> --context "<text>" [--wait 240]
Latency: Syncthing ~10s each way + broker tick <=5 min + Codex ~15s => budget 2-6 min.
"""
import argparse, json, os, shutil, socket, subprocess, sys, time, uuid

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Vault root differs per OS; env override first (peers set OBSIDIAN_VAULT in settings env).
VAULT = os.environ.get("OBSIDIAN_VAULT", r"%VAULT%")
BUS_SECONDOP = os.path.join(VAULT, "_machine-bus", "_secondop")
HOST = os.environ.get("COMPUTERNAME", socket.gethostname())


def _local_secondop():
    """Path to this node's OWN secondop.py, if the engine is installed here."""
    for p in (os.path.expanduser("~/.claude/scripts/cc-review/secondop.py"),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "cc-review", "secondop.py")):
        if os.path.isfile(p):
            return p
    return None


def _has_local_codex():
    """Local Codex = the DEFAULT rail (Anton, 17.07: each node runs its own subscription).
    The broker is a fallback only: its 5-min tick can never fit the 90s /tt budget."""
    if not _local_secondop():
        return False
    exe = shutil.which("codex")
    if not exe:
        for cand in (os.path.join(os.environ.get("APPDATA", ""), "npm", "codex.cmd"),
                     "/usr/local/bin/codex", os.path.expanduser("~/.local/bin/codex")):
            if cand and os.path.isfile(cand):
                exe = cand
                break
    if not exe:
        return False
    try:
        base = ["cmd", "/c", exe] if exe.lower().endswith((".cmd", ".bat")) else [exe]
        out = subprocess.run(base + ["login", "status"], capture_output=True, text=True, timeout=30)
        # `codex login status` prints to STDERR, not stdout -- checking one channel silently
        # demoted every node to the broker rail (caught live 17.07). Never assume the channel.
        # Exit code is the structural marker: a stale/garbled "logged in" text with rc!=0
        # must NOT elect the local rail (Codex VERIFY, 17.07).
        return out.returncode == 0 and "logged in" in ((out.stdout or "") + (out.stderr or "")).lower()
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("point", choices=["t1", "t2", "t3"])
    ap.add_argument("--task", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--ritual", default="", help="какой ритуал позвал (tt/session/manual) -- прокидывается в счётчики")
    ap.add_argument("--force-broker", action="store_true", help="не звать локальный Codex, идти через шину")
    # Default MUST exceed the broker tick (5 min) + sync latency, or a req filed right after a
    # tick is guaranteed to time out (Codex T3-BREAK finding, 16.07): 300s tick + 2x sync + Codex.
    ap.add_argument("--wait", type=int, default=420, help="seconds to poll for the answer (0 = fire-and-forget)")
    args = ap.parse_args()

    # RAIL 1 (default): this node's own Codex -- ~15-20s, fits the ritual budget, no single point
    # of failure. RAIL 2 (fallback): the fleet broker over Syncthing, for nodes without Codex.
    if not args.force_broker and _has_local_codex():
        local = _local_secondop()
        cmd = [sys.executable, local, args.point, "--task", args.task, "--context", args.context]
        if args.ritual:
            cmd += ["--ritual", args.ritual]
        print("rail: LOCAL codex (%s)" % os.path.basename(local))
        return subprocess.call(cmd)
    print("rail: BROKER (локального Codex нет -- ставь свой, канон codex-local-autonomy-0717); "
          "⚠️ ответ может не успеть в бюджет /tt")

    os.makedirs(BUS_SECONDOP, exist_ok=True)
    rid = "%s-%s-%s" % (HOST, time.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:6])
    req_path = os.path.join(BUS_SECONDOP, "req-%s.json" % rid)
    ans_path = os.path.join(BUS_SECONDOP, "ans-%s.json" % rid)
    tmp = req_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"task": args.task, "point": args.point, "context": args.context,
                   "from": HOST, "ts": int(time.time())}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, req_path)
    print("queued: %s" % os.path.basename(req_path))
    if not args.wait:
        return 0
    deadline = time.time() + args.wait
    while time.time() < deadline:
        if os.path.exists(ans_path):
            with open(ans_path, encoding="utf-8") as fh:
                ans = json.load(fh)
            if "reply" in ans:
                print(ans["reply"])
                return 0
            print("ERROR from broker: %s" % ans.get("error"))
            return 1
        time.sleep(10)
    print("TIMEOUT: ответ ещё не пришёл (брокер тикает раз в 5 мин) -- забери позже: %s" % ans_path)
    return 2


if __name__ == "__main__":
    sys.exit(main())
