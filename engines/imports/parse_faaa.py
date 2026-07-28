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
"""FAAA Follow-ups adapter — Phase 1 parser.

Source: Telegram JSON export (result.json) of the CRM call-log
  "CALLS 889 MAIN FA FAAAA follow up MAIN".
Each substantive message is a structured FA (follow-up / call summary):
  [status] Время / Группа в ТГ / Лички (lead @handles) / Общение велось /
  Тема / Название звонка / bullets / Договорились(Мы/Они) / Питчил.

Output: faaa-archive.jsonl  (one row per message, all raw + parsed fields)
        faaa-parse-stats.json  (ascii-safe stats)
ASCII-only stdout (Windows cp1252).
"""
import os
import json, io, re
from collections import Counter
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

SRC = os.path.expanduser(r"~\Downloads\Telegram Desktop\FAAA Follow ups ChatExport_2026-05-30\result.json")
OUT = IMPORTS

# ---- team / internal handles (NOT leads). Lowercased substrings. ----
TEAM_HANDLE_SUBSTR = [
    "corp_acct", "plainumvc", "platinum1", "platinumfund", "platinum_",
    "owner_alt", "aowner_alt", "work_acct_a", "work_acct_b", "tonydz", "tony_",
    "zetaltd", "zetald", "helper_m", "personal_acct", "ksplat",
    "lead_sc", "claweng", "clawrus", "eventstodaybot",
]
# exact team handles (lowercased, no @)
TEAM_HANDLE_EXACT = {
    "helper_k", "helper_e", "helper_a", "teammate_n", "helper_h",
    "frogwithgreenbelly", "gemmary",
}

def is_team_handle(h):
    x = h.lstrip("@").lower()
    if x in TEAM_HANDLE_EXACT:
        return True
    return any(s in x for s in TEAM_HANDLE_SUBSTR)

def flatten(text):
    """Telegram text field -> (plaintext, [lead-ish mentions], [links])."""
    if isinstance(text, str):
        return text, [], []
    parts, mentions, links = [], [], []
    for seg in text:
        if isinstance(seg, str):
            parts.append(seg)
        else:
            t = seg.get("type"); v = seg.get("text", "")
            parts.append(v)
            if t == "mention":
                mentions.append(v.strip())
            elif t == "mention_name":
                mentions.append(v.strip())
            elif t in ("link", "text_link"):
                links.append(seg.get("href", v))
    return "".join(parts), mentions, links

# ---- field regexes (Cyrillic, tolerant of spacing & colon presence) ----
def field(label_re, txt):
    m = re.search(r'(?:^|\n)\s*(?:\d+\s*[\.\)]\s*)?' + label_re + r'\s*:?\s*(.+)', txt, re.I)
    return m.group(1).strip() if m else None

RE_HANDLE = re.compile(r'@([A-Za-z][\w\d_]{2,31})')
RE_BULLET = re.compile(r'(?:^|\n)\s*[\-—•⁃*]\s+\S')

# names that are not a real lead -> treat as no-name (fall back to handle/group)
BAD_NAMES = {
    "intro call", "intro", "intro 1st call", "1st call", "first call",
    "follow up", "followup", "фоллоу ап", "фоллоуап", "звонок", "call",
    "vc", "fund", "b2b", "meeting", "zoom", "dev incubator", "team",
    "platinum", "platinum dev incubator", "platinum fund", "no name",
    "intro meeting", "discovery call", "zoom call", "search fund",
}
STATUS_WORDS = [
    "лид не пришёл", "лид не пришел", "лид непришел", "попросили перебукать",
    "звонок перенесен", "звонок перенесён", "перенесен", "перенесён",
    "не пришел", "не пришёл", "перебукать", "отменен", "отменён", "отмена",
    "no show", "noshow", "rescheduled",
]
# connectors that separate the lead from our side in a call name
CONNECTOR_RE = re.compile(r'\s+and\s+|\s*<>\s*|\s+x\s+|\s+х\s+|\s+et\s+|\s*\+\s*|\s+between\s+|\s+with\s+', re.I)
# a chunk that is PURELY a meeting wrapper (no lead info) -> drop it
GENERIC_CHUNK_RE = re.compile(
    r'^(?:\d+\s*(?:minute|min|минут\w*)(?:\s*(?:zoom\s*call|meeting))?|'   # "60 minute meeting"
    r'intro(?:\s*meeting|\s*call)?|discovery call|zoom call|meeting|call|'
    r'follow\s*up|фоллоу\s*ап|duplicate.*)$', re.I)
WRAP_PREFIX_RE = re.compile(
    r'^(?:\d+\s*(?:minute|min|минут\w*)(?:\s*(?:zoom\s*call|meeting))?|'
    r'intro\s*meeting|discovery call|zoom call|duplicate\s*\|?)\s+', re.I)

