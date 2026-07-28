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
r"""content_miner.py - the "content lane" of the content-factory.

WHAT (Anton 2026-07-08, "я хз что добавить, это твоя задача" = Claude owns TASTE):
Every Claude Code session is raw material for the build-in-public reality show
([[everything-becomes-content]], [[positioning-anton-mike-one-machine]]). This engine
reads OUR sessions (past archive + live) and drops every CONTENT-WORTHY MOMENT into
the content funnel as a DRAFT - WITHOUT Anton nudging "add it to the log".

Same family as the alpha-extraction miners and intention_mine.py: a CHEAP
deterministic detector (0 LLM tokens) shrinks the corpus to a small candidate
digest; the LLM judge (Sonnet nightly / me in-session) keeps only the real signal,
assigns a publish TIER, and feeds it into the funnel. Publication stays draft-first
(Anton's "+" gates the /episode -> content_publish path). Nothing here publishes.

DISTINCT from its siblings (do NOT duplicate them):
  - intention_mine.py  -> user PAINS/QUESTIONS ("how do I X") -> build-in-public ASK posts.
  - voice_triage.py    -> Anton's VOICE notes (chat 00) -> post-material.
  - content_miner.py   -> content-worthy MOMENTS in the WORK itself (a thing shipped,
                          a war-story bug, a novel multi-agent/consensus build, an
                          insight, a wow) -> episode candidates.

REUSE (AK-47, no parallel monolith):
  - vault_sessions.recent_sessions()  = the live cross-machine session pool reader.
  - fb_diary_collect.is_noise         = shared boilerplate/noise filter.
  - voice_triage.py append            = the canonical funnel intake writer (owns
                                        posts.jsonl upsert/dedup). We add source_kind
                                        "session" there and feed through it.

COMMANDS:
  mine [--day D | --days N | --all] [--operator Anton|all]
        DETERMINISTIC scan -> candidate digest md (0 tokens). Prints SESSIONS/CANDIDATES.
  capture --title .. --note .. [--tier ..] [--sid ..] [--src ..] [--angle ..]
          [--visibility public|personal|private] [--when ISO]
        The REFLEX + the judge's writer: append ONE content candidate to the funnel
        (draft-first) via voice_triage. Dedup + privacy-gated. 0 tokens.
  captured [--limit N]   show the capture ledger (what this engine has fed the funnel).

Prints are ASCII-only (Windows cp1252 safe). Stdlib + sibling modules only.
"""
import os, sys, io, re, json, hashlib, argparse, datetime, subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))            # ...\content-factory
IMPORTS = os.path.dirname(HERE)                              # %IMPORTS%
sys.path.insert(0, IMPORTS)
import vault_sessions                                        # live cross-machine pool reader
try:
    import fb_diary_collect as fdc                           # shared noise filter
    _is_boiler = fdc.is_noise
except Exception:                                            # degrade gracefully if sibling moves
    def _is_boiler(s):
        low = (s or "").lstrip()
        return (not low or low.startswith(("<system-reminder>", "Caveat:", "<command-name>",
                                           "<local-command", "<command-message>")))

MINER = os.path.join(HERE, "miner")
CANDIR = os.path.join(MINER, "candidates")
LEDGER = os.path.join(MINER, "captured.jsonl")
DEBTLOG = os.path.join(MINER, "debt-log.md")
VOICE_TRIAGE = os.path.join(HERE, "voice_triage.py")

