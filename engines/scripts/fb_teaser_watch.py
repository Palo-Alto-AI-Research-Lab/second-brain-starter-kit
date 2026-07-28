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
"""fb_teaser_watch.py -- deterministic detector + ledger for the "FB-first -> teaser backfill" lane.

THE GAP (Anton 2026-06-30): Anton sometimes writes a post DIRECTLY on his FB wall, bypassing the
voice->episode pipeline. Those posts have NO teaser in @ClawRus (RU) / X (EN) -> reach is lost.
This watcher (run 1x/day) detects "Anton authored an FB post AND there is no teaser yet" and the
SKILL then drafts + (when armed) posts a teaser FOR EACH such post.

RULE (Anton 2026-06-30): ONE teaser per un-teased post -- if a check finds 5 posts without a
teaser, make 5 teasers. NOT a daily quota. The ledger guarantees each post gets exactly one
(once teased -> recorded -> never repeats).

FLOOD GUARD: the very first armed run would see the whole recent wall as "un-teased" -> mass post.
So the watcher is FORWARD-ONLY by default: the first run SEEDS existing wall posts as `skip`
(backfill_done=true) and posts nothing; from then on every NEW post gets exactly one teaser.
`daily_hard_cap` is only a runaway-bug backstop, not a feature cap.

DIVISION OF LABOUR (AK-47 / skill-design-three-layer):
  * THIS script = 0-token deterministic brain: ledger, dedup, forward-only seed, hard-cap backstop,
    arm/disarm kill-switch. NO network, NO LLM.
  * The /fb-watch SKILL = reads the FB wall via Claude-in-Chrome, feeds the post list here, gets the
    "needs-teaser" list, writes teasers (Opus voice, per teaser-writing-playbook), posts RU via
    Telegram MCP when armed, records back here.

Files (in the vault _imports, NOT in ~/.claude/scripts):
  ledger : <CF>/fb_teaser_ledger.json    config : <CF>/fb_watch_config.json

Usage:
  python fb_teaser_watch.py unteased --in posts.json   # stdin '-' ok; JSON list of NEW/un-teased
                          [--max-age-hours 72]         # unknown posts older than this -> auto seed-skip
                          [--no-auto-skip]             # disable the freshness flood-guard
  python fb_teaser_watch.py seen --id <id> [--permalink ..] [--text ..] [--ts ..]
  python fb_teaser_watch.py record-draft --id <id>     # teaser drafted for this post
  python fb_teaser_watch.py mark-posted --id <id> --rail ru|en
  python fb_teaser_watch.py seed-skip --id <id>        # forward-only backfill: mark as handled, no teaser
  python fb_teaser_watch.py can-post --rail ru         # exit 0 = armed & under hard-cap, exit 3 = blocked
  python fb_teaser_watch.py backfill-status            # exit 0 = done, exit 1 = not yet (first run seeds)
  python fb_teaser_watch.py mark-backfill-done
  python fb_teaser_watch.py status | config | arm | disarm

Exit: 0 ok | 1 backfill-not-done | 2 bad input | 3 blocked (disarmed / hard-cap)
ASCII-only stdout (Windows-safe); JSON files UTF-8.
"""
import os, sys, json, argparse, datetime, hashlib, re

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CF_DIR = os.environ.get("FB_TEASER_CF_DIR", r"%IMPORTS%\content-factory")
LEDGER = os.path.join(CF_DIR, "fb_teaser_ledger.json")
CONFIG = os.path.join(CF_DIR, "fb_watch_config.json")
# Below this many scanned posts a run is a harvest failure, not a quiet "nothing new".
MIN_HARVEST = int(os.environ.get("FB_TEASER_MIN_HARVEST", "3"))

