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
"""Phase 2: triage + sessionize.
Reads telegram-archive.jsonl, drops media-only (audio/photo/video/file per user),
classifies text, assigns session ids (30-min gap) and month buckets.
Writes telegram-archive-classified.jsonl + triage_stats.json.
"""
import json, re
from pathlib import Path
from datetime import datetime
from collections import Counter

OUT = Path(r"E:/Obsidian/_imports")
SRC = OUT / "telegram-archive.jsonl"
GAP_MIN = 30  # session gap threshold in minutes

recs = [json.loads(l) for l in SRC.open(encoding="utf-8")]

# keep only meaningful text-bearing rows; drop service + pure media per user.
# (audio transcripts already arrive as text from "Personal Audio Summary",
#  so dropping type=='audio' placeholders loses nothing.)
URL_ONLY = re.compile(r'^\[?https?://\S+\]?(\(\S+\))?$')

kept = []
for r in recs:
    if r["type"] != "text":
        continue
    t = (r.get("text") or "").strip()
    if not t:
        continue
    n = len(t)
    if n < 10:
        cls = "noise"
    elif URL_ONLY.match(t):
        cls = "link"
    elif n >= 200:
        cls = "post"
    else:
        cls = "fragment"
    r["cls"] = cls
    r["len"] = n
    kept.append(r)

# sort chronologically (ts is ISO so lexical sort works; Nones last)
kept.sort(key=lambda r: (r.get("ts") is None, r.get("ts") or ""))

# sessionize on 30-min gaps
def parse(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S") if ts else None

session_id = 0
prev = None
for r in kept:
    ts = parse(r.get("ts"))
    if ts is None:
        r["session"] = session_id
        continue
    if prev is None or (ts - prev).total_seconds() > GAP_MIN * 60:
        session_id += 1
    r["session"] = session_id
    r["month"] = r["ts"][:7]
    prev = ts

# stats
stats = {
    "kept_text_rows": len(kept),
    "by_class": dict(Counter(r["cls"] for r in kept)),
    "sessions": session_id,
    "by_month": dict(sorted(Counter(r.get("month") for r in kept if r.get("month")).items())),
    "posts_by_month": dict(sorted(Counter(r["month"] for r in kept if r["cls"] == "post" and r.get("month")).items())),
}
# session size distribution
sess_sizes = Counter(r["session"] for r in kept)
stats["session_size_max"] = max(sess_sizes.values())
stats["sessions_over_50_msgs"] = sum(1 for v in sess_sizes.values() if v > 50)

with (OUT / "telegram-archive-classified.jsonl").open("w", encoding="utf-8") as f:
    for r in kept:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

(OUT / "triage_stats.json").write_text(
    json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

print("DONE kept=", len(kept), "sessions=", session_id)
print(json.dumps(stats["by_class"]))
