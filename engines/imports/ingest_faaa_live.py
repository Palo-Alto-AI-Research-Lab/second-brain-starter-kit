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
"""FAAA LIVE incremental ingest — process new messages pulled from the Telegram
chat via MCP (faaa/faaa-new-msgs.json, MCP shape) into the existing CRM.

Steps: dedup by id vs faaa-archive.jsonl -> classify FA (RU + English + 👣/🤝) ->
extract lead @handle (regex, MCP gives plain text) -> dedup vs existing leads by
handle (NEW vs APPEND) -> emit faaa/live_bundles.json (for synth) + advance plan.
ASCII-only stdout."""
import json, io, re, os
from collections import defaultdict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"
OUT = IMPORTS
F = os.path.join(OUT, "faaa")

# ---- team / non-lead handles ----
TEAM_SUB = ["corp_acct", "plainumvc", "platinum1", "owner_alt", "aowner_alt", "work_acct_a",
            "work_acct_b", "tony_", "personal_acct", "zetaltd", "zetald", "helper_m",
            "ksplat", "lead_sc", "Nina", "Rita",
            "teammate_r", "teammate_d", "teammate_d"]  # +team handles (Rita=@teammate_r; Denis=@teammate_d/@teammate_d, internal site/outreach ops)
EMAIL_DOM = {"gmail", "yahoo", "hotmail", "outlook", "icloud", "mail", "proton",
             "gmx", "yandex", "qq", "163", "me", "live", "msn"}
def is_team(h):
    x = h.lstrip("@").lower()
    return any(s in x for s in TEAM_SUB)

RE_HANDLE = re.compile(r'(?<![\w.])@([A-Za-z][\w\d_]{3,31})')  # not preceded by word/.(email)

def handles_in(line):
    out = []
    for h in RE_HANDLE.findall(line or ""):
        if h.lower() in EMAIL_DOM:
            continue
        hh = "@" + h
        if not is_team(hh) and hh not in out:
            out.append(hh)
    return out

def is_fa(txt):
    low = txt.lower()
    return (("👣" in txt) or ("🤝" in txt and ("participant" in low or "участник" in low))
            or ("thank you for the call" in low) or ("short follow" in low)
            or ("follow-up of our call" in low) or ("follow up of our call" in low)
            or ("фоллоуап" in low) or ("фоллоу-ап" in low) or ("фоллоу ап" in low)
            or ("название звонка" in low)
            or (("участник" in low or "participants" in low) and ("договор" in low or "agreements" in low)))

def attendee_line(txt):
    for pat in (r'(?:^|\n)[^\n]*?\bParticipants?\s*:[^\n]*', r'(?:^|\n)[^\n]*?\bУчастник\w*[^\n]*',
                r'(?:^|\n)\s*Личк\w*[^\n]*'):  # allow a leading word, e.g. "Meeting participants:" — else body @handles (intro targets) leak in
        m = re.search(pat, txt, re.I)
        if m:
            return m.group(0)
    return None

# ---- existing handle -> slug index (fast, from checkpoints) ----
h2slug = {}
try:
    final = json.load(io.open(os.path.join(F, "final_slugs.json"), encoding="utf-8"))
    leads = json.load(io.open(os.path.join(OUT, "faaa-leads.json"), encoding="utf-8"))
    for l in leads:
        slug = final.get(str(l["lead_id"]), {}).get("slug")
        if slug:
            for h in l.get("handles", []):
                h2slug.setdefault(h.lower(), slug)
except Exception:
    pass
try:  # DM leads
    dmf = json.load(io.open(os.path.join(F, "dm_final_slugs.json"), encoding="utf-8"))
    nl = json.load(io.open(os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\new_leads.json"), encoding="utf-8-sig"))
    for r in nl:
        lid = "dm-" + str(r["telegram_id"])
        slug = dmf.get(lid, {}).get("slug")
        if slug and r.get("handle"):
            h2slug.setdefault(("@" + r["handle"]).lower(), slug)
except Exception:
    pass

# ---- already-imported ids ----
seen_ids = set()
for line in io.open(os.path.join(OUT, "faaa-archive.jsonl"), encoding="utf-8"):
    try: seen_ids.add(int(json.loads(line)["id"]))
    except Exception: pass

# ---- process new messages ----
data = json.load(io.open(os.path.join(F, "faaa-new-msgs.json"), encoding="utf-8"))
new = data.get("results", [])
bundles = []      # NEW leads -> synth
appends = []      # calls to append to existing card
archive_rows = []
n_fa = n_chatter = n_dup = n_internal = 0
for m in new:
    mid = int(m["id"])
    if mid in seen_ids:
        n_dup += 1; continue
    txt = (m.get("text") or "").strip()
    date = m.get("date", "")[:16].replace("T", " ")
    fa = is_fa(txt) and len(txt) >= 120
    al = attendee_line(txt)
    lead_handles = handles_in(al) if al else handles_in(txt)
    archive_rows.append({"id": mid, "date": m.get("date"), "sender": m.get("from") or m.get("sender"),
                         "cls": "call_summary" if fa else "longtext", "text": txt,
                         "lead_handles": lead_handles, "live_import": "2026-06-06"})
    if not fa:
        n_chatter += 1; continue
    n_fa += 1
    if not lead_handles:
        n_internal += 1; continue   # team-only call (no external lead) -> archived only, NOT a CRM lead card
    key_handle = lead_handles[0].lower()
    call = {"id": mid, "date": date, "by": m.get("from") or m.get("sender"), "text": txt}
    if key_handle and key_handle in h2slug:
        appends.append({"slug": h2slug[key_handle], "handle": key_handle, "call": call})
    else:
        bundles.append({"lead_key": key_handle or ("msg-%d" % mid),
                        "handles": lead_handles, "display": (lead_handles[0] if lead_handles else "lead"),
                        "calls": [call]})

# merge bundles that share a handle (same new lead, multiple calls)
merged = {}
for b in bundles:
    k = b["lead_key"]
    if k in merged:
        merged[k]["calls"] += b["calls"]
        for h in b["handles"]:
            if h not in merged[k]["handles"]: merged[k]["handles"].append(h)
    else:
        merged[k] = b
bundles = list(merged.values())

io.open(os.path.join(F, "live_bundles.json"), "w", encoding="utf-8").write(json.dumps(bundles, ensure_ascii=False, indent=1))
io.open(os.path.join(F, "live_appends.json"), "w", encoding="utf-8").write(json.dumps(appends, ensure_ascii=False, indent=1))
io.open(os.path.join(F, "live_archive_rows.json"), "w", encoding="utf-8").write(json.dumps(archive_rows, ensure_ascii=False))
print("LIVE INGEST: new_msgs=%d dup=%d FA=%d chatter=%d internal=%d | NEW_leads=%d APPEND_to_existing=%d"
      % (len(new), n_dup, n_fa, n_chatter, n_internal, len(bundles), len(appends)))
for b in bundles:
    print("  NEW lead: %s (%d call) handles=%s" % (b["display"], len(b["calls"]), b["handles"]))
