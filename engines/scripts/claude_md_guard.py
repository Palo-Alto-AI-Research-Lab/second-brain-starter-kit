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
# claude_md_guard.py — size guard for the ALWAYS-LOADED global CLAUDE.md.
# Referenced by skill /intake (run after any CLAUDE.md write). AK-47: stdlib only.
# GREEN <= soft, YELLOW soft..hard, RED > hard (fix NOW by structural tidy:
# move mechanics down to Bible/memory/skill, keep trigger+essence+pointer, block <= 4 lines).
# Exit codes: 0 = GREEN/YELLOW, 1 = RED (so callers can gate on it).
# Usage: python claude_md_guard.py [--hard-kb 82] [--soft-kb 78] [--notify]
#   --notify: on YELLOW/RED also post a one-line alert to TG chat 03 via bus_ping.

import argparse, os, re, sys

CLAUDE_MD = os.path.expanduser(r"~/.claude/CLAUDE.md")

def top_blocks(text, n=5):
    parts = re.split(r"(?m)^## ", text)
    rows = []
    for b in parts[1:]:
        title = b.split("\n", 1)[0][:60]
        rows.append((len(("## " + b).encode("utf-8")), title))
    return sorted(rows, reverse=True)[:n]

def main():
    ap = argparse.ArgumentParser()
    # anton 2026-07-22 (live, HP17): raised soft 78->100, hard 82->120; cycle = grow, then re-revision every few weeks
    ap.add_argument("--hard-kb", type=float, default=120.0)
    ap.add_argument("--soft-kb", type=float, default=100.0)
    ap.add_argument("--notify", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(CLAUDE_MD):
        print(f"RED: CLAUDE.md not found at {CLAUDE_MD}")
        return 1
    raw = open(CLAUDE_MD, "rb").read()
    kb = len(raw) / 1024
    lines = raw.count(b"\n")

    if kb > a.hard_kb:
        status, code = "RED", 1
    elif kb > a.soft_kb:
        status, code = "YELLOW", 0
    else:
        status, code = "GREEN", 0

    print(f"{status}: CLAUDE.md {len(raw)} B = {kb:.1f} KB, {lines} lines "
          f"(soft {a.soft_kb:.0f} KB / hard {a.hard_kb:.0f} KB)")
    if status != "GREEN":
        print("Fix = structural tidy (write-service-files-tight-no-recompress): "
              "move mechanics to Bible/memory/skill, keep trigger+essence+pointer. Fattest blocks:")
        text = raw.decode("utf-8", errors="replace")
        for size, title in top_blocks(text):
            print(f"  {size:6d} B  ## {title}")
        if a.notify:
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import bus_ping
                bus_ping.post(f"{'🔴' if status == 'RED' else '🟡'} claude_md_guard: "
                              f"CLAUDE.md {kb:.1f} KB (hard {a.hard_kb:.0f} KB) — нужна структурная уборка")
            except Exception as e:
                print(f"(notify failed: {e})")
    return code

if __name__ == "__main__":
    sys.exit(main())
