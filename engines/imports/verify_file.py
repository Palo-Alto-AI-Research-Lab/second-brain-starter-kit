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
"""Verify that EVERY message in one source HTML page is present in the vault.
Layer-2 check: each text message must appear in its day-ledger (±1 day for UTC edge).
Media check: per-day media-message counts vs ledger placeholder counts.
Writes a UTF-8 report; stdout stays ASCII."""
import os
import re, html
from pathlib import Path

SRC = Path(os.path.expanduser(r"~\Downloads\Telegram Desktop\ChatExport_2026-05-30\messages21.html"))
try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
LEDGER = Path(VAULT) / "01-Conversations" / "Telegram" / "Assistants-Ops" / "sessions"
OUT = Path(IMPORTS)

A_RE = re.compile(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', re.S)
def dehtml(s):
    if s is None: return ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    def a(m):
        href, txt = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href.startswith("http") and href not in txt:
            return f"{txt} ({href})" if txt else href
        return txt
    s = A_RE.sub(a, s); s = re.sub(r"<[^>]+>", "", s); return html.unescape(s).strip()

def norm(s): return re.sub(r"\s+", " ", s or "").strip()

# ---- parse the source page ------------------------------------------------
raw = SRC.read_text(encoding="utf-8", errors="replace")
blocks = re.split(r'(?=<div class="message (?:default|service))', raw)
rows = []
last = None
for b in blocks:
    if b.startswith('<div class="message service'): continue
    joined = 'clearfix joined"' in b
    fn = re.search(r'<div class="from_name">\s*(.*?)\s*</div>', b, re.S)
    if fn: last = fn.group(1).split("<")[0].strip()
    sender = last
    dm = re.search(r'title="(\d{2})\.(\d{2})\.(\d{4}) ', b)
    date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else None
    tm = re.search(r'<div class="text">\s*(.*?)\s*</div>\s*(?:<span class="reactions"|</div>)', b, re.S)
    text = dehtml(tm.group(1)) if tm else ""
    mid = re.search(r'id="message-?(\d+)"', b)
    media = sorted(set(re.findall(r'media_(voice_message|photo|file|video_message|video_file|animation)', b)))
    if not (mid or text or media): continue
    rows.append({"id": mid.group(1) if mid else None, "date": date,
                 "sender": sender, "text": text, "media": media})

# ---- ledger cache ---------------------------------------------------------
cache = {}
def ledger(d):
    if d not in cache:
        p = LEDGER / f"Sessions-{d}.md"
        if p.exists():
            t = p.read_text(encoding="utf-8")
            t = re.sub(r"(?m)^[ \t]*>[ \t]?", "", t)  # strip blockquote markers
            cache[d] = norm(t)
        else:
            cache[d] = None
    return cache[d]
def shift(d, n):
    from datetime import date as D, timedelta
    y,m,dd = map(int, d.split("-")); return (D(y,m,dd)+timedelta(days=n)).isoformat()

# ---- verify ---------------------------------------------------------------
text_msgs = [r for r in rows if r["text"]]
media_only = [r for r in rows if not r["text"] and r["media"]]
matched, missing = [], []
for r in text_msgs:
    sig = norm(r["text"])
    probe = sig if len(sig) <= 120 else sig[:120]
    found = False
    for off in (0, -1, 1):
        d = shift(r["date"], off) if r["date"] else None
        lg = ledger(d) if d else None
        if lg and probe in lg:
            found = True; break
    (matched if found else missing).append(r)

# media coverage per day
from collections import Counter
src_media_days = Counter(r["date"] for r in media_only)
media_report = []
for d, n in sorted(src_media_days.items()):
    lg = LEDGER / f"Sessions-{d}.md"
    placeholders = len(re.findall(r"не выгружено", lg.read_text(encoding="utf-8"))) if lg.exists() else 0
    media_report.append(f"  {d}: source media-only={n}  ledger placeholders={placeholders}")

dates = sorted(set(r["date"] for r in rows if r["date"]))
ledgers_exist = [d for d in dates if (LEDGER/f"Sessions-{d}.md").exists()]
rep = []
rep.append(f"SOURCE messages21.html")
rep.append(f"date range: {dates[0]} .. {dates[-1]}  ({len(dates)} days)")
rep.append(f"ledgers present in vault: {len(ledgers_exist)}/{len(dates)}")
rep.append(f"total parsed messages: {len(rows)}")
rep.append(f"  text messages: {len(text_msgs)}  ->  matched {len(matched)}, MISSING {len(missing)}")
rep.append(f"  media-only messages: {len(media_only)}")
rep.append("media coverage per day (source vs ledger placeholders):")
rep += media_report
if missing:
    rep.append("\n=== MISSING text messages ===")
    for r in missing[:40]:
        rep.append(f"[{r['date']} | {r['sender']} | id{r['id']}] {norm(r['text'])[:100]}")
else:
    rep.append("\nALL text messages found in vault ledgers.")
(OUT/"_verify21.txt").write_text("\n".join(rep), encoding="utf-8")
print("MESSAGES", len(rows), "TEXT", len(text_msgs), "MATCHED", len(matched), "MISSING", len(missing))
print("DATES", dates[0], "..", dates[-1], "LEDGERS", f"{len(ledgers_exist)}/{len(dates)}")
print("MEDIA_ONLY", len(media_only))