# --------------------------------------------------------------- signal lexicon
# Content-worthiness for a build-in-public REALITY SHOW - the "story/moment" signal,
# NOT business-alpha and NOT user-intention.
#
# CALIBRATION (the "поймётся на масштабе?" lesson, /tt 2026-07-09): in a corpus where
# EVERY session is AI-building work, ambient words ("готово","скилл","workflow",
# "субагент","движок") fire on ~100% of sessions -> zero filtering. So this detector
# does NOT binary-classify; it SCORES with RARE, weighted markers and RANKS. Only the
# rare, quotable, story-shaped beats score high. The digest surfaces the TOP-N; the
# LLM judge picks from those. Ambient vocabulary is deliberately EXCLUDED.
#
# families: marker-list -> weight. A session's score = sum of weights of DISTINCT
# markers it hits. Keep if score >= MIN_SCORE (ranked, capped, nothing dropped silently).
FAMILIES = {
    # REACTION (w3): Anton's genuine excitement -> the most quotable show beats (rare).
    "wow": (3, [
        "это веха", "/wow", "офигеть", "офигел", "гениальн", "это шедевр",
        "круто получилось", "обалден", "прорыв", "breakthrough", "это магия",
        "волшебн", "это будущее", "не верю что", "поразительно", "восхитительно",
        "это победа", "это огонь", "это бомба", "кайф", "красота какая",
    ]),
    # WAR (w2): debug drama / failure-and-fix war-story.
    "war": (2, [
        "зомби", "грабли", "потеря данных", "воскрес", "факап", "тихий сбой",
        "молча слома", "чуть не потер", "корень оказал", "root cause", "разгадал",
        "неделями", "весь день чин", "самолечен", "self-heal", "крэш", "паника",
        "снёс всё", "снес все", "откатил", "восстановил из", "чуть не убил",
        "две недели", "дважды похорон", "мучил", "боролся с",
    ]),
    # META (w1): named novel human+AI build. Weight 1 - in THIS corpus these words are
    # ambient infra-vocabulary (nearly every session touches consensus/second-brain), so
    # they broaden recall but must NOT dominate the rank; a real story needs wow/war too.
    "meta": (1, [
        "консенсус", "курьер между", "цифровой двойник", "цифрового двойника",
        "рой агент", "несколько машин сами", "машины сами договор", "agent team",
        "мультиагент", "multi-agent", "между машинами", "второй мозг", "second brain",
        "декомпоз", "fan-out", "автономно договор", "kill switch", "kill-switch",
        "клон антона", "digital twin", "реалити-шоу", "reality show",
    ]),
    # SHIP (w1): a genuine milestone phrasing (weak alone; matters with company).
    "ship": (1, [
        "с нуля собрал", "за один вечер", "за час собрал", "теперь само",
        "полностью автоном", "наконец заработал", "всё заработало", "one-shot",
        "готово ✅", "shipped", "выкатил",
    ]),
    # WEAK (w1): generic value words.
    "weak": (1, [
        "инсайт", "урок", "паттерн", "лечи корень", "до->после", "до→после",
        "в разы", "прототип", "эксперимент", "неожиданн", "элегантн", "красиво",
    ]),
}
STRONG_FAMS = ("wow", "war", "meta")   # families whose match yields a snippet-worthy line
MIN_SCORE = 4                          # below this -> not a candidate (ranked above it)
# session is mostly a routine check / low content -> drop unless something scores
LOW_TITLE = ("/1", "/sync", "/inbox", "/agenda", "ping", "статус", "?", "проверь синк",
             "resume", "продолжаем", "где мы")

# privacy: mark (do NOT silently publish) - the judge generalizes or drops. Kept to
# markers that are genuinely private; deliberately NOT "клиент"/"phone"/"+1" (those fire
# on "Syncthing клиент", version numbers, and the PUBLIC co-founder number +1 341...).
PRIV = ["пароль", "password", "секрет ", "api key", "api_key", "ghp_", "sk-ant",
        " crm", "crm-", "лид:", "lead:", "досье", "паспорт", "виза ", "налог",
        "@gmail", "@corp_acct"]
SECRET_RX = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{18,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bgh[posu]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}(?:\.[A-Za-z0-9_\-]*){2,4}"),
    re.compile(r"(?i)\b(password|passwd|пароль|api[_-]?key|secret|access[_-]?token)\b\s*[:=]\s*\S+"),
]


def has_secret(t):
    return any(rx.search(t or "") for rx in SECRET_RX)


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def _low(s):
    return _norm(s).lower()


def _family_hits(low):
    """-> (score, tags, strong_fams_present) for a lowercased text blob."""
    score, tags, strong = 0, [], []
    for fam, (w, words) in FAMILIES.items():
        hits = sorted({word for word in words if word in low})
        if not hits:
            continue
        # cap per-family distinct hits at 3 so a long transcript can't win on length alone
        score += w * min(len(hits), 3)
        tags.append("%s×%d" % (fam, len(hits)))
        if fam in STRONG_FAMS:
            strong.append(fam)
    return score, tags, strong


def score_session(rec):
    """-> dict(score, tags, snippets, priv). score < MIN_SCORE = not a candidate."""
    turns = rec.get("turns") or []
    title = rec.get("title") or ""
    hay_parts = [title] + [t for _, t in turns if not _is_boiler(t)]
    hay = _low("\n".join(hay_parts))

    tl = _low(title)
    if any(tl.startswith(x) or tl == x.strip() for x in LOW_TITLE):
        # a routine-check title still counts if the body scores high on its own
        pass

    score, tags, _ = _family_hits(hay)
    if score < MIN_SCORE:
        return {"score": score, "tags": tags, "snippets": [], "priv": 0}

    # snippets: the actual story lines (a strong-family marker), redact secrets, cap 5.
    def strong_markers(low):
        return [fam for fam in STRONG_FAMS
                if any(w in low for w in FAMILIES[fam][1])]
    strong_snips, weak_snips, seen = [], [], set()
    for role, txt in turns:
        if _is_boiler(txt):
            continue
        for raw in re.split(r"(?<=[.!?\n])\s+", txt):
            line = _norm(raw)
            if len(line) < 12 or len(line) > 260:
                continue
            low = line.lower()
            fams = strong_markers(low)
            weak_here = any(w in low for w in FAMILIES["weak"][1] + FAMILIES["ship"][1])
            if not fams and not weak_here:
                continue
            if has_secret(line):
                continue  # never carry a secret into the digest
            key = low[:80]
            if key in seen:
                continue
            seen.add(key)
            entry = "[%s] %s" % (role[:1].upper(), line)
            (strong_snips if fams else weak_snips).append(entry)
        if len(strong_snips) >= 6:
            break
    snippets = (strong_snips + weak_snips)[:5]

    priv = 1 if any(p in hay for p in PRIV) else 0
    return {"score": score, "tags": tags, "snippets": snippets, "priv": priv}


