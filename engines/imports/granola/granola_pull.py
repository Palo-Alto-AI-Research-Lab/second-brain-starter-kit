#!/usr/bin/env python3
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
"""Granola -> vault pull (official public API, key from secrets\\granola.env).
Backfill + nightly incremental in one: lists all notes (cursor pagination),
fetches detail+transcript only for NEW or UPDATED (by updated_at), saves raw
JSON snapshot + renders a vault meeting note. Idempotent; stdout ASCII-only.
Canon: vault 02-Decisions\\decision-granola-extraction-official-api.md
Usage: python granola_pull.py [--dry] [--limit N]
"""
import json, os, re, sys, time
import urllib.request, urllib.error

BASE = "https://public-api.granola.ai/v1"
ENV = r"%WORKDIR%\secrets\granola.env"
HOME = r"%IMPORTS%\granola"
RAW = os.path.join(HOME, "raw")
STATE = os.path.join(HOME, "state.json")
VAULT_DIR = r"%VAULT%\04-Projects\granola-meetings"
RATE_SLEEP = 0.25  # 5 rps cap -> stay well under

def load_key():
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            if line.startswith("GRANOLA_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("NO_KEY_IN_ENV")

def api_get(path, key, tries=3):
    url = BASE + path
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(2 ** (i + 1)); continue
            raise
        except Exception:
            if i < tries - 1:
                time.sleep(2 ** (i + 1)); continue
            raise
        finally:
            time.sleep(RATE_SLEEP)

TRANSLIT = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
'ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}

def slugify(title):
    s = (title or "untitled").lower()
    s = "".join(TRANSLIT.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:60] or "untitled")

