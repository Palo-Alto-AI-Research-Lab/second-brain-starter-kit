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
declined_scan.py - nightly safety-net for the declined-decisions registry.

WHY: declines logged in session retros used to never reach the registry (the
06-15..06-21 backlog). This catches them DAILY so nothing is lost between sessions.

WHAT IT DOES (deterministic, 0 LLM tokens, can't hallucinate a decline):
  1. Parse the registry -> set of retro files ALREADY cited as a Source (dedup key)
     + the entry titles already present.
  2. Scan recent retro notes that are NOT yet sourced in the registry.
  3. Pull lines that look like a real decline (Decision: rejected/deferred,
     a Declined/Rejected/Deferred heading, strong RU/EN decline phrases in a
     bullet/heading line).
  4. Append the hits to an "## AUTO-CAPTURED - review" SHELF in the registry,
     grouped by source, tagged #needs-review. NOT the main log - a human (me at
     /retro, or Anton) promotes the genuine ones. This is the preference-sweep
     "propose, don't blind-write" rule applied to declines (see the very first
     registry entry 2026-06-06, which deferred a blind auto-writer as unsafe).
  5. Idempotent: a source already cited in the main log OR already on the shelf
     is skipped, so re-running never duplicates.

WEEKLY (Monday, or --revisit): also write a revisit digest of all OPEN declined
items + their "Revisit if" condition to revisit-latest.md, so the conditions get
re-checked instead of rotting.

