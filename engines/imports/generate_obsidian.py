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
"""Phase 3 generator: classified JSONL -> Obsidian markdown into STAGING.
- every post (>=200 chars) -> own file in posts/
- monthly session masters in sessions/ (Feb-2025 split per-session per user)
- person files for top-5 participants
Nothing is written to the live vault here; output goes to _imports/staging/.
"""
import json, re, html
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

IMP = Path(r"E:/Obsidian/_imports")
SRC = IMP / "telegram-archive-classified.jsonl"
STAGE = IMP / "staging"
POSTS = STAGE / "01-Conversations/Telegram/Arhiv-Golosa/posts"
SESS = STAGE / "01-Conversations/Telegram/Arhiv-Golosa/sessions"
PEOPLE = STAGE / "07-People"
for d in (POSTS, SESS, PEOPLE):
    d.mkdir(parents=True, exist_ok=True)

CHAT = "Архив ГОЛОСА Content"
# user chose to break the Feb-2025 spike along conversation boundaries; per raw
# 30-min session that yielded 45 near-empty micro-files, so we bucket by DAY
# (each day file keeps the 30-min sessions as `## Сессия N` subsections).
SPLIT_BY_DAY_MONTHS = {"2025-02"}
TRANSCRIPT_SENDER = "Personal Audio Summary"

TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z',
    'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',' ':'-'}

def translit(s):
    s = s.lower()
    out = []
    for ch in s:
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append('-')
    res = ''.join(out)
    res = re.sub(r'-+', '-', res).strip('-')
    return res

def slugify(text, maxlen=48):
    first_line = text.strip().splitlines()[0] if text.strip() else "untitled"
    # drop leading mentions/hashtags noise for slug
    first_line = re.sub(r'\[@[^\]]+\]\([^)]+\)', '', first_line)
    first_line = re.sub(r'https?://\S+', '', first_line)
    s = translit(first_line)[:maxlen].strip('-')
    return s or "post"

def yaml_str(s):
    if s is None:
        return '""'
    s = s.replace('\n', ' ').replace('\r', ' ').strip()
    s = s.replace('"', "'")
    return '"' + s[:90] + '"'

def hashtags(text):
    return sorted({h.lower() for h in re.findall(r'#(\w+)', text)})

def title_of(text):
    line = text.strip().splitlines()[0] if text.strip() else "(no text)"
    line = re.sub(r'\s+', ' ', line)
    return line[:80]

recs = [json.loads(l) for l in SRC.open(encoding="utf-8")]
posts = [r for r in recs if r["cls"] == "post"]

# ---- generate post files ----
used = set()
post_index = {}  # msg_id -> slug filename (for linking from sessions)
for r in posts:
    ts = r.get("ts") or "0000-00-00T00:00:00"
    date = ts[:10]
    base = f"{date}-{slugify(r['text'])}"
    fname = base
    i = 2
    while fname in used:
        fname = f"{base}-{i}"
        i += 1
    used.add(fname)
    post_index[r["id"]] = fname

    is_tr = r.get("sender") == TRANSCRIPT_SENDER
    tags = ["telegram", "telegram-post"] + (["transcript"] if is_tr else []) + hashtags(r["text"])
    month = r.get("month") or date[:7]
    sess_link = (f"Sessions-{date}" if month in SPLIT_BY_DAY_MONTHS
                 else f"Sessions-{month}")
    fm = [
        "---",
        f"title: {yaml_str(title_of(r['text']))}",
        f"type: {'transcript' if is_tr else 'telegram-post'}",
        "source: telegram-archive",
        f"chat: {yaml_str(CHAT)}",
        f"author: {yaml_str(r.get('sender'))}",
        f"date: {ts}",
        f"msg_id: {r['id']}",
        f"session: {r.get('session')}",
        f"month: {month}",
        f"is_transcript: {'true' if is_tr else 'false'}",
        f"reply_to_msg: {r.get('reply_to') if r.get('reply_to') else 'null'}",
        "tags: [" + ", ".join(tags) + "]",
        "---",
        "",
        r["text"],
        "",
        "## See Also",
        f"- Сессия: [[{sess_link}]]",
        "- [[_Telegram-MOC]]",
        "",
    ]
    (POSTS / f"{fname}.md").write_text("\n".join(fm), encoding="utf-8")

