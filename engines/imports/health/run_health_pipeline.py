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
"""One-shot runner: parse -> generate -> moc -> dashboard -> validate.
Then prints the robocopy line for the caller to execute (staging -> vault).
Reused by BOTH the first backfill and the weekly incremental sync (single
source of truth). Deterministic, 0 tokens, idempotent. ASCII-only stdout.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STEPS = ["parse_health.py", "generate_health.py", "build_health_moc.py", "build_health_dashboard.py", "validate_health.py"]

def main():
    for s in STEPS:
        print("=== %s ===" % s)
        r = subprocess.run([PY, os.path.join(HERE, s)], cwd=HERE)
        if r.returncode != 0:
            print("STEP FAILED: %s" % s)
            sys.exit(r.returncode)
    print("\nPIPELINE OK. Now robocopy staging -> vault:")
    print(r'  robocopy "%s\staging" "%VAULT%\01-Conversations\Telegram\Health" /E /XO' % HERE)

if __name__ == "__main__":
    main()
