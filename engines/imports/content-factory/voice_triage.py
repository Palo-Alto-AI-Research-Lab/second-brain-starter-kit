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
"""
voice_triage.py - deterministic state + queue helper for the voice-triage lane
                  AND the unified post-material store (content-factory v2, S4).

The MESSAGE PULL + CLASSIFICATION are done in-session (Telegram MCP + LLM judge);
a standalone script can't reach the MCP. This helper does only the 0-token
deterministic parts:
  - remember which messages were already triaged (dedup by chat max-id)
  - append routed items to the three HUMAN queue files (task / alpha / post)
  - keep a MACHINE-READABLE post-material store (posts.jsonl) = the S5 handoff
  - flag privacy/visibility on each post-material item
  - turn one post-material item into an "episode seed" S5's episode_adapter reads
  - report counters (the visibility layer, so silent failures are caught)
  - keep all file I/O UTF-8, print only ASCII to stdout (Windows cp1252 trap)

Queues / store live in:  %IMPORTS%\\content-factory\\triage\\
  _seen.json            -> {"hub": <max_msg_id>, "saved": <max_msg_id>}
  tasks.md              -> 🔧 things to DO   (feeds Hanging-Tasks-Dashboard later)
  alpha.md              -> 💎 ideas / insights / bets (feeds alpha engine later)
  posts.md              -> 📝 post-material pointers (HUMAN view)
  posts.jsonl           -> 📝 post-material records (MACHINE view = S5 handoff)
  episode-seeds/<slug>.json -> one episode seed per chosen post (S5 consumes)

Usage:
  python voice_triage.py read-state
  python voice_triage.py save-state --hub 3400 --saved 1788000
  python voice_triage.py append --bucket task|alpha|post --title "..." --note "..." \
         --src hub:3399 --when 2026-06-27T10:00 \
         [--visibility public|personal|private] [--source-kind voice|openclaw|event]
  python voice_triage.py set-visibility --id hub:3401 --visibility personal
  python voice_triage.py seed-episode --id hub:3417 [--slug my-slug] [--allow-private]
  python voice_triage.py status
  python voice_triage.py list [--status new|seeded|done] [--visibility public|...]
  python voice_triage.py migrate-posts        # backfill posts.jsonl from posts.md
  python voice_triage.py mark-published --id hub:3417 [--platform tg_clawrus] [--url U]
  python voice_triage.py link-episode --id hub:3417 --slug <episode-slug>
  python voice_triage.py reconcile-published [--write]
  python voice_triage.py funnel [--days 7] [--json]
"""
import argparse, contextlib, json, os, re, sys, time, datetime

# `status` is ASCII-only, but `list` echoes Cyrillic post titles. A Windows
# console is cp1251/cp1252 and cannot encode them -> mojibake (caught by the
# parallel-S4 review 2026-06-29). Force stdout to UTF-8 so titles read correctly
# when the console is UTF-8 or piped to a file; errors=replace never crashes.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
TRIAGE = os.path.join(BASE, "triage")
SEEN = os.path.join(TRIAGE, "_seen.json")
POSTS_MD = os.path.join(TRIAGE, "posts.md")
POSTS_JSONL = os.path.join(TRIAGE, "posts.jsonl")
SEEDS_DIR = os.path.join(TRIAGE, "episode-seeds")
QUEUES = {"task": "tasks.md", "alpha": "alpha.md", "post": "posts.md"}
ICON = {"task": "[TASK]", "alpha": "[ALPHA]", "post": "[POST]"}
HEADER = {
    "task": "# Triage queue: TASKS (things to DO)\n",
    "alpha": "# Triage queue: ALPHA (ideas / insights / bets)\n",
    "post":  "# Triage queue: POST-material pointers\n",
}
VISIBILITY = ("public", "personal", "private")
SOURCE_KINDS = ("voice", "openclaw", "event", "session")  # +session: content_miner.py (CC sessions -> funnel)

# ---------------------------------------------------------------- shared utils
def ensure():
    os.makedirs(TRIAGE, exist_ok=True)

