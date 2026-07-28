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
r"""nightly_run.py — the СОСТАВ nightly watcher (ALL 13 topics, sensitive included).

One entry point for the scheduled job:
  1) LIVE incremental fetch of all 13 groups into sostav.db   (nightly_fetch.main)
  2) deterministic alpha detector over a rolling 3-day window  (sostav_alpha.run)
     -> private candidate report _imports\alpha\candidates\sostav-nightly-<date>-report.md

0 LLM tokens, 0 GPU. The expensive LLM-judge stage stays SEPARATE and on-demand
(/alpha-judge sostav) — cheap detector nightly, judge when Anton reviews.

⛔ HIGH SENSITIVITY: output is PRIVATE only — never outbound/public (Anton controls leakage
at the output; ingestion of everything he as a member can see is allowed).

Run:  python nightly_run.py    (system Python)
"""
import sys, asyncio, datetime
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"%IMPORTS%\sostav")

import nightly_fetch
import sostav_alpha

def main():
    # 1) fetch new messages (idempotent, auto-backfills missed nights)
    asyncio.run(nightly_fetch.main())
    # 2) detector over the last 3 days (covers a missed run or two)
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=3)).isoformat()
    until = (today + datetime.timedelta(days=1)).isoformat()
    tag = f"nightly-{today.strftime('%Y%m%d')}"
    sostav_alpha.run(since, until, 25, tag)

if __name__ == "__main__":
    main()