def fmt_ts(sec):
    try:
        sec = int(float(sec)); return "%d:%02d" % (sec // 60, sec % 60)
    except Exception:
        return "?"

def render_note(d):
    nid = d["id"]
    title = (d.get("title") or "Untitled meeting").strip()
    created = d.get("created_at", "")
    date = created[:10]
    cal = d.get("calendar_event") or {}
    att = d.get("attendees") or []
    participants = []
    for a in att:
        nm = (a.get("name") or "").strip(); em = (a.get("email") or "").strip()
        participants.append(nm + (" <" + em + ">" if em else ""))
    lines = []
    lines.append("---")
    lines.append('title: "%s"' % title.replace('"', "'"))
    lines.append("date: %s" % date)
    lines.append("type: meeting")
    lines.append("source: granola")
    lines.append("granola_id: %s" % nid)
    lines.append("granola_updated: %s" % d.get("updated_at", ""))
    lines.append("web_url: %s" % d.get("web_url", ""))
    if cal.get("scheduled_start_time"):
        lines.append("scheduled_start: %s" % cal["scheduled_start_time"])
    lines.append("participants:")
    for p in participants:
        lines.append('  - "%s"' % p.replace('"', "'"))
    lines.append("origin: mixed")
    lines.append("authored_by: hybrid")
    lines.append("auto_generated: true")
    lines.append("machine: HUB1")
    lines.append("tags: [granola, meeting, call]")
    lines.append("---")
    lines.append("")
    lines.append("# %s" % title)
    lines.append("")
    lines.append("> Звонок из Granola · %s · [открыть в Granola](%s)" % (date, d.get("web_url", "")))
    lines.append("")
    if participants:
        lines.append("**Участники:** " + "; ".join(participants))
        lines.append("")
    summary = d.get("summary_markdown") or d.get("summary_text") or ""
    if summary.strip():
        lines.append("## Саммари")
        lines.append("")
        lines.append(summary.strip())
        lines.append("")
    if d.get("transcript_unavailable"):
        lines.append("> ⚠️ Транскрипт недоступен через API (502) — есть только саммари. Полная версия: [в Granola](%s)" % d.get("web_url", ""))
        lines.append("")
    tr = d.get("transcript")
    if isinstance(tr, list) and tr:
        lines.append("## Транскрипт")
        lines.append("")
        for seg in tr:
            raw_sp = seg.get("speaker")
            if isinstance(raw_sp, dict):
                sp = raw_sp.get("name") or raw_sp.get("label") or raw_sp.get("source") or "?"
                if sp == "microphone": sp = "Мы (мик)"
                elif sp == "speaker": sp = "Собеседник"
            else:
                sp = raw_sp or "?"
            sp = str(sp).strip()
            tx = (seg.get("text") or "").strip()
            if tx:
                lines.append("- **%s** [%s]: %s" % (sp, fmt_ts(seg.get("start_time", 0)), tx))
        lines.append("")
    return "\n".join(lines), date, slugify(title)

def main():
    dry = "--dry" in sys.argv
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    key = load_key()
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(VAULT_DIR, exist_ok=True)
    state = {}
    if os.path.exists(STATE):
        state = json.load(open(STATE, encoding="utf-8"))
    # 1. list all notes
    notes, cursor, pages = [], None, 0
    while True:
        path = "/notes?page_size=30" + (("&cursor=" + cursor) if cursor else "")
        d = api_get(path, key)
        notes += d.get("notes", [])
        pages += 1
        cursor = d.get("cursor")
        if not d.get("hasMore") or not cursor:
            break
        if pages > 200:
            print("WARN pagination cap hit"); break
    print("listed pages=%d notes=%d known=%d" % (pages, len(notes), len(state)))
    # 2. new / changed
    todo = [n for n in notes if state.get(n["id"]) != n.get("updated_at", "")]
    if limit:
        todo = todo[:limit]
    print("to_fetch=%d" % len(todo))
    if dry:
        return
    new_cnt = upd_cnt = err_cnt = 0
    for i, n in enumerate(todo):
        nid = n["id"]
        try:
            d = api_get("/notes/%s?include=transcript" % nid, key)
        except Exception:
            # transcript may 502 server-side (oversized); fall back to summary-only
            try:
                d = api_get("/notes/%s" % nid, key)
                d["transcript_unavailable"] = True
            except Exception as e:
                err_cnt += 1; print("ERR fetch %s %s" % (nid, e.__class__.__name__)); continue
        with open(os.path.join(RAW, nid + ".json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        body, date, slug = render_note(d)
        fname = "%s-%s-%s.md" % (date, slug, nid[-6:])
        fpath = os.path.join(VAULT_DIR, fname)
        existed = nid in state
        # title may change in Granola -> new slug -> stale duplicate under old name.
        # Remove any prior render of THIS note (same id suffix + granola_id match).
        import glob as _glob
        for old in _glob.glob(os.path.join(VAULT_DIR, "*-%s.md" % nid[-6:])):
            if os.path.abspath(old) == os.path.abspath(fpath):
                continue
            try:
                head = open(old, encoding="utf-8").read(1500)
                if ("granola_id: %s" % nid) in head:
                    os.remove(old)
                    print("renamed: removed stale %s" % os.path.basename(old))
            except Exception:
                pass
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(body)
        # partial (502-fallback) imports stay "dirty" in state -> retried every run
        # until the transcript finally comes through
        if d.get("transcript_unavailable"):
            state[nid] = "PARTIAL|" + d.get("updated_at", "")
        else:
            state[nid] = d.get("updated_at", "")
        if existed: upd_cnt += 1
        else: new_cnt += 1
        if (i + 1) % 20 == 0:
            json.dump(state, open(STATE, "w", encoding="utf-8"))
            print("progress %d/%d" % (i + 1, len(todo)))
    json.dump(state, open(STATE, "w", encoding="utf-8"))
    print("DONE new=%d updated=%d errors=%d state_total=%d vault_dir=%s" %
          (new_cnt, upd_cnt, err_cnt, len(state), VAULT_DIR))

if __name__ == "__main__":
    main()
