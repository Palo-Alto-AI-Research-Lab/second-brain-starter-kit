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
"""FAAA Phase 2 — lead identity resolution (deterministic dedup).

Union-find over call summaries:
  - share a non-team lead @handle  -> same lead (STRONG, exact id)
  - share full normalized lead name -> same lead (MEDIUM)
Single-token common names that collide a lot are flagged review_split.

Output: faaa-leads.json  (lead_id -> aggregate)
        faaa-cluster-stats.txt (UTF-8 human report)
"""
import json, io, re
from collections import Counter, defaultdict
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OUT = _IROOT
rows = [json.loads(l) for l in io.open(OUT + r"\faaa-archive.jsonl", encoding="utf-8")]
fa = [r for r in rows if r["cls"] == "call_summary" and (r["lead_handles"] or r["lead_name_norm"])]

# ---- union-find ----
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

for r in fa:
    find(r["id"])

# index by handle and by name
by_handle = defaultdict(list)
by_name = defaultdict(list)
for r in fa:
    for h in r["lead_handles"]:
        by_handle[h.lower()].append(r["id"])
    if r["lead_name_norm"]:
        by_name[r["lead_name_norm"]].append(r["id"])

# how common is each normalized name (collision risk for single tokens)
name_freq = Counter(r["lead_name_norm"] for r in fa if r["lead_name_norm"])

# union by handle (strong, exact id, always)
for h, ids in by_handle.items():
    for i in ids[1:]:
        union(ids[0], i)
# union by name: only multi-token full names (e.g. "Dan Marin").
# single first-names ("Alex", "Igor") are NOT merged by name alone — they only
# join via a shared handle. Safer to leave a rare lead as 2 cards than to fuse
# two different people named "Alex".
# Guard: never union by a generic/wrapper name or one that recurs absurdly often
# (a real lead name almost never exceeds ~13 calls) — that signals a parse artifact.
GENERIC_NAME = re.compile(r'\b(meeting|call|zoom|intro|discovery|minute|follow ?up|'
                          r'duplicate|platinum|incubator|anton|tony)\b', re.I)
for nm, ids in by_name.items():
    if len(nm.split()) >= 2 and not GENERIC_NAME.search(nm) and name_freq[nm] <= 15:
        for i in ids[1:]:
            union(ids[0], i)

# build clusters
clusters = defaultdict(list)
id2row = {r["id"]: r for r in fa}
for r in fa:
    clusters[find(r["id"])].append(r)

WRAP = re.compile(r'\b(meeting|intro|discovery|zoom|call|duplicate|with|between|min|minute|fund)\b', re.I)
def score_name(n):
    """Higher = more like a clean human/company lead name."""
    s = 0.0
    toks = n.split()
    if 1 <= len(toks) <= 4: s += 3
    if n[:1].isupper(): s += 1
    if "@" in n: s -= 4
    if WRAP.search(n): s -= 4
    if any(ch.isdigit() for ch in n): s -= 2
    if len(n) > 40: s -= 3
    s -= 0.02 * len(n)         # prefer concise
    return s

leads = []
for cid, members in clusters.items():
    members.sort(key=lambda r: r.get("unixtime") or "0")
    names = Counter()
    handles = Counter()
    companies = Counter()
    pitchers = Counter()
    for r in members:
        if r["lead_name"]:
            names[r["lead_name"].strip()] += 1
        for h in r["lead_handles"]:
            handles[h] += 1
        if r["tg_group"]:
            companies[r["tg_group"].strip()] += 1
        if r["pitched_by"]:
            pitchers[r["pitched_by"].strip()] += 1
    disp = (max(names, key=lambda n: (score_name(n), names[n])) if names else
            (members[0]["lead_handles"][0] if members[0]["lead_handles"] else "?"))
    norms = set(r["lead_name_norm"] for r in members if r["lead_name_norm"])
    review = any(name_freq[n] > 6 and len(n.split()) == 1 for n in norms)
    leads.append({
        "lead_id": cid,
        "display_name": disp,
        "name_variants": [n for n, _ in names.most_common()],
        "name_norms": sorted(norms),
        "handles": [h for h, _ in handles.most_common()],
        "companies": [c for c, _ in companies.most_common(8)],
        "pitchers": [p for p, _ in pitchers.most_common()],
        "call_ids": [r["id"] for r in members],
        "n_calls": len(members),
        "first_date": members[0]["date"],
        "last_date": members[-1]["date"],
        "review_split": review,
    })

leads.sort(key=lambda x: -x["n_calls"])
io.open(OUT + r"\faaa-leads.json", "w", encoding="utf-8").write(
    json.dumps(leads, ensure_ascii=False, indent=1))

# ---- report ----
dist = Counter(min(l["n_calls"], 10) for l in leads)
multi = [l for l in leads if l["n_calls"] >= 2]
rep = io.open(OUT + r"\faaa-cluster-stats.txt", "w", encoding="utf-8")
def w(s=""): rep.write(str(s) + "\n")
w("FA call summaries clustered: %d" % len(fa))
w("UNIQUE LEADS: %d" % len(leads))
w("  single-call leads : %d" % sum(1 for l in leads if l["n_calls"] == 1))
w("  multi-call leads  : %d" % len(multi))
w("  flagged review_split: %d" % sum(1 for l in leads if l["review_split"]))
w()
w("=== calls-per-lead distribution ===")
for k in sorted(dist):
    label = ("%d" % k) if k < 10 else "10+"
    w("  %-4s calls : %d leads" % (label, dist[k]))
w()
w("=== TOP 40 most-touched leads ===")
for l in leads[:40]:
    w("  %3dx  %-32s  %s  [%s..%s]%s" % (
        l["n_calls"], l["display_name"][:32],
        (l["handles"][0] if l["handles"] else "-"),
        (l["first_date"] or "?")[:10], (l["last_date"] or "?")[:10],
        "  <REVIEW>" if l["review_split"] else ""))
w()
w("=== top 30 normalized names by frequency (over-merge risk) ===")
for nm, c in name_freq.most_common(30):
    w("  %4d  %s" % (c, nm))
rep.close()
print("DONE leads=%d multi=%d review=%d"
      % (len(leads), len(multi), sum(1 for l in leads if l["review_split"])))
