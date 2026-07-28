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
Phase 3 generate: pokupki-archive.jsonl -> staging tree.
Layer 2 archive: sessions/Sessions-YYYY-MM-DD.md (reply-threaded, role-iconed,
                 media placeholders; non-knowledge raw text lives here - 1 copy).
Layer 1 knowledge: posts/YYYY-MM-DD-slug.md (full raw text - 1 copy - + provenance).
Rule 5 honoured: a knowledge message's raw text lives only in its note (the ledger
shows a <=150-char preview + link); every other message's raw lives only in the ledger.
UTF-8 files only; ASCII stdout.
"""
import re, json
from collections import defaultdict, Counter
from pathlib import Path
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

OUT = Path(_IROOT)
STAGE = OUT / "staging_pokupki"
CHAT_DIR = STAGE / "01-Conversations" / "Telegram" / "Pokupki"
LEDGER_DIR = CHAT_DIR / "sessions"
POSTS_DIR = CHAT_DIR / "posts"
for d in (LEDGER_DIR, POSTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

rows = [json.loads(l) for l in (OUT / "pokupki-archive.jsonl").read_text(encoding="utf-8").splitlines()]
by_id = {r["id"]: r for r in rows}

# ---- translit slug ---------------------------------------------------------
_MAP = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z',
 'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s',
 'т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'',
 'ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slugify(text, maxlen=55):
    t = (text or "").lower().strip()
    t = t.split("\n")[0]
    s = "".join(_MAP.get(ch, ch) for ch in t)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "post"

def yaml_esc(s):
    return (s or "").replace('"', "'").replace("\n", " ").strip()

# ---- icons / labels --------------------------------------------------------
def role_icon(r):
    o = r["origin"]
    if o == "anton": return "\U0001F7E2"   # green
    if o == "Alina":  return "\U0001F535"   # blue
    if r["role"] == "assistant": return "⚪"  # white
    return "⚫"                          # black (external)
ROLE_WORD = {"anton":"Антон","Alina":"Алина","assistant":"ассистент","external":"внешний"}
def role_word(r):
    if r["origin"] == "anton": return "Антон"
    if r["origin"] == "Alina": return "Алина"
    if r["role"] == "assistant": return "ассистент"
    return "внешний"

def media_label(r):
    mk = r["media_kind"]; dur = r.get("media_dur")
    if not mk: return None
    if mk == "voice":      return f"\U0001F3A4 голосовое{(' '+str(dur)+'s') if dur else ''} _[не транскрибировано]_"
    if mk == "video_note": return f"\U0001F4F9 видео-кружок{(' '+str(dur)+'s') if dur else ''} _[не выгружено]_"
    if mk == "video":      return "\U0001F39E️ видео _[не выгружено]_"
    if mk == "photo":      return "\U0001F5BC️ фото _[не выгружено]_"
    if mk == "pdf":        return "\U0001F4C4 PDF _[не выгружено]_"
    if mk == "file":       return "\U0001F4CE файл _[не выгружено]_"
    if mk == "contact":    return "\U0001F464 контакт"
    if mk == "location":   return "\U0001F4CD геолокация"
    if mk == "poll":       return "\U0001F4CA опрос"
    if mk == "sticker":    return None
    return None

def snippet(r, n=70):
    if r["text"]:
        s = re.sub(r"\s+", " ", r["text"]).strip()
        return (s[:n] + "…") if len(s) > n else s
    ml = media_label(r)
    return re.sub(r"\s*_\[.*?\]_", "", ml).strip() if ml else "—"

DELEG_AT = re.compile(r"@\w+")
SROK_RE = re.compile(r"[CС]рок\s*:\s*([^\n]+)")
def delegated_to(r):
    f = r.get("delegated_footer") or ""
    m = DELEG_AT.search(f)
    return m.group(0) if m else None
def srok(r):
    f = r.get("delegated_footer") or ""
    m = SROK_RE.search(f)
    if not m:
        return None
    v = m.group(1).strip()
    # stop at the next footer marker on the same line; reject non-deadline noise
    v = re.split(r"\s*(?:Вникл|Сокращ|Делегир|Перев)[а-яё]*\b", v)[0].strip()
    if len(v) < 3 or re.match(r"^(да|нет|-+|—)$", v, re.I):
        return None
    return v[:60]

# ---- assign collision-safe filenames to knowledge rows ---------------------
used = set()
id2post = {}
for r in sorted([r for r in rows if r["knowledge"]], key=lambda r: (r["date"], r["id"])):
    base = f"{r['date']}-{slugify(r['text'])}"
    stem = base; k = 2
    while stem in used:
        stem = f"{base}-{k}"; k += 1
    used.add(stem); id2post[r["id"]] = stem

# ---- authored_by per origin ------------------------------------------------
def authored_by(r):
    if r["origin"] == "anton": return "human"      # his voice/words (transcription != authorship)
    if r["origin"] == "Alina":  return "human"
    return "hybrid"                                  # assistant-compiled / external unknown

def post_tags(r):
    t = ["telegram", "pokupki", "покупки"]
    if r["origin"] == "anton": t.append("anton-original")
    if r["origin"] == "Alina":  t.append("Alina")
    if r["note_type"] == "purchase-research": t.append("purchase-research")
    if r["note_type"] == "directive": t.append("директива")
    if r["pinned"]: t.append("pinned")
    return t

def value_score(r):
    v = 0.6 if r["origin"] == "anton" else 0.4
    if r["pinned"]: v += 0.1
    return round(min(v, 0.9), 2)

# ---- generate POST notes ---------------------------------------------------
posts_written = 0
for r in rows:
    if not r["knowledge"]:
        continue
    stem = id2post[r["id"]]
    title = yaml_esc(r["text"].split("\n")[0][:80]) or f"Покупки #{r['id']}"
    fm = ["---",
          f'title: "{title}"',
          "type: telegram-post",
          f"note_type: {r['note_type']}",
          "source: telegram-pokupki",
          'chat: "Покупки"',
          f'author: "{yaml_esc(r["from"])}"',
          f"from_id: {r['from_id']}",
          f"authored_by: {authored_by(r)}",
          f"origin: {r['origin']}",
          f"date: {r['ts']}",
          f"msg_id: {r['id']}",
          f'session: "[[Sessions-{r["date"]}]]"',
          f"month: {r['date'][:7]}",
          f"pinned: {str(r['pinned']).lower()}",
          f"is_directive: {str(r['is_directive']).lower()}"]
    if r.get("transcribed_by"): fm.append(f'transcribed_by: "{yaml_esc(r["transcribed_by"])}"')
    if r.get("posted_by"):      fm.append(f'posted_by: "{yaml_esc(r["posted_by"])}"')
    dto = delegated_to(r)
    if dto: fm.append(f'delegated_to: "{dto}"')
    sk = srok(r)
    if sk: fm.append(f'deadline: "{yaml_esc(sk)}"')
    if r.get("forwarded_from"): fm.append(f'forwarded_from: "{yaml_esc(r["forwarded_from"])}"')
    if r.get("reply_to"):       fm.append(f"reply_to: {r['reply_to']}")
    fm += [f"has_link: {str(r['has_link']).lower()}",
           "concept: ",                       # filled by concept-mapping pass
           f"tags: [{', '.join(post_tags(r))}]",
           f"value_score: {value_score(r)}",
           "---", ""]
    body = [r["text"], ""]
    # provenance line for relayed voice
    if r["is_directive"] and r["origin"] == "anton":
        prov = "> _Голос Антона"
        if r.get("transcribed_by"): prov += f", транскрибировал(а): {r['transcribed_by']}"
        if dto: prov += f" · делегировано {dto}"
        if sk: prov += f" · срок: {sk}"
        prov += "_"
        body += [prov, ""]
    # back-links + reply context
    body.append("## Контекст")
    body.append(f"- День: [[Sessions-{r['date']}]] · сообщение #{r['id']} в чате «Покупки»")
    rt = r.get("reply_to")
    if rt and rt in by_id:
        p = by_id[rt]
        link = f" → [[{id2post[rt]}]]" if rt in id2post else ""
        body.append(f"- В ответ на [{role_word(p)} {p['from']}]: «{snippet(p)}»{link}")
    (POSTS_DIR / f"{stem}.md").write_text("\n".join(fm + body) + "\n", encoding="utf-8")
    posts_written += 1

# ---- generate DAY LEDGERS --------------------------------------------------
by_day = defaultdict(list)
for r in rows:
    if r["date"]:
        by_day[r["date"]].append(r)

PREVIEW = 150
ledgers_written = 0
for day, msgs in sorted(by_day.items()):
    msgs = sorted(msgs, key=lambda r: r["id"])
    parts = sorted(set(m["from"] for m in msgs if m["from"]))
    oc = Counter(m["origin"] for m in msgs)
    nk = sum(1 for m in msgs if m["knowledge"])
    nvoice = sum(1 for m in msgs if m["media_kind"] == "voice")
    fm = ["---", "type: session-ledger", "source: telegram-pokupki",
          'chat: "Покупки"', f"date: {day}", f"month: {day[:7]}",
          f"message_count: {len(msgs)}", f"knowledge_posts: {nk}",
          f"voice_not_transcribed: {nvoice}",
          "origin: mixed", "authored_by: human",
          "tags: [telegram, pokupki, session]", "---", "",
          f"# Покупки — {day}", "",
          f"> {len(msgs)} сообщений · 🟢анти:{oc.get('anton',0)} 🔵Алина:{oc.get('Alina',0)} "
          f"⚪микс:{oc.get('mixed',0)} ⚫внеш:{oc.get('external',0)} · "
          f"📝 заметок: {nk} · 🎤 голосовых: {nvoice}", "",
          "---", ""]
    for m in msgs:
        if m["bucket"] == "empty" and not m["media_kind"]:
            continue
        tm = (m["ts"] or "")[11:16]
        head = f"**{tm} · {role_icon(m)} {m['from']}**"
        if m["is_directive"] and m["origin"] == "anton":
            head += f" _(директива Антона через {m.get('transcribed_by') or m.get('posted_by') or 'ассистента'})_"
        if m["pinned"]:
            head += " 📌"
        if m.get("edited"):
            head += " _(ред.)_"
        fm.append(head)
        rt = m.get("reply_to")
        if rt and rt in by_id:
            p = by_id[rt]
            fm.append(f"↳ _в ответ [{p['from']} {(p['ts'] or '')[11:16]}]_: «{snippet(p)}»")
        elif rt:
            fm.append(f"↳ _в ответ на #{rt}_")
        ml = media_label(m)
        if ml:
            fm.append(ml)
        if m["text"]:
            if m["knowledge"]:
                s = re.sub(r"\s+", " ", m["text"]).strip()
                prev = (s[:PREVIEW] + "…") if len(s) > PREVIEW else s
                fm.append(f"> {prev}")
                fm.append(f"> 📝 [[{id2post[m['id']]}|полный текст]]")
            else:
                fm.append("\n".join("> " + ln for ln in m["text"].split("\n")))
        fm.append("")
    (LEDGER_DIR / f"Sessions-{day}.md").write_text("\n".join(fm) + "\n", encoding="utf-8")
    ledgers_written += 1

# ---- manifest + stats ------------------------------------------------------
(OUT / "pokupki-id2post.json").write_text(json.dumps(id2post, ensure_ascii=False), encoding="utf-8")
print("POSTS", posts_written, "LEDGERS", ledgers_written)
print("STAGE", str(CHAT_DIR))