def is_our_side(chunk):
    """True if this call-name chunk denotes Anton/Platinum (our side), not the lead."""
    c = chunk.lower().strip(" -—:&.,\t\"❗️✨")
    if not c:
        return True
    if re.search(r'platinum|incubator|\bb2b\b|rust\s*&\s*solidity', c):
        return True
    if re.search(r'\bvc\b.*\bai\b|\bai incubator\b', c):
        return True
    # our principals: Anton Dziatkovskii / Tony / Malika (NOT a lead named "Anton X")
    if re.search(r'(anton|antony|tony)\w*[\s,].{0,25}(dziat|dzyat|diatkov|from|vc|platinum|incubator|malika)', c):
        return True
    if c in ("anton", "antony", "tony", "malika", "platinum team",
             "tony + malika", "anton dz", "anton from", "tony frm",
             "anton Dziatkovskii", "antony dzyatkovskii",
             # Platinum team principals who appear in later-era call names as our side
             "azam", "azam shaghaghi", "Madina", "Madina ash",
             "malika daulet", "zeta", "polina"):
        return True
    if re.search(r'\btony,|tony \+|✨\s*tony|✨\s*anton', c):
        return True
    return False

def extract_lead_name(call_name):
    """Extract the external lead's name by dropping our-side chunks."""
    if not call_name:
        return None
    cn = re.sub(r'[!❗️✨]+', ' ', call_name)               # strip priority/decoration
    cn = re.sub(r'\(rust\s*&\s*solidity\)', '', cn, flags=re.I)
    cn = re.sub(r'^\s*\d+\s*[\.\)]\s*', '', cn)            # leading "3."
    parts = [p.strip(" -—:&.,\t\"'<>") for p in CONNECTOR_RE.split(cn)]
    lead_parts = [p for p in parts if p and not is_our_side(p)
                  and not GENERIC_CHUNK_RE.match(p) and p.lower() not in BAD_NAMES]
    if not lead_parts:
        return None
    cand = WRAP_PREFIX_RE.sub('', lead_parts[0]).strip(" -—:&.,\t\"'<>")
    if not cand or len(cand) < 2:
        return None
    if cand.lower() in BAD_NAMES or 'platinum' in cand.lower():
        return None
    return cand

def norm_name(name):
    if not name:
        return None
    x = name.lower()
    x = re.sub(r'https?://\S+', ' ', x)
    x = re.sub(r'[^\w\s]', ' ', x, flags=re.UNICODE)   # drop punctuation/emoji
    x = re.sub(r'\s+', ' ', x).strip()
    # drop trailing company connectors
    x = re.sub(r'\b(team|inc|ltd|llc|ventures?|capital|labs?|protocol|finance|games?)\b', '', x).strip()
    x = re.sub(r'\s+', ' ', x).strip()
    return x or None

def lead_handles_from_lichki(lichki_line, obshenie_line, mentions):
    """Lead's @handles = Telegram-TYPED mentions on the Лички line (team-filtered).

    Using typed mentions (not a regex over text) avoids scraping email domains
    like '@gmail'/'@yahoo' which are NOT mentions in the export.
    """
    cand = [m for m in mentions if m.startswith("@")]
    if lichki_line:
        src = [m for m in cand if m in lichki_line]
    else:  # no Лички line: take mentions not on the "Общение велось" line
        src = [m for m in cand if not (obshenie_line and m in obshenie_line)]
    out, seen = [], set()
    for m in src:
        if is_team_handle(m) or m.lower() in seen:
            continue
        seen.add(m.lower()); out.append(m)
    return out

# ---------------------------------------------------------------
d = json.load(io.open(SRC, encoding="utf-8"))
msgs = d["messages"]
rows = []
stats = Counter()

