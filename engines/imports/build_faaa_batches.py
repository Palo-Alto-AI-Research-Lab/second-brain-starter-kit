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
"""FAAA Phase 3 — assemble per-lead call bundles and pack into LLM batches.

Output:
  faaa/batches/batch_NNNN.json  - input for synthesis agents
  faaa/leads_index.json         - lead_id -> {slug, display_name, ...} (stable)
  faaa/call2lead.json           - call msg_id -> lead_id  (for ledger linking)
ASCII-only stdout.
"""
import json, io, re, os
from collections import OrderedDict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

OUT = IMPORTS
BDIR = OUT + r"\faaa\batches"
os.makedirs(BDIR, exist_ok=True)

rows = [json.loads(l) for l in io.open(OUT + r"\faaa-archive.jsonl", encoding="utf-8")]
leads = json.load(io.open(OUT + r"\faaa-leads.json", encoding="utf-8"))
id2row = {r["id"]: r for r in rows}

TRANSLIT = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
    "abvgdeejziyklmnoprstufhccss y eyaABVGDEEJZIYKLMNOPRSTUFHCCSS Y EYA")
def slugify(text):
    if not text:
        return "lead"
    t = text.lower().translate(str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        "abvgdeejziyklmnoprstufhccss y eya"))
    t = re.sub(r"['`’]", "", t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    t = re.sub(r"-+", "-", t)
    return (t[:48].strip("-")) or "lead"

# stable slug per lead (provisional; render may refine but keeps this as fallback/id)
used = {}
def uniq_slug(base):
    s = base
    if s in used:
        used[base] += 1
        s = "%s-%d" % (base, used[base])
    else:
        used[base] = 1
    return s

leads_index = OrderedDict()
call2lead = {}
bundles = []
# order leads chronologically by first_date for coherent batches
leads_sorted = sorted(leads, key=lambda l: (l.get("first_date") or "9999"))
for l in leads_sorted:
    lid = l["lead_id"]
    slug = uniq_slug(slugify(l["display_name"]))
    calls = []
    for cid in l["call_ids"]:
        r = id2row.get(cid)
        if not r:
            continue
        call2lead[cid] = lid
        calls.append({
            "id": cid,
            "date": (r.get("date") or "")[:16].replace("T", " "),
            "by": r.get("sender"),
            "status": r.get("status"),
            "tema": r.get("tema"),
            "call_name": r.get("call_name"),
            "pitched_by": r.get("pitched_by"),
            "text": r.get("text"),
        })
    calls.sort(key=lambda c: c["date"])
    leads_index[str(lid)] = {
        "slug": slug,
        "display_name": l["display_name"],
        "handles": l["handles"],
        "companies": l["companies"][:4],
        "pitchers": l["pitchers"][:6],
        "n_calls": l["n_calls"],
        "first_date": (l["first_date"] or "")[:10],
        "last_date": (l["last_date"] or "")[:10],
    }
    bundles.append({
        "lead_id": lid,
        "slug": slug,
        "display_name": l["display_name"],
        "name_variants": l["name_variants"][:6],
        "handles": l["handles"],
        "companies": l["companies"][:5],
        "pitchers": l["pitchers"][:6],
        "first_date": (l["first_date"] or "")[:10],
        "last_date": (l["last_date"] or "")[:10],
        "n_calls": l["n_calls"],
        "calls": calls,
    })

# ---- reuse v1 synthesis for leads whose call-id SET is unchanged ----
SDIR2 = OUT + r"\faaa\synth2"
os.makedirs(SDIR2, exist_ok=True)
prev_sig = {}
prev_path = OUT + r"\faaa-leads-prev.json"
if os.path.exists(prev_path):
    prev_leads = json.load(io.open(prev_path, encoding="utf-8"))
    prev_calls = {l["lead_id"]: frozenset(l["call_ids"]) for l in prev_leads}
    sdir1 = OUT + r"\faaa\synth"
    if os.path.isdir(sdir1):
        for fn in os.listdir(sdir1):
            if not fn.endswith(".json"):
                continue
            try:
                for o in json.load(io.open(os.path.join(sdir1, fn), encoding="utf-8-sig")):
                    if isinstance(o, dict) and "lead_id" in o:
                        sig = prev_calls.get(int(o["lead_id"]))
                        if sig is not None:
                            prev_sig[sig] = o
            except Exception:
                pass

reused = {}          # new_lead_id -> synth obj (re-keyed)
to_synth = []
for b in bundles:
    sig = frozenset(c["id"] for c in b["calls"])
    if sig in prev_sig:
        o = dict(prev_sig[sig]); o["lead_id"] = b["lead_id"]
        reused[str(b["lead_id"])] = o
    else:
        to_synth.append(b)
io.open(SDIR2 + r"\reused.json", "w", encoding="utf-8").write(
    json.dumps(reused, ensure_ascii=False))

# clear stale batch files, then pack ONLY to-synthesize leads (~45 calls/batch)
for fn in os.listdir(BDIR):
    if fn.startswith("batch_") and fn.endswith(".json"):
        os.remove(os.path.join(BDIR, fn))
batches = []
cur, cur_calls = [], 0
for b in to_synth:
    cur.append(b); cur_calls += max(1, b["n_calls"])
    if cur_calls >= 45 or len(cur) >= 35:
        batches.append(cur); cur, cur_calls = [], 0
if cur:
    batches.append(cur)

for i, batch in enumerate(batches):
    io.open("%s\\batch_%04d.json" % (BDIR, i), "w", encoding="utf-8").write(
        json.dumps({"batch_id": i, "leads": batch}, ensure_ascii=False))
print("REUSE reused=%d to_synth_leads=%d new_batches=%d"
      % (len(reused), len(to_synth), len(batches)))

io.open(OUT + r"\faaa\leads_index.json", "w", encoding="utf-8").write(
    json.dumps(leads_index, ensure_ascii=False))
io.open(OUT + r"\faaa\call2lead.json", "w", encoding="utf-8").write(
    json.dumps(call2lead, ensure_ascii=False))

tot_calls = sum(b["n_calls"] for b in bundles)
print("DONE leads=%d batches=%d calls_in_leads=%d avg_leads/batch=%.1f"
      % (len(bundles), len(batches), tot_calls, len(bundles)/max(1,len(batches))))