DEFAULT_CONFIG = {
    "clawrus_chat": -1006847702008,        # @ClawRus megagroup (Anton's literal RU target 2026-06-30)
    "clawrus_account": "work_acct_b",          # creator -> can post
    "armed": False,                         # False = draft-first; True = auto-post RU
    "x_poster_ready": False,                # until the social-tools DR builds an X poster -> EN stays draft
    "backfill_done": False,                 # forward-only: first run seeds the existing wall as skip
    "daily_hard_cap": 25,                   # runaway-bug backstop ONLY (not a per-post quota)
    "teaser_len_ru": [240, 370],            # HARD for ClawRus
    "teaser_len_x": [0, 280],               # X hard limit (EN, when poster exists)
    "playbook": r"%VAULT%\08-Templates\teaser-writing-playbook.md",
    "note": "ONE teaser per un-teased post. armed=False keeps all draft-first. First armed run is forward-only (seeds backlog as skip)."
}


def _today():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _load(path, default):
    if not os.path.exists(path):
        return json.loads(json.dumps(default))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(default))


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _ledger():
    return _load(LEDGER, {"posts": {}, "post_log": []})


def _config():
    cfg = _load(CONFIG, DEFAULT_CONFIG)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def _post_done(entry):
    """A post no longer needs a teaser once RU is drafted, posted, or seeded as skip."""
    return entry.get("teaser_ru", "none") in ("drafted", "posted", "skip")


# ---- STABLE DEDUP KEYS (QQQ root-fix #4b8e6e2f, 2026-07-05) -------------------------------
# PROVEN 2026-07-05: FB rotates pfbid per harvest — same wall scanned twice the same day gave
# 0/8 key overlap with the ledger -> the whole wall read as "new" (only armed=false saved us).
# pfbid is NOT identity. Identity lanes, in order of trust:
#   1) story_fbid — FB's stable numeric id (when the harvester resolves it from the canonical URL)
#   2) text_hash  — sha1 of whitespace-normalized text (when the harvester supplies text)
#   3) exact key  — legacy pfbid (same-session only; kept for back-compat)
# The HARVESTER CONTRACT therefore requires text (and/or story_fbid) per post — enforced softly
# here (stderr warning) and in the fb-watch skill.

def _stable_id(s):
    """FB's stable numeric story id out of an id/permalink, '' if absent."""
    if not s:
        return ""
    m = (re.search(r"(?:story_fbid=|/posts/|/videos/|[?&]fbid=)(\d{10,})", s)
         or re.match(r"^\s*(\d{10,})\s*$", s))
    return m.group(1) if m else ""


def _text_hash(text):
    """sha1[:12] of whitespace-normalized text; '' for empty text."""
    norm = " ".join((text or "").split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12] if norm else ""


def _ledger_indexes(led):
    """(by_sid, by_hash): stable-id and text-hash lookups over every ledger entry."""
    by_sid, by_hash = {}, {}
    for key, e in led["posts"].items():
        for sid in (e.get("story_fbid", ""), _stable_id(key), _stable_id(e.get("permalink", ""))):
            if sid:
                by_sid.setdefault(sid, key)
        th = e.get("text_hash", "")
        if th:
            by_hash.setdefault(th, key)
    return by_sid, by_hash


# ---- FRESHNESS GUARD (flood root-fix, 2026-07-14) -----------------------------------------
# The pfbid-rotation flood scenario needs BOTH holes at once: a rotated key AND a ledger entry
# without stable keys (9 early seeds were seeded key-only). Identity lanes close hole 1 for new
# entries; this guard closes hole 2 for good: an UNKNOWN post OLDER than --max-age-hours is by
# definition not "just written" -> it is backlog. The watcher's job is NEW posts only, so stale
# unknowns are auto-seeded as skip (WITH stable keys) instead of being offered for a teaser.
# Unparseable/missing ts counts as stale: the safe failure mode is a missed teaser (visible in
# stderr), never a flood.

_REL_TS = re.compile(r"(\d+)\s*(m|min|minute|h|hour|d|day|w|week)", re.I)
_ISO_TS = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")


