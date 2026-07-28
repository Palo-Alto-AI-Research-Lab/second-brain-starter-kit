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
r"""lint_approval_routing.py -- deterministic gate for the "ask Anton" routing class.

ROOT it closes (Anton 2026-07-05 + 2026-07-07):
  A) BYPASS: a skill/routine hand-rolls an OK-question straight into a group chat (03) instead
     of going through approval.py -> the question lands in heartbeat noise and Anton misses it
     (fb-watch bug 2026-07-05, ask #4b8e6e2f drowned). The rule "asks go through approval.py,
     02-POLICE first" was canon but had NO gate, so skills drifted.
  B) 02-NOISE (NEW 2026-07-07, Anton "пишите в 02, там я точно увижу"): 02-POLICE (-6491142604)
     is the CLEAN channel -- its whole value is that it carries ONLY questions to Anton. If any
     code posts non-approval content (heartbeat/status/chatter) to 02, it rots into a second 03.
     So: referencing the police chat id anywhere OTHER than the approval engine, without an
     approval-ask signature present, is a regression.

The gate itself (this file) is called by run_architect.cmd; its flag is surfaced by sys_check.py
as chk-lint-flags (_lint_approval.flag -> RED-ping via /arch). It was MISSING 2026-07-05..07
(lost in the hpkg migration) -> the nightly run only logged an error and the gate was silently
dead. Rebuilt + extended 2026-07-07.

Baseline+flag+report shape identical to lint_path_hardcode.py / lint_vault_walk.py.
Deterministic, 0 tokens, READ-ONLY, ASCII-only stdout.
Run: python lint_approval_routing.py           (exit 1 if any NEW violation)
     python lint_approval_routing.py --arch     (same; arg accepted for the nightly runner)
     python lint_approval_routing.py --rebaseline
Out: <arch>\_lint_approval.txt (report) + <arch>\_lint_approval.flag (present iff NEW violations)
"""
import os, re, sys

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

HOME     = os.path.expanduser("~")
CLAUDE   = os.path.join(HOME, ".claude")
IMPORTS  = os.environ.get("IMPORTS_ROOT", r"%IMPORTS%")
ARCH     = os.path.join(IMPORTS, "arch")
REPORT   = os.path.join(ARCH, "_lint_approval.txt")
FLAG     = os.path.join(ARCH, "_lint_approval.flag")
BASELINE = os.path.join(ARCH, "_lint_approval_baseline.txt")

# roots holding executable/instruction code that could route an ask
ROOTS = [os.path.join(CLAUDE, "skills"), os.path.join(CLAUDE, "scripts"), IMPORTS]
EXTS  = (".py", ".md", ".cmd", ".ps1")

# dead trees -- copies / backups, never live code
DEAD = ("_portability-backup", "_sync-conflict-archive", "_archive", "__pycache__",
        "_pre-restore", "_config-backup", ".git", "_attic", ".stversions",
        "_backup-whisper", "_archive_oneoffs", "_transit", "scripts-pre-hpkg")

# files that are ALLOWED to name the police id / carry ask signatures: the engine + pure transports.
# A transport legitimately MOVES any message (incl. an ask) but never authors the routing decision.
WHITELIST = ("approval.py", "approval.json", "lint_approval_routing.py",
             "bus_send.py", "machine_bus.py", "tg_bus.py", "tg_bus_send.py", "tg_bus_read.py",
             "consensus.py", "bus_seen.py", "sync_monitor.py", "aibus_lite.py",
             # escalation transport (post_police = the sanctioned 02 delivery) + read-only pulse tail
             "bus_ping.py", "pulse_tg_feed.py")

POLICE_ID = "-6491142604"          # 02-POLICE
GROUP_ID  = "-996940094"           # 03 group (heartbeat noise)

# an approval-ask signature (the question-to-Anton envelope, in any of its forms)
ASK_RX = re.compile(
    r"НУЖЕН\s+(?:ТВОЙ\s+)?ОК"          # "НУЖЕН ТВОЙ ОК"
    r"|ВОПРОС\s+ВИСИТ"                  # escalate envelope
    r"|→\s*ANTON"                       # "[machine → ANTON]"
    r"|QQQ\s*=\s*да"                    # "Ответь: QQQ = да"
    r"|НУЖЕН\s+ОК", re.IGNORECASE)

