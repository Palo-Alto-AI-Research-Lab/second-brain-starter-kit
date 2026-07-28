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
"""Token-optimal step 1: collapse the ~2700 external transcript notes into the
UNIQUE set of shows/series (by `parent:`/title), so the author can be resolved
once per series, not once per note. Read-only. Stdout ASCII; report UTF-8 + JSON."""
import re, json, collections
from pathlib import Path
import os
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"
VAULT = Path(_VROOT)
ROOT = VAULT / "01-Conversations" / "_transcripts"
OUT = Path(os.path.join(_IROOT, "qqq2"))

def getk(head, key):
    m = re.search(rf"(?m)^{key}:\s*(.+?)\s*$", head)
    return m.group(1).strip().strip('"\'') if m else ""

def clean_series(title):
    t = title.strip()
    t = re.sub(r"\s*\(?(video|youtube)?\s*transcri\w+\)?\s*$", "", t, flags=re.I)
    t = re.sub(r"[-_\s]*part[-_\s]*\d+.*$", "", t, flags=re.I)
    t = re.sub(r"[-_\s]*ep\.?\s*\d+.*$", "", t, flags=re.I)
    t = re.sub(r"\s*\d{1,3}p?$", "", t)         # trailing episode numbers
    t = re.sub(r"\s*-\s*US$", "", t)
    return t.strip() or title.strip()

series = collections.defaultdict(lambda: {"count": 0, "folders": collections.Counter(),
                                          "sample_titles": [], "sample_path": "",
                                          "origins": collections.Counter()})
total = skipped_dialogue = 0
for p in ROOT.rglob("*.md"):
    rel = str(p.relative_to(VAULT))
    if "dialogues_export" in rel or "dialogues_work_acct_b" in rel:
        skipped_dialogue += 1
        continue
    try:
        with open(p, "rb") as f:
            head = f.read(3500).decode("utf-8", "ignore")
    except Exception:
        continue
    origin = getk(head, "origin")
    if origin != "external":
        continue
    total += 1
    parent = getk(head, "parent")
    title = getk(head, "title")
    # series key: parent basename if present else cleaned title
    if parent:
        key = re.sub(r"^\[\[|\]\]$", "", parent).split("|")[0].strip()
    else:
        key = clean_series(title)
    folder_top = str(p.relative_to(ROOT)).split("\\")[0]
    s = series[key]
    s["count"] += 1
    s["folders"][folder_top] += 1
    s["origins"][origin] += 1
    if title and title not in s["sample_titles"] and len(s["sample_titles"]) < 3:
        s["sample_titles"].append(title)
    if not s["sample_path"]:
        s["sample_path"] = rel

rows = sorted(series.items(), key=lambda kv: -kv[1]["count"])
rep = [f"external transcript notes: {total}; unique series: {len(series)}; dialogues skipped: {skipped_dialogue}", ""]
js = []
for key, s in rows:
    folder = s["folders"].most_common(1)[0][0]
    rep.append(f"{s['count']:5d} | [{folder}] {key}  | e.g. {s['sample_titles'][:1]}")
    js.append({"series": key, "count": s["count"], "folder": folder,
               "sample_titles": s["sample_titles"], "sample_path": s["sample_path"]})
(OUT / "series_unique.txt").write_text("\n".join(rep), encoding="utf-8")
(OUT / "series_unique.json").write_text(json.dumps(js, ensure_ascii=False, indent=1), encoding="utf-8")
print("EXTRACT OK external_notes", total, "unique_series", len(series), "dialogues_skipped", skipped_dialogue)
