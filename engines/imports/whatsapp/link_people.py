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
"""
Rail 1 (PEOPLE): deterministic match of WhatsApp DM contacts to the broader vault.
Key = phone last10 (WhatsApp jid digits) -> apple contacts.db -> vault_matches.
Fallback = fuzzy name tokens via namesearch names.db.
READ-ONLY: writes only people_matches.json (a proposal table). NO vault edits here.
"""
import sqlite3, json, io, sys, os, re, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WA_DB   = r"%IMPORTS%\whatsapp\whatsapp_train.db"
CONTACTS= r"%IMPORTS%\apple-contacts\contacts.db"
NAMES   = r"%IMPORTS%\namesearch\names.db"
WA_NOTES= r"%VAULT%\01-Conversations\WhatsApp"
OUT     = r"%IMPORTS%\whatsapp\people_matches.json"

# 1) jid -> WhatsApp note (parse frontmatter jid:, incl. list form)
wa_note_by_jid = {}
for f in glob.glob(os.path.join(WA_NOTES, "*.md")):
    base = os.path.splitext(os.path.basename(f))[0]
    if base.startswith("_"): continue
    txt = open(f, encoding="utf-8").read()[:600]
    for j in re.findall(r"(\d+)@s\.whatsapp\.net", txt):
        wa_note_by_jid[j] = base

# 2) named DMs from WhatsApp
w = sqlite3.connect(WA_DB).cursor()
dms = w.execute("select name,jid from chats where named=1 and is_group=0").fetchall()

c = sqlite3.connect(CONTACTS).cursor()
def by_phone(last10):
    cid = c.execute("select contact_id from phones where last10=? limit 1", (last10,)).fetchone()
    if not cid: return None
    cid = cid[0]
    disp = c.execute("select display from contacts where id=?", (cid,)).fetchone()
    vm = c.execute("select vault_note,tier,quality from vault_matches where contact_id=?", (cid,)).fetchone()
    return {"contact_id": cid, "display": disp[0] if disp else None,
            "vault_note": vm[0] if vm else None, "tier": vm[1] if vm else None}

n = sqlite3.connect(NAMES).cursor()
def kind_rank(p):
    """Higher = more canonical person node to link to."""
    pl = p.lower()
    if "person-" in pl: return 5                     # canonical person note
    if "platinum-crm\\leads" in pl or "platinum-crm/leads" in pl: return 4  # CRM lead
    if "personal-dms" in pl or "telegram" in pl: return 3   # cross-channel history
    if "\\contacts\\" in pl or "/contacts/" in pl: return 2 # apple contact stub
    if "moc" in pl: return 1
    return 0

def by_name(display):
    if not display: return []
    toks = [t.lower() for t in re.findall(r"[A-Za-zА-Яа-я]{4,}", display)]
    paths = {}
    for t in toks:
        for (p,) in n.execute("select distinct path from nkeys where tok=?", (t,)):
            if not p.lower().endswith(".md"): continue          # drop apple:NNNN keys
            if "01-conversations\\whatsapp" in p.lower() or "01-conversations/whatsapp" in p.lower():
                continue                                         # drop WA self-hits
            paths[p] = paths.get(p, 0) + 1
    # rank: token-hits first, then node kind
    ranked = sorted(paths.items(), key=lambda kv: (kv[1], kind_rank(kv[0])), reverse=True)
    return [(cnt, p) for p, cnt in ranked][:5]

out = []
for name, jid in dms:
    ph = jid.split("@")[0]; l10 = ph[-10:]
    wa_note = wa_note_by_jid.get(ph) or wa_note_by_jid.get(jid.split("@")[0])
    m = by_phone(l10)
    rec = {"wa_name": name, "jid": jid, "phone": ph, "wa_note": wa_note,
           "contact": m["display"] if m else None}
    if m and m["vault_note"]:
        rec.update(target=m["vault_note"], tier="T1-phone->vault", via=m["tier"])
    else:
        cands = by_name(m["display"] if m else name)
        if cands:
            best = max((p for _, p in cands), key=kind_rank)   # prefer person-note/CRM over stub
            rec.update(target=best, tier="T2-name-candidate",
                       name_candidates=[p for _, p in cands])
        else:
            rec.update(target=None, tier="T3-no-broader-node (WA note is canonical)")
    out.append(rec)

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# ASCII-safe summary to stdout; full table via the json (read separately)
from collections import Counter
tiers = Counter(r["tier"].split(" ")[0] for r in out)
print("people_matches.json written:", len(out), "DMs")
print("tiers:", dict(tiers))