# references the police (02) chat by raw id or config key
POLICE_RX = re.compile(re.escape(POLICE_ID) + r"|tg_police")
# references a group chat by raw id (03) -- the wrong place to put an ask
GROUP_RX  = re.compile(re.escape(GROUP_ID) + r"|tg_group")
# goes through the engine (any mention counts as "routed correctly")
ENGINE_RX = re.compile(r"approval\.py|approval\s+ask|cmd_ask|approval_config|approvals\.db", re.IGNORECASE)


def iter_files():
    seen = set()
    for base in ROOTS:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not any(x in d for x in DEAD)]
            if any(x in root for x in DEAD):
                continue
            for fn in files:
                if fn.endswith(EXTS):
                    p = os.path.join(root, fn)
                    if p not in seen:
                        seen.add(p); yield p


def main():
    viol = []   # (relpath, check, detail)
    scanned = 0
    for path in iter_files():
        fn = os.path.basename(path).lower()
        if fn in (w.lower() for w in WHITELIST):
            continue
        try:
            t = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        scanned += 1
        rel = path
        for base in ROOTS:
            if path.startswith(base):
                rel = path[len(os.path.dirname(base)):].lstrip("\\/"); break
        has_ask   = bool(ASK_RX.search(t))
        has_engine = bool(ENGINE_RX.search(t))
        hits_pol  = bool(POLICE_RX.search(t))
        hits_grp  = bool(GROUP_RX.search(t))

        # Check A -- BYPASS: authors an ask AND hardcodes a chat id, but never touches the engine.
        if has_ask and (hits_pol or hits_grp) and not has_engine:
            where = "02-POLICE" if hits_pol else "03-group"
            viol.append((rel, "A-bypass", "ask hardcoded to %s, not via approval.py" % where))

        # Check B -- 02-NOISE: names the police chat but carries NO ask -> non-approval content to 02.
        if hits_pol and not has_ask and not has_engine:
            viol.append((rel, "B-02noise", "references 02-POLICE without an approval-ask (non-question content?)"))

    def key(r, c): return r + "::" + c
    cur = {key(r, c) for r, c, _ in viol}

    rebase = "--rebaseline" in sys.argv
    if rebase or not os.path.exists(BASELINE):
        os.makedirs(ARCH, exist_ok=True)
        open(BASELINE, "w", encoding="utf-8").write("\n".join(sorted(cur)))
        base, first = cur, True
    else:
        base = {x for x in open(BASELINE, encoding="utf-8").read().splitlines() if x}
        first = False

    new = [(r, c, d) for r, c, d in viol if key(r, c) not in base]

    lines = ["approval-routing lint -- %d files scanned" % scanned,
             "rule A: asks to Anton go THROUGH approval.py (never hand-rolled into a chat id)",
             "rule B: 02-POLICE (-6491142604) carries ONLY approval questions -- no other content",
             "known/baselined (accepted): %d  |  NEW since baseline: %d" % (len(base), len(new)), ""]
    if new:
        lines.append("NEW VIOLATIONS (regressions): %d" % len(new))
        for r, c, d in sorted(new):
            lines.append("  [%s] %s" % (c, r))
            lines.append("        %s" % d)
    else:
        lines.append("CLEAN: 0 NEW approval-routing violations (baseline holding).")
    lines.append("")
    lines.append("--- full known list (%d) ---" % len(viol))
    for r, c, d in sorted(viol):
        lines.append("  [%s] %s -- %s" % (c, r, d))
    os.makedirs(ARCH, exist_ok=True)
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines))

    if new:
        open(FLAG, "w", encoding="utf-8").write(
            "%d NEW approval-routing violation(s) -- see _lint_approval.txt" % len(new))
        print("LINT-APPROVAL: RED -- %d NEW violation(s) -> %s" % (len(new), REPORT))
        return 1
    if os.path.exists(FLAG):
        os.remove(FLAG)
    tag = "baseline created (%d known)" % len(cur) if first else "baseline holding (%d known)" % len(base)
    print("LINT-APPROVAL: GREEN -- %d scanned, 0 NEW; %s -> %s" % (scanned, tag, REPORT))
    return 0


if __name__ == "__main__":
    import argparse  # validator gate (class fix 21.07): --help/unknown flag exit BEFORE any side effect; body still reads sys.argv
    _gate = argparse.ArgumentParser(description='lint: approval asks must route via approval.py')
    _gate.add_argument('--rebaseline', action="store_true", help='rewrite baseline')
    _gate.add_argument('--arch', action="store_true", help='run under nightly arch rail')
    _gate.parse_args()
    sys.exit(main())
