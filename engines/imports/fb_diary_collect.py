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
"""fb_diary_collect.py - gather one day of Claude Code (openclaw) conversation
text into a single UTF-8 file for the daily Facebook-diary generator.

Usage:
    python fb_diary_collect.py [YYYY-MM-DD]

SOURCE = HYBRID (cross-machine, Anton 2026-06-23; RESTORED 2026-07-25):
  1. PRIMARY - the SHARED session pool via vault_sessions.recent_sessions(day=...):
     EVERY machine's dialogs of that day (hub + laptop + Macs), machine-stamped.
  2. LOCAL FILL - this machine's own ~/.claude/projects sessions of the same day that
     the pool does not have yet (the archive task runs nightly ~03:30, so today's live
     work - and, measured 2026-07-25, most of this hub's manual work - is pool-invisible).
  Dedup by session id (jsonl basename == cliSessionId); the pool version wins.
A 2026-07-14 portability refactor had silently reverted this collector to LOCAL-ONLY
(the vault_sessions engine stayed alive, the consumer got unplugged = a broken Connect
chain), so the "diary of the whole fleet" was quietly a diary of one machine.

- Every block header carries [machine: X] so the writer can see which computer it was.
- Extracts human-readable user prompts + assistant prose; skips tool_use / tool_result
  noise, system reminders, subagent grind, and automated cron self-runs (SENTINEL).
- Writes %IMPORTS%\\fb_diary\\raw-<day>.md (UTF-8, no BOM, LF).
- Prints an ASCII-ONLY summary to stdout (Windows cp1252 safe - never print Cyrillic):
  DAY / SESSIONS / FROM_VAULT / FROM_LOCAL_FILL / CHARS / TRUNCATED / OUT (+ MACHINE rows).

Extending later (ChatGPT / claude.ai): write another collector that APPENDS more
"### session:" blocks into the same raw-<day>.md and the generator will fold them in
(build_inbox.py counts that literal prefix - keep it).

NOTE for importers: intention_mine.py reuses the primitives below (PROJECTS,
FILE_WINDOW_HOURS, extract_text, line_local_date, is_noise) - keep those names.
"""
import os, sys, json, glob, io, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # run-from-anywhere
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"
try:
    import vault_sessions                      # shared cross-machine pool reader
except Exception:
    vault_sessions = None

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
OUTDIR = os.path.join(_IROOT, "fb_diary")
MAX_TOTAL = 280000          # char cap on the concatenated narrative
PER_SESSION = 22000         # char cap per session (keep head+tail) so heavy days keep breadth
MIN_KEEP = 700              # every session is at least this visible (header + who + gist)
FILE_WINDOW_HOURS = 48      # only open sessions touched within this window
SENTINEL = "FACEBOOK_DIARY_AUTORUN"  # marks the generator's own session -> excluded
# Sessions that are automated cron runs (not Anton talking to me) are excluded too.


def target_day():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return datetime.date.today().strftime("%Y-%m-%d")


def line_local_date(o):
    ts = o.get("timestamp")
    if not ts:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d")
    return dt.astimezone().strftime("%Y-%m-%d")


def extract_text(content):
    out = []
    if isinstance(content, str):
        s = content.strip()
        if s:
            out.append(s)
    elif isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                s = (b.get("text") or "").strip()
                if s:
                    out.append(s)
    return out


def is_noise(s):
    low = s.lstrip()
    return (not low
            or low.startswith("<system-reminder>")
            or low.startswith("Caveat:")
            or low.startswith("<command-name>")
            or low.startswith("<local-command")
            or low.startswith("<command-message>"))


def this_machine():
    if vault_sessions is not None:
        try:
            return vault_sessions.this_machine_label()
        except Exception:
            pass
    return os.environ.get("COMPUTERNAME") or "local"


TRIM_MARK = "\n...[session trimmed]...\n"


def trim_to(text, cap):
    """Keep head + tail of a block within `cap` chars (the head carries the '### session:'
    header + who/where, the tail carries how the session ended).

    The header LINE is never cut: it is the block's identity and build_inbox.py counts it,
    so a stdout counter can never over-report what the file actually contains.
    """
    if len(text) <= cap:
        return text
    head_line = text.split("\n", 1)[0]
    if cap <= len(head_line) + len(TRIM_MARK) + 40:
        return head_line + TRIM_MARK
    room = cap - len(TRIM_MARK)
    head = room * 2 // 3
    tail = room - head
    return text[:head] + TRIM_MARK + (text[-tail:] if tail else "")


