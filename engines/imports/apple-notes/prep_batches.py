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
"""Split the 649 notes into triage batch files for workflow agents.
Each batch: ~25 notes, body truncated to 3500 chars. UTF-8 JSON.
"""
import json
from pathlib import Path

EXPORT = Path(r"E:\Google Drive on HP Palo Alto\!_Claude_Mac16\Apple Notes Export 2026-06-11")
OUT = Path(r"%IMPORTS%\apple-notes")
BATCH_DIR = OUT / "triage_batches"
BATCH_DIR.mkdir(exist_ok=True)

data = json.loads((EXPORT / "notes_export.json").read_text(encoding="utf-8"))
analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
recs = {r["idx"]: r for r in analysis["notes"]}

BATCH = 25
notes = data["notes"]
n_batches = 0
for start in range(0, len(notes), BATCH):
    batch = []
    for i in range(start, min(start + BATCH, len(notes))):
        n = notes[i]
        r = recs[i]
        md = (n.get("markdown") or "")
        body = md[:3500]
        truncated = len(md) > 3500
        batch.append({
            "idx": i,
            "title": n.get("title"),
            "created": r["created"],
            "modified": r["modified"],
            "body_len": r["body_len"],
            "lang": r["lang"],
            "attachments": r["attachments"],
            "regex_secret_flags": r["secrets"],
            "is_exact_dup_of": r["dup_of"],
            "body": body,
            "body_truncated": truncated,
        })
    fn = BATCH_DIR / f"batch_{start//BATCH:02d}.json"
    fn.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    n_batches += 1

print("BATCHES:", n_batches, "NOTES:", len(notes))
print("OK")
