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
r"""Merge freshly-pulled messages (raw\_new\<slug>.json) into raw\<slug>.json.

The weekly routine / manual skill writes ONLY the new messages (id > watermark)
per chat into raw\_new\<slug>.json via the Telegram MCP. This merges them into
the canonical raw\<slug>.json, deduping by message id (idempotent — re-running
with the same _new files adds nothing). Prints how many genuinely-new per chat.
ASCII-only stdout.
"""
import json, os, io

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
NEW = os.path.join(RAW, "_new")
REG = json.load(io.open(os.path.join(HERE, "chats.json"), encoding="utf-8"))
SLUGS = [c["slug"] for c in REG["chats"]]

def load(p):
    if not os.path.exists(p):
        return []
    d = json.load(io.open(p, encoding="utf-8-sig"))
    if isinstance(d, dict):
        d = d.get("results", d.get("messages", []))
    return d or []

def main():
    total_new = 0
    for slug in SLUGS:
        base_p = os.path.join(RAW, slug + ".json")
        new_p = os.path.join(NEW, slug + ".json")
        base = load(base_p)
        new = load(new_p)
        if not new:
            continue
        have = set(m.get("id") for m in base if m.get("id") is not None)
        added = [m for m in new if m.get("id") is not None and m.get("id") not in have]
        if added:
            base.extend(added)
            base.sort(key=lambda m: m.get("id", 0))
            json.dump(base, io.open(base_p, "w", encoding="utf-8"), ensure_ascii=False)
            total_new += len(added)
            print("  %-28s +%d (now %d)" % (slug, len(added), len(base)))
    print("MERGE OK total_new=%d" % total_new)
    # write a flag file the runner can read
    json.dump({"total_new": total_new}, io.open(os.path.join(HERE, "last_merge.json"), "w", encoding="utf-8"))

if __name__ == "__main__":
    main()