def _age_hours(ts):
    """Best-effort age in hours from a harvest ts ('2h', '35 minutes ago', ISO). None = unknown."""
    ts = (ts or "").strip()
    if not ts:
        return None
    m = _ISO_TS.search(ts)
    if m:
        try:
            dt = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                   int(m.group(4) or 12), int(m.group(5) or 0))
            return max(0.0, (datetime.datetime.now() - dt).total_seconds() / 3600.0)
        except ValueError:
            return None
    m = _REL_TS.search(ts)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()[0]
        return n / 60.0 if unit == "m" else n * (1.0 if unit == "h" else 24.0 if unit == "d" else 168.0)
    return None


# ---------------- commands ----------------

def cmd_unteased(a):
    # utf-8-sig: PowerShell's Out-File/redirect writes a BOM; plain utf-8 then dies "bad posts json".
    raw = sys.stdin.read() if a.infile == "-" else open(a.infile, "r", encoding="utf-8-sig").read()
    raw = raw.lstrip("﻿")
    try:
        posts = json.loads(raw)
    except Exception as e:
        print("ERR bad posts json: %s" % e); sys.exit(2)
    if not isinstance(posts, list):
        print("ERR posts must be a JSON list of {id,permalink,text,ts}"); sys.exit(2)
    led = _ledger()
    by_sid, by_hash = _ledger_indexes(led)
    need, aliased, skipped_reshare, no_text, stale_seeded = [], 0, 0, 0, 0
    dirty = False
    for p in posts:
        pid = str(p.get("id") or p.get("permalink") or "").strip()
        if not pid:
            continue
        # authored-only filter (QQQ #4b8e6e2f): reshares/foreign posts never get teasers.
        # Fields are optional (absent = pass) so old harvests keep working.
        if p.get("is_reshare") is True or p.get("author_is_anton") is False:
            skipped_reshare += 1
            continue
        sid = _stable_id(pid) or _stable_id(p.get("permalink", ""))
        th = _text_hash(p.get("text", ""))
        if not th:
            no_text += 1
        # identity lanes: exact key -> stable numeric id -> text hash
        key = pid if pid in led["posts"] else (by_sid.get(sid) or by_hash.get(th) or None)
        if key and key != pid:
            aliased += 1
        e = led["posts"].get(key) if key else None
        if e is None or not _post_done(e):
            age = _age_hours(p.get("ts", ""))
            if e is None and not a.no_auto_skip and (age is None or age > a.max_age_hours):
                # stale unknown -> backlog, not "new": seed as skip WITH stable keys
                se = _touch(led, pid)
                se["teaser_ru"] = "skip"; se["teaser_en"] = "skip"; se["seeded_at"] = _now_iso()
                se["seed_reason"] = "stale-auto (age=%s h, max=%d)" % (
                    "?" if age is None else "%.0f" % age, a.max_age_hours)
                if p.get("permalink"):
                    se["permalink"] = p["permalink"]
                if th:
                    se["text_hash"] = th
                if sid:
                    se["story_fbid"] = sid
                stale_seeded += 1
                dirty = True
                continue
            need.append({"id": pid, "permalink": p.get("permalink", ""),
                         "text": p.get("text", ""), "ts": p.get("ts", "")})
    if dirty:
        _save(LEDGER, led)
    print(json.dumps(need, ensure_ascii=False, indent=2))
    sys.stderr.write("unteased=%d of %d scanned (aliased=%d reshare-skipped=%d stale-auto-skipped=%d)\n"
                     % (len(need), len(posts), aliased, skipped_reshare, stale_seeded))
    if stale_seeded:
        sys.stderr.write("NOTE: %d unknown post(s) older than %dh (or with unparseable ts) were "
                         "auto-seeded as skip -- backlog never floods; use --no-auto-skip to disable\n"
                         % (stale_seeded, a.max_age_hours))
    if no_text:
        sys.stderr.write("WARN: %d posts came WITHOUT text -> hash-dedup blind for them; "
                         "harvest must include full text per post (pfbid rotates!)\n" % no_text)
    # Visibility layer (consensus #0223a74a, 2026-07-20): a thin scan is a HARVEST FAILURE,
    # not "no posts". The FB profile wall virtualizes and renders ~1 post; the Content Library
    # (/professional_dashboard/content/content_library/) returns the real table. A silent small
    # number used to read as "wall is clean" -- it never is.
    if len(posts) < MIN_HARVEST:
        sys.stderr.write("HARVEST-THIN: only %d post(s) scanned (expected >=%d) -> treat as HARVEST FAILURE, "
                         "not 'no new posts'. Re-harvest via Content Library and FLAG to chat 03.\n"
                         % (len(posts), MIN_HARVEST))
        sys.exit(4)


