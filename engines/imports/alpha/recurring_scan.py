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
"""recurring_scan.py - RECURRING-PATTERN miner (alpha engine miner #5).

Alpha Protocol: decision-alpha-extraction-engine-variant-a.
Sibling of bets_scan.py, contradictions_scan.py, bridge_scan.py, stance_scan.py.
Does NOT modify vault files or other miners.

What it does (cheap detector -> LLM judge later; 0 LLM tokens here):
- Scans Anton's OWN notes for sentences carrying a CONVICTION/CLAIM (belief,
  normative statement, strong opinion).
- Extracts TOPIC ANCHORS from each conviction sentence: domain-specific nouns
  (>= 5 chars, after removing function/stance stopwords).
- Builds an inverted index: topic_anchor -> list of (note, year, sentence).
- A TOPIC = CANDIDATE if it appears as anchor in >= 3 DISTINCT notes spanning
  >= 2 DISTINCT calendar years (multi-year recurrence = core conviction).
- Also surfaces TOPIC-GROUPS from curated notes (belief-*, concept-*, insight-*)
  where the same word recurs across >= 5 notes even without year spans -- those
  are permanent patterns worth reviewing.
- Ranks candidates by (distinct_years * distinct_notes) DESC.
- Writes a SQLite ledger (recurring_ledger.db) and a report of top 10
  candidates, each with Obsidian [[link]] evidence and verdict checkbox.

Feeds: candidates\\recurring-report-latest.md
Natural home: [[insight-worldview-throughlines]] (cross-year recurring themes).

Token-economy: 0 tokens here. LLM judge reads only top-10 digest.

Usage:
    python recurring_scan.py                     # incremental + refresh report
    python recurring_scan.py --all               # full rescan
    python recurring_scan.py --today 2026-06-15  # override today (testing)

Outputs (%IMPORTS%\\alpha\\):
    recurring_ledger.db
    candidates\\recurring-report-<date>.md + recurring-report-latest.md
"""
import os, sys, io, re, json, sqlite3, datetime, collections
from alpha_roots import ROOTS_FOR

OUTDIR = r"%IMPORTS%\alpha"
CANDIR = os.path.join(OUTDIR, "candidates")
DB     = os.path.join(OUTDIR, "recurring_ledger.db")
STATE  = os.path.join(OUTDIR, "_recurring_state.json")

# per-miner roots: single source = alpha_roots.py
ROOTS = ROOTS_FOR("recurring")

# Curated roots = Anton's distillation layer; author-gate relaxed for these.
CURATED_ROOTS = {
    r"%VAULT%\03-Insights",
    r"%VAULT%\06-Concepts",
    r"%VAULT%\09-Bridges",
}

# ---------------------------------------------------------------------------
# AUTHOR GATE
# ---------------------------------------------------------------------------
EXCLUDE_ORIGIN = {
    "external", "gdrive-personal-mixed", "gdrive-external",
    "claude", "chatgpt", "ai", "mixed",
}

def _is_anton(txt, path, is_curated_root=False):
    """Return True if this note is authored by Anton himself."""
    if is_curated_root:
        m = re.search(r"^\s*origin\s*:\s*[\"']?([^\"'\n]+)[\"']?\s*$", txt, re.M | re.I)
        if m:
            val = m.group(1).strip().lower()
            truly_external = {"external", "gdrive-personal-mixed", "gdrive-external"}
            if any(v in val for v in truly_external):
                return False
        return True
    m = re.search(r"^\s*origin\s*:\s*[\"']?([^\"'\n]+)[\"']?\s*$", txt, re.M | re.I)
    if m:
        val = m.group(1).strip().lower()
        if val in ("anton", "anton-original", "self"):
            return True
        if any(v in val for v in EXCLUDE_ORIGIN):
            return False
    ab = re.search(r"^\s*authored_by\s*:\s*[\"']?([^\"'\n]+)[\"']?\s*$", txt, re.M | re.I)
    if ab:
        v = ab.group(1).strip().lower()
        if "human" in v or "anton" in v:
            return True
        if "ai" in v or "claude" in v or "hybrid" in v:
            return False
    return True

