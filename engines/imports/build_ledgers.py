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
"""FAAA Phase 6 — day-bucketed raw archive ledgers + archive MOC.

Every message appears once chronologically:
  - call_summary -> dated one-liner linking to its lead card (text lives in card)
  - chatter/fragment/longtext -> verbatim (their single copy)
  - media-only -> placeholder (voice/photo not exported)
Output: staging/01-Conversations/Telegram/FAAA-Follow-ups/sessions/Sessions-YYYY-MM-DD.md
        + _FAAA-Follow-ups-MOC.md
ASCII-only stdout.
"""
import json, io, os, re
from collections import defaultdict, Counter, OrderedDict

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

OUT = IMPORTS
STAGE = OUT + r"\staging"
CONVDIR = STAGE + r"\01-Conversations\Telegram\FAAA-Follow-ups"
SESSDIR = CONVDIR + r"\sessions"
os.makedirs(SESSDIR, exist_ok=True)

rows = [json.loads(l) for l in io.open(OUT + r"\faaa-archive.jsonl", encoding="utf-8")]
call2slug = json.load(io.open(OUT + r"\faaa\call2slug.json", encoding="utf-8"))
call2lead = json.load(io.open(OUT + r"\faaa\call2lead.json", encoding="utf-8"))
final = json.load(io.open(OUT + r"\faaa\final_slugs.json", encoding="utf-8"))

# synth gist (synth2: v2 batches + reused.json dict)
synth = {}
sdir = OUT + r"\faaa\synth2"
for fn in os.listdir(sdir):
    if fn.endswith(".json"):
        try:
            data = json.load(io.open(os.path.join(sdir, fn), encoding="utf-8-sig"))
            objs = data.values() if isinstance(data, dict) else data
            for o in objs:
                if isinstance(o, dict) and "lead_id" in o:
                    synth[int(o["lead_id"])] = o
        except Exception:
            pass

def neutralize(s):
    """Break every '[[' run in raw text so Obsidian/validator don't see a wikilink."""
    return re.sub(r'(?<=\[)\[', r'\\[', s or "")

def gist(lead_id):
    s = synth.get(lead_id)
    if not s:
        return ""
    g = s.get("what_they_want") or s.get("summary") or ""
    g = g.split(". ")[0].strip()
    return g[:120]

MEDIA_ICON = {"voice_message": "🎤 голосовое", "audio_file": "🎧 аудио",
              "video_message": "📹 видеокружок", "video_file": "🎬 видео",
              "photo": "🖼 фото", "sticker": "🃏 стикер", "animation": "🎞 gif",
              "file": "📎 файл"}

# group by day
by_day = defaultdict(list)
for r in rows:
    if r.get("type") == "service":
        continue
    d = (r.get("date") or "")[:10]
    if d:
        by_day[d].append(r)

