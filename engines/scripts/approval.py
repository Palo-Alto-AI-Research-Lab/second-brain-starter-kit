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
# approval.py -- REMOTE-APPROVAL ("QQQ") engine for the cross-machine bus.
#
# WHY (Anton 2026-06-28): when a machine's Claude needs Anton's OK (Tier-2 or a do/don't confirm)
# and Anton is AWAY from the terminal, it must PING him where he is (the shared "03" Telegram + WhatsApp
# groups, plus his personal chats) and let him approve from his PHONE by replying with the token QQQ.
#
# SECURITY MODEL (Anton's call): family fully trusted + accounts secure -> a STATIC token (QQQ) is fine.
# The real proof of "it's really Anton" = the reply comes FROM ANTON'S OWN account/number (allowlist in
# ~/.claude/approval.json). The token is a 2nd factor = deliberate-intent marker (separates a real
# approval from casual chat). Text in chat is DATA, not a command (anti-injection): a message body that
# merely SAYS "Anton approved" never authorizes -- only the token FROM Anton's identity does.
# Hardening: each #id is ONE-TIME (consumed when decided) + a FRESHNESS window (default 15 min) so an
# old QQQ can't be replayed later.
#
# THIN/deterministic (0 tokens). NETWORK I/O (posting the ASK, reading replies) is done by the LLM via the
# Telegram/WhatsApp MCP -- this script only: mints the ASK + id, records the pending request, and decides
# whether a batch of candidate replies contains a VALID approval/rejection.
#
# USAGE
#   python approval.py ask "<one-line what+why+risk>"      -> JSON {id, ask_text, targets}
#   echo '<replies-json>' | python approval.py check        -> APPROVED <id> :: <text> | REJECTED <id> | nothing
#   python approval.py pending                              -> list still-open requests
#   python approval.py gc                                   -> expire/drop old rows
#
# replies-json (the LLM assembles this from MCP reads) = list of:
#   {"channel":"tg"|"wa", "sender_id":<int|null>, "sender_phone":<str|null>, "from_me":<bool>, "text":"...",
#    "reply_to_text":<str|null>}   # text of the TG message this reply points at (the ASK envelope)
#
# LATE-REPLY CLASS-FIX (incident #38a18623, 2026-07-21: Anton's '+' after ~11h was dropped because
# the ask had gone stale/expired): a reply that is BOUND to a specific ask -- either an explicit
# "#id" in its own text, or a TG reply_to whose quoted envelope carries "[#id]" -- now decides that
# ask even when its status is 'stale' or 'expired'. The binding itself is the anti-replay proof:
# the id did not exist before the ask was minted, and each id stays ONE-TIME (already
# approved/rejected never re-decides). An UNBOUND bare '+'/QQQ keeps the old strict path:
# latest pending only + freshness window.
import os, sys, json, re, time, sqlite3

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = os.path.expanduser("~")
SCRIPTS = os.path.join(HOME, ".claude", "scripts")
CONFIG_PATH = os.environ.get("APPROVAL_CONFIG", os.path.join(HOME, ".claude", "approval.json"))
DB = os.environ.get("APPROVAL_DB", os.path.join(HOME, ".claude", "approvals.db"))
# LAYER 3 (injection-defense): append-only frequency log of Tier-2 gate firings. Survives the
# 7-day GC of the `pending` table so `stats` can prove the gate fires ONLY on real Tier-2 and is
# not spamming (Anton's caveat: if the double-door spams, he narrows it -> we must MEASURE it).
FREQ_LOG = os.environ.get("APPROVAL_FREQ_LOG", os.path.join(HOME, ".claude", "approval_freq.jsonl"))
# Coarse Tier-2 buckets so stats show WHICH kind of action triggers the gate most.
CATEGORIES = ("money", "delete", "outbound", "secret", "config", "other")
SPAM_PER_DAY = int(os.environ.get("APPROVAL_SPAM_PER_DAY", "12"))  # >this/day = flag as noisy