MANUAL FIX: run `python declined_scan.py 1` (arg = days back, default 1).
Encoding: ASCII-only console prints (Windows cp1251 safe); files read/written utf-8.
"""
import os
import re
import sys
import io
import datetime
import shutil

def _find_registry():
    """Locate declined-decisions.md across machines (laptop/hub have different project folder names).
    Order: explicit env -> any ~/.claude/projects/*/memory/ that has it (newest) -> hub default."""
    import glob
    base = os.path.expanduser(r"~\.claude\projects")
    name = os.environ.get("CLAUDE_MEMORY_NAME")
    if name:
        p = os.path.join(base, name, "memory", "declined-decisions.md")
        if os.path.exists(p):
            return p
    hits = glob.glob(os.path.join(base, "*", "memory", "declined-decisions.md"))
    if hits:
        return max(hits, key=os.path.getmtime)
    return os.path.join(base, "E---CLAUDE-HUB1-June26", "memory", "declined-decisions.md")

REGISTRY = _find_registry()
RETROS   = r"%VAULT%\01-Conversations\Claude\Retros"
HERE     = os.path.dirname(os.path.abspath(__file__))
BACKUPS  = os.path.join(HERE, "backups")
REVISIT_OUT = os.path.join(HERE, "revisit-latest.md")
LOG      = os.path.join(HERE, "declined_scan.log")
HIGHWATER = os.path.join(HERE, "highwater.json")          # shrink-tripwire baseline
ALERT    = os.path.expanduser(r"~\.claude\scripts\tg_bus_send.py")  # chat-03 scream rail
DROP_FRAC = 0.8   # alert if entry-count falls below 80% of the high-water mark (>20% loss)
KEEP_DAILY = 30   # how many daily snapshots to retain

SHELF_HEADER = "## AUTO-CAPTURED - review"

# strong decline signals (case-insensitive); we only trust lines that are a
# bullet / heading / explicit "Decision:" so prose mentions don't trip it.
DECLINE_RE = re.compile(
    r"(decision:\s*\**\s*(rejected|deferred|declined|superseded))"
    r"|\b(rejected|declined|deferred)\b"
    r"|отклон|отклад|отлож|не\s+бер[её]м|не\s+будем|отказал|передумал"
    r"|не\s+делаем|не\s+нужн|не\s+важн|не\s+усложн|против\s+этого",
    re.IGNORECASE,
)
# a line is "structural" (worth trusting) if it is a heading or a bullet
STRUCT_RE = re.compile(r"^\s*(#{1,6}\s|[-*]\s|\d+\.\s)|decision:", re.IGNORECASE)
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")
SRCFILE_RE = re.compile(r"retro-\d{4}-\d{2}-\d{2}-[A-Za-z0-9][A-Za-z0-9\-]*")
DATED_RE   = re.compile(r"retro-(\d{4})-(\d{2})-(\d{2})-")


def log(msg):
    line = "[{0}] {1}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    # ASCII-safe console echo
    print(line.encode("ascii", "replace").decode("ascii"))


def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_registry(path):
    text = read(path)
    sourced = set(m.group(0).lower() for m in SRCFILE_RE.finditer(text))
    titles = set(re.findall(r"^###\s+(.*)$", text, re.MULTILINE))
    return text, sourced, titles


def recent_retros(days):
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=max(0, days - 1))
    out = []
    for name in os.listdir(RETROS):
        if not name.endswith(".md"):
            continue
        if not (name.startswith("retro-") or name.startswith("proposal-")):
            continue
        m = DATED_RE.match(name)
        d = None
        if m:
            try:
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                d = None
        if d is None:
            # fall back to mtime
            ts = os.path.getmtime(os.path.join(RETROS, name))
            d = datetime.date.fromtimestamp(ts)
        if d >= cutoff:
            out.append((name, d))
    out.sort(key=lambda x: x[1])
    return out


def scan_retro(path, cap=8):
    """Return list of candidate decline lines (with nearest heading), capped."""
    try:
        lines = read(path).splitlines()
    except Exception:
        return []
    hits = []
    cur_head = ""
    for ln in lines:
        hm = HEADING_RE.match(ln)
        if hm:
            cur_head = hm.group(1).strip()
        if not ln.strip():
            continue
        if not STRUCT_RE.search(ln):
            continue
        if not DECLINE_RE.search(ln):
            continue
        snippet = ln.strip().lstrip("#*- ").strip()
        if len(snippet) < 8:
            continue
        snippet = snippet[:240]
        ctx = (" [" + cur_head[:60] + "]") if cur_head else ""
        hits.append(snippet + ctx)
        if len(hits) >= cap:
            break
    # de-dup within file, keep order
    seen = set()
    uniq = []
    for h in hits:
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(h)
    return uniq


def build_shelf_block(new_by_source, today):
    out = []
    out.append("")
    out.append("> Auto-captured by declined_scan.py on {0}. These are CANDIDATES from session retros".format(today.isoformat()))
    out.append("> not yet in the main log. Promote the real ones into the Log (with a clean entry), then")
    out.append("> they drop off this shelf automatically (dedup is by Source filename). #needs-review")
    out.append("")
    for src, snips in new_by_source:
        out.append("### {0}  #needs-review".format(src))
        for s in snips:
            out.append("- {0}".format(s))
        out.append("- Source: {0}".format(src))
        out.append("")
    return "\n".join(out)


def inject_shelf(text, block):
    """Insert/extend the AUTO-CAPTURED shelf. Returns new text."""
    if SHELF_HEADER in text:
        # append our block right after the shelf header's intro (before next '## ' or EOF)
        idx = text.index(SHELF_HEADER)
        # find end of shelf (next top-level '## ' after header, or EOF)
        rest = text[idx + len(SHELF_HEADER):]
        nxt = re.search(r"\n## ", rest)
        insert_at = idx + len(SHELF_HEADER) + (nxt.start() if nxt else len(rest))
        return text[:insert_at] + "\n" + block + text[insert_at:]
    else:
        sep = "" if text.endswith("\n") else "\n"
        return text + sep + "\n" + SHELF_HEADER + "\n" + block + "\n"


def shelf_existing_sources(text):
    """Sources already on the shelf (so we don't re-add)."""
    if SHELF_HEADER not in text:
        return set()
    idx = text.index(SHELF_HEADER)
    rest = text[idx:]
    nxt = re.search(r"\n## (?!AUTO)", rest)  # next non-shelf '## '
    seg = rest[: nxt.start()] if nxt else rest
    return set(m.group(0).lower() for m in SRCFILE_RE.finditer(seg))


def write_revisit_digest(text, today):
    """Reformat all OPEN declined entries + Revisit-if into a weekly review file."""
    entries = re.split(r"\n(?=### )", text)
    rows = []
    for e in entries:
        hm = re.match(r"###\s+(.*)", e)
        if not hm:
            continue
        title = hm.group(1).strip()
        if title.endswith("#needs-review"):
            continue
        if "YYYY-MM-DD" in title or "<" in title:  # skip the Entry-format template
            continue
        if re.search(r"superseded|OVERTURNED|SUPERSEDED|СДЕЛАН", e):
            # closed/overturned - skip from "open" list
            if "Revisit if" not in e:
                continue
        rv = re.search(r"Revisit if:?\s*(.+)", e)
        rv_txt = rv.group(1).strip() if rv else "-"
        if rv_txt in ("-", "—", ""):
            continue
        rows.append((title, rv_txt[:300]))
    lines = []
    lines.append("# Revisit digest - declined-decisions ({0})".format(today.isoformat()))
    lines.append("")
    lines.append("Re-check each Revisit-if below against TODAY's reality. If a condition now holds,")
    lines.append("reopen that item EXPLICITLY as a trade-off (do not silently re-pitch). {0} open items.".format(len(rows)))
    lines.append("")
    for t, rv in rows:
        lines.append("- **{0}**".format(t))
        lines.append("  - Revisit if: {0}".format(rv))
    with io.open(REVISIT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(rows)


ENTRY_RE = re.compile(r"(?m)^### ")


def count_entries(text):
    """Number of '### ' entries in the registry (the shrink metric)."""
    return len(ENTRY_RE.findall(text))


def daily_backup(today):
    """Once-per-day timestamped snapshot of the registry (independent of write-time .bak).
    Keeps the last KEEP_DAILY. Second safety net alongside git + the per-write .bak."""
    try:
        dst = os.path.join(BACKUPS, "daily-{0}.bak".format(today.isoformat()))
        if not os.path.exists(dst):
            shutil.copy2(REGISTRY, dst)
            log("daily backup -> {0}".format(os.path.basename(dst)))
        dailies = sorted(g for g in os.listdir(BACKUPS) if g.startswith("daily-") and g.endswith(".bak"))
        for old in dailies[:-KEEP_DAILY]:
            os.remove(os.path.join(BACKUPS, old))
    except Exception as e:
        log("daily backup FAIL: {0}".format(str(e)[:120]))


def scream(msg):
    """Post an alert to chat-03 via tg_bus_send.py (the standing cc-alerts-to-chat-03 rail).
    Never raises. An alert must NEVER die silently: if the group rail does not confirm
    ("BUS-SEND OK"), fall back to bus_ping.py (Anton's Saved Messages); log every verdict."""
    import subprocess
    sent = False
    try:
        if os.path.exists(ALERT):
            r = subprocess.run([sys.executable, ALERT, msg, "--to", "ALL"],
                               capture_output=True, text=True, timeout=90)
            out = (r.stdout or r.stderr or "").strip()
            log("scream rail: {0}".format(out[:120]))
            sent = "BUS-SEND OK" in out
        else:
            log("scream: group rail script missing ({0})".format(ALERT))
    except Exception as e:
        log("scream rail FAIL: {0}".format(str(e)[:120]))
    if not sent:
        # fallback rail: Saved Messages via bus_ping.py (same Telethon session, different target)
        fb = os.path.expanduser(r"~\.claude\scripts\bus_ping.py")
        try:
            if os.path.exists(fb):
                r = subprocess.run([sys.executable, fb, msg],
                                   capture_output=True, text=True, timeout=90)
                out = (r.stdout or r.stderr or "").strip()
                log("scream fallback bus_ping: {0}".format(out[:120]))
                sent = "PING OK" in out
        except Exception as e:
            log("scream fallback FAIL: {0}".format(str(e)[:120]))
    if not sent:
        log("scream: ALL RAILS DOWN, alert only in this log -> {0}".format(msg[:160]))


def guard_shrink(text, today, accept=False):
    """Tripwire: if the registry shrinks >20% below its all-time high-water mark, SCREAM.
    Catches the silent data-loss class (sync-conflict clobber, accidental truncation) that
    git alone misses (git happily snapshots the shrunk file). --accept-count resets the
    baseline after a LEGIT prune so it stops alerting."""
    import json
    cur = count_entries(text)
    hw = 0
    try:
        if os.path.exists(HIGHWATER):
            hw = int(json.load(io.open(HIGHWATER, encoding="utf-8")).get("max_entries", 0))
    except Exception:
        # highwater corrupt -> do NOT silently reset the baseline (that would blind the
        # tripwire right when things are going wrong). Recover it deterministically from
        # the newest daily backup snapshot instead.
        hw = 0
        try:
            dailies = sorted(g for g in os.listdir(BACKUPS) if g.startswith("daily-") and g.endswith(".bak"))
            if dailies:
                hw = count_entries(read(os.path.join(BACKUPS, dailies[-1])))
                log("guard: highwater CORRUPT -> baseline recovered from {0} = {1}".format(dailies[-1], hw))
        except Exception as e2:
            log("guard: highwater corrupt AND backup recovery failed: {0}".format(str(e2)[:120]))

    if accept:
        new_hw = cur
        log("guard: baseline ACCEPTED at {0} entries (was {1})".format(cur, hw))
    elif cur >= hw:
        new_hw = cur                      # new high-water, all good
    else:
        new_hw = hw                       # keep the mark; don't let a shrink lower it
        if hw and cur < hw * DROP_FRAC:
            pct = int(round((1 - cur / float(hw)) * 100))
            scream("⚠️ declined-decisions shrank: {0} -> {1} entries (-{2}%). "
                   "Likely a sync-conflict clobbered the registry (as on 2026-06-21). "
                   "Restore from git/backup. Reset baseline after a legit prune: "
                   "python declined_scan.py --accept-count".format(hw, cur, pct))
            log("guard: SHRINK ALERT fired (hw={0} cur={1})".format(hw, cur))

    try:
        json.dump({"max_entries": new_hw, "last_entries": cur, "updated": today.isoformat()},
                  io.open(HIGHWATER, "w", encoding="utf-8"))
    except Exception as e:
        log("guard: highwater write FAIL: {0}".format(str(e)[:120]))
    log("guard: entries={0} highwater={1}".format(cur, new_hw))


def main():
    days = 1
    do_revisit = False
    accept = False
    for a in sys.argv[1:]:
        if a == "--revisit":
            do_revisit = True
        elif a == "--accept-count":
            accept = True
        else:
            try:
                days = int(a)
            except ValueError:
                pass

    if not os.path.isdir(BACKUPS):
        os.makedirs(BACKUPS)

    today = datetime.date.today()
    log("=== declined_scan start (days={0}, revisit={1}) ===".format(days, do_revisit or today.weekday() == 0))

    try:
        text, sourced, titles = load_registry(REGISTRY)
    except Exception as e:
        # registry gone/unreadable = the WORST case for "чтобы не терять" -> must scream,
        # never die silently before the guard even runs.
        log("registry UNREADABLE: {0}".format(str(e)[:160]))
        scream("🔴 declined-decisions registry MISSING/unreadable at {0} ({1}). "
               "Restore from git / declined-scan backups\\daily-*.bak.".format(REGISTRY, str(e)[:80]))
        sys.exit(1)
    daily_backup(today)
    guard_shrink(text, today, accept=accept)
    on_shelf = shelf_existing_sources(text)
    skip = sourced | on_shelf
    log("registry: {0} sources cited, {1} on shelf".format(len(sourced), len(on_shelf)))

    new_by_source = []
    scanned = 0
    for name, d in recent_retros(days):
        scanned += 1
        base = name[:-3] if name.endswith(".md") else name  # drop .md
        if base.lower() in skip:
            continue
        snips = scan_retro(os.path.join(RETROS, name))
        if snips:
            new_by_source.append((base, snips))

    log("scanned {0} recent retros, {1} have un-logged decline candidates".format(scanned, len(new_by_source)))

    if new_by_source:
        # safety backup before touching the registry
        bak = os.path.join(BACKUPS, "declined-decisions-{0}.bak".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
        shutil.copy2(REGISTRY, bak)
        block = build_shelf_block(new_by_source, today)
        newtext = inject_shelf(text, block)
        with io.open(REGISTRY, "w", encoding="utf-8") as f:
            f.write(newtext)
        log("appended {0} sources to shelf; backup={1}".format(len(new_by_source), os.path.basename(bak)))
    else:
        log("nothing new to capture")

    # weekly revisit digest (Monday) or on demand
    if do_revisit or today.weekday() == 0:
        n = write_revisit_digest(text, today)
        log("revisit digest written: {0} open items -> {1}".format(n, os.path.basename(REVISIT_OUT)))

    log("=== done ===")


if __name__ == "__main__":
    main()
