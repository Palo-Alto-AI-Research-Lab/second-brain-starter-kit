#!/usr/bin/env python3
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
r"""incremental_pull.py — pull ONLY recently-updated ChatGPT conversations via
backend-api and emit a ZIP in the official-export shape so the existing
chatgpt_export_to_vault.py can fold them in (idempotent by conversation_id).

Token: secrets\bearer.txt (cookie/bearer that already works).
Usage: python incremental_pull.py [YYYY-MM-DD cutoff] [--projects-only]
       (default cutoff 2026-06-14; --projects-only = only chats inside ChatGPT
        Projects, zip named incremental-<date>-projects.zip -- for backfills)
Handles OpenAI's intermittent HTTP 500 on /conversations with retries.

NOTE (2026-07-06): /conversations does NOT list chats that live inside ChatGPT
Projects (gizmos) -- they are enumerated separately via /gizmos/snorlax/sidebar
+ /gizmos/<id>/conversations, else project deep-researches never reach the vault.
"""
import os, sys, json, time, zipfile, datetime, uuid, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
BEARER = open(os.path.join(ROOT, "secrets", "bearer.txt")).read().strip()
DEVICE_ID = str(uuid.uuid4())  # detail endpoint 403s without OAI-Device-Id
_ARGS = sys.argv[1:]
PROJECTS_ONLY = "--projects-only" in _ARGS
_POS = [a for a in _ARGS if not a.startswith("--")]
CUTOFF = _POS[0] if _POS else "2026-06-14"
cutoff_dt = datetime.datetime.fromisoformat(CUTOFF + "T00:00:00+00:00")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
BASE = "https://chatgpt.com/backend-api"


def get(url, tries=8):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + BEARER, "User-Agent": UA,
                "Accept": "application/json", "oai-language": "en-US",
                "Referer": "https://chatgpt.com/", "Origin": "https://chatgpt.com",
                "OAI-Device-Id": DEVICE_ID})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = "HTTP %s" % e.code
            if e.code in (401, 403):
                print("AUTH FAILED (HTTP %s) - ChatGPT token dead/expired, needs refresh" % e.code, flush=True)
                sys.exit(7)
            if e.code in (500, 502, 503, 429):
                time.sleep(4 + i * 2); continue
            raise
        except Exception as e:
            last = str(e); time.sleep(4 + i * 2)
    print("PULL FAILED after %d tries on %s (%s)" % (tries, url, last), flush=True)
    sys.exit(8)


def to_epoch(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    try:
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


# 1) discover updated convs since cutoff
ids, offset = [], 0
while not PROJECTS_ONLY:
    page = get("%s/conversations?offset=%d&limit=28&order=updated" % (BASE, offset))
    items = page.get("items", [])
    if not items: break
    stop = False
    for it in items:
        ut = datetime.datetime.fromisoformat(str(it["update_time"]).replace("Z", "+00:00"))
        if ut.tzinfo is None:
            ut = ut.replace(tzinfo=datetime.timezone.utc)
        if ut < cutoff_dt:
            stop = True; break
        ids.append((it["id"], it.get("title")))
    print("listed offset=%d total_new=%d" % (offset, len(ids)), flush=True)
    if stop or len(items) < 28: break
    offset += 28
    time.sleep(3)

# 1b) chats inside ChatGPT Projects (gizmos) -- absent from /conversations
seen = {cid for cid, _ in ids}
try:
    sidebar = get("%s/gizmos/snorlax/sidebar?limit=40" % BASE)
    projects = []
    for it in sidebar.get("items", []):
        g = it.get("gizmo") or (it.get("resource") or {}).get("gizmo") or it
        gid = g.get("id") or g.get("gizmo_id")
        name = ((g.get("display") or {}).get("name")) or g.get("title") or gid
        if gid:
            projects.append((gid, name))
    print("=== %d projects in sidebar ===" % len(projects), flush=True)
    for gid, pname in projects:
        fresh, cursor, pages = 0, None, 0
        while pages < 40:  # safety cap; limit>50 -> HTTP 422
            url = "%s/gizmos/%s/conversations?limit=50" % (BASE, gid)
            if cursor:
                url += "&cursor=" + urllib.parse.quote(cursor, safe="")
            page = get(url)
            items = page.get("items", [])
            pages += 1
            page_has_fresh = False
            for it in items:
                ut = to_epoch(it.get("update_time"))
                cid = it.get("id")
                if ut is not None and ut >= cutoff_dt.timestamp():
                    page_has_fresh = True
                if not cid or cid in seen or ut is None or ut < cutoff_dt.timestamp():
                    continue
                seen.add(cid)
                ids.append((cid, it.get("title")))
                fresh += 1
            cursor = page.get("cursor")
            # list is update-desc: a page with zero fresh items => the rest is older
            if not cursor or not items or not page_has_fresh:
                break
            time.sleep(2)
        print("  project %-40s +%d convs (%d pages)" % ((pname or "")[:40], fresh, pages), flush=True)
        time.sleep(2)
except (KeyError, ValueError, TypeError) as e:
    # malformed sidebar payload must not kill the main nightly pull
    print("project enumeration failed (%s) -- continuing with main list only" % e, flush=True)

print("=== %d conversations updated since %s ===" % (len(ids), CUTOFF), flush=True)

# 2) fetch each full conversation, normalize, collect
convs = []
for cid, title in ids:
    d = get("%s/conversation/%s" % (BASE, cid))
    d["conversation_id"] = cid
    if "id" not in d: d["id"] = cid
    d["create_time"] = to_epoch(d.get("create_time"))
    d["update_time"] = to_epoch(d.get("update_time"))
    convs.append(d)
    print("  fetched %s | %s" % (cid[:8], (title or "")[:60]), flush=True)
    time.sleep(2)

# 3) write zip in official shape
suffix = "-projects" if PROJECTS_ONLY else ""
out_zip = os.path.join(ROOT, "raw", "incremental-%s%s.zip" % (datetime.date.today().isoformat(), suffix))
os.makedirs(os.path.dirname(out_zip), exist_ok=True)
with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("conversations.json", json.dumps(convs, ensure_ascii=False))
print("WROTE %s (%d conversations)" % (out_zip, len(convs)), flush=True)
