# -*- coding: utf-8 -*-
"""Phase 1 parser: Telegram HTML export -> JSONL checkpoint.
Lossless parse of all message types. Audio kept but tagged type='audio'
so Phase 2 can drop it (user: forget audio, all already transcribed).
"""
import re, json, html as html_lib
from pathlib import Path
from datetime import datetime

EXPORT = Path(r"C:/Users/_/Downloads/Telegram Desktop/ChatExport_2026-05-27")
OUT = Path(r"E:/Obsidian/_imports")
FILES = ["messages.html", "messages2.html", "messages3.html"]

A_TAG = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
TAG = re.compile(r'<[^>]+>')

def clean(raw):
    if raw is None:
        return ""
    raw = A_TAG.sub(lambda m: f"[{TAG.sub('', m.group(2)).strip()}]({m.group(1)})", raw)
    raw = re.sub(r'<br\s*/?>', '\n', raw)
    raw = TAG.sub('', raw)
    return html_lib.unescape(raw).strip()

def first(pattern, block, flags=re.DOTALL):
    m = re.search(pattern, block, flags)
    return m.group(1) if m else None

def to_iso(title):
    # "18.09.2023 17:17:09 UTC+00:00"
    if not title:
        return None
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})', title)
    if not m:
        return None
    d, mo, y, h, mi, s = m.groups()
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

records = []
last_sender = None
stats = {"text": 0, "audio": 0, "photo": 0, "video": 0, "file": 0,
         "empty": 0, "service": 0, "poll": 0, "with_reply": 0}

for fname in FILES:
    text = (EXPORT / fname).read_text(encoding="utf-8")
    blocks = re.split(r'(?=<div class="message )', text)
    for b in blocks:
        mid = re.search(r'<div class="message[^"]*" id="message(-?\d+)"', b)
        if not mid:
            continue
        msg_id = mid.group(1)

        if 'class="message service"' in b[:60]:
            content = clean(first(r'<div class="body details">\s*(.*?)\s*</div>', b))
            records.append({"id": msg_id, "type": "service", "text": content, "file": fname})
            stats["service"] += 1
            continue

        title = first(r'class="pull_right date details" title="([^"]+)"', b)
        ts_iso = to_iso(title)

        fn = first(r'<div class="from_name">\s*(.*?)\s*</div>', b)
        if fn:
            # some from_name divs embed a <span class="date details"> with the
            # message date (forward-style); strip it before reading the name
            fn = re.sub(r'<span class="date details".*?</span>', '', fn, flags=re.DOTALL)
            last_sender = clean(fn)
        sender = last_sender

        rep = re.search(r'go_to_message\(?(-?\d+)\)?', b)
        reply_to = rep.group(1) if rep else None
        if reply_to:
            stats["with_reply"] += 1

        media_type = first(r'class="media clearfix pull_left media_(\w+)"', b)
        media_title = first(r'<div class="title bold">\s*(.*?)\s*</div>', b) if media_type else None
        media_title = clean(media_title) if media_title else None

        is_poll = 'media_poll' in b

        # text: the message body text div (skip media title which is its own class)
        content = clean(first(r'<div class="text">\s*(.*?)\s*</div>', b))

        if media_type in ("audio_file", "voice_message"):
            mtype = "audio"
        elif media_type == "photo":
            mtype = "photo"
        elif media_type == "video":
            mtype = "video"
        elif media_type == "file":
            mtype = "file"
        elif is_poll:
            mtype = "poll"
        elif content:
            mtype = "text"
        else:
            mtype = "empty"
        stats[mtype] = stats.get(mtype, 0) + 1

        records.append({
            "id": msg_id,
            "ts": ts_iso,
            "ts_raw": title,
            "sender": sender,
            "type": mtype,
            "text": content,
            "media": media_type,
            "media_title": media_title,
            "reply_to": reply_to,
            "file": fname,
        })

# write JSONL (UTF-8, no console printing of cyrillic to avoid cp1252 crash)
out_path = OUT / "telegram-archive.jsonl"
with out_path.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# write ascii-safe stats report
report = {
    "total_records": len(records),
    "by_type": stats,
    "senders": {},
    "date_range": {},
}
from collections import Counter
sc = Counter(r.get("sender") for r in records if r.get("sender"))
report["senders"] = dict(sc.most_common(15))
dates = sorted(r["ts"] for r in records if r.get("ts"))
if dates:
    report["date_range"] = {"first": dates[0], "last": dates[-1]}

(OUT / "parse_stats.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("DONE. total_records=", len(records))
print("by_type=", json.dumps(stats))
print("output:", out_path)