def _touch(led, pid):
    return led["posts"].setdefault(pid, {"first_seen": _now_iso(), "teaser_ru": "none", "teaser_en": "none"})


def cmd_seen(a):
    led = _ledger(); e = _touch(led, a.id)
    if a.permalink:
        e["permalink"] = a.permalink
    if a.text is not None:
        e["text_hash"] = _text_hash(a.text)          # normalized (rotation-proof lane)
    sid = _stable_id(a.id) or _stable_id(a.permalink or "")
    if sid:
        e["story_fbid"] = sid                          # strongest stable lane
    if a.ts: e["fb_ts"] = a.ts
    _save(LEDGER, led); print("seen ok: %s" % a.id)


def cmd_record_draft(a):
    led = _ledger(); e = _touch(led, a.id)
    if e.get("teaser_ru", "none") == "none": e["teaser_ru"] = "drafted"
    if e.get("teaser_en", "none") == "none": e["teaser_en"] = "drafted"
    e["drafted_at"] = _now_iso(); _save(LEDGER, led); print("draft recorded: %s" % a.id)


def cmd_seed_skip(a):
    led = _ledger(); e = _touch(led, a.id)
    e["teaser_ru"] = "skip"; e["teaser_en"] = "skip"; e["seeded_at"] = _now_iso()
    # store stable keys at seed time too -- a seed without them dies on the next pfbid rotation
    if getattr(a, "permalink", None):
        e["permalink"] = a.permalink
    if getattr(a, "text", None):
        e["text_hash"] = _text_hash(a.text)
    sid = _stable_id(a.id) or _stable_id(getattr(a, "permalink", "") or "")
    if sid:
        e["story_fbid"] = sid
    _save(LEDGER, led); print("seeded skip (forward-only backfill): %s" % a.id)


def cmd_can_post(a):
    cfg = _config()
    if not cfg.get("armed"):
        print("BLOCKED: disarmed (draft-first)."); sys.exit(3)
    led = _ledger(); cap = int(cfg.get("daily_hard_cap", 25))
    n = sum(1 for x in led["post_log"] if x.get("date") == _today())
    if n >= cap:
        print("BLOCKED: daily hard-cap %d hit (%d today) -- likely a bug/flood, not normal." % (cap, n)); sys.exit(3)
    print("OK: armed, %d/%d hard-cap today, rail=%s" % (n, cap, a.rail)); sys.exit(0)


def cmd_mark_posted(a):
    led = _ledger(); e = _touch(led, a.id)
    e["teaser_%s" % a.rail] = "posted"; e["posted_%s_at" % a.rail] = _now_iso()
    led["post_log"].append({"date": _today(), "rail": a.rail, "id": a.id, "at": _now_iso()})
    _save(LEDGER, led); print("marked posted: %s rail=%s" % (a.id, a.rail))


def cmd_backfill_status(_):
    cfg = _config()
    if cfg.get("backfill_done"):
        print("backfill: DONE (forward-only active)"); sys.exit(0)
    print("backfill: NOT DONE -- first run seeds existing wall as skip"); sys.exit(1)