def fit_budget(blocks, budget, weights=None):
    """Fit ALL blocks into `budget` chars WITHOUT dropping any of them: each block first
    gets a floor (MIN_KEEP -> it is always visible, with machine + topic), then the rest
    of the budget is split PROPORTIONALLY to `weights` - how much ANTON himself typed in
    that session. A 3-hour real conversation keeps its meat; a session that is mostly my
    own prose or robot grind keeps its head. (Weighting by raw size would not work: almost
    every busy-day block hits PER_SESSION, so size-proportional degenerates to equal.)

    ROOT-CAUSE FIX 2026-07-25: the old cap simply cut the concatenated tail, so on a busy
    day the file silently ended after the first ~15 sessions - stdout said "170 sessions,
    5 machines" while the file held 15 blocks and ZERO from this hub. A counter that
    over-reports what a consumer will actually read is worse than a small file.
    -> (blocks, n_trimmed)
    """
    n = len(blocks)
    if not n:
        return blocks, 0
    sizes = [len(b) for b in blocks]
    if sum(sizes) <= budget:
        return blocks, 0

    w = list(weights) if weights else list(sizes)
    w = [max(int(x), 1) for x in w]
    floor = min(MIN_KEEP, budget // n)
    caps = [min(s, floor) for s in sizes]
    for _ in range(4):                       # hand out the rest, reclaiming unused slack
        remaining = budget - sum(caps)
        need = [i for i in range(n) if sizes[i] > caps[i]]
        total_w = sum(w[i] for i in need)
        if remaining <= 0 or not need or not total_w:
            break
        if sum(sizes[i] - caps[i] for i in need) <= remaining:
            for i in need:
                caps[i] = sizes[i]
            break
        for i in need:
            caps[i] = min(sizes[i], caps[i] + int(w[i] * remaining / total_w))

    out, trimmed = [], 0
    for i, b in enumerate(blocks):
        if caps[i] < sizes[i]:
            b = trim_to(b, caps[i])
            trimmed += 1
        out.append(b)
    return out, trimmed


def render_block(sid, cwd, machine, title, turns):
    """One '### session:' block. The literal prefix is a CONTRACT - build_inbox.py counts it."""
    head = "### session: %s   (cwd: %s)  [machine: %s]" % (sid, cwd or "?", machine or "?")
    if title:
        head += "  title: %s" % title[:90].replace("\n", " ")
    block = [head]
    for role, s in turns:
        block.append("[%s] %s" % ("ANTON" if role == "user" else "OPENCLAW", s))
    human = sum(len(s) for role, s in turns if role == "user")   # budget weight
    return trim_to("\n".join(block), PER_SESSION), human


def vault_blocks(day):
    """PRIMARY: every machine's sessions of `day` from the shared pool.
    -> (blocks, seen_session_ids, per-machine counts)"""
    blocks, seen, by_machine = [], set(), {}
    if vault_sessions is None:
        return blocks, seen, by_machine
    try:
        recs = vault_sessions.recent_sessions(day=day)
    except Exception:
        return blocks, seen, by_machine
    for rec in sorted(recs, key=lambda r: (r.get("machine") or "", r.get("session_id") or "")):
        if vault_sessions.is_cron_session(rec):        # automated run, not a real chat
            continue
        if os.sep + "subagents" + os.sep in (rec.get("path") or ""):
            continue
        turns = [(role, s) for role, s in rec.get("turns", []) if not is_noise(s)]
        if not turns:
            continue
        sid = rec.get("session_id") or ""
        seen.add(sid)
        mch = rec.get("machine") or "?"
        by_machine[mch] = by_machine.get(mch, 0) + 1
        blocks.append(render_block("%s.jsonl" % sid, "?", mch, rec.get("title") or "", turns))
    return blocks, seen, by_machine


def main():
    day = target_day()
    now = datetime.datetime.now().timestamp()
    label = this_machine()

    vblocks, seen_ids, by_machine = vault_blocks(day)
    sessions = list(vblocks)          # [(block_text, human_chars)]
    n_vault, n_local = len(vblocks), 0

    files = glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True)
    for f in sorted(files, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0):
        if os.path.splitext(os.path.basename(f))[0] in seen_ids:   # already in from the pool
            continue
        if os.sep + "subagents" + os.sep in f:      # skip verbose subagent grind
            continue
        try:
            if now - os.path.getmtime(f) > FILE_WINDOW_HOURS * 3600:
                continue
        except OSError:
            continue

        turns, cwd, skip = [], "", False
        try:
            with io.open(f, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    if not cwd and o.get("cwd"):
                        cwd = o.get("cwd")
                    d = line_local_date(o)
                    if d is not None and d != day:
                        continue
                    msg = o.get("message") or {}
                    typ = o.get("type")
                    role = msg.get("role") or (typ if typ in ("user", "assistant") else None)
                    if role not in ("user", "assistant"):
                        continue
                    for s in extract_text(msg.get("content")):
                        if SENTINEL in s or "<scheduled-task" in s:
                            skip = True   # automated cron run, not a real conversation
                        if is_noise(s):
                            continue
                        turns.append((role, s))
        except OSError:
            continue

        if skip or not turns:
            continue
        sessions.append(render_block(os.path.basename(f), cwd, label, "", turns))
        n_local += 1
        by_machine[label] = by_machine.get(label, 0) + 1

    # Fair fit: every session survives (trimmed if needed) instead of the tail being cut.
    texts = [t for t, _ in sessions]
    weights = [w for _, w in sessions]
    texts, n_trimmed = fit_budget(texts, max(MAX_TOTAL - 2 * max(len(texts) - 1, 0), 0), weights)
    body = "\n\n".join(texts)

    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)
    outpath = os.path.join(OUTDIR, "raw-%s.md" % day)
    with io.open(outpath, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)

    print("DAY", day)
    print("SESSIONS", len(sessions))
    print("FROM_VAULT", n_vault)
    print("FROM_LOCAL_FILL", n_local)
    print("CHARS", len(body))
    print("TRUNCATED", 1 if n_trimmed else 0)
    print("TRIMMED_BLOCKS", n_trimmed)
    print("OUT", outpath)
    for mch in sorted(by_machine):
        print("MACHINE %s %d" % (mch, by_machine[mch]))


if __name__ == "__main__":
    main()
