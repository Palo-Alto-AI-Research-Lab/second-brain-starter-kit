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
r"""lint_agents_mirror.py -- deterministic gate for the "Codex canon mirror went STALE" class.

ROOT it closes (found 2026-07-25): CLAUDE.md got the full v2 revision on 22.07 but Codex's
~/.codex/AGENTS.md silently stayed on the June canon for a MONTH -- Codex worked by month-old
rules and the old header-diff checker (check_drift.py, retired) went blind after the revision
because CLAUDE.md switched from '## ' headers to numbered sections. Nobody compared VERSIONS.

Rule: CLAUDE.md carries 'ВЕРСИЯ: vX.Y.Z' in its header (canon since 23.07); AGENTS.md carries
'MIRRORS: CLAUDE.md vX.Y.Z'. MAJOR.MINOR must match; a PATCH-only lag is noted but green
(micro-edits do not require re-mirroring; a new rule bumps MINOR per canon-versioning).
Missing stamp on either side = violation. Node without ~/.codex = skip green (no Codex here).

No baseline file: state is binary current (stale vs fresh), not an accumulating violation list.
Deterministic, 0 tokens, READ-ONLY outside its report files, ASCII-only stdout.
Run: python lint_agents_mirror.py                       (exit 1 iff stale/missing)
     python lint_agents_mirror.py --claude-md P --agents-md P   (test override)
Out: _lint_agents_mirror.txt + _lint_agents_mirror.flag (present iff violation)
"""
import argparse, os, re, sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

ARCH   = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(ARCH, "_lint_agents_mirror.txt")
FLAG   = os.path.join(ARCH, "_lint_agents_mirror.flag")

HOME       = os.path.expanduser("~")
CLAUDE_MD  = os.path.join(HOME, ".claude", "CLAUDE.md")
AGENTS_MD  = os.path.join(HOME, ".codex", "AGENTS.md")

RX_CANON  = re.compile(r"ВЕРСИЯ:\s*v(\d+)\.(\d+)\.(\d+)")
RX_MIRROR = re.compile(r"MIRRORS:\s*CLAUDE\.md\s*v(\d+)\.(\d+)\.(\d+)")


def head(path, lines=12):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readline() for _ in range(lines))
    except OSError:
        return None


def find_ver(text, rx):
    m = rx.search(text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def write_report(lines, violation):
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if violation:
        with open(FLAG, "w", encoding="utf-8") as f:
            f.write("stale\n")
    elif os.path.exists(FLAG):
        os.remove(FLAG)


def main():
    ap = argparse.ArgumentParser(description="Gate: AGENTS.md (Codex canon mirror) must not lag CLAUDE.md by MAJOR.MINOR.")
    ap.add_argument("--claude-md", default=CLAUDE_MD)
    ap.add_argument("--agents-md", default=AGENTS_MD)
    a = ap.parse_args()

    rep = ["lint_agents_mirror -- Codex canon mirror freshness"]

    if not os.path.isdir(os.path.dirname(a.agents_md)):
        rep.append("SKIP: no ~/.codex on this node (Codex not installed) -> green")
        write_report(rep, False)
        print("agents-mirror: SKIP (no Codex here)")
        return 0

    ch = head(a.claude_md)
    ah = head(a.agents_md)
    cv = find_ver(ch, RX_CANON)
    av = find_ver(ah, RX_MIRROR)

    if ch is None:
        rep.append("VIOLATION: CLAUDE.md not readable at %s" % a.claude_md)
    elif cv is None:
        rep.append("VIOLATION: CLAUDE.md has no 'ВЕРСИЯ: vX.Y.Z' header line (versioning canon broken)")
    if ah is None:
        rep.append("VIOLATION: AGENTS.md not readable at %s" % a.agents_md)
    elif av is None:
        rep.append("VIOLATION: AGENTS.md has no 'MIRRORS: CLAUDE.md vX.Y.Z' stamp (mirror unversioned)")

    violation = any(l.startswith("VIOLATION") for l in rep)
    if not violation:
        rep.append("canon  CLAUDE.md v%d.%d.%d" % cv)
        rep.append("mirror AGENTS.md v%d.%d.%d" % av)
        if cv[:2] != av[:2]:
            rep.append("VIOLATION: mirror lags by MAJOR.MINOR -- Codex is working by OLD rules."
                       " Fix: hub rebuilds ~/.codex/AGENTS.md from CLAUDE.md v%d.%d.%d and updates the MIRRORS stamp." % cv)
            violation = True
        elif cv[2] != av[2]:
            rep.append("note: PATCH lag only (v%d.%d.%d vs v%d.%d.%d) -- green, re-mirror on next MINOR." % (cv + av))
        else:
            rep.append("OK: mirror matches canon version.")

    write_report(rep, violation)
    print("agents-mirror: %s" % ("VIOLATION -> flag set" if violation else "ok"))
    return 1 if violation else 0


if __name__ == "__main__":
    sys.exit(main())