def read_state():
    if os.path.exists(SEEN):
        with open(SEEN, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hub": 0, "saved": 0}

# transliteration for ASCII slugs (Cyrillic post titles -> safe folder names)
_TR = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z",
    "и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
    "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch",
    "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}
def slugify(text, fallback="post"):
    s = (text or "").strip().lower()
    out = []
    for ch in s:
        if ch in _TR:
            out.append(_TR[ch])
        elif ch.isascii() and (ch.isalnum()):
            out.append(ch)
        elif ch in " -_/\\.,:;()[]":
            out.append("-")
        # drop everything else
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    slug = slug[:60].strip("-")
    return slug or fallback

# ---- concurrency + damaged-line safety (hardened 2026-07-27 after the Codex break)
# posts.jsonl is now written by TWO rails (the triage routine appends, the publisher
# writes back "published"). Every write is a read-modify-REWRITE of the whole file, so
# without a lock a concurrent pair silently loses one side's records. House rule is
# "one writer per file"; where a second writer is unavoidable, it takes a lock first.
LOCK_PATH = os.path.join(TRIAGE, "_posts.lock")
_LOCK_DEPTH = [0]          # re-entrant: mutate_posts() may nest (upsert inside a command)
_BAD_LINES = []            # unparsable lines are CARRIED OVER, never dropped on rewrite

@contextlib.contextmanager
def posts_lock(timeout=15.0, stale=180.0):
    if _LOCK_DEPTH[0] > 0:                       # already held by an outer frame
        _LOCK_DEPTH[0] += 1
        try:
            yield
        finally:
            _LOCK_DEPTH[0] -= 1
        return
    ensure()
    deadline = time.time() + timeout
    fd = None
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:                                 # a crashed process must not block forever
                if time.time() - os.path.getmtime(LOCK_PATH) > stale:
                    os.unlink(LOCK_PATH)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise RuntimeError("posts.jsonl locked by another writer (>%ds): %s"
                                   % (int(timeout), LOCK_PATH))
            time.sleep(0.15)
    _LOCK_DEPTH[0] += 1
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd); fd = None
        yield
    finally:
        _LOCK_DEPTH[0] -= 1
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(LOCK_PATH)
        except OSError:
            pass

def load_posts():
    """Read posts.jsonl -> list of dicts (one post-material record each).

    A line that does not parse is kept aside (not dropped): save_posts writes it back
    verbatim. Swallowing it silently would mean the next rewrite DELETES a record
    nobody ever decided to delete (named by the Codex breaker 2026-07-27).
    """
    recs = []
    del _BAD_LINES[:]
    if os.path.exists(POSTS_JSONL):
        with open(POSTS_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().lstrip("﻿")
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    _BAD_LINES.append(line)
    if _BAD_LINES:
        print("WARN posts.jsonl: %d damaged line(s) preserved as-is (not parsed, not lost)"
              % len(_BAD_LINES))
    return recs

def save_posts(recs):
    """Atomic rewrite: temp file + replace, so a crash mid-write cannot leave a
    half-written registry behind. Damaged lines are carried over verbatim."""
    ensure()
    tmp = POSTS_JSONL + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for line in _BAD_LINES:
            f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, POSTS_JSONL)

def mutate_posts(fn):
    """Locked read-modify-write. EVERY mutation of the store goes through here."""
    with posts_lock():
        recs = load_posts()
        out = fn(recs)
        save_posts(recs)
        return out

_STATUS_RANK = {"new": 0, "seeded": 1, "done": 2}
def upsert_post(rec, keep_richer_note=False):
    """Insert or update a post-material record by its id (idempotent).

    On UPDATE, content fields (title/note/when/source_kind/lang_hint) refresh,
    but CURATED / PROGRESS fields are protected so a re-feed or re-append never
    clobbers human work (caught by /tt 2026-06-30 when a re-feed reset a seeded
    item to new):
      - status     : never downgrades (new<seeded<done)
      - slug       : kept once set
      - visibility : kept once curated to non-public (human override wins)
    """
    return mutate_posts(lambda recs: _upsert_into(recs, rec, keep_richer_note))

def _upsert_into(recs, rec, keep_richer_note=False):
    for i, r in enumerate(recs):
        if r.get("id") == rec.get("id"):
            merged = dict(r)
            for k, v in rec.items():
                if v in (None, "") and k != "note":
                    continue
                if k == "status" and _STATUS_RANK.get(v, 0) <= _STATUS_RANK.get(r.get("status", "new"), 0):
                    continue  # don't downgrade or reset progress
                if k == "slug" and r.get("slug"):
                    continue  # keep curated slug
                if k == "visibility" and r.get("visibility") not in (None, "", "public"):
                    continue  # keep human override (personal/private)
                if (k == "note" and keep_richer_note
                        and len(str(v)) < len(str(r.get("note", "")))):
                    # ONLY the plan feeder passes keep_richer_note: its note is
                    # derived from the plan's one-line cluster title and would
                    # otherwise clobber the fuller triage/miner note every day
                    # (/tt 2026-07-26). An explicit `append` still shortens a
                    # note on purpose - a human trimming it must not be ignored
                    # (failure mode named by the Codex breaker).
                    continue
                merged[k] = v
            recs[i] = merged
            return "updated"          # mutate_posts() does the (locked) save
    recs.append(rec)
    return "added"

def find_post(recs, pid):
    for r in recs:
        if r.get("id") == pid:
            return r
    return None

# ------------------------------------------------------------------- commands
def cmd_read_state(_):
    print(json.dumps(read_state()))

def cmd_save_state(a):
    ensure()
    st = read_state()
    if a.hub is not None:
        st["hub"] = max(int(st.get("hub", 0)), int(a.hub))
    if a.saved is not None:
        st["saved"] = max(int(st.get("saved", 0)), int(a.saved))
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print("saved-state hub=%s saved=%s" % (st["hub"], st["saved"]))