def _captured_ids():
    ids = set()
    if os.path.exists(LEDGER):
        for ln in io.open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    ids.add(json.loads(ln).get("src"))
                except Exception:
                    pass
    return ids


def cmd_mine(args):
    os.makedirs(CANDIR, exist_ok=True)
    if args.all:
        recs = vault_sessions.recent_sessions(days=3650, with_turns=True)
        scope = "ALL"
    elif args.day:
        recs = vault_sessions.recent_sessions(day=args.day, with_turns=True)
        scope = args.day
    else:
        recs = vault_sessions.recent_sessions(days=args.days, with_turns=True)
        scope = "last-%dd" % args.days

    op = (args.operator or "Anton").lower()
    cap = args.cap if args.cap is not None else (120 if args.all else 30)
    already = _captured_ids()
    scored = []
    n_sess = n_drop = n_cron = n_op = n_done = 0
    for rec in recs:
        if vault_sessions.is_cron_session(rec):
            n_cron += 1
            continue
        if op != "all" and (rec.get("operator") or "").lower() != op:
            n_op += 1
            continue
        sid = rec.get("session_id") or ""
        src = "cc:%s" % sid[:8]
        if src in already:
            n_done += 1
            continue
        n_sess += 1
        r = score_session(rec)
        if r["score"] < MIN_SCORE:
            n_drop += 1
            continue
        scored.append((rec, r, src))

    scored.sort(key=lambda x: -x[1]["score"])
    n_over = len(scored)
    shown = scored[:cap]
    n_capped = n_over - len(shown)

    # score bands for readability
    def band(s):
        return "HOT" if s >= 12 else ("WARM" if s >= 7 else "WATCH")
    from collections import OrderedDict
    bands = OrderedDict((b, []) for b in ("HOT", "WARM", "WATCH"))
    for rec, r, src in shown:
        bands[band(r["score"])].append((rec, r, src))

    day = datetime.date.today().strftime("%Y-%m-%d")
    L = []
    L.append("# Content-miner candidates - scope %s (%s scan)" % (scope, day))
    L.append("")
    L.append("_Deterministic content-worthiness prefilter (0 tokens): RARE weighted markers, "
             "RANKED. The LLM judge keeps only real signal, assigns a TIER "
             "(teaser/medium/longread/dev-log) + a 1-line angle, then feeds the funnel via "
             "`content_miner.py capture` (draft-first, NEVER publishes). Privacy: `[PRIV]` = "
             "generalize or drop; never leak secrets/CRM/personal._")
    L.append("")
    L.append("- sessions scanned: %d | over threshold (score>=%d): %d | shown (cap %d): %d | "
             "capped-off: %d" % (n_sess, MIN_SCORE, n_over, cap, len(shown), n_capped))
    L.append("- bands: HOT=%d, WARM=%d, WATCH=%d" %
             (len(bands["HOT"]), len(bands["WARM"]), len(bands["WATCH"])))
    L.append("- skipped: cron=%d, other-operator=%d, already-captured=%d, below-threshold=%d"
             % (n_cron, n_op, n_done, n_drop))
    if n_capped:
        L.append("- NOTE: %d candidates above threshold were capped off this run (raise --cap "
                 "to see them; they are NOT lost - a later run re-surfaces uncaptured ones)." % n_capped)
    for b in ("HOT", "WARM", "WATCH"):
        L.append("")
        L.append("## %s (%d)" % (b, len(bands[b])))
        for rec, r, src in bands[b]:
            priv = " [PRIV]" if r["priv"] else ""
            L.append("")
            L.append("### %s | %s | %s | %s%s  {score %d · %s}"
                     % (src, rec.get("date", "?"), rec.get("machine", "?"),
                        rec.get("operator", "?"), priv, r["score"], ", ".join(r["tags"])))
            t = _norm(rec.get("title") or "")[:120]
            if t:
                L.append("**%s**" % t)
            for s in r["snippets"]:
                L.append("- %s" % s)
    body = "\n".join(L) + "\n"
    outname = "cand-%s.md" % (day if not args.all else "ALL-%s" % day)
    out = os.path.join(CANDIR, outname)
    io.open(out, "w", encoding="utf-8", newline="\n").write(body)
    io.open(os.path.join(CANDIR, "cand-latest.md"), "w", encoding="utf-8", newline="\n").write(body)

    print("SCOPE", scope)
    print("SESSIONS", n_sess)
    print("OVER_THRESHOLD", n_over)
    print("SHOWN", len(shown))
    print("CAPPED_OFF", n_capped)
    print("HOT", len(bands["HOT"]))
    print("WARM", len(bands["WARM"]))
    print("WATCH", len(bands["WATCH"]))
    print("SKIP_CRON", n_cron)
    print("SKIP_OTHER_OP", n_op)
    print("SKIP_DONE", n_done)
    print("BELOW_THRESHOLD", n_drop)
    print("OUT", out)