for m in msgs:
    if m.get("type") == "service":
        stats["service"] += 1
        rows.append({"id": m["id"], "date": m.get("date"), "type": "service",
                     "cls": "service", "text": "", "action": m.get("action")})
        continue

    txt, mentions, links = flatten(m.get("text", ""))
    txt = txt.replace(" ", " ")
    txt_s = txt.strip()
    low = txt.lower()

    # media flags
    is_media = bool(m.get("media_type") or m.get("photo") or m.get("file"))
    media_kind = m.get("media_type") or ("photo" if m.get("photo") else ("file" if m.get("file") else None))

    # parsed FA fields
    vremya     = field(r'Врем\w*', txt)
    tg_group   = field(r'Групп\w*\s+в\s+ТГ', txt)
    obshenie   = field(r'Общени\w*\s+велось', txt)
    tema       = field(r'Тема', txt)
    call_name  = field(r'Назван\w*\s+звонка', txt)
    pitched    = field(r'Питчил\w*', txt) or field(r'Питчинг', txt)
    # лички / общение lines (full line text, for handle attribution)
    lm = re.search(r'(?:^|\n)\s*Личк\w*[^\n]*', txt, re.I)
    lichki_line = lm.group(0) if lm else None
    om = re.search(r'(?:^|\n)\s*Общени\w*\s+велось[^\n]*', txt, re.I)
    obshenie_line = om.group(0) if om else None

    # English "Short follow-up" format (2024 H2 -> 2026): Thank you for the call /
    # Short follow-up / Participants: <lead @handle>, Platinum VC: ... / Promised
    is_eng_fa = (("thank you for the call" in low) or ("short follow-up" in low)
                 or ("short followup" in low) or ("\U0001F463" in txt)   # 👣 footprints
                 or ("follow-up of our call" in low) or ("follow up of our call" in low)
                 or ("фоллоуап" in low) or ("фоллоу-ап" in low) or ("фоллоу ап" in low)
                 or (("participants:" in low or "участник" in low)
                     and ("\U0001F91D" in txt or "promised" in low or "agreements" in low
                          or "договор" in low or "platinum.fund" in low
                          or "about platinum" in low or "about vc" in low)))
    participants_line = None
    if is_eng_fa:
        pm = re.search(r'(?:^|\n)\s*Participants?\s*:[^\n]*', txt, re.I)
        participants_line = pm.group(0) if pm else None
        if not call_name:                       # title line = first line before the signature
            for ln in txt.split("\n"):
                s2 = ln.strip()
                if not s2:
                    continue
                sl = s2.lower()
                if s2.startswith("🙌") or "thank you for the call" in sl \
                        or sl.startswith("short follow") or sl.startswith("participants"):
                    break
                call_name = s2
                break

    lead_handles = lead_handles_from_lichki(lichki_line or participants_line, obshenie_line, mentions)
    lead_name = extract_lead_name(call_name)
    # fallback lead name from group "<X> <> Platinum"
    if not lead_name and tg_group:
        g = re.split(r'<>|x platinum|х platinum|\bplatinum\b|cheesus', tg_group, flags=re.I)[0]
        g = g.strip(" -—:<>").strip()
        if g and len(g) > 1:
            lead_name = g

    n_bullets = len(RE_BULLET.findall(txt))
    has_dogovor = ("договор" in low) or ("\nмы:" in low) or ("\nони:" in low) or ("от нас" in low) or ("от не" in low)

    # ---- classify ----
    status = None
    for sw in STATUS_WORDS:
        if sw in low:
            status = sw
            break

    is_fa = bool(call_name or is_eng_fa or (tema and (lichki_line or n_bullets >= 1)) or
                 (lichki_line and (n_bullets >= 2 or has_dogovor)))
    if is_media and len(txt_s) < 10:
        cls = "media_only"
    elif len(txt_s) < 8:
        cls = "noise"
    elif is_fa:
        cls = "call_summary"
    elif len(txt_s) < 220:
        cls = "fragment"
    else:
        cls = "longtext"   # >=220 chars but no FA structure (process notes, long chatter)
    stats[cls] += 1

    rows.append({
        "id": m["id"],
        "date": m.get("date"),
        "unixtime": m.get("date_unixtime"),
        "sender": m.get("from"),
        "from_id": m.get("from_id"),
        "edited": bool(m.get("edited")),
        "reply_to": m.get("reply_to_message_id"),
        "fwd": m.get("forwarded_from"),
        "media": media_kind,
        "type": "message",
        "cls": cls,
        "status": status,
        "text": txt_s,
        "links": links,
        "mentions": mentions,
        # parsed FA fields
        "vremya": vremya,
        "tg_group": tg_group,
        "obshenie": obshenie,
        "tema": tema,
        "call_name": call_name,
        "pitched_by": pitched,
        "lead_name": lead_name,
        "lead_name_norm": norm_name(lead_name),
        "lead_handles": lead_handles,
        "n_bullets": n_bullets,
        "has_dogovor": has_dogovor,
    })

# write JSONL
with io.open(os.path.join(OUT, "faaa-archive.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# stats (ascii-safe)
fa = [r for r in rows if r["cls"] == "call_summary"]
with_handle = sum(1 for r in fa if r["lead_handles"])
with_name = sum(1 for r in fa if r["lead_name_norm"])
with_either = sum(1 for r in fa if r["lead_handles"] or r["lead_name_norm"])
report = {
    "total": len(rows),
    "by_class": dict(stats),
    "fa_count": len(fa),
    "fa_with_lead_handle": with_handle,
    "fa_with_lead_name": with_name,
    "fa_with_either_key": with_either,
    "fa_with_neither": len(fa) - with_either,
}
io.open(os.path.join(OUT, "faaa-parse-stats.json"), "w", encoding="utf-8").write(
    json.dumps(report, ensure_ascii=False, indent=2))
print("DONE rows=%d fa=%d handle=%d name=%d either=%d neither=%d"
      % (len(rows), len(fa), with_handle, with_name, with_either, len(fa)-with_either))