# ---------------------------------------------------------------------------
# CONVICTION MARKERS -- sentence must carry at least one.
# ---------------------------------------------------------------------------
CONVICTION_MARKERS = [
    # first-person belief (Russian)
    "я считаю", "я думаю", "я уверен", "я верю", "мне кажется",
    "на мой взгляд", "по-моему", "я знаю", "я понял", "я убеждён",
    "убежден", "убеждён",
    # normative / evaluative (Russian)
    "главное", "важнее", "важно ", "ключевое", "лучше", "хуже",
    "нужно", "надо ", "нельзя", "правильно", "неправильно",
    "необходимо", "всегда", "никогда",
    # English equivalents
    "i believe", "i think", "i know", "the key is", "always", "never",
    "you must", "we must", "most important", "crucial",
]

# Noise to drop -- vault telemetry, meta-about-ledgers, etc.
DROP_CTX = [
    "заметок", "person-нот", "волт вырос", "параллельн", "битых ссыл",
    "реиндекс", "value_score", "frontmatter", "резолвед",
    "калибровк", "скоркарт", "скоринг", "ledger", "прогнозы получили",
    "прогноз-реестр", "% строго", "фрагмент", "series ",
    # specific vault-admin patterns
    "source_path", "cluster_id", "first_seen", "dist_years",
]

# ---------------------------------------------------------------------------
# TOPIC-ANCHOR EXTRACTION
# A topic anchor = a domain noun that survives after removing stance/function
# words.  We stem it lightly to merge inflection variants.
# ---------------------------------------------------------------------------
FUNCTION_STOPWORDS = {
    # conviction stance words (we want the TOPIC, not the stance verb)
    "я", "считаю", "думаю", "уверен", "верю", "кажется", "знаю",
    "понял", "решил", "убеждён", "убежден", "убеждена",
    # normative
    "главное", "важнее", "важно", "ключевое", "лучше", "хуже", "нужно",
    "надо", "стоит", "нельзя", "правильно", "неправильно", "необходимо",
    "всегда", "никогда", "нужен", "нужна", "можно", "должен", "должна",
    # Russian function words (short)
    "что", "это", "как", "так", "все", "всё", "для", "при", "без",
    "или", "но", "и", "в", "на", "с", "по", "за", "от", "до",
    "из", "к", "о", "об", "со", "чем", "уже", "еще", "ещё",
    "не", "он", "они", "она", "мы", "ты", "вы", "их", "его", "её",
    "там", "тут", "тоже", "также", "очень", "просто", "потому",
    "поэтому", "когда", "если", "тогда", "тоже", "даже", "только",
    "быть", "есть", "был", "была", "были", "будет", "будут", "стать",
    "чтобы", "раз", "лишь", "себя", "своего", "свою", "своей",
    # Generic stems of ultra-common Russian action/descriptive words
    # (these survive the 5-char WORD_RE but are semantically empty as topics).
    "сдела", "дела", "котор", "которы", "которо", "больш",
    "чтобы", "потому", "почему", "после", "между",
    "всего", "самого", "самой", "самых", "самый",
    "хочет", "хочу", "хотел", "хотеть",
    "может", "могут", "могу", "могли", "мочь",
    "нужно", "нужны", "нужен", "нужна",
    "стало", "стала", "стали", "стать",
    "знает", "знаю", "знал", "знать",
    "любой", "любого", "любые", "любых",
    "своих", "своего", "своей", "своим",
    "всем", "всех", "всему", "всеми",
    "такой", "такая", "такие", "таких",
    "другой", "другие", "других",
    "очень", "совсем", "почти", "около",
    "сначал", "начал", "начала", "начало",
    "сделан", "сделать", "делать", "делал",
    # Temporal / generic quantifiers / generic verbs (noise as topic anchors)
    "сейчас", "теперь", "сколько", "сколько", "когда", "потом",
    "вообщ", "конечно", "кстат", "иметь",
    "понима", "понять", "знаешь",
    "антон",  # Anton's own name = always in his notes, not a topic
    "этого", "этот", "этому", "этим", "этих",
    "через", "между", "внутр", "наруж",
    "место", "месяц",  # generic positional/temporal words
    "много", "мало",
    "какой", "какая", "какое", "каких",
    "задач", "задача",  # borderline generic - appears everywhere; let domain-specific compound carry it
    "денег",  # duplicate stem variant of "деньг" -- IDF handles this but explicit is cleaner
    "работа", "работает",  # work/works = too generic; "работать" etc.
    "месяц",  # temporal unit, not a topic
    # More generic qualifiers / discourse markers (noise as TOPIC anchors)
    "например", "наприм",   # "for example"
    "необходимост",          # "necessity" = normative, not a topic
    "наших", "нашего", "нашей", "наших",  # possessive pronoun
    "ничего",                # "nothing" - generic negation
    "срочно", "срочн",       # "urgently" - adverb, not topic
    "хорошо", "хорош",       # "well/good" - evaluative, not topic
    "человек",               # "person" - too generic in any note about people
    "ответ", "ответа",       # "answer" - generic discourse
    "брать", "берет", "взять",  # "to take" - generic verb
    "ребят", "ребята",       # "guys" - address form, not topic
    # Generic DOMAIN vocabulary (2026-07-04): bare business nouns are FREQUENT but not
    # an "insight" - the recurring miner's value is SPECIFIC themes, not field vocabulary.
    # Screen verdict 2026-07-04: these 7 anchors were top-scored yet ALL judged noise
    # (recurring precision 0.00). Stems match _stem() output for their inflections.
    "деньг", "людей", "люди", "бизнес", "продукт", "команд", "инвестор",
    "компани", "проект", "рынок", "клиент", "сделк",
    # discourse/modal function-word leaks (not domain whack-a-mole):
    "именно", "навсегд", "навсегда", "возможно", "перед", "перел",
    # English function (>=5 chars subset)
    "i", "the", "is", "it", "in", "of", "a", "an", "to", "that",
    "and", "or", "but", "you", "we", "they", "this", "are", "be",
    "must", "will", "have", "has", "for", "on", "with", "at", "do",
    "which", "their", "there", "about", "would", "could", "should",
    "think", "know", "believe", "feel", "always", "never",
    "important", "always", "never", "every",
}

