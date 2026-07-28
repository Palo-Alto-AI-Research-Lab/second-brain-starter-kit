#!/usr/bin/env python
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
"""Memory Index Guard — keep MEMORY.md from ever bloating past the always-loaded window.

0-token, deterministic. Checks the caps from memory/memory-index-hygiene.md:
  bytes <= 20000, lines <= 135, every entry <= 150 chars.
Also guards the CLASS of silent memory loss (added 2026-07-04 after 23 orphans found):
  - orphan check: every memory *.md must have a pointer in MEMORY.md or MEMORY-archive.md;
  - sync-conflict check: *.sync-conflict-* in the memory dir = machines fighting over a file
    (merge the unique lines into the live copy FIRST, only then delete the conflict copy).
Prints a GREEN/RED report, exits 0 (ok) / 1 (over budget), and writes a flag file
MEMORY_OVER_BUDGET.flag next to MEMORY.md when RED (cleared when GREEN) so the
breach is visible at session start. Run manually or 3x/week via the scheduled task.
"""
import io, os, re, sys, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PING = os.path.join(HERE, "bus_ping.py")  # proven Telegram-Saved notifier; self-skips where no session


def _targets():
    """EVERY project's MEMORY.md, not one hardcoded path.

    Until 2026-07-21 this pointed at `projects/E---CLAUDE-HUB1-June26/memory/MEMORY.md`
    only. This script is SYNCED to the whole fleet, so on every other machine/project the guard
    dutifully judged a file that session never loads, while the always-loaded index that WAS
    live went unguarded (hub: 123 lines / 35 over-length entries, reported as someone else's
    green). Same class the fleet spent 20-21.07 on: the judge answers confidently about the
    wrong thing. Globbing matches rule_home_guard.py, which had it right all along.
    """
    root = os.path.join(HERE, "..", "projects")
    out = []
    for proj in sorted(glob.glob(os.path.join(root, "*", "memory", "MEMORY.md"))):
        out.append(os.path.normpath(proj))
    return out

MAX_BYTES, MAX_LINES, MAX_ENTRY = 20000, 135, 150

def _notify(text):
    """On RED (scheduled run with --notify) alert the clan bus group chat 03 (cc-alerts-to-chat-03). Never raises."""
    try:
        subprocess.run([sys.executable, PING, "--post", text], timeout=60)
    except Exception as e:
        print("notify failed:", e)

