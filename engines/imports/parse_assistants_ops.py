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
Assistants-Ops Telegram import -- TEST SAMPLE build (messages71-73).
Two-layer output into staging/ (never the live vault):
  Layer 1  -> 03-Insights/Operations/reglament-*.md   (atomic rules)
  Layer 2  -> 01-Conversations/Telegram/Assistants-Ops/sessions/Sessions-YYYY-MM-DD.md
Provenance: anton's rules/tasks = origin:anton (#anton-original);
            Alina's = origin:Alina (#origin-Alina); assistants = origin:mixed.
Windows/Cyrillic: all output is UTF-8 files; stdout stays ASCII (counts only).
"""
import re, json, html, hashlib, os
from pathlib import Path
from datetime import datetime
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

# Export FOLDER override for re-import (telegram-reimport skill). Unset -> original default.
SRC = Path(os.environ.get("TG_EXPORT", os.path.expanduser(r"~\Downloads\Telegram Desktop\ChatExport_2026-05-30")))
# all 73 pages in natural order: messages.html, messages2.html ... messages73.html
def _pagenum(name):
    m = re.search(r"messages(\d*)\.html", name)
    return int(m.group(1)) if m and m.group(1) else 0
FILES = sorted((p.name for p in SRC.glob("messages*.html")), key=_pagenum)
OUT = Path(IMPORTS)
STAGE = OUT / "staging"
RULES_DIR = STAGE / "03-Insights" / "Operations"
LEDGER_DIR = STAGE / "01-Conversations" / "Telegram" / "Assistants-Ops" / "sessions"
CHAT_DIR = STAGE / "01-Conversations" / "Telegram" / "Assistants-Ops"
for d in (RULES_DIR, LEDGER_DIR, CHAT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- sender -> (origin, role) ---------------------------------------------
# Anton (the voice principal) across his several accounts:
ANTON_ACCTS = {
    "Tony frm Palo Alto Ai Research lab", "Anton Dziatkovskii 2023",
    "Tony 📍Silicon Valley 🇺🇸 VC &amp; Ai Incubator📍Bay Area",
    "Personal Audio Summary",
}
# Alina (the other principal) across her accounts:
ANNA_ACCTS = {
    "Alina Dz", "01 Alina AAAAA АААААА 01 Dziatkovskaia", "Алина",
}
# The rotating assistant team over the years (current + former):
ASSISTANT_ACCTS = {
    "Helena Kondricheva Tickets 77", "Oksana Assistant",
    "Ekaterina Lavrenyuk Assistant Екатерина Лавренюк", "Anastasiia assistent",
    "Yuliya", "Ecaterina Klimbovskaya", "Eva Alina",
    "Rita Vasilieva Assistance", "Inna", "Zubeyde", "Olya Tkalich",
    "Alice-Mariia Aesir", "Evgeniya Kazantseva", "Varvara Boger", "Kate",
    "Julia | Executive Search", "Катерина Рудакова", "Evgeniia Vialaya",
    "Maria Assistent", "Margaret", "Виктория", "Екатерина", "Anastasia_Betsy",
    "Tatyana", "Iryna", "Maria", "Elena OTC",
}
def who(name):
    n = (name or "").strip()
    if n in ANTON_ACCTS:     return ("anton", "principal")
    if n in ANNA_ACCTS:      return ("Alina",  "principal")
    if n in ASSISTANT_ACCTS: return ("mixed", "assistant")
    return ("external", "external")  # channels, vendors, contractors, one-offs

# transliteration map (Cyrillic -> latin kebab)
_MAP = {
 'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
 'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
 'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts',
 'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slugify(text, maxlen=55):
    t = (text or "").lower()
    out = []
    for ch in t:
        out.append(_MAP.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "rule"

# ---- HTML helpers ----------------------------------------------------------
A_RE = re.compile(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', re.S)
def dehtml(s):
    if s is None: return ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    def a_sub(m):
        href, txt = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href.startswith("http") and href not in txt:
            return f"{txt} ({href})" if txt else href
        return txt
    s = A_RE.sub(a_sub, s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return s.strip()

def parse_ts(title):
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})", title or "")
    if not m: return None, None
    d, mo, y, hh, mm, ss = m.groups()
    iso = f"{y}-{mo}-{d}T{hh}:{mm}:{ss}"
    return iso, f"{y}-{mo}-{d}"

# ---- parse -----------------------------------------------------------------
rows = []
last_sender = None
for fn in FILES:
    raw = (SRC / fn).read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r'(?=<div class="message (?:default|service))', raw)
    for b in blocks:
        mid = re.search(r'id="message-?(\d+)"', b)
        is_service = b.startswith('<div class="message service')
        if is_service:
            last_sender = last_sender  # date dividers / pins -> ignore, keep sender
            continue
        joined = 'class="message default clearfix joined"' in b
        fn_m = re.search(r'<div class="from_name">\s*(.*?)\s*</div>', b, re.S)
        if fn_m:
            nm = fn_m.group(1)
            nm = nm.split("<")[0].strip()
            last_sender = nm
        sender = last_sender if joined or not fn_m else last_sender
        date_m = re.search(r'<div class="pull_right date details" title="([^"]+)"', b)
        iso, day = parse_ts(date_m.group(1) if date_m else "")
        text_m = re.search(r'<div class="text">\s*(.*?)\s*</div>\s*(?:<span class="reactions"|</div>)', b, re.S)
        text = dehtml(text_m.group(1)) if text_m else ""
        reply_m = re.search(r'go_to_message(\d+)', b) if 'reply_to details' in b else None
        reply_to = reply_m.group(1) if reply_m else None
        media = sorted(set(re.findall(r'media_(voice_message|photo|file|video_message|video_file|animation)', b)))
        if not mid and not text and not media:
            continue
        origin, role = who(sender)
        rows.append({
            "id": mid.group(1) if mid else None,
            "file": fn, "ts": iso, "date": day, "sender": sender,
            "origin": origin, "role": role, "reply_to": reply_to,
            "media": media, "text": text,
        })

# ---- classify into streams -------------------------------------------------
REPORT_RE = re.compile(r"Отч[её]т\s*за|^Не?\s*на смене|Total:\s|\d+\s*ч\s*\d+\s*мин", re.M)
PLAN_RE   = re.compile(r"^На смене.*План|Планы:", re.S)
RULE_RE   = re.compile(r"^\s*Правил[оа]\b|Правило в Библию|Правило в регламент|в Библию\s*:")
TASK_RE   = re.compile(r"Делегировано")

def classify(r):
    t = r["text"]
    if not t:
        return "media" if r["media"] else "empty"
    if REPORT_RE.search(t): return "report"
    if RULE_RE.search(t):   return "rule"
    if PLAN_RE.search(t):   return "plan"
    if TASK_RE.search(t):   return "task"
    if len(t) < 12:         return "noise"
    return "chatter"

# footer fields (translator / delegated / status)
# broad: catches Перевела/Перевел/Перевала/Перевелаа typos, stops at newline or tag
TRANS_RE = re.compile(r"Перев[а-яё]*:\s*([^\n<]+)")
DELEG_RE = re.compile(r"Делегировано:\s*([^\n]+)")
# Alina authors a directive ONLY via her own account/handle or an explicit source
# phrase. Generic "задача Алина" = a task in Alina's domain, NOT Alina authoring it.
ANNA_MARK = re.compile(r"@helper_an\b|@helper_an\b|От Алина\b|Алина просит")
def footer(t):
    tr = TRANS_RE.search(t); dl = DELEG_RE.search(t)
    return (tr.group(1).strip() if tr else None,
            dl.group(1).strip() if dl else None)

# PROVENANCE FIX: a message carrying the bot-relay footer ("Перевёл: бот",
# "Перевела: Полина") and/or "Делегировано:" is a VOICE-PRINCIPAL DIRECTIVE.
# Anton dictates by voice -> bot/assistant transcribes & posts it (often as a
# "joined" message under the assistant's name). The IDEA is Anton's, so
# origin:anton + authored_by:human, with the poster/translator in transcribed_by.
# Alina types her own directives under her name -> origin:Alina.
for r in rows:
    tr, dl = footer(r["text"])
    is_dir = bool(dl) or bool(tr)
    r["is_directive"] = is_dir
    r["relayed_by"] = tr or ("бот" if is_dir else None)
    r["poster"] = r["sender"]
    if is_dir:
        if r["sender"] == "Alina Dz" or ANNA_MARK.search(r["text"]):
            r["origin"], r["role"] = "Alina", "principal"
        else:
            r["origin"], r["role"] = "anton", "principal"

for r in rows:
    r["stream"] = classify(r)

# ---- write JSONL checkpoint -----------------------------------------------
with open(OUT / "assistants-ops-sample.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---- Layer 1: export rule CANDIDATES (curated later by the LLM pass) -------
def yaml_esc(s): return (s or "").replace('"', "'").replace("\n", " ")
rule_candidates = []
for r in rows:
    if r["stream"] != "rule": continue
    body = r["text"]
    tr, dl = footer(body)
    core = re.split(r"\n\s*(?:Перев[её]л|Делегировано|Срок)", body)[0].strip()
    core = re.sub(r"^\s*Правил[оа]\b[^:\n]*:\s*", "", core).strip()
    rule_candidates.append({
        "id": r["id"], "date": r["date"], "sender": r["sender"],
        "origin_guess": r["origin"], "role": r["role"],
        "is_directive": r.get("is_directive", False),
        "relayed_by": r.get("relayed_by"), "delegated": dl,
        "text": core, "raw": body,
    })
(OUT / "rule_candidates.json").write_text(
    json.dumps(rule_candidates, ensure_ascii=False, indent=1), encoding="utf-8")
rule_notes = []  # filled by build_rules.py after curation

# ---- Layer 2: day ledgers --------------------------------------------------
from collections import defaultdict, Counter
by_day = defaultdict(list)
for r in rows:
    if r["date"]: by_day[r["date"]].append(r)

ICON = {"rule":"\U0001F4D6 ПРАВИЛО","task":"\U0001F4CB Задача",
        "report":"\U0001F4CA Отчёт","plan":"\U0001F5D3 План",
        "chatter":"\U0001F4AC","reference":"\U0001F517","media":"\U0001F4CE медиа",
        "noise":"·","empty":"·"}
ROLE_TAG = {"principal":"ПРИНЦИПАЛ","assistant":"ассистент","external":"внешний"}
for day, msgs in sorted(by_day.items()):
    sc = Counter(m["stream"] for m in msgs)
    parts = sorted(set(m["sender"] for m in msgs if m["sender"]))
    fm = [
        "---", "type: session-ledger", "source: telegram-assistants-ops",
        'chat: "Assistants-Ops"', f"date: {day}", f"month: {day[:7]}",
        f"message_count: {len(msgs)}",
        "origin: mixed", "authored_by: human",
        "tags: [telegram, assistants-ops, session]",
        "---", "", f"# Смена {day}", "",
        f"> {len(msgs)} сообщений · потоки: " +
        ", ".join(f"{k}:{v}" for k, v in sc.most_common()) , "",
    ]
    # (rule cross-links are appended by build_rules.py after LLM curation)
    fm.append("---")
    for m in msgs:
        if m["stream"] in ("noise", "empty") and not m["text"]:
            continue
        tlabel = ICON.get(m["stream"], m["stream"])
        tm = (m["ts"] or "")[11:16]
        rl = ROLE_TAG.get(m["role"], m["role"])
        if m.get("is_directive") and m["origin"] in ("anton", "Alina"):
            principal = "Антона" if m["origin"] == "anton" else "Алина"
            rl = f"директива {principal} · через {m.get('poster','')}"
        head = f"\n**{tm} · {m['sender']}** _({rl})_ — {tlabel}"
        if m["reply_to"]:
            head += f"  ↳ ответ на #{m['reply_to']}"
        fm.append(head)
        if m["media"]:
            fm.append(f"_[{', '.join(m['media'])} — не выгружено]_")
        if m["text"]:
            quoted = "\n".join("> " + ln for ln in m["text"].split("\n"))
            fm.append(quoted)
    (LEDGER_DIR / f"Sessions-{day}.md").write_text("\n".join(fm) + "\n", encoding="utf-8")

# ---- chat MOC (Bible MOC + concept hub are built by build_rules.py) -------
months = sorted(set(d[:7] for d in by_day))
moc = ["---", "type: moc", 'title: "Assistants-Ops — чат ассистентов"',
       "tags: [moc, assistants-ops]", "---", "",
       "# Assistants-Ops — MOC", "",
       f"> {len(rows)} сообщений · {len(by_day)} дней · {len(months)} месяцев", "",
       "Рабочий чат с ассистентами (бытовые вопросы) + Библия регламентов.", "",
       "## База знаний", "",
       "- [[_Operations-Bible-MOC]] — все регламенты (Библия)",
       "- [[_Bible-Trello-Index]] — формализованные карточки Trello",
       "- [[concept-bible-platinum]] — свод регламентов (Holy Bible)", "",
       "## Смены по месяцам", ""]
by_month = defaultdict(list)
for d in by_day: by_month[d[:7]].append(d)
for mo in months:
    days = sorted(by_month[mo])
    cnt = sum(len(by_day[d]) for d in days)
    moc.append(f"- **{mo}** — {len(days)} дней, {cnt} сообщ.: " +
               " · ".join(f"[[Sessions-{d}\\|{d[8:]}]]" for d in days))
(CHAT_DIR / "_Assistants-Ops-MOC.md").write_text("\n".join(moc) + "\n", encoding="utf-8")

# ---- stats report (UTF-8 file; stdout ASCII) ------------------------------
sc = Counter(r["stream"] for r in rows)
rolec = Counter(r["role"] for r in rows)
og = Counter(c["origin_guess"] for c in rule_candidates)
rep = {
    "messages_parsed": len(rows), "days": len(by_day), "months": len(months),
    "streams": dict(sc), "roles": dict(rolec),
    "rule_candidates": len(rule_candidates),
    "rule_candidate_origins": dict(og), "ledgers_written": len(by_day),
}
(OUT / "assistants-ops-report.json").write_text(
    json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

print("PARSED_MESSAGES", len(rows))
print("DAYS", len(by_day), "MONTHS", len(months))
print("RULE_CANDIDATES", len(rule_candidates))
print("STREAMS", dict(sc))
print("ROLES", dict(rolec))
print("STAGING", str(STAGE))