WORD_RE  = re.compile(r"[а-яёa-z]{5,}", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+")
WS         = re.compile(r"\s+")

# Lite Russian suffix stripping (order = longest first).
RU_SUFFIXES = (
    "ирования", "ирование", "изацию", "изации", "изация",
    "ование", "ования", "ований",
    "ующего", "ующему", "ующими", "ующий", "ующих", "ующем",
    "ующей", "ующая", "ующее",
    "ировать", "ировал", "ирован",
    "ности", "ность",
    "ского", "скому", "ской", "ских", "ский", "ская", "ское",
    "ьного", "ьному", "ьной", "ьных", "ьный", "ьная", "ьное",
    "ного", "ному", "ной", "ных", "ный", "ная", "ное",
    "ями", "ами", "ых", "ый", "ой", "ом", "ую",
    "ей", "ии", "ий", "ая", "ое", "ие",
    "ях", "ам", "ах",
    "ою", "ью",
    "ть", "ся", "сь",
    "ов", "ев",
    "и", "е", "а", "у", "ю", "я",
)

def _stem(word):
    for suf in RU_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[:-len(suf)]
    return word

def _topic_anchors(sentence):
    """Return set of topic-anchor stems from a conviction sentence."""
    words = WORD_RE.findall(sentence.lower())
    anchors = set()
    for w in words:
        if w not in FUNCTION_STOPWORDS and len(w) >= 5:
            stem = _stem(w)
            # Require stem >= 5 chars to avoid stub-stems of common words
            if len(stem) >= 5 and stem not in FUNCTION_STOPWORDS:
                anchors.add(stem)
    return anchors

# ---------------------------------------------------------------------------
# NOTE PARSING
# ---------------------------------------------------------------------------

def note_date(txt, path):
    """Best-effort source date: frontmatter date/created/updated, or filename."""
    for field in ("date", "created", "updated", "date_established"):
        m = re.search(r"^\s*%s\s*:\s*[\"']?(\d{4}-\d{2}-\d{2})" % field, txt, re.M)
        if m:
            return m.group(1)
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", os.path.basename(path))
    return m.group(1) if m else ""

def note_year(date_str):
    m = re.match(r"(20\d{2})", date_str)
    return m.group(1) if m else ""

def parse(path):
    try:
        txt = io.open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    title = ""
    m = re.search(r'^\s*title\s*:\s*["\']?(.*?)["\']?\s*$', txt, re.M)
    if m:
        title = m.group(1).strip()
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    return title, txt

def extract_convictions(txt):
    """Yield (sentence, anchors_set) for each conviction sentence in the body."""
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", txt, flags=re.S)
    for raw in SENT_SPLIT.split(body):
        s = WS.sub(" ", raw).strip()
        if not (25 < len(s) < 400):
            continue
        if s.count("|") >= 3 or s.lstrip().startswith("#"):
            continue
        low = s.lower()
        if not any(m in low for m in CONVICTION_MARKERS):
            continue
        if any(d in low for d in DROP_CTX):
            continue
        anch = _topic_anchors(s)
        if anch:
            yield s, anch

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args    = sys.argv[1:]
    full    = "--all" in args
    today   = "2026-06-15"
    if "--today" in args:
        today = args[args.index("--today") + 1]

    state = {}
    if not full and os.path.isfile(STATE):
        try:
            state = json.load(io.open(STATE, encoding="utf-8"))
        except (OSError, ValueError):
            state = {}

    if not os.path.isdir(CANDIR):
        os.makedirs(CANDIR)

    con = sqlite3.connect(DB)
    if full:
        # --all = TRUE full rebuild. Derived anchors are CACHED in convictions.anchors;
        # without this drop, a changed stopword/threshold never propagates (INSERT OR IGNORE
        # keeps stale rows, step-2 re-indexes from them). Wipe = re-extract with CURRENT rules.
        # Safe: this DB is a pure derived cache of the vault; verdicts live in alpha_review.db.
        con.executescript("DROP TABLE IF EXISTS convictions;"
                          "DROP TABLE IF EXISTS topic_index;"
                          "DROP TABLE IF EXISTS topic_summary;")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS convictions(
            id         INTEGER PRIMARY KEY,
            source_path  TEXT,
            source_title TEXT,
            source_year  TEXT,
            sentence     TEXT,
            anchors      TEXT,
            first_seen   TEXT,
            UNIQUE(source_path, sentence)
        );
        CREATE TABLE IF NOT EXISTS topic_index(
            anchor       TEXT,
            source_path  TEXT,
            source_title TEXT,
            source_year  TEXT,
            sentence     TEXT,
            PRIMARY KEY(anchor, source_path, sentence)
        );
        CREATE TABLE IF NOT EXISTS topic_summary(
            anchor      TEXT PRIMARY KEY,
            dist_years  INTEGER,
            dist_notes  INTEGER,
            score       REAL,
            updated     TEXT
        );
    """)
    con.commit()

    # -----------------------------------------------------------------------
    # 1. COLLECT: scan changed notes, extract convictions + anchors.
    # -----------------------------------------------------------------------
    files = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        curated = root in CURATED_ROOTS
        for dp, _dn, fns in os.walk(root):
            _dn[:] = [d for d in _dn if not d.startswith(".")]  # skip .stversions (Syncthing archive) & dotdirs
            for fn in fns:
                if fn.endswith(".md") and not fn.startswith("_"):
                    files.append((os.path.join(dp, fn), curated))

    new_state   = dict(state)
    scanned     = 0
    new_convict = 0
    for path, is_curated in files:
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        if not full and state.get(path) == mt:
            continue
        new_state[path] = mt
        parsed = parse(path)
        if not parsed:
            continue
        title, txt = parsed
        if not _is_anton(txt, path, is_curated_root=is_curated):
            continue
        scanned += 1
        yr = note_year(note_date(txt, path))
        for sent, anchors in extract_convictions(txt):
            anch_str = " ".join(sorted(anchors))
            try:
                con.execute(
                    "INSERT OR IGNORE INTO convictions"
                    "(source_path,source_title,source_year,sentence,anchors,first_seen)"
                    " VALUES(?,?,?,?,?,?)",
                    (path, title, yr, sent, anch_str, today))
                if con.total_changes:
                    new_convict += 1
                    # Index each anchor -> this note+sentence
                    for anchor in anchors:
                        con.execute(
                            "INSERT OR IGNORE INTO topic_index"
                            "(anchor,source_path,source_title,source_year,sentence)"
                            " VALUES(?,?,?,?,?)",
                            (anchor, path, title, yr, sent))
            except sqlite3.Error:
                pass
    con.commit()

    # -----------------------------------------------------------------------
    # 2. TOPIC SUMMARY: aggregate per anchor across all stored convictions.
    # -----------------------------------------------------------------------
    # Rebuild from scratch for idempotency.
    con.execute("DELETE FROM topic_summary")
    # Re-index all stored convictions (incremental runs may miss earlier data).
    rows_all = con.execute("SELECT source_path,source_title,source_year,sentence,anchors FROM convictions").fetchall()
    for path, title, yr, sent, anch_str in rows_all:
        for anchor in anch_str.split():
            con.execute(
                "INSERT OR IGNORE INTO topic_index(anchor,source_path,source_title,source_year,sentence)"
                " VALUES(?,?,?,?,?)",
                (anchor, path, title, yr, sent))

    # Total distinct notes scanned (for IDF-like frequency threshold).
    total_notes_scanned = con.execute("SELECT COUNT(DISTINCT source_path) FROM convictions").fetchone()[0]
    # Ultra-common stems that appear in > 12% of all conviction notes = generic vocabulary,
    # not a specific recurring THEME (tightened 0.20 -> 0.12 on 2026-07-04 after screen
    # precision came back 0.00 - top-scored anchors were all field-generic nouns).
    MAX_NOTE_FRACTION = 0.12
    max_notes_for_anchor = max(3, int(total_notes_scanned * MAX_NOTE_FRACTION))

    # Aggregate
    anchors_list = con.execute("SELECT DISTINCT anchor FROM topic_index").fetchall()
    for (anchor,) in anchors_list:
        rows = con.execute(
            "SELECT DISTINCT source_path, source_year FROM topic_index WHERE anchor=?",
            (anchor,)).fetchall()
        dist_notes = len(rows)
        dist_years = len({r[1] for r in rows if r[1]})
        # Filter ultra-common stems: too many notes = generic word, not a topic.
        if dist_notes > max_notes_for_anchor:
            score = 0.0   # will be excluded from candidates
        else:
            score = float(dist_years * dist_notes)
        con.execute(
            "INSERT OR REPLACE INTO topic_summary(anchor,dist_years,dist_notes,score,updated)"
            " VALUES(?,?,?,?,?)",
            (anchor, dist_years, dist_notes, score, today))
    con.commit()

    # -----------------------------------------------------------------------
    # 3. CANDIDATES: top topics by score (years >= 2, notes >= 3).
    # Also include "curated-signal" topics: >= 5 distinct curated notes
    # (belief-*/insight-*/concept-*) -- even without year spans, these
    # represent Anton's permanent recurring themes.
    # -----------------------------------------------------------------------
    # Primary: multi-year recurrence
    candidates_dated = con.execute("""
        SELECT anchor, dist_years, dist_notes, score
        FROM topic_summary
        WHERE dist_years >= 2 AND dist_notes >= 3
        ORDER BY score DESC LIMIT 20
    """).fetchall()

    # Secondary: curated-layer high-note-count (no year requirement)
    curated_paths_re = r'%03-Insights%'
    candidates_curated = con.execute("""
        SELECT ts.anchor, ts.dist_years, ts.dist_notes, ts.score
        FROM topic_summary ts
        WHERE ts.dist_notes >= 5 AND ts.dist_years < 2
        ORDER BY ts.dist_notes DESC, ts.score DESC LIMIT 10
    """).fetchall()

    # Merge, deduplicate, keep top 10
    seen_anchors = set()
    all_candidates = []
    for row in candidates_dated:
        if row[0] not in seen_anchors:
            seen_anchors.add(row[0])
            all_candidates.append(("dated", row))
    for row in candidates_curated:
        if row[0] not in seen_anchors:
            seen_anchors.add(row[0])
            all_candidates.append(("curated", row))
    all_candidates.sort(key=lambda x: -x[1][3])
    top = all_candidates[:10]

    total_anchors    = con.execute("SELECT COUNT(DISTINCT anchor) FROM topic_index").fetchone()[0]
    total_candidates = len(candidates_dated) + len(candidates_curated)

    day = datetime.datetime.strptime(today, "%Y-%m-%d").strftime("%Y-%m-%d")
    L = [
        "# Recurring-pattern -- kandidaty v [[insight-worldview-throughlines]] (%s)" % day,
        "",
        "_(Recurring convictions: >= 3 notes x >= 2 years. "
        "Deterministic scan, 0 tokens. "
        "Verdict: update [[insight-worldview-throughlines]].)_",
        "",
        "- topic anchors indexed: **%d** | candidates (>=3 notes x >=2 years): **%d** | shown: %d"
        % (total_anchors, len(candidates_dated), len(top)),
        "",
    ]

    if not top:
        L.append("_No candidates at current threshold._")
    for rank, (kind, (anchor, dist_years, dist_notes, score)) in enumerate(top, 1):
        # Fetch representative evidence rows (up to 4, from distinct notes and years)
        ev_rows = con.execute("""
            SELECT source_path, source_title, source_year, sentence
            FROM topic_index WHERE anchor=?
            ORDER BY source_year, source_path
        """, (anchor,)).fetchall()

        # Pick up to 3 examples from distinct notes
        seen_ev_paths = set()
        examples = []
        for ep, et, ey, es in ev_rows:
            if ep not in seen_ev_paths:
                seen_ev_paths.add(ep)
                examples.append((ep, et, ey, es))
            if len(examples) >= 3:
                break

        years_seen = sorted({r[2] for r in ev_rows if r[2]})
        kind_tag   = "[dated]" if kind == "dated" else "[curated]"
        L.append("### #%d -- %s  %s" % (rank, anchor, kind_tag))
        L.append("- score: **%.0f** (years x notes = %d x %d)" % (
            score, dist_years, dist_notes))
        L.append("- years: %s" % (", ".join(years_seen) if years_seen else "(no date in notes)"))
        L.append("- distinct notes: %d" % len({r[0] for r in ev_rows}))
        L.append("")
        for ep, et, ey, es in examples:
            link = "[[%s]]" % os.path.splitext(os.path.basename(ep))[0]
            # safe ASCII for stdout; Cyrillic goes to the UTF-8 file
            L.append("  - %s (%s): \"%s\"" % (link, ey or "?", es))
        L.append("")
        L.append("- verdict: [ ] add to throughlines  [ ] already there  [ ] noise  [ ] new pattern")
        L.append("")

    body = "\n".join(L) + "\n"
    dated_name  = "recurring-report-%s.md" % day
    latest_name = "recurring-report-latest.md"
    for name in (dated_name, latest_name):
        io.open(os.path.join(CANDIR, name), "w", encoding="utf-8", newline="\n").write(body)

    json.dump(new_state, io.open(STATE, "w", encoding="utf-8"))
    con.close()

    # All stdout ASCII-only (cp1252 safety on Windows)
    print("SCANNED", scanned)
    print("NEW_CONVICTIONS", new_convict)
    print("TOPIC_ANCHORS", total_anchors)
    print("CANDIDATES", len(candidates_dated))
    print("REPORT", os.path.join(CANDIR, "recurring-report-latest.md"))


if __name__ == "__main__":
    main()