def cmd_append(a):
    ensure()
    if a.bucket not in QUEUES:
        print("ERR bad bucket"); sys.exit(2)
    if a.visibility not in VISIBILITY:
        print("ERR bad visibility (public|personal|private)"); sys.exit(2)
    if a.source_kind not in SOURCE_KINDS:
        print("ERR bad source-kind (voice|openclaw|event|session)"); sys.exit(2)
    path = os.path.join(TRIAGE, QUEUES[a.bucket])
    new = not os.path.exists(path)
    when = a.when or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    # 1) HUMAN view (unchanged behaviour) -----------------------------------
    block = []
    if new:
        block.append(HEADER[a.bucket])
    tag = "" if a.visibility == "public" else "  [%s]" % a.visibility.upper()
    block.append("\n## %s %s%s  (src %s, %s)\n" % (ICON[a.bucket], a.title.strip(), tag, a.src or "-", when))
    if a.note:
        block.append(a.note.strip() + "\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(block))
    # 2) MACHINE view for POST bucket (the S5 handoff store) -----------------
    upserted = ""
    if a.bucket == "post":
        rec = {
            "id": a.src or "post:%s" % when,
            "when": when,
            "title": a.title.strip(),
            "note": (a.note or "").strip(),
            "source_kind": a.source_kind,
            "visibility": a.visibility,
            "lang_hint": a.lang_hint,
            "status": "new",
            "slug": "",
        }
        upserted = " | posts.jsonl:" + upsert_post(rec)
    print("appended %s -> %s%s" % (a.bucket, QUEUES[a.bucket], upserted))

def cmd_set_visibility(a):
    if a.visibility not in VISIBILITY:
        print("ERR bad visibility (public|personal|private)"); sys.exit(2)
    def _set(recs):
        r = find_post(recs, a.id)
        if not r:
            print("ERR no post-material with id %s" % a.id); sys.exit(2)
        r["visibility"] = a.visibility
    mutate_posts(_set)
    print("visibility %s -> %s" % (a.id, a.visibility))

def cmd_seed_episode(a):
    """Turn one post-material record into an episode SEED that S5 consumes."""
    box = {}
    def _seed(recs):                     # locked: this mutates the store too (/retro 27.07)
        r = find_post(recs, a.id)
        if not r:
            print("ERR no post-material with id %s" % a.id); sys.exit(2)
        vis = r.get("visibility", "public")
        if vis == "private" and not a.allow_private:
            print("BLOCKED %s is PRIVATE - personal lane only; use --allow-private to override" % a.id)
            sys.exit(3)
        os.makedirs(SEEDS_DIR, exist_ok=True)
        slug = a.slug or slugify(r.get("title", ""), fallback=slugify(a.id))
        seed = {
            "slug": slug,
            "title": r.get("title", ""),
            "source": r.get("id"),
            "visibility": vis,
            "lang_hint": r.get("lang_hint", "ru"),
            "source_kind": r.get("source_kind", "voice"),
            "material": r.get("note", ""),
            "created": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "from": "S4-voice_triage",
            "decision": "decision-content-pipeline-reality-show",
        }
        out = os.path.join(SEEDS_DIR, slug + ".json")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
        r["status"] = "seeded"
        r["slug"] = slug
        box.update(out=out, vis=vis)
    mutate_posts(_seed)
    out, vis = box["out"], box["vis"]
    print("seeded %s -> %s (visibility=%s)" % (a.id, out, vis))
    print("HANDOFF S5: python episode_adapter.py new --from-seed %s" % out)

def cmd_status(_):
    recs = load_posts()
    total = len(recs)
    by_src = {}
    by_vis = {}
    by_st = {}
    for r in recs:
        by_src[r.get("source_kind", "?")] = by_src.get(r.get("source_kind", "?"), 0) + 1
        by_vis[r.get("visibility", "?")] = by_vis.get(r.get("visibility", "?"), 0) + 1
        by_st[r.get("status", "?")] = by_st.get(r.get("status", "?"), 0) + 1
    seeds = 0
    if os.path.isdir(SEEDS_DIR):
        seeds = len([x for x in os.listdir(SEEDS_DIR) if x.endswith(".json")])
    def fmt(d):
        return ", ".join("%s=%d" % (k, d[k]) for k in sorted(d)) or "-"
    print("POST_MATERIAL_TOTAL %d" % total)
    print("BY_SOURCE          %s" % fmt(by_src))
    print("BY_VISIBILITY      %s" % fmt(by_vis))
    print("BY_STATUS          %s" % fmt(by_st))
    print("PUBLIC_PENDING     %d" % len([r for r in recs
          if r.get("visibility") == "public" and r.get("status") == "new"]))
    print("EPISODE_SEEDS      %d" % seeds)

def cmd_list(a):
    recs = load_posts()
    if a.status:
        recs = [r for r in recs if r.get("status") == a.status]
    if a.visibility:
        recs = [r for r in recs if r.get("visibility") == a.visibility]
    if not recs:
        print("(no matching post-material)"); return
    for r in recs:
        print("%-14s %-9s %-8s %-6s %s" % (
            r.get("id", "?"), r.get("visibility", "?"), r.get("status", "?"),
            r.get("source_kind", "?"), r.get("title", "")[:70]))

# ------------------------------------------------- PUBLISHED write-back (2026-07-27)
# WHY: the funnel could count what ARRIVED but never what got PUBLISHED - the last
# hop had no write-back, so the canon metric "published/active >= 80%" was not just
# low, it was UNCOMPUTABLE (weekly report 27.07 had to print "n/a"). A metric nobody
# can compute is a broken pipeline, not a bad number (Connect rule: own it A->Z).
#
# Publication FACTS live on three rails; a fact is real if ANY of them says so
# (rule "check ALL the places, not one"):
#   1) registry/pub_ledger.jsonl   event=posted, id="episode:<slug>"   <- fact journal
#   2) registry/pubmetrics.db      publications.story_id="episode:<slug>" <- metrics
#   3) episodes/<slug>/meta.json   status=="published"                 <- adapter view
# The join key back into this store is the record's `slug` (set by seed-episode or
# by `link-episode` when an episode was built outside the funnel).
REGISTRY = os.path.join(BASE, "registry")
PUB_LEDGER = os.path.join(REGISTRY, "pub_ledger.jsonl")
PUB_DB = os.path.join(REGISTRY, "pubmetrics.db")
EPISODES_DIR = os.path.join(BASE, "episodes")
TRIAGE_LOG = os.path.join(TRIAGE, "triage_log.jsonl")
ACTIVE_STATUSES = ("post", "merge", "series", "bank")  # canon: 6 statuses, 4 are "active"


def _fact(facts, slug, rail, at="", platform="", url=""):
    """Merge one rail's sighting into the fact for `slug`.

    One episode normally goes out as a FAN (teaser -> TG, medium -> FB, longread ->
    GitHub...), so platforms accumulate into a list. Collapsing them to one field
    produced a frankenstein record - the timestamp of one publication next to the
    platform of another (/tt 2026-07-27 caught it).
    """
    f = facts.setdefault(slug, {"at": "", "platforms": [], "url": "", "rails": []})
    if rail not in f["rails"]:
        f["rails"].append(rail)
    # keep the EARLIEST known publication moment (that is when it actually went out)
    if at and (not f["at"] or at < f["at"]):
        f["at"] = at
    if platform and platform not in f["platforms"]:
        f["platforms"].append(platform)
    if url and not f["url"]:
        f["url"] = url
    f["platform"] = ", ".join(f["platforms"])   # flat view for humans/records
    return f


def published_facts():
    """-> ({slug: {...}}, [rails_down]) across all publish rails.

    A rail that cannot be read (DB locked, file corrupt, folder missing) is REPORTED,
    never treated as "nothing published there": a silent fallback to 0 would print a
    confident wrong number, which is worse than an honest gap (Codex break 2026-07-27).
    """
    facts = {}
    down = []
    # rail 1: the fact journal
    if not os.path.exists(PUB_LEDGER):
        down.append("pub_ledger: file missing (%s)" % PUB_LEDGER)
    else:
        try:
            bad = 0
            with open(PUB_LEDGER, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        bad += 1
                        continue
                    if e.get("event") != "posted":
                        continue
                    pid = str(e.get("id", ""))
                    if pid.startswith("episode:"):
                        _fact(facts, pid[len("episode:"):], "pub_ledger",
                              str(e.get("at", ""))[:16], e.get("platform", ""), e.get("url", ""))
            if bad:
                down.append("pub_ledger: %d unreadable line(s) skipped" % bad)
        except OSError as exc:
            down.append("pub_ledger: %s" % str(exc)[:60])
    # rail 2: the metrics DB (dist-tracker / gh / tg collectors write here too)
    if not os.path.exists(PUB_DB):
        down.append("pubmetrics.db: file missing")
    else:
        try:
            import sqlite3
            con = sqlite3.connect("file:%s?mode=ro" % PUB_DB.replace("\\", "/"), uri=True,
                                  timeout=5.0)
            try:
                for sid, plat, url, pat in con.execute(
                        "select story_id, platform, url, published_at from publications "
                        "where story_id like 'episode:%'"):
                    _fact(facts, str(sid)[len("episode:"):], "pubmetrics",
                          str(pat or "")[:16], plat or "", url or "")
            finally:
                con.close()
        except Exception as exc:                     # locked/corrupt must not fake a zero
            down.append("pubmetrics.db unreadable: %s" % str(exc)[:60])
    # rail 3: the episode's own meta
    if not os.path.isdir(EPISODES_DIR):
        down.append("episodes/: folder missing")
    else:
        broken = 0
        for slug in os.listdir(EPISODES_DIR):
            meta = os.path.join(EPISODES_DIR, slug, "meta.json")
            if not os.path.exists(meta):
                continue
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    m = json.load(f)
            except Exception:
                broken += 1
                continue
            if str(m.get("status", "")).lower() == "published":
                f = _fact(facts, slug, "episode_meta",
                          str(m.get("wow_date") or m.get("created") or "")[:16])
                # эпизод = ВЕЕР тиров (тизер/медиум/лонгрид/дев-лог). Вышел один тир -
                # материал наружу вышел (done честен), но выдавать это за «вышло всё»
                # нельзя: держим план веера рядом с фактом (Grok break 2026-07-27).
                f["tiers_planned"] = len(m.get("parts") or [])
        if broken:
            down.append("episodes/: %d unreadable meta.json" % broken)
    return facts, down


def _apply_published(rec, at="", platform="", url="", via="manual"):
    """Stamp one record as published (idempotent; never downgrades an earlier fact)."""
    rec["status"] = "done"
    pub = rec.get("published") or {}
    rec["published"] = {
        "at": at or pub.get("at") or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "platform": platform or pub.get("platform", ""),
        "url": url or pub.get("url", ""),
        "via": via,
    }
    return rec


def cmd_unpublish(a):
    """Откатить «опубликовано»: пост удалён/отозван, зелёная галочка обязана погаснуть.

    Факт публикации в журналах остаётся (он БЫЛ), поэтому запись помечается
    `retracted` - иначе ближайший reconcile честно увидит старый факт и воскресит
    done, и мы получим вечную ложную зелень (Grok break 2026-07-27).
    """
    if not (a.reason or "").strip():
        print("ERR --reason is required: why the publication was taken down"); sys.exit(2)
    box = {}
    def _un(recs):
        r = find_post(recs, a.id)
        if not r:
            print("ERR no post-material with id %s" % a.id); sys.exit(2)
        box["was"] = r.get("status", "new")
        r["status"] = "seeded" if r.get("slug") else "new"
        r["retracted"] = {"at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
                          "reason": a.reason.strip(),
                          "was_published": r.pop("published", {})}
    mutate_posts(_un)
    print("UNPUBLISHED %s (%s -> %s) reason=%s" % (
        a.id, box.get("was"), "seeded/new", a.reason.strip()[:60]))

def cmd_mark_published(a):
    """The write-back API every publish rail must call after a successful publish."""
    box = {}
    def _mark(recs):
        r = find_post(recs, a.id)
        if not r:
            print("ERR no post-material with id %s" % a.id); sys.exit(2)
        box["was"] = r.get("status", "new")
        _apply_published(r, a.when, a.platform, a.url, a.via or "manual")
    mutate_posts(_mark)
    print("PUBLISHED %s (%s -> done) platform=%s via=%s" % (
        a.id, box.get("was"), a.platform or "-", a.via or "manual"))


def cmd_link_episode(a):
    """Sew an episode slug onto a funnel record (episodes built outside the funnel).

    Without this the join key is missing and the item stays 'new' forever even
    though it was published - which is exactly why published/active read 0%.
    """
    facts = published_facts()[0]
    box = {}
    def _link(recs):
        r = find_post(recs, a.id)
        if not r:
            print("ERR no post-material with id %s" % a.id); sys.exit(2)
        r["slug"] = a.slug
        if r.get("status", "new") == "new":
            r["status"] = "seeded"
        if a.slug in facts:
            f = facts[a.slug]
            _apply_published(r, f["at"], f["platform"], f["url"],
                             "link-episode:" + ",".join(f["rails"]))
            box["published"] = ",".join(f["rails"])
        box["status"] = r.get("status")
    mutate_posts(_link)
    if box.get("published"):
        print("LINKED %s -> episode:%s | already published -> done (%s)" % (
            a.id, a.slug, box["published"]))
    else:
        print("LINKED %s -> episode:%s (no publication fact yet, status=%s)" % (
            a.id, a.slug, box.get("status")))


def cmd_reconcile_published(a):
    """Deterministic 0-token matcher: publication facts -> funnel records.

    DRY-RUN by default (shadow-first): prints what it WOULD close; --write applies.
    Also names the facts it could NOT attach - an unattached publication means the
    loop is still open somewhere, and silence there would fake a healthy funnel.
    """
    facts, down = published_facts()
    closed, already, unlinked, retracted = [], [], [], []
    def _reconcile(recs):
        by_slug = {}
        for r in recs:
            if r.get("slug"):
                by_slug.setdefault(r["slug"], []).append(r)
        for slug, f in sorted(facts.items()):
            targets = by_slug.get(slug) or []
            if not targets:
                unlinked.append((slug, f))
                continue
            for r in targets:
                if r.get("status") == "done":
                    already.append((slug, r.get("id")))
                    continue
                if r.get("retracted"):
                    retracted.append((slug, r.get("id")))   # снято руками - не воскрешаем
                    continue
                if a.write:
                    _apply_published(r, f["at"], f["platform"], f["url"],
                                     "reconcile:" + ",".join(f["rails"]))
                closed.append((slug, r.get("id")))
    if a.write:
        mutate_posts(_reconcile)
    else:
        _reconcile(load_posts())          # dry-run: read only, never touch the store
    print("RECONCILE %s" % ("WRITE" if a.write else "DRY-RUN (add --write to apply)"))
    for msg in down:
        print("  RAIL DOWN! %s" % msg)
    print("  facts_found        %d" % len(facts))
    print("  closed_to_done     %d" % len(closed))
    for slug, pid in closed:
        print("    + %-22s <- %s" % (pid, slug))
    print("  already_done       %d" % len(already))
    print("  skipped_retracted  %d  (taken down by hand - reconcile never revives them)" % len(retracted))
    for slug, pid in retracted:
        print("    - %-22s <- %s" % (pid, slug))
    print("  facts_unattached   %d  (published, but no funnel record carries that slug)" % len(unlinked))
    for slug, f in unlinked:
        print("    ? episode:%-40s rails=%s" % (slug[:40], ",".join(f["rails"])))
    if unlinked:
        print("  FIX: python voice_triage.py link-episode --id <post-id> --slug <slug>")


# --------------------------------------------------------------- funnel stats
def _log_rows(days):
    """triage_log.jsonl rows inside the window (days<=0 -> everything)."""
    rows = []
    if not os.path.exists(TRIAGE_LOG):
        return rows
    cutoff = None
    if days and days > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with open(TRIAGE_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("﻿")
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            day = (o.get("run") or o.get("when") or "")[:10]
            if cutoff and day < cutoff:
                continue
            rows.append(o)
    return rows


def funnel_data(days=7):
    """The numbers behind the PUBLISHED metric. Pure read, 0 tokens."""
    rows = _log_rows(days)
    posts = {r.get("id"): r for r in load_posts()}
    by_status = {}
    seen_ids, active_ids, no_reason = [], [], []
    for o in rows:
        st = o.get("content_status", "?")
        by_status[st] = by_status.get(st, 0) + 1
        pid = o.get("id")
        if pid:
            seen_ids.append(pid)
        if st in ACTIVE_STATUSES and pid:
            active_ids.append(pid)
        if st == "suppress" and not (o.get("reason") or "").strip():
            no_reason.append(pid)
    arrived = len(rows)
    active = sum(by_status.get(s, 0) for s in ACTIVE_STATUSES)
    internal = by_status.get("internal", 0)
    suppressed = by_status.get("suppress", 0)
    uniq_active = list(dict.fromkeys(active_ids))
    seeded = [i for i in uniq_active if (posts.get(i) or {}).get("status") == "seeded"]
    published = [i for i in uniq_active if (posts.get(i) or {}).get("status") == "done"]
    facts, rails_down = published_facts()
    linked_slugs = {r.get("slug") for r in posts.values() if r.get("slug")}
    unattached = sorted(s for s in facts if s not in linked_slugs)
    # A publication with no funnel record is only ALARMING while it is fresh. The
    # historical wow-episodes grew from live sessions, not from voice notes, and a
    # flag that can never go green is a watchdog people learn to ignore - so old
    # ones stay VISIBLE (listed) but stop screaming.
    cutoff = ((datetime.date.today() - datetime.timedelta(days=days)).isoformat()
              if days and days > 0 else "")
    unattached_recent = [s for s in unattached
                         if not cutoff or (facts[s]["at"] or "")[:10] >= cutoff]
    store_done = [r for r in posts.values() if r.get("status") == "done"]
    rate = (100.0 * len(published) / active) if active else None
    flags = []
    for msg in rails_down:
        # first flag on purpose: if a rail is down, every number below is a FLOOR,
        # not a measurement - say so instead of printing a confident zero.
        flags.append("RAIL_DOWN: %s -> published-count may be UNDERSTATED" % msg)
    if active + internal + suppressed != arrived:
        flags.append("COMPLETENESS: active+internal+suppress (%d) != arrived (%d) - something died silently"
                     % (active + internal + suppressed, arrived))
    if no_reason:
        flags.append("SUPPRESS_WITHOUT_REASON: %d (canon requires a reason)" % len(no_reason))
    if unattached_recent:
        flags.append("UNATTACHED_PUBLICATIONS: %d episodes published IN THIS WINDOW but tied to no "
                     "funnel record (published-count understated until linked)" % len(unattached_recent))
    if rate is not None and rate < 80.0:
        flags.append("PUBLISH_RATE: %.0f%% of active material published (canon floor 80%%)" % rate)
    return {
        "window_days": days,
        "arrived": arrived,
        "by_status": by_status,
        "active": active,
        "internal": internal,
        "suppressed": suppressed,
        "seeded": len(seeded),
        "published": len(published),
        "published_ids": published,
        "publish_rate": rate,
        "store_total": len(posts),
        "store_done": len(store_done),
        "facts_total": len(facts),
        "rails_down": rails_down,
        "unattached": unattached,
        "unattached_recent": unattached_recent,
        "suppress_no_reason": no_reason,
        "flags": flags,
        "generated": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
    }


def cmd_funnel(a):
    d = funnel_data(a.days)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    win = "all time" if a.days <= 0 else "last %d days" % a.days
    print("VOICE->CONTENT FUNNEL (%s, generated %s)" % (win, d["generated"]))
    print("  ARRIVED            %d" % d["arrived"])
    print("  ACTIVE             %d  (post/merge/series/bank)" % d["active"])
    print("  SEEDED             %d  (episode seed created)" % d["seeded"])
    print("  PUBLISHED          %d%s" % (d["published"],
          "" if d["publish_rate"] is None else "  = %.0f%% of active" % d["publish_rate"]))
    print("  INTERNAL           %d" % d["internal"])
    print("  SUPPRESSED         %d" % d["suppressed"])
    print("  ---")
    print("  STORE_DONE_TOTAL   %d / %d records" % (d["store_done"], d["store_total"]))
    print("  PUBLISH_FACTS      %d episodes (all rails)" % d["facts_total"])
    print("  UNATTACHED_FACTS   %d  (of them fresh in window: %d)" % (
        len(d["unattached"]), len(d["unattached_recent"])))
    for f in d["flags"]:
        print("  FLAG! %s" % f)
    if not d["flags"]:
        print("  OK no flags")


# backfill posts.jsonl from the legacy human posts.md (one-time, idempotent)
_MD_HDR = re.compile(r"^##\s*\[POST\]\s*(.*?)\s*\(src\s*([^,]+?),\s*([^)]+?)\)\s*$")
def cmd_migrate_posts(_):
    if not os.path.exists(POSTS_MD):
        print("MIGRATED 0 (no posts.md)"); return
    existing = {r.get("id") for r in load_posts()}
    added = 0
    with open(POSTS_MD, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        m = _MD_HDR.match(lines[i].strip())
        if m:
            title, src, when = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            # strip any [PERSONAL]/[PRIVATE] tag the human view may carry
            vis = "public"
            tm = re.search(r"\[(PERSONAL|PRIVATE)\]", title)
            if tm:
                vis = tm.group(1).lower()
                title = re.sub(r"\s*\[(PERSONAL|PRIVATE)\]\s*", " ", title).strip()
            # gather note lines until next header or blank-then-header
            note = []
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("## "):
                if lines[j].strip():
                    note.append(lines[j].strip())
                j += 1
            if src not in existing:
                upsert_post({
                    "id": src, "when": when, "title": title,
                    "note": " ".join(note), "source_kind": "voice",
                    "visibility": vis, "lang_hint": "ru",
                    "status": "new", "slug": "",
                })
                existing.add(src)
                added += 1
            i = j
        else:
            i += 1
    print("MIGRATED %d new records (posts.jsonl now %d total)" % (added, len(load_posts())))

# feed the curated daily plan (plan-<DAY>.md) into posts.jsonl ----------------
# The daily "Decide" step already CLUSTERS both sources (voice + openclaw) and
# judges each "Публично?". Re-asking an LLM to do that (old SKILL step 6b) is
# fragile and has never fired (openclaw=0 in the store). This lifts the already-
# made ✅-public clusters into the machine store deterministically (0 tokens,
# idempotent via upsert). It writes ONLY posts.jsonl (the S5 handoff); posts.md
# stays the voice-triage human queue, and the plan itself is the human view here.
PLANS_DIR = os.path.join(BASE, "plans")
_ROW = re.compile(r"^\s*\|(.+)\|\s*$")

def _parse_plan_clusters(day):
    """Return [{title,src,source_kind,visibility,note}] for ✅-public plan rows."""
    path = os.path.join(PLANS_DIR, "plan-%s.md" % day)
    if not os.path.exists(path):
        return None  # signal "no plan" distinctly from "plan with 0 public"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    # locate the table header to map columns by name
    cols = None
    rows = []
    for ln in lines:
        m = _ROW.match(ln)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        joined = " ".join(cells).lower()
        if cols is None:
            if "кластер" in joined and ("публично" in joined or "public" in joined):
                cols = {name.lower(): i for i, name in enumerate(cells)}
            continue
        if set("".join(cells)) <= set("-: "):  # the |---|---| separator row
            continue
        rows.append(cells)
    if cols is None:
        return []
    def col(cells, *names):
        for n in names:
            for k, i in cols.items():
                if n in k and i < len(cells):
                    return cells[i]
        return ""
    out = []
    for n, cells in enumerate(rows, 1):
        pub = col(cells, "публично", "public").lower()
        # yes-marker = ✅ (natural/SKILL default) OR the word "да" (legacy); ⛔ = skip.
        if "⛔" in pub or not ("✅" in pub or "да" in pub or "yes" in pub):
            continue
        title = col(cells, "кластер", "cluster").strip()
        if not title or set(title) <= set("-— "):
            continue
        src_cell = col(cells, "источник", "source")
        # whichever of hub:/cc: appears FIRST in the cell wins (a row should only
        # ever cite one primary source, but don't hardcode priority if it doesn't).
        id_match = re.search(r"hub:(\d+)|cc:(live-[0-9a-f]+)", src_cell)
        if id_match:
            if id_match.group(1):
                src, kind = "hub:%s" % id_match.group(1), "voice"
            else:
                src, kind = "cc:%s" % id_match.group(2), "session"
        elif re.search(r"raw-|openclaw", src_cell.lower()):
            src, kind = "openclaw:%s#%d" % (day, n), "openclaw"
        else:
            src, kind = "plan:%s#%d" % (day, n), "event"
        vis = "personal" if re.search(r"личн|personal", pub) else "public"
        note = title
        if "обобщ" in pub.lower():
            note += "  [ОБОБЩИТЬ специфику перед публикацией]"
        out.append({"title": title[:90], "src": src, "source_kind": kind,
                    "visibility": vis, "note": note})
    return out

def cmd_feed_from_plan(a):
    day = a.day or datetime.datetime.now().strftime("%Y-%m-%d")
    clusters = _parse_plan_clusters(day)
    if clusters is None:
        print("FEED 0 (no plan-%s.md)" % day); return
    if not clusters:
        print("FEED 0 (plan-%s.md has no public clusters)" % day); return
    # never disturb an item already in flight (seeded/done) - the feed only
    # introduces NEW clusters and refreshes still-"new" ones (root fix /tt 06-30).
    in_flight = {r.get("id") for r in load_posts()
                 if r.get("status") in ("seeded", "done")}
    added = updated = kept = 0
    for c in clusters:
        if c["src"] in in_flight:
            kept += 1
            continue
        rec = {
            "id": c["src"], "when": "%sT08:45" % day, "title": c["title"],
            "note": c["note"], "source_kind": c["source_kind"],
            "visibility": c["visibility"], "lang_hint": "ru",
            "status": "new", "slug": "",
        }
        if upsert_post(rec, keep_richer_note=True) == "added":
            added += 1
        else:
            updated += 1
    print("FEED plan-%s: added %d, updated %d, kept-in-flight %d (posts.jsonl now %d)" % (
        day, added, updated, kept, len(load_posts())))

# ----------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("read-state").set_defaults(func=cmd_read_state)
    s = sub.add_parser("save-state"); s.add_argument("--hub", type=int); s.add_argument("--saved", type=int); s.set_defaults(func=cmd_save_state)
    ap = sub.add_parser("append")
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--src", default="")
    ap.add_argument("--when", default="")
    ap.add_argument("--visibility", default="public")
    ap.add_argument("--source-kind", dest="source_kind", default="voice")
    ap.add_argument("--lang-hint", dest="lang_hint", default="ru")
    ap.set_defaults(func=cmd_append)
    sv = sub.add_parser("set-visibility")
    sv.add_argument("--id", required=True); sv.add_argument("--visibility", required=True)
    sv.set_defaults(func=cmd_set_visibility)
    se = sub.add_parser("seed-episode")
    se.add_argument("--id", required=True); se.add_argument("--slug", default="")
    se.add_argument("--allow-private", action="store_true")
    se.set_defaults(func=cmd_seed_episode)
    sub.add_parser("status").set_defaults(func=cmd_status)
    ls = sub.add_parser("list")
    ls.add_argument("--status", default=""); ls.add_argument("--visibility", default="")
    ls.set_defaults(func=cmd_list)
    sub.add_parser("migrate-posts").set_defaults(func=cmd_migrate_posts)
    mp = sub.add_parser("mark-published")
    mp.add_argument("--id", required=True)
    mp.add_argument("--platform", default=""); mp.add_argument("--url", default="")
    mp.add_argument("--when", default=""); mp.add_argument("--via", default="manual")
    mp.set_defaults(func=cmd_mark_published)
    up = sub.add_parser("unpublish")
    up.add_argument("--id", required=True); up.add_argument("--reason", default="")
    up.set_defaults(func=cmd_unpublish)
    le = sub.add_parser("link-episode")
    le.add_argument("--id", required=True); le.add_argument("--slug", required=True)
    le.set_defaults(func=cmd_link_episode)
    rp = sub.add_parser("reconcile-published")
    rp.add_argument("--write", action="store_true")
    rp.set_defaults(func=cmd_reconcile_published)
    fn = sub.add_parser("funnel")
    fn.add_argument("--days", type=int, default=7)
    fn.add_argument("--json", action="store_true")
    fn.set_defaults(func=cmd_funnel)
    ff = sub.add_parser("feed-from-plan")
    ff.add_argument("--day", default="")
    ff.set_defaults(func=cmd_feed_from_plan)
    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help(); sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()