def cmd_mark_backfill_done(_):
    cfg = _config(); cfg["backfill_done"] = True; _save(CONFIG, cfg)
    print("backfill marked DONE: from now every NEW un-teased post gets one teaser.")


def cmd_status(_):
    led = _ledger(); cfg = _config(); posts = led["posts"]
    ru_p = sum(1 for e in posts.values() if e.get("teaser_ru") == "posted")
    dr = sum(1 for e in posts.values() if e.get("teaser_ru") == "drafted")
    sk = sum(1 for e in posts.values() if e.get("teaser_ru") == "skip")
    today_p = sum(1 for x in led["post_log"] if x.get("date") == _today())
    print("FB-teaser watch status")
    print("  armed: %s | x_poster_ready: %s | backfill_done: %s" % (cfg["armed"], cfg["x_poster_ready"], cfg["backfill_done"]))
    print("  rule: ONE teaser per un-teased post | hard-cap(safety): %s/day" % cfg["daily_hard_cap"])
    print("  posts tracked: %d (ru posted %d / drafted %d / seeded-skip %d)" % (len(posts), ru_p, dr, sk))
    print("  posted today: %d/%d (hard-cap)" % (today_p, cfg["daily_hard_cap"]))
    print("  RU target: chat %s via %s | EN(X): draft-only until poster" % (cfg["clawrus_chat"], cfg["clawrus_account"]))
    print("  playbook: %s" % cfg["playbook"])


def cmd_config(_):
    print(json.dumps(_config(), ensure_ascii=False, indent=2))


def cmd_arm(_):
    cfg = _config(); cfg["armed"] = True; _save(CONFIG, cfg)
    print("ARMED: auto-post RU teasers ON. First run is forward-only (seeds backlog). Disarm any time.")


def cmd_disarm(_):
    cfg = _config(); cfg["armed"] = False; _save(CONFIG, cfg)
    print("DISARMED: back to draft-first. Nothing auto-posts.")


def main():
    ap = argparse.ArgumentParser(prog="fb_teaser_watch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("unteased"); p.add_argument("--in", dest="infile", default="-")
    p.add_argument("--max-age-hours", type=int, default=72)   # unknown & older -> auto seed-skip
    p.add_argument("--no-auto-skip", action="store_true")     # disable the freshness guard
    p.set_defaults(fn=cmd_unteased)
    p = sub.add_parser("seen"); p.add_argument("--id", required=True); p.add_argument("--permalink", default="")
    p.add_argument("--text", default=None); p.add_argument("--ts", default=""); p.set_defaults(fn=cmd_seen)
    p = sub.add_parser("record-draft"); p.add_argument("--id", required=True); p.set_defaults(fn=cmd_record_draft)
    p = sub.add_parser("seed-skip"); p.add_argument("--id", required=True)
    p.add_argument("--permalink", default=""); p.add_argument("--text", default=None)  # stable keys at seed time
    p.set_defaults(fn=cmd_seed_skip)
    p = sub.add_parser("can-post"); p.add_argument("--rail", required=True, choices=["ru", "en"]); p.set_defaults(fn=cmd_can_post)
    p = sub.add_parser("mark-posted"); p.add_argument("--id", required=True); p.add_argument("--rail", required=True, choices=["ru", "en"]); p.set_defaults(fn=cmd_mark_posted)
    p = sub.add_parser("backfill-status"); p.set_defaults(fn=cmd_backfill_status)
    p = sub.add_parser("mark-backfill-done"); p.set_defaults(fn=cmd_mark_backfill_done)
    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("config"); p.set_defaults(fn=cmd_config)
    p = sub.add_parser("arm"); p.set_defaults(fn=cmd_arm)
    p = sub.add_parser("disarm"); p.set_defaults(fn=cmd_disarm)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
