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
"""Read-only: surface near-duplicate ACTIVE full-text reglament rules within each theme.
Writes a UTF-8 report file (Windows console can't print Cyrillic)."""
import re, pathlib, difflib, collections, itertools
import os
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OPS = pathlib.Path(os.path.join(_VROOT, "03-Insights", "Operations"))
REPORT = pathlib.Path(os.path.join(_IROOT, "dedup_report.txt"))
notes = []
for p in OPS.glob("reglament-*.md"):
    if p.name.startswith("reglament-card-"):
        continue
    t = p.read_text(encoding="utf-8")
    fm = {}
    m = re.search(r"^---\n(.*?)\n---", t, re.S)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"([\w-]+):\s*(.*)", line)
            if mm:
                fm[mm.group(1)] = mm.group(2).strip()
    if fm.get("status") != "active":
        continue
    rm = re.search(r"\*\*Правило:\*\*\s*(.+)", t)
    stmt = rm.group(1).strip() if rm else ""
    notes.append({"fn": p.stem, "theme": fm.get("theme", "?"), "date": fm.get("date_established", ""),
                  "origin": fm.get("origin", ""), "msg": fm.get("msg_id", ""), "stmt": stmt})

def norm(s):
    s = s.lower()
    s = re.sub(r"[^а-яёa-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

by = collections.defaultdict(list)
for n in notes:
    by[n["theme"]].append(n)

TH = 0.40
out = [f"ACTIVE full-text rules: {len(notes)}"]
total = 0
for theme, ns in sorted(by.items()):
    parent = list(range(len(ns)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    sims = {}
    for i, j in itertools.combinations(range(len(ns)), 2):
        r = difflib.SequenceMatcher(None, norm(ns[i]["stmt"]), norm(ns[j]["stmt"])).ratio()
        if r >= TH:
            parent[find(i)] = find(j)
            sims[(i, j)] = round(r, 2)
    clusters = collections.defaultdict(list)
    for i in range(len(ns)):
        clusters[find(i)].append(i)
    multi = [c for c in clusters.values() if len(c) > 1]
    if not multi:
        continue
    out.append(f"\n#### {theme} ({len(ns)} active) — {len(multi)} cluster(s)")
    for c in multi:
        total += 1
        rs = [sims[(a, b)] for a, b in itertools.combinations(sorted(c), 2) if (a, b) in sims]
        out.append(f"  --- cluster (max sim {max(rs) if rs else '?'}, {len(c)} rules) ---")
        for idx in sorted(c, key=lambda x: ns[x]["date"]):
            n = ns[idx]
            out.append(f"   [{n['date']} | {n['origin']} | msg{n['msg']}] {n['fn']}")
            out.append(f"       {n['stmt'][:200]}")
out.append(f"\nTOTAL candidate clusters: {total}")
REPORT.write_text("\n".join(out), encoding="utf-8")
print("OK report rules", len(notes), "clusters", total, "->", str(REPORT))
