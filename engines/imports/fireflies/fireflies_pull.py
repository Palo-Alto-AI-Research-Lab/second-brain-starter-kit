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
"""Fireflies.ai -> vault pull (official GraphQL API, key from secrets\\fireflies.env).
Parallel sibling of granola_pull.py. Fireflies bot auto-joins calendar calls
(Autojoin ON) so it catches corporate/team calls Granola's manual-start misses,
AND gives real diarized speaker NAMES (vs Granola's microphone/speaker channels).

Backfill + nightly incremental: paginates transcripts (limit/skip), saves a raw
JSON snapshot per call, renders a vault meeting note. Idempotent via state.json
(transcripts are immutable once processed -> id presence = done).

The raw JSON is written with Granola-COMPATIBLE keys (id/title/created_at/
updated_at/attendees/transcript) so call_distill.py can consume it unchanged.

Env read is \\r-safe (Windows/Syncthing CRLF gotcha -> Bearer header corruption).
Usage: python fireflies_pull.py [--dry] [--limit N]  ; stdout ASCII-only.
"""
import json, os, re, sys, time
import urllib.request, urllib.error

GRAPHQL = "https://api.fireflies.ai/graphql"
# Per-machine secrets dir: env override -> known per-machine roots (hub / HP17 / Mac / ANCHOR1).
# Was hardcoded to the hub path, which broke every peer (HP17 2026-07-27). Canon:
# skill-authoring-portable-paths, one-system-propagate.
ENV_CANDIDATES = [
    os.environ.get("FIREFLIES_ENV") or "",
    os.path.join(os.environ.get("CLAUDE_SECRETS", ""), "fireflies.env")
    if os.environ.get("CLAUDE_SECRETS") else "",
    os.path.join(os.path.expanduser("~"), ".claude", "secrets", "fireflies.env"),
    r"%WORKDIR%\secrets\fireflies.env",
    os.path.join(os.path.expanduser("~"), "!CLAUDE-HP17 May26", "secrets", "fireflies.env"),
]
ENV = next((p for p in ENV_CANDIDATES if p and os.path.exists(p)), ENV_CANDIDATES[-2])
HOME = r"%IMPORTS%\fireflies"
RAW = os.path.join(HOME, "raw")
STATE = os.path.join(HOME, "state.json")
VAULT_DIR = r"%VAULT%\04-Projects\fireflies-meetings"
PAGE = 25            # Fireflies limit per page
RATE_SLEEP = 0.4

