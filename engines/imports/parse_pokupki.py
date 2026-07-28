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
Phase 1 parse: Pokupki (purchases) Telegram result.json -> pokupki-archive.jsonl
Roster keyed on stable from_id. Relay-footer override (Anton's dictated voice).
Status-ledger + media-kind + knowledge-candidate flags. Windows/Cyrillic: UTF-8
files only, ASCII stdout. Models parse_assistants_ops.py conventions.
"""
import re, json, os
from collections import Counter, defaultdict
from pathlib import Path
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

# Export path override for re-import (telegram-reimport skill): TG_EXPORT = the export FOLDER.
# Unset -> identical to the original hard-coded default (backward compatible).
_ENV = os.environ.get("TG_EXPORT")
SRC = (Path(_ENV) / "result.json") if _ENV else Path(os.path.expanduser(r"~\Downloads\Telegram Desktop\\Покупки ChatExport_2026-05-30 (2)\result.json"))
OUT = Path(IMPORTS)
JSONL = OUT / "pokupki-archive.jsonl"
REPORT = OUT / "pokupki-parse-report.txt"

data = json.loads(SRC.read_text(encoding="utf-8"))
MSGS = data["messages"]

# ---- roster: from_id -> (origin, role) ------------------------------------
ANTON_IDS = {"user5966672828", "user226258979", "user7303193973"}
ANNA_IDS  = {"user426601098"}
# bot that transcribes Anton's voice memos -> his content (transcription != authorship)
PAS_IDS   = {"user5305064675"}            # "Personal Audio Summary"
ASSISTANT_IDS = {
    "user211067686","user489495224","user87864031","user281413791","user7020224638",
    "user9110567260","user491984776","user3358031936","user2060931467","user587779309",
    "user4286009743","user505488052","user7301492879","user3061144566","user478891369",
    "user1007340082","user5351469091","user421440605","user338528443",
}
AI_IDS = {"user1778159120"}               # "Eliza AI Agent Manager"

def who(fid):
    if fid in ANTON_IDS or fid in PAS_IDS: return ("anton", "principal")
    if fid in ANNA_IDS:                    return ("Alina", "principal")
    if fid in ASSISTANT_IDS:               return ("mixed", "assistant")
    return ("external", "external")        # channel, AI agent, family, vendors, forwards

# ---- text rendering (str OR entity list); keep links ----------------------
def render_text(m):
    t = m.get("text", "")
    if isinstance(t, str):
        return t.strip()
    parts = []
    for seg in t:
        if isinstance(seg, str):
            parts.append(seg)
        elif isinstance(seg, dict):
            typ = seg.get("type"); txt = seg.get("text", "")
            if typ == "text_link":
                href = seg.get("href", "")
                parts.append(f"{txt} ({href})" if href and href not in txt else txt)
            else:                          # link/plain/bold/mention/hashtag/code/...
                parts.append(txt)
    return "".join(parts).strip()

# ---- relay / directive footer (Anton's voice transcribed by an assistant) --
# Disambiguate "Перевела <Name>" (relay: translated-by) from "перевела деньги"
# (transferred money) by anchoring the verb to a known relay NAME / handle / бот.
RELAY_NAME = (r"(?:бот|Полина\w*|Лен\w*|Кат\w*|Маш\w*|Арина\w*|Юли\w*|Елен\w*|"
              r"Хелен\w*|Рита\w*|Ольг\w*|Ол[яейю]|Ев\w*|Зубейде|Кейт|Инн\w*|"
              r"Маргарет|Викт\w*|Игорь\w*|@\w+)")
TRANS_RE = re.compile(rf"Перев[еёа]л[аи]?\s*:?\s*({RELAY_NAME})\b", re.I)
DELEG_RE = re.compile(r"Делегировано\b\s*:?\s*([^\n]*)")      # passive footer form only
ANNA_MARK = re.compile(r"@helper_an\b|@helper_an\b|От Алина\b|Алина просит")
# trailing footer lines to lift OUT of the body into frontmatter (metadata, not content)
FOOTER_LINE = re.compile(
    rf"^\s*(?:Перев[еёа]л[аи]?\s*:?\s*{RELAY_NAME}\b.*|Делегировано\b.*|[CС]рок\s*:.*|"
    r"Вникл[ао]\b.*|Сокращ[а-яё]*\b.*|Что дальше.*|Исполнитель\b.*)\s*$", re.I)
def strip_footer(t):
    """Cut the trailing contiguous block of footer/metadata lines off the body."""
    lines = t.split("\n")
    i = len(lines)
    while i > 0 and (FOOTER_LINE.match(lines[i-1]) or not lines[i-1].strip()):
        i -= 1
    if i >= len(lines):
        return t.strip(), None
    body = "\n".join(lines[:i]).strip()
    if not body:                       # all-footer (rare) -> keep original, no strip
        return t.strip(), None
    return body, "\n".join(lines[i:]).strip()

HAS_LINK = re.compile(r"https?://")
HAS_PRICE = re.compile(r"(\d[\d ., ]*\s*(?:€|\$|eur|евро|usd|долл|руб|₽))|"
                       r"((?:€|\$)\s*\d)|(\bцена\b)", re.I)
RULE_IN_BODY = re.compile(r"(правил[ао] в библию|пишем правило|правило по|"
                          r"новое правило|в библию\s*[:\-])", re.I)

# ---- status-ledger detector (numbered list + status words) ----------------
NUMLINE_RE = re.compile(r"^\s*(?:\d+[\.\)]|[-•*✅❌])\s*", re.M)
STATUS_RE = re.compile(r"(отгруж|апрув|approve|ищем|заказан|куплен|оплач|✅|❌|⏳|"
                       r"готов|выполн|в процессе|ждем|жду|на апруве|нет апрува|отправл)", re.I)
def is_status_ledger(t):
    lines = NUMLINE_RE.findall(t)
    return len(lines) >= 3 and len(STATUS_RE.findall(t)) >= 2

# ---- media kind ------------------------------------------------------------
def media_kind(m):
    mt = m.get("media_type")
    if mt == "voice_message": return "voice"
    if mt == "video_message": return "video_note"
    if mt in ("video_file", "animation"): return "video"
    if mt == "sticker" or "sticker_emoji" in m: return "sticker"
    if "photo" in m: return "photo"
    if "file" in m:
        mime = m.get("mime_type", "")
        if mime == "application/pdf": return "pdf"
        if mime.startswith("image/"): return "photo"
        return "file"
    if "contact_information" in m: return "contact"
    if "location_information" in m: return "location"
    if "poll" in m: return "poll"
    return None

MEDIA_DUR = lambda m: m.get("duration_seconds")

# ---- pinned target ids -----------------------------------------------------
PINNED = set()
for m in MSGS:
    if m.get("type") == "service" and m.get("action") == "pin_message":
        if m.get("message_id"): PINNED.add(m["message_id"])

# ---- build rows ------------------------------------------------------------
rows = []
for m in MSGS:
    if m.get("type") != "message":
        continue
    fid = m.get("from_id", "")
    origin, role = who(fid)
    fwd = m.get("forwarded_from")
    text = render_text(m)
    mk = media_kind(m)
    # forwarded content is NOT the poster's own words -> external (protects #anton-original)
    if fwd:
        origin, role = "external", "external"
    # relay override: a directive footer => Anton's dictated voice (transcription != authorship)
    tr = TRANS_RE.search(text); dl = DELEG_RE.search(text)
    is_dir = bool(tr or dl)
    transcribed_by = None; posted_by = None
    if is_dir and role == "assistant":
        posted_by = m.get("from")
        transcribed_by = (tr.group(1).strip() if tr else "бот")
        if ANNA_MARK.search(text):
            origin, role = "Alina", "principal"
        else:
            origin, role = "anton", "principal"
    elif fid in PAS_IDS:
        transcribed_by = "Personal Audio Summary"   # voice->text bot; content is Anton's
    # lift the structured relay footer out of the body (it's metadata, not content)
    body, footer = strip_footer(text) if is_dir else (text, None)
    n = len(body)
    # status ledger?
    statled = bool(body) and is_status_ledger(body)
    # triage bucket (on cleaned body)
    if n == 0:      bucket = "media" if mk else "empty"
    elif n < 10:    bucket = "noise"
    elif n < 200:   bucket = "frag"
    else:           bucket = "post"
    has_link = bool(HAS_LINK.search(body)); has_price = bool(HAS_PRICE.search(body))
    # knowledge-layer selection
    #  - Anton's reasoning/directives = the core knowledge (all, >=60 chars)
    #  - assistant/Alina/external = only genuine product RESEARCH (link + price/length)
    if statled:
        knowledge, note_type = False, None
    elif origin == "anton" and (bucket == "post" or (is_dir and n >= 60)):
        knowledge, note_type = True, ("directive" if is_dir else "anton-post")
    elif origin in ("mixed", "Alina", "external") and bucket == "post" \
            and has_link and has_price:
        knowledge, note_type = True, "purchase-research"
    else:
        knowledge, note_type = False, None
    rows.append({
        "id": m["id"],
        "ts": m.get("date"),
        "date": (m.get("date") or "")[:10],
        "from": m.get("from"),
        "from_id": fid,
        "origin": origin,
        "role": role,
        "reply_to": m.get("reply_to_message_id"),
        "forwarded_from": fwd,
        "media_kind": mk,
        "media_dur": MEDIA_DUR(m) if mk in ("voice", "video_note", "video") else None,
        "edited": bool(m.get("edited")),
        "pinned": m["id"] in PINNED,
        "is_directive": is_dir,
        "transcribed_by": transcribed_by,
        "posted_by": posted_by,
        "delegated_footer": footer,
        "is_status_ledger": statled,
        "is_rule_candidate": bool(RULE_IN_BODY.search(body)) or (m["id"] in PINNED and n >= 20),
        "has_link": has_link,
        "bucket": bucket,
        "knowledge": knowledge,
        "note_type": note_type,
        "text": body,
    })

# ---- write JSONL checkpoint ------------------------------------------------
with open(JSONL, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---- stats report (UTF-8 file; ASCII stdout) ------------------------------
by_origin = Counter(r["origin"] for r in rows)
by_bucket = Counter(r["bucket"] for r in rows)
know = [r for r in rows if r["knowledge"]]
know_by_origin = Counter(r["origin"] for r in know)
know_by_type = Counter(r["note_type"] for r in know)
statled_posts = sum(1 for r in rows if r["is_status_ledger"])
relay = sum(1 for r in rows if r["is_directive"] and r["origin"] == "anton")
rule_cands = sum(1 for r in rows if r["is_rule_candidate"])
fwd_ct = sum(1 for r in rows if r["forwarded_from"])
days = sorted(set(r["date"] for r in rows if r["date"]))
months = sorted(set(d[:7] for d in days))
media_kinds = Counter(r["media_kind"] for r in rows if r["media_kind"])

L = []
L.append(f"rows: {len(rows)}")
L.append(f"by_origin: {dict(by_origin)}")
L.append(f"by_bucket: {dict(by_bucket)}")
L.append(f"media_kinds: {dict(media_kinds)}")
L.append(f"status_ledger posts: {statled_posts}")
L.append(f"relay->anton (directive) msgs: {relay}")
L.append(f"forwarded msgs (->external): {fwd_ct}")
L.append(f"pinned distinct targets: {len(PINNED)}")
L.append(f"rule candidates (pinned rule-like + 'правило в библию'): {rule_cands}")
L.append(f"KNOWLEDGE notes: {len(know)}  by_origin={dict(know_by_origin)}  by_type={dict(know_by_type)}")
L.append(f"days: {len(days)}  months: {len(months)}  ({months[0]}..{months[-1]})")
# knowledge candidate length histogram
kl = sorted(len(r['text']) for r in know)
if kl:
    L.append(f"knowledge len: min{kl[0]} med{kl[len(kl)//2]} p90{kl[int(len(kl)*0.9)]} max{kl[-1]}")
REPORT.write_text("\n".join(L), encoding="utf-8")

print("ROWS", len(rows))
print("KNOWLEDGE", len(know), "by_type", dict(know_by_type))
print("BUCKETS", dict(by_bucket))
print("RELAY_ANTON", relay, "FWD", fwd_ct, "PINNED", len(PINNED), "RULECANDS", rule_cands)
print("DAYS", len(days), "MONTHS", len(months))