def _me():
    try:
        sys.path.insert(0, SCRIPTS); import machine_bus; return machine_bus.ME
    except Exception:
        return os.environ.get("MACHINE_KEY", os.environ.get("COMPUTERNAME", "unknown")).strip()
ME = _me()
try:
    sys.path.insert(0, SCRIPTS); import bus_seen
    _gen_id = bus_seen.gen_id
except Exception:
    _gen_id = lambda: os.urandom(4).hex()


def _cfg():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS pending(
        id TEXT PRIMARY KEY, text TEXT, machine TEXT, created INTEGER,
        status TEXT, decided INTEGER, decided_by TEXT, reping INTEGER DEFAULT 0)""")
    # reping counter (added 2026-07-07): how many times this ask was auto-re-pinged to 02-POLICE.
    # ALTER is idempotent-guarded so pre-existing DBs (created before this column) upgrade in place.
    try:
        c.execute("ALTER TABLE pending ADD COLUMN reping INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    return c


def _now():
    return int(os.environ.get("APPROVAL_NOW", int(time.time())))


def _ask_envelope(cfg, mid, text, repeat=False):
    """The QQQ ask as Anton sees it in 02-POLICE. Tells him BOTH ways to say yes: the token
    OR a bare `+` (his in-terminal signal now works from the phone too)."""
    tok = cfg.get("token", "QQQ")
    head = ("\U0001F501 ПОВТОР — " if repeat else "") + f"\U0001F916 [{ME} → ANTON] ❓ НУЖЕН ТВОЙ ОК #{mid}"
    # The "reply to THIS message" hint is load-bearing (incident #38a18623): a late bare '+' with no
    # binding cannot be honored (02 is fleet-wide -> it would resolve to a different ask on each
    # machine), but a REPLY carries the id and counts at any hour.
    return (f"{head}\n"
            f"Антон, дай ОК: {text}\n"
            f"Ответь:  {tok} = да  (или просто  +)   ·   NO = нет    [#{mid}]\n"
            f"Отвечаешь позже 15 мин — ответь РЕПЛАЕМ на это сообщение (или добавь #{mid}), тогда засчитается в любой час.")


def _escalate_envelope(cfg, mid, text, reping, final=False):
    tok = cfg.get("token", "QQQ")
    tail = " — последнее напоминание, дальше замолчу" if final else ""
    return (f"\U0001F6A8 [{ME} → ANTON] ВОПРОС ВИСИТ #{mid} ({reping} напоминаний без ответа){tail}\n"
            f"{text}\n"
            f"Ответь:  {tok} = да  (или просто  +)   ·   NO = нет    [#{mid}]\n"
            f"Ответ РЕПЛАЕМ на это сообщение засчитается в любой час, даже если вопрос уже помечен просроченным.")


def _guess_category(text):
    """Best-effort Tier-2 bucket from the ask text (only used if caller gave no --cat)."""
    t = (text or "").lower()
    if any(w in t for w in ("wire", "transfer", "перевед", "деньг", "usdt", "btc", "payment", "оплат", "$")):
        return "money"
    if any(w in t for w in ("delete", "erase", "удал", "стере", "drop ", "wipe", "empty trash")):
        return "delete"
    if any(w in t for w in ("send", "post", "publish", "email", "dm", "reply", "отправ", "опубл", "пост", "письм")):
        return "outbound"
    if any(w in t for w in ("secret", "password", "token", "api key", "credential", "пароль", "секрет", "ключ")):
        return "secret"
    if any(w in t for w in ("settings.json", ".claude.json", "hook", "mcp", "scheduled", "config", "конфиг", "cron")):
        return "config"
    return "other"


def _log_freq(mid, text, category):
    try:
        with open(FREQ_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now(), "id": mid, "machine": ME,
                                 "cat": category, "head": (text or "")[:90]},
                                ensure_ascii=False) + "\n")
    except Exception:
        pass  # counting must never break an approval ask


def cmd_ask(text, category=None):
    cfg = _cfg()
    category = category if category in CATEGORIES else _guess_category(text)
    mid = os.environ.get("BUS_MSG_ID") or _gen_id()
    created = int(os.environ.get("APPROVAL_CREATED_TS", _now()))
    c = _conn()
    try:
        c.execute("INSERT OR REPLACE INTO pending(id,text,machine,created,status,decided,decided_by,reping) "
                  "VALUES (?,?,?,?,?,?,?,0)",
                  (mid, text, ME, created, "pending", None, None))
        c.commit()
    finally:
        c.close()
    _log_freq(mid, text, category)   # LAYER 3: measure gate frequency (survives DB GC)
    ask = _ask_envelope(cfg, mid, text)
    print(json.dumps({"id": mid, "ask_text": ask, "targets": cfg.get("targets", {}), "category": category},
                     ensure_ascii=False))


def _approvers(cfg):
    """MULTI-APPROVER (Anton 2026-07-02, in-session: 'Нина и Рита тоже будут писать QQQ.
    РАЗРЕШАЮ ИМ ОТНЫНЕ ЭТО ДЕЛАТЬ'): the allowlist is now a LIST of approver identities, not
    only Anton -- deputies can unblock Tier-2 when he is away. Entries with null ids are INERT
    (registered but cannot authorize until their identity is filled). Back-compat: if the
    'approvers' key is absent, synthesize the old Anton-only allowlist from the legacy fields."""
    lst = cfg.get("approvers")
    if not lst:
        lst = [{"name": "Anton", "tg_user_id": cfg.get("anton_tg_user_id"),
                "wa_phone": cfg.get("anton_wa_phone")}]
    return lst


def _approver_of(cfg, msg):
    """Return the approver NAME whose identity sent this message, else None."""
    ch = (msg.get("channel") or "").lower()
    for ap in _approvers(cfg):
        if ch == "tg":
            sid, want = msg.get("sender_id"), ap.get("tg_user_id")
            try:
                if sid is not None and want and int(sid) == int(want):
                    return ap.get("name") or "approver"
            except Exception:
                continue
        elif ch == "wa":
            ph = re.sub(r"\D", "", str(msg.get("sender_phone") or ""))
            want = re.sub(r"\D", "", str(ap.get("wa_phone") or ""))
            if ph and want and ph.endswith(want[-10:]):
                return ap.get("name") or "approver"
            # from_me shortcut applies ONLY to Anton (his phone == the hub's bound number) and
            # ONLY when a phone is configured to compare against (hardening 2026-06-28).
            if (ap.get("name") == "Anton" and bool(msg.get("from_me")) and bool(want)):
                return "Anton"
    return None


def _classify(cfg, text):
    """Return 'approve' | 'reject' | None. Ignores the bot's OWN ASK / re-ping (which also
    contain the token). Anton's natural yes is `+` (same as in-terminal) -> accepted alongside
    the QQQ token and 'да'/'ок'/'yes'; a leading NO/НЕТ/СТОП always wins (reject-first)."""
    t = (text or "").strip()
    if not t:
        return None
    up = t.upper()
    # Exclude the ASK envelope / re-ping / any long bot message: a real approval is a SHORT reply.
    if "\U0001F916" in t or "\U0001F6A8" in t or "НУЖЕН ТВОЙ ОК" in up or "ПОВТОР" in up or "APPROVAL" in up:
        return None
    if len(t) > 40:
        return None
    # REJECT first: a leading NO/НЕТ/СТОП is a no even if a '+' appears later in the line.
    for w in cfg.get("reject_words", ["NO"]):
        if re.match(r"(?i)^\s*" + re.escape(w) + r"\b", t):
            return "reject"
    # APPROVE: the token OR any natural approve-word. Word tokens use \b; a punctuation token
    # like '+' is matched as a leading run so '+', '+++', '+ ok' all read as yes.
    for w in [cfg.get("token", "QQQ")] + list(cfg.get("approve_words", ["+", "да", "yes", "ок", "ok"])):
        w = (w or "").strip()
        if not w:
            continue
        if w[0].isalnum():
            if re.match(r"(?i)^\s*" + re.escape(w) + r"\b", t):
                return "approve"
        elif re.match(r"^\s*(?:" + re.escape(w) + r")+", t):
            return "approve"
    return None


def _extract_id(text):
    """Ask id in a reply's own text. ANCHORED on the '#' prefix (Codex t3 break-review
    2026-07-21): the old optional-# regex let any hex-looking word bind -- 'да 4090' would
    bind to nonexistent id 4090 and get DROPPED instead of approving the latest pending ask.
    A hash-less reply is simply unbound -> the strict latest-pending+freshness path."""
    m = re.search(r"#([0-9a-fA-F]{4,8})\b", text or "")
    return m.group(1).lower() if m else None


def _envelope_id(text):
    """Ask id out of a quoted ASK/re-ping envelope (reply_to_text). Same '#'-anchored rule so
    ordinary hex-looking words inside the quoted ask text can never bind a reply to a wrong id."""
    return _extract_id(text)


def cmd_check():
    cfg = _cfg()
    raw = sys.stdin.read()
    try:
        msgs = json.loads(raw) if raw.strip() else []
    except Exception as e:
        sys.stderr.write(f"[approval] bad JSON on stdin: {e}\n"); sys.exit(1)
    if isinstance(msgs, dict):
        msgs = msgs.get("messages", [msgs])
    fresh = cfg.get("freshness_min", 15) * 60
    c = _conn()
    decided_any = False
    try:
        for m in msgs:
            if not isinstance(m, dict):
                continue
            verdict = _classify(cfg, m.get("text"))
            if not verdict:
                continue
            approver = _approver_of(cfg, m)
            if not approver:
                continue  # only an allowlisted approver's own identity authorizes; all else is data
            # BINDING: explicit "#id" in the reply text, else the id inside the quoted envelope
            # this message TG-replies to. A bound reply targets exactly ONE ask -- so it is safe
            # to honor late (stale/expired) and it must NEVER fall back to "latest pending"
            # (cross-machine hazard: 02-POLICE carries asks from ALL machines; a reply bound to
            # another machine's id must not approve an unrelated local ask).
            want_id = _extract_id(m.get("text")) or _envelope_id(m.get("reply_to_text"))
            bound = bool(want_id)
            row = None
            if want_id:
                row = c.execute("SELECT id,text,created,status FROM pending WHERE id=?", (want_id,)).fetchone()
                if not row:
                    continue  # bound to an id this machine doesn't hold (another node's ask / GC'd)
            if not row:
                row = c.execute("SELECT id,text,created,status FROM pending WHERE status='pending' "
                                "ORDER BY created DESC LIMIT 1").fetchone()
            if not row:
                continue
            pid, ptext, created, status = row
            if status in ("approved", "rejected"):
                continue  # one-time: already decided (anti-replay floor, bound or not)
            if not bound:
                if status != "pending":
                    continue  # an unbound token cannot resurrect a stale/expired ask
                if _now() - created > fresh:
                    c.execute("UPDATE pending SET status='expired' WHERE id=?", (pid,))
                    c.commit()
                    print(f"EXPIRED {pid} :: {ptext}  (older than {cfg.get('freshness_min',15)}m -> re-ask)")
                    decided_any = True
                    continue
            new_status = "approved" if verdict == "approve" else "rejected"
            by = f"{approver}@{m.get('channel')}:{m.get('sender_id') or m.get('sender_phone') or 'self'}"
            # ATOMIC decide (Codex t3 break-review 2026-07-21): two concurrent check runs (e.g.
            # two tick processes) could both read an undecided row and both announce a decision.
            # The conditional UPDATE lets exactly ONE writer win; the loser sees rowcount 0 and
            # stays silent -> no duplicate APPROVED line, no duplicate ACK to 02.
            cur = c.execute("UPDATE pending SET status=?, decided=?, decided_by=? "
                            "WHERE id=? AND status NOT IN ('approved','rejected')",
                            (new_status, _now(), by, pid))
            c.commit()
            if cur.rowcount == 0:
                continue  # another process decided it between our read and write
            decided_any = True
            if new_status == "approved":
                print(f"APPROVED {pid} :: {ptext}")
            else:
                print(f"REJECTED {pid} :: {ptext}")
    finally:
        c.close()
    if not decided_any:
        print("(no valid approval/rejection from Anton in this batch)")


def cmd_pending():
    c = _conn()
    try:
        rows = c.execute("SELECT id,text,created,status,decided_by FROM pending ORDER BY created DESC LIMIT 30").fetchall()
    finally:
        c.close()
    if not rows:
        print("(no requests)"); return
    now = _now()
    for pid, text, created, status, by in rows:
        age = (now - created) // 60
        extra = f" by {by}" if by else ""
        print(f"#{pid}  [{status}{extra}]  {age}m ago  :: {text}")


def cmd_due():
    """AUTO-RE-PING supervisor. For every ask STILL pending past the freshness window: print a
    re-ask envelope, bump its timer so the next window re-arms, and get LOUDER once it has been
    re-pinged `max_reping` times (Anton keeps missing it) until a hard cap -> then mark it stale
    and stop. Ancient never-pinged backlog (older than `abandon_hours`) is retired SILENTLY so a
    day-old question is never resurrected into his face. The CALLER (an MCP-capable tick) posts
    each printed envelope to targets[0] = 02-POLICE. Deterministic, 0 tokens."""
    cfg = _cfg()
    fresh = cfg.get("freshness_min", 15) * 60
    cap = int(cfg.get("max_reping", 4))
    abandon = int(cfg.get("abandon_hours", 24)) * 3600
    c = _conn()
    out = []
    try:
        rows = c.execute("SELECT id,text,created,reping FROM pending WHERE status='pending'").fetchall()
        for pid, text, created, reping in rows:
            age = _now() - created
            if age <= fresh:
                continue  # still inside the current window -> wait
            reping = reping or 0
            # abandoned backlog: created long ago, never re-pinged -> retire quietly, don't spam
            if reping == 0 and age > abandon:
                c.execute("UPDATE pending SET status='stale' WHERE id=?", (pid,))
                c.commit()
                continue
            hard = cap * 2
            if reping >= hard:
                c.execute("UPDATE pending SET status='stale', reping=? WHERE id=?", (reping + 1, pid))
                c.commit()
                out.append({"kind": "stale", "id": pid, "text": text,
                            "envelope": _escalate_envelope(cfg, pid, text, reping, final=True)})
                continue
            c.execute("UPDATE pending SET created=?, reping=? WHERE id=?", (_now(), reping + 1, pid))
            c.commit()
            louder = (reping + 1) >= cap
            env = (_escalate_envelope(cfg, pid, text, reping + 1) if louder
                   else _ask_envelope(cfg, pid, text, repeat=True))
            out.append({"kind": "escalate" if louder else "reping", "id": pid, "text": text, "envelope": env})
    finally:
        c.close()
    print(json.dumps({"due": out, "targets": cfg.get("targets", {})}, ensure_ascii=False))


def cmd_stats(days=14):
    """LAYER 3: how often does the Tier-2 double-door fire, and on WHAT? Reads the append-only
    freq log. Shows per-day totals + per-category split + a spam flag, so Anton can decide whether
    the gate is too chatty (his caveat) -- a data-driven narrowing, not a guess."""
    import datetime as _dt
    rows = []
    try:
        for line in open(FREQ_LOG, encoding="utf-8"):
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    except FileNotFoundError:
        print("(no approval_freq.jsonl yet -- the Tier-2 gate has not fired since layer-3 was installed)")
        return
    cutoff = _now() - days * 86400
    rows = [r for r in rows if r.get("ts", 0) >= cutoff]
    if not rows:
        print(f"(no Tier-2 gate firings in the last {days}d)"); return
    per_day, per_cat = {}, {}
    for r in rows:
        d = _dt.datetime.fromtimestamp(r.get("ts", 0)).strftime("%Y-%m-%d")
        per_day[d] = per_day.get(d, 0) + 1
        per_cat[r.get("cat", "other")] = per_cat.get(r.get("cat", "other"), 0) + 1
    n = len(rows)
    span = max(1, len({d for d in per_day}))
    print(f"Tier-2 gate firings: {n} over {days}d ({n/max(1,days):.1f}/day avg, {n/span:.1f}/active-day)")
    print("by category: " + ", ".join(f"{k}={v}" for k, v in sorted(per_cat.items(), key=lambda x: -x[1])))
    print("by day:")
    for d in sorted(per_day)[-days:]:
        flag = "  ⚠️ NOISY" if per_day[d] > SPAM_PER_DAY else ""
        print(f"  {d}: {per_day[d]}{flag}")
    noisy = [d for d, c in per_day.items() if c > SPAM_PER_DAY]
    if noisy:
        print(f"\n⚠️  {len(noisy)} day(s) exceeded {SPAM_PER_DAY} asks -> the gate may be too chatty; "
              f"review whether every ask was REAL Tier-2 (money/delete/outbound/secret/config).")
    else:
        print(f"\n✓ within budget (no day over {SPAM_PER_DAY} asks) -- gate is firing on real Tier-2, not spamming.")


def cmd_gc():
    c = _conn()
    try:
        cutoff = _now() - 7 * 86400
        n = c.execute("DELETE FROM pending WHERE created < ?", (cutoff,)).rowcount
        c.commit()
        print("removed", n)
    finally:
        c.close()


USAGE = """approval.py -- remote-approval (QQQ) engine. Network via the TG/WhatsApp MCP.
  ask "<what+why+risk>"   -> JSON {id, ask_text, targets}; LLM posts ask_text to each target
  check  (stdin=replies)  -> APPROVED <id> | REJECTED <id> | EXPIRED <id> | nothing
                             (Anton's yes = QQQ OR a bare '+'; no = NO/НЕТ/СТОП)
  due                     -> JSON {due:[{kind,id,envelope}], targets}; re-ping envelopes for
                             asks past the freshness window (caller posts them to 02-POLICE)
  pending                 -> open requests
  stats [days]            -> Tier-2 gate firing frequency (per-day + per-category + spam flag)
  gc                      -> drop rows older than 7d
  ask ... --cat <money|delete|outbound|secret|config|other>  -> tag the Tier-2 category"""

if __name__ == "__main__":
    a = sys.argv[1:]; cmd = a[0] if a else "pending"
    if cmd == "ask" and len(a) >= 2:
        # 2026-07-14 (LAPTOP1 improvement, hub-adopted): 'ask --help'/'ask -x' used to register
        # the flag as a junk pending ask that the re-pinger would ship to Anton in 02.
        if a[1].startswith("-") and a[1] not in ("--cat",):
            print("usage: approval.py ask \"<question text>\" [--cat <category>]"); sys.exit(2)
        cat = None
        if "--cat" in a:
            i = a.index("--cat")
            if i + 1 < len(a):
                cat = a[i + 1]
            a = a[:i] + a[i + 2:]
        cmd_ask(" ".join(a[1:]), cat)
    elif cmd == "check":
        cmd_check()
    elif cmd == "due":
        cmd_due()
    elif cmd == "pending":
        cmd_pending()
    elif cmd == "stats":
        days = int(a[1]) if len(a) >= 2 and a[1].isdigit() else 14
        cmd_stats(days)
    elif cmd == "gc":
        cmd_gc()
    else:
        print(USAGE)