VALID_TIERS = ("teaser", "medium", "longread", "dev-log", "auto")


def cmd_capture(args):
    """The REFLEX + judge writer: one content candidate -> funnel (draft-first)."""
    os.makedirs(MINER, exist_ok=True)
    title = _norm(args.title)
    note = _norm(args.note or "")
    if not title:
        print("ERR empty title"); sys.exit(2)
    tier = (args.tier or "auto").lower()
    if tier not in VALID_TIERS:
        print("ERR bad tier (teaser|medium|longread|dev-log|auto)"); sys.exit(2)

    # privacy gate: hard-refuse raw secrets; downgrade visibility on private markers.
    if has_secret(title + "\n" + note):
        print("BLOCKED: candidate carries a secret-looking token - not captured. "
              "Rewrite without the secret."); sys.exit(3)
    vis = (args.visibility or "public").lower()
    if vis == "public" and any(p in (title + "\n" + note).lower() for p in PRIV):
        vis = "personal"
        print("NOTE: private marker found -> visibility downgraded to 'personal' "
              "(generalize before any publish).")

    src = args.src or ("cc:%s" % (args.sid[:8] if args.sid else "live-" +
                       hashlib.sha1(_norm(title).encode("utf-8")).hexdigest()[:6]))
    when = args.when or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")

    # tier + angle live as a machine-readable prefix in the note so /episode picks them up.
    prefix = "[tier:%s]" % tier
    if args.angle:
        prefix += " [angle: %s]" % _norm(args.angle)
    full_note = (prefix + " " + note).strip()

    cmd = [sys.executable, VOICE_TRIAGE, "append", "--bucket", "post",
           "--title", title, "--note", full_note, "--src", src,
           "--source-kind", "session", "--visibility", vis,
           "--lang-hint", (args.lang_hint or "ru"), "--when", when]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        sys.stdout.write(r.stderr or "")
        print("CAPTURE_FAILED (voice_triage append returned %d)" % r.returncode)
        sys.exit(4)

    with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"src": src, "title": title, "tier": tier,
                            "visibility": vis, "when": when,
                            "captured_at": datetime.datetime.now().isoformat(timespec="seconds")},
                           ensure_ascii=False) + "\n")
    print("CAPTURED %s [tier:%s vis:%s] -> funnel posts.jsonl (draft)" % (src, tier, vis))


def cmd_captured(args):
    if not os.path.exists(LEDGER):
        print("(none captured yet)"); return
    rows = [json.loads(l) for l in io.open(LEDGER, encoding="utf-8") if l.strip()]
    for row in rows[-(args.limit or 40):]:
        t = (row.get("title") or "")[:66].encode("ascii", "replace").decode("ascii")
        print("%s [%-8s %-8s] %s" % (row.get("when", ""), row.get("tier", ""),
                                     row.get("visibility", ""), t))
    print("TOTAL_CAPTURED", len(rows))


def main():
    ap = argparse.ArgumentParser(description="content-lane miner (sessions -> funnel drafts)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mine")
    m.add_argument("--day")
    m.add_argument("--days", type=int, default=2)
    m.add_argument("--all", action="store_true")
    m.add_argument("--operator", default="Anton")
    m.add_argument("--cap", type=int, default=None, help="max candidates in digest (default 30, 120 for --all)")
    m.set_defaults(f=cmd_mine)

    c = sub.add_parser("capture")
    c.add_argument("--title", required=True)
    c.add_argument("--note")
    c.add_argument("--tier")
    c.add_argument("--angle")
    c.add_argument("--sid")
    c.add_argument("--src")
    c.add_argument("--visibility", default="public")
    c.add_argument("--lang-hint", dest="lang_hint", default="ru")
    c.add_argument("--when")
    c.set_defaults(f=cmd_capture)

    cl = sub.add_parser("captured")
    cl.add_argument("--limit", type=int, default=40)
    cl.set_defaults(f=cmd_captured)

    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