def load_key():
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()          # strips trailing \r too (CRLF-safe)
            if line.startswith("FIREFLIES_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("NO_KEY_IN_ENV")

def gql(query, key, tries=3):
    body = json.dumps({"query": query}).encode("utf-8")
    for i in range(tries):
        try:
            req = urllib.request.Request(GRAPHQL, data=body, headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("errors"):
                raise RuntimeError("GQL:" + json.dumps(d["errors"])[:200])
            return d["data"]
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

LIST_Q = """{ transcripts(limit:%d, skip:%d) {
 id title date dateString duration host_email organizer_email participants
 meeting_attendees { displayName email name }
 speakers { id name }
 sentences { index speaker_name text start_time }
 summary { overview action_items keywords bullet_gist }
} }"""

TRANSLIT = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
'ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}

def slugify(title):
    s = "".join(TRANSLIT.get(c, c) for c in (title or "untitled").lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "untitled"

def fmt_ts(sec):
    try:
        sec = int(float(sec)); return "%d:%02d" % (sec // 60, sec % 60)
    except Exception:
        return "?"

def normalize(t):
    """Add Granola-compatible keys so call_distill.py consumes this unchanged."""
    date_iso = (t.get("dateString") or "")
    att = []
    for a in (t.get("meeting_attendees") or []):
        att.append({"name": a.get("displayName") or a.get("name") or "",
                    "email": a.get("email") or ""})
    tr = []
    for s in (t.get("sentences") or []):
        tr.append({"speaker": s.get("speaker_name") or "?",
                   "text": s.get("text") or "",
                   "start_time": s.get("start_time") or 0})
    t["created_at"] = date_iso
    t["updated_at"] = date_iso          # Fireflies transcripts are immutable
    t["attendees"] = att
    t["transcript"] = tr
    t["source"] = "fireflies"
    return t

def render_note(t):
    tid = t["id"]
    title = (t.get("title") or "Untitled meeting").strip()
    date = (t.get("dateString") or "")[:10]
    parts = []
    for a in (t.get("meeting_attendees") or []):
        nm = (a.get("displayName") or a.get("name") or "").strip()
        em = (a.get("email") or "").strip()
        parts.append((nm + (" <" + em + ">" if em else "")) or em)
    speakers = [s.get("name", "") for s in (t.get("speakers") or []) if s.get("name")]
    L = ["---",
         'title: "%s"' % title.replace('"', "'"),
         "date: %s" % date, "type: meeting", "source: fireflies",
         "fireflies_id: %s" % tid,
         "duration_min: %s" % round((t.get("duration") or 0) / 60.0, 1),
         "participants:"]
    for p in parts:
        L.append('  - "%s"' % p.replace('"', "'"))
    L += ["speakers: [%s]" % ", ".join('"%s"' % s.replace('"', "'") for s in speakers),
          "origin: mixed", "authored_by: hybrid", "auto_generated: true",
          "machine: HUB1", "tags: [fireflies, meeting, call]", "---", "",
          "# %s" % title, "",
          "> Звонок из Fireflies · %s · %s мин" % (date, round((t.get("duration") or 0)/60.0, 1)), ""]
    if parts:
        L += ["**Участники:** " + "; ".join(parts), ""]
    if speakers:
        L += ["**Говорили:** " + ", ".join(speakers), ""]
    sm = t.get("summary") or {}
    if sm.get("overview"):
        L += ["## Саммари Fireflies (не доверяем — только справочно)", "", str(sm["overview"]).strip(), ""]
    sents = t.get("sentences") or []
    if sents:
        L += ["## Транскрипт (дословный)", ""]
        for s in sents:
            tx = (s.get("text") or "").strip()
            if tx:
                L.append("- **%s** [%s]: %s" % (s.get("speaker_name") or "?", fmt_ts(s.get("start_time", 0)), tx))
        L.append("")
    return "\n".join(L), date, slugify(title)

def main():
    dry = "--dry" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    key = load_key()
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(VAULT_DIR, exist_ok=True)
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    # 1. list all transcripts (paginate)
    items, skip, pages = [], 0, 0
    while True:
        data = gql(LIST_Q % (PAGE, skip), key)
        batch = data.get("transcripts") or []
        items += batch
        pages += 1
        if len(batch) < PAGE:
            break
        skip += PAGE
        if pages > 200:
            print("WARN pagination cap hit"); break
    print("listed pages=%d transcripts=%d known=%d" % (pages, len(items), len(state)))
    # 2. new ones (id not in state)
    todo = [t for t in items if t["id"] not in state]
    if limit:
        todo = todo[:limit]
    print("to_fetch=%d" % len(todo))
    if dry:
        return
    new_cnt = err_cnt = 0
    for i, t in enumerate(todo):
        tid = t["id"]
        try:
            t = normalize(t)
            with open(os.path.join(RAW, tid + ".json"), "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False)
            body, date, slug = render_note(t)
            fname = "%s-%s-%s.md" % (date, slug, tid[-6:])
            with open(os.path.join(VAULT_DIR, fname), "w", encoding="utf-8") as f:
                f.write(body)
            state[tid] = date
            new_cnt += 1
        except Exception as e:
            err_cnt += 1
            print("ERR %s %s" % (tid[-6:], str(e)[:60]))
            continue
        if (i + 1) % 20 == 0:
            json.dump(state, open(STATE, "w", encoding="utf-8"))
    json.dump(state, open(STATE, "w", encoding="utf-8"))
    print("DONE new=%d errors=%d state_total=%d vault_dir=%s" %
          (new_cnt, err_cnt, len(state), VAULT_DIR))

if __name__ == "__main__":
    main()