month_days = defaultdict(list)
day_stats = {}
for day in sorted(by_day):
    msgs = sorted(by_day[day], key=lambda r: (r.get("date") or "", r.get("id", 0)))
    month = day[:7]
    month_days[month].append(day)
    ncall = sum(1 for r in msgs if r["cls"] == "call_summary")
    day_stats[day] = (len(msgs), ncall)

    out = []
    out.append("---")
    out.append("type: session-ledger")
    out.append("source: telegram-faaa")
    out.append("chat: \"CALLS FAAA follow up MAIN\"")
    out.append("date: " + day)
    out.append("month: " + month)
    out.append("origin: mixed")
    out.append("authored_by: hybrid")
    out.append("msg_count: %d" % len(msgs))
    out.append("call_count: %d" % ncall)
    out.append("tags: [telegram, session, platinum-crm, faaa-archive]")
    out.append("---")
    out.append("")
    out.append("# FAAA звонки — %s" % day)
    out.append("")
    out.append("> Архив чата follow-up'ов. Итоги звонков → карточки лидов; "
               "остальное (чаттер, процессы, медиа) — здесь дословно. "
               "[[_FAAA-Follow-ups-MOC|← весь архив]]")
    out.append("")
    for r in msgs:
        hhmm = (r.get("date") or "")[11:16]
        who = r.get("sender") or "?"
        cls = r["cls"]
        if cls == "call_summary":
            cid = r["id"]
            slug = call2slug.get(str(cid)) or call2slug.get(cid)
            lid = call2lead.get(str(cid)) or call2lead.get(cid)
            title = final.get(str(lid), {}).get("title") if lid is not None else None
            st = (" · " + r["status"]) if r.get("status") else ""
            if slug:
                g = gist(int(lid)) if lid is not None else ""
                line = "- **%s** %s — 📞 [[%s|%s]]%s" % (
                    hhmm, who, slug, (title or slug), st)
                if g:
                    line += " — _%s_" % g
                out.append(line)
            else:
                # unclustered call (no identifiable lead) -> keep text verbatim here
                txt = neutralize((r.get("text") or "").strip())
                out.append("- **%s** %s — 📞 звонок (без карточки)%s:" % (hhmm, who, st))
                for line in txt.split("\n"):
                    out.append("  > " + line if line.strip() else "  >")
        elif cls == "media_only":
            icon = MEDIA_ICON.get(r.get("media") or "", "📎 медиа (не выгружено)")
            out.append("- **%s** %s — %s" % (hhmm, who, icon))
        else:
            txt = neutralize((r.get("text") or "").strip())
            if not txt:
                continue
            out.append("- **%s** %s:" % (hhmm, who))
            for line in txt.split("\n"):
                out.append("  > " + line if line.strip() else "  >")
    io.open(os.path.join(SESSDIR, "Sessions-%s.md" % day), "w",
            encoding="utf-8").write("\n".join(out) + "\n")

# ---- archive MOC ----
total_msgs = sum(v[0] for v in day_stats.values())
total_calls = sum(v[1] for v in day_stats.values())
m = []
m.append("---")
m.append("type: moc")
m.append("title: \"FAAA Follow-ups — архив звонков\"")
m.append("source: telegram-faaa")
m.append("origin: mixed")
m.append("authored_by: hybrid")
m.append("date_added: 2026-05-31")
m.append("tags: [moc, telegram, platinum-crm, faaa-archive]")
m.append("---")
m.append("")
m.append("# FAAA Follow-ups — архив звонков Platinum")
m.append("")
m.append("Сырой хронологический архив чата **CALLS FAAA follow up MAIN** "
         "(итоги звонков с лидами, %s → %s)." % (
             min(by_day), max(by_day)))
m.append("")
m.append("- Сообщений: **%d** · звонков-саммари: **%d** · дней: **%d**" % (
    total_msgs, total_calls, len(by_day)))
m.append("- Карточки лидов (синтез по @хендлу+имени): **[[_Platinum-CRM-MOC]]**")
m.append("- Итоги звонков вынесены в карточки лидов; здесь — полный сырой лог.")
m.append("")
m.append("## Индекс по месяцам")
m.append("")
m.append("| Месяц | Дней | Сообщений | Звонков |")
m.append("|---|---|---|---|")
for month in sorted(month_days):
    days = month_days[month]
    mm = sum(day_stats[d][0] for d in days)
    cc = sum(day_stats[d][1] for d in days)
    # link to first day of month as anchor
    m.append("| %s | %d | %d | %d |" % (month, len(days), mm, cc))
m.append("")
m.append("## Все дни")
m.append("")
cur_month = None
for day in sorted(by_day):
    if day[:7] != cur_month:
        cur_month = day[:7]
        m.append("")
        m.append("**%s**" % cur_month)
    n, c = day_stats[day]
    m.append("- [[Sessions-%s]] — %d сообщ., %d звонк." % (day, n, c))
io.open(CONVDIR + r"\_FAAA-Follow-ups-MOC.md", "w", encoding="utf-8").write(
    "\n".join(m) + "\n")

print("DONE days=%d msgs=%d calls=%d months=%d"
      % (len(by_day), total_msgs, total_calls, len(month_days)))
