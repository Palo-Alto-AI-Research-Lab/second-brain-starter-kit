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
"""Extract notes with exploded-heading mangling (Mac exporter artifact)
into per-note files for LLM repair. Deterministic detection.
"""
import json, re
from pathlib import Path

EXPORT = Path(r"E:\Google Drive on HP Palo Alto\!_Claude_Mac16\Apple Notes Export 2026-06-11")
OUT = Path(r"%IMPORTS%\apple-notes")
MDIR = OUT / "mangled"
MDIR.mkdir(exist_ok=True)

data = json.loads((EXPORT / "notes_export.json").read_text(encoding="utf-8"))
analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
recs = {r["idx"]: r for r in analysis["notes"]}
gen = json.loads((OUT / "gen_report.json").read_text(encoding="utf-8"))

H1 = re.compile(r'^#{1,6} ?(.*)$')
affected = []
for i, n in enumerate(data["notes"]):
    md = n.get("markdown") or ""
    lines = [l for l in md.splitlines() if l.strip()]
    run, found = [], False
    for l in lines:
        m = H1.match(l)
        if m:
            run.append(m.group(1))
        else:
            run = []
        if len(run) >= 3:
            frags = sum(1 for x in run if len(x) <= 4 or (x and x[0].islower()))
            if frags >= 2:
                found = True
                break
    if found:
        affected.append(i)

# only notes that actually went into the vault (skip quarantined; dups/junk have no own file)
quar = {q["idx"] for q in gen["quarantined"]}
dups = {d["idx"] for d in gen["skipped_dups"]}
in_vault = [i for i in affected if i not in quar and i not in dups]

for i in in_vault:
    n = data["notes"][i]
    (MDIR / f"note_{i}.json").write_text(json.dumps({
        "idx": i, "title": n["title"], "slug": recs[i]["slug"],
        "markdown": n["markdown"],
    }, ensure_ascii=False, indent=1), encoding="utf-8")

(OUT / "mangled_list.json").write_text(json.dumps(in_vault), encoding="utf-8")
print("AFFECTED:", len(affected), " IN_VAULT:", len(in_vault))
print("IDX:", ",".join(map(str, in_vault)))
print("OK")