def check_one(MEM):
    """Judge ONE project's MEMORY.md. -> (code, problems). code: 0 ok / 1 red / 2 soft-tidy."""
    FLAG = os.path.join(os.path.dirname(MEM), "MEMORY_OVER_BUDGET.flag")
    with io.open(MEM, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    nbytes = os.path.getsize(MEM)
    nlines = len(lines)
    over = [l for l in lines if len(l) > MAX_ENTRY]
    problems = []
    if nbytes > MAX_BYTES: problems.append("bytes %d > %d" % (nbytes, MAX_BYTES))
    if nlines > MAX_LINES: problems.append("lines %d > %d" % (nlines, MAX_LINES))
    if over:             problems.append("%d entries over %d chars" % (len(over), MAX_ENTRY))

    # Silent-loss class guards (2026-07-04): orphaned memory files + Syncthing conflict copies.
    mem_dir = os.path.dirname(MEM)
    arch_p = os.path.join(mem_dir, "MEMORY-archive.md")
    idx_txt = io.open(MEM, encoding="utf-8-sig").read()
    arch_txt = io.open(arch_p, encoding="utf-8-sig").read() if os.path.exists(arch_p) else ""
    conflicts = [f for f in os.listdir(mem_dir) if ".sync-conflict-" in f]
    # hub-*.md = warm sub-indexes (hot-dispatcher rebuild 2026-07-04): a pointer inside a hub
    # file counts as coverage, so spokes clustered into hubs are NOT orphans.
    hub_txt = ""
    for f in os.listdir(mem_dir):
        if f.startswith("hub-") and f.endswith(".md") and ".sync-conflict-" not in f:
            hub_txt += io.open(os.path.join(mem_dir, f), encoding="utf-8-sig").read()
    orphans = [f for f in os.listdir(mem_dir)
               if f.endswith(".md") and not f.startswith("MEMORY")
               and ".sync-conflict-" not in f
               and f not in idx_txt and f not in arch_txt and f not in hub_txt]
    if conflicts: problems.append("%d sync-conflict file(s): %s" % (len(conflicts), ", ".join(conflicts[:3])))
    if orphans:   problems.append("%d orphaned memory file(s) w/o index pointer: %s" % (len(orphans), ", ".join(orphans[:5])))

    # Drift audit (2026-07-04, decision-memory-index-hot-dispatcher): dead pointers + duplicate slugs.
    slug_re = re.compile(r"\]\(([a-z0-9._-]+\.md)\)")
    refs = set(slug_re.findall(idx_txt)) | set(slug_re.findall(arch_txt)) | set(slug_re.findall(hub_txt))
    dead = sorted(s for s in refs if not os.path.exists(os.path.join(mem_dir, s)))
    live_slugs = [slug_re.search(l).group(1) for l in lines if slug_re.search(l)]
    dups = sorted({s for s in live_slugs if live_slugs.count(s) > 1})
    if dead: problems.append("%d dead pointer(s) to missing files: %s" % (len(dead), ", ".join(dead[:5])))
    if dups: problems.append("%d duplicate live line(s): %s" % (len(dups), ", ".join(dups[:5])))

    # --quiet (SessionStart hook): stay SILENT when healthy, speak only on RED. Keeps a per-session
    # hook from adding GREEN noise every start (deploy_check pattern: print only when there's a problem).
    quiet = "--quiet" in sys.argv
    label = os.path.basename(os.path.dirname(os.path.dirname(MEM)))  # the project this index serves
    if not quiet:
        print("[%s] MEMORY.md: %d bytes / %d lines / %d over-length entries / %d orphans / %d conflicts"
              % (label, nbytes, nlines, len(over), len(orphans), len(conflicts)))

    # --soft: pre-emptive trigger for the weekly tidy routine (act BEFORE the hard cap).
    # exit 2 = tidy recommended (approaching budget), exit 0 = fine. Does not write the flag.
    if "--soft" in sys.argv:
        # soft-redline 15KB / 110 lines (decision-memory-index-hot-dispatcher-2026-07-04:
        # hot file target 60-100 lines / 8-12KB; hard caps stay the emergency boundary)
        soft = (nbytes >= 15000) or (nlines >= 110) or (len(over) > 0)
        if soft:
            # message MUST restate the real condition above (was ">=18KB or >=120 lines" while the
            # code gated on 15000/110 -> a reader trusting the print had the wrong redline; fixed 2026-07-17)
            print("[%s] SOFT: tidy recommended (>=15KB or >=110 lines or any over-length)." % label)
            return 2, problems
        print("[%s] SOFT: fine, no tidy needed." % label)
        return 0, []

    if problems:
        with io.open(FLAG, "w", encoding="utf-8", newline="\n") as f:
            f.write("MEMORY.md OVER BUDGET: " + "; ".join(problems) + "\n")
            for l in over[:10]:
                f.write("  long: " + l[:90] + "\n")
        print("[%s] RED -> " % label + "; ".join(problems))
        print("Action: over budget -> trim hooks / move DONE to MEMORY-archive.md; orphans -> add pointer line; "
              "sync-conflict -> merge unique lines into live copy FIRST, then delete the conflict file.")
        return 1, ["[%s] %s" % (label, p) for p in problems]
    if os.path.exists(FLAG):
        os.remove(FLAG)
    if not quiet:
        print("[%s] GREEN: within budget (<= %dB / <= %d lines / <= %d chars)." % (label, MAX_BYTES, MAX_LINES, MAX_ENTRY))
    return 0, []


def main():
    targets = _targets()
    if not targets:
        print("RED: no projects/*/memory/MEMORY.md found under", os.path.normpath(os.path.join(HERE, "..", "projects")))
        return 1
    worst, all_problems = 0, []
    for mem in targets:
        code, problems = check_one(mem)
        all_problems += problems
        # RED (1) always outranks soft-tidy (2): a hard breach must not be masked by a soft hint.
        if code == 1 or (code == 2 and worst == 0):
            worst = code
    if all_problems and "--notify" in sys.argv and worst == 1:
        _notify("🧠 Memory guard RED (%s). Уборка: распух → подрезать/в архив; сироты → вернуть указатель; "
                "sync-conflict → смерджить уникальное в живой файл, потом удалить копию." % "; ".join(all_problems[:4]))
    return worst


if __name__ == "__main__":
    import argparse  # validator gate (class fix 21.07); body still reads sys.argv
    _g = argparse.ArgumentParser(description="MEMORY.md budget guard, all projects (nightly)")
    _g.add_argument("--quiet", action="store_true", help="suppress green output")
    _g.add_argument("--soft", action="store_true", help="soft mode, no flag file")
    _g.add_argument("--notify", action="store_true", help="alert on RED")
    _g.parse_args()
    sys.exit(main())