# ---- generate session masters ----
def render_msg(r):
    t = r["text"]
    tm = (r.get("ts") or "")[11:16]
    sender = r.get("sender") or "?"
    if r["cls"] == "post" and r["id"] in post_index:
        snippet = re.sub(r'\s+', ' ', t)[:280]
        return f"**{sender}** ({tm}): {snippet}… → [[{post_index[r['id']]}|полный текст]]"
    return f"**{sender}** ({tm}): {t}"

by_month = defaultdict(list)
for r in recs:
    if r.get("month"):
        by_month[r["month"]].append(r)

def write_session_file(path, header, msgs):
    parts = msgs
    participants = sorted({m.get("sender") for m in parts if m.get("sender")})
    fm = [
        "---",
        f"title: {yaml_str(header)}",
        "type: telegram-sessions",
        "source: telegram-archive",
        f"chat: {yaml_str(CHAT)}",
        f"message_count: {len(parts)}",
        "tags: [telegram, telegram-sessions]",
        "---",
        "",
        f"# {header}",
        "",
    ]
    # group by session
    cur = None
    for m in parts:
        if m.get("session") != cur:
            cur = m.get("session")
            d = (m.get("ts") or "")[:10]
            fm.append(f"\n## Сессия {cur} — {d}\n")
        fm.append(render_msg(m) + "\n")
    fm += ["", "## See Also", "- [[_Telegram-MOC]]", ""]
    path.write_text("\n".join(fm), encoding="utf-8")

session_files = 0
for month, msgs in sorted(by_month.items()):
    msgs.sort(key=lambda r: (r.get("ts") or ""))
    if month in SPLIT_BY_DAY_MONTHS:
        by_day = defaultdict(list)
        for m in msgs:
            by_day[(m.get("ts") or "")[:10]].append(m)
        for day, dm in sorted(by_day.items()):
            write_session_file(SESS / f"Sessions-{day}.md",
                                f"Telegram {day}", dm)
            session_files += 1
    else:
        write_session_file(SESS / f"Sessions-{month}.md",
                           f"Telegram sessions {month}", msgs)
        session_files += 1

# ---- person files (top 5 by total message volume, excluding bots/Anton) ----
EXCLUDE = {TRANSCRIPT_SENDER, "Deleted Account"}
ANTON = {"Tony frm Palo Alto Ai Research lab"}
vol = Counter(r.get("sender") for r in recs if r.get("sender"))
ranked = [(s, n) for s, n in vol.most_common()
          if s not in EXCLUDE and not (s or "").startswith("Tony")]
top5 = ranked[:5]
for sender, n in top5:
    first = min((r["ts"] for r in recs if r.get("sender") == sender and r.get("ts")), default="?")
    last = max((r["ts"] for r in recs if r.get("sender") == sender and r.get("ts")), default="?")
    pcount = sum(1 for r in posts if r.get("sender") == sender)
    slug = translit(sender)
    fm = [
        "---",
        f"title: {yaml_str(sender)}",
        "type: person",
        "context: telegram-content-team",
        f"telegram_messages: {n}",
        f"telegram_long_posts: {pcount}",
        f"first_seen: {first[:10]}",
        f"last_seen: {last[:10]}",
        "tags: [person, telegram, content-team]",
        "---",
        "",
        f"# {sender}",
        "",
        "## Роль",
        f"Участник контент-команды Антона в Telegram-чате «{CHAT}». "
        f"Всего сообщений: {n}, длинных постов: {pcount}. "
        f"Период активности: {first[:10]} — {last[:10]}.",
        "",
        "## See Also",
        "- [[_Telegram-MOC]]",
        "",
    ]
    (PEOPLE / f"person-{slug}.md").write_text("\n".join(fm), encoding="utf-8")

print("POSTS:", len(post_index))
print("SESSION_FILES:", session_files)
print("PERSON_FILES:", len(top5))
print("TOP5:", [s for s, _ in top5])
