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
r"""alpha_harvest.py — fold the 10 miners' heterogeneous judge reports into ONE
uniform table the review screen can read.

WHY this exists
---------------
Each miner's LLM-judge writes a FREEFORM markdown report
(`candidates\<miner>-judged-latest.md`) — bets uses a table, openq/novelty use
`**#N**` heading blocks, formats differ per miner AND per run. There is no single
machine-readable list of "what the judge kept for Anton to look at". This script is
the thin, TOLERANT adapter: it reads every judged report, pulls out the KEEPER items
(✅/OK/KEEPER/PARTIAL/🟡 — never the 🗑/DROP ones), and upserts them into a uniform
`alpha_review.db` table. The review server reads ONLY this clean table, so the
fragile per-format parsing lives in exactly one place (AK-47: one repairable seam).

It NEVER touches the detectors, the ledgers, or the judge skill — read-only on the
judged .md files, writes only its own db. Idempotent: re-running upserts by a stable
text_hash, so Anton's gold/miss verdicts (stored in a SEPARATE table) survive a
re-harvest even if the judge re-words a reason.

  python alpha_harvest.py          # harvest all miners -> alpha_review.db, print coverage
  python alpha_harvest.py --quiet   # same, no per-file print

Coverage is PRINTED (kept/scanned per file) so a parser miss is visible, not silent.
"""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os, re, sys, sqlite3, hashlib
from datetime import datetime, timezone

ALPHADIR = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.join(ALPHADIR, "candidates")
DB = os.path.join(ALPHADIR, "alpha_review.db")

# miner key -> (judged filename, curated HOME note it feeds). Mirrors skill alpha-judge.
MINERS = [
    ("bets",          "bets-judged-latest.md",          "insight-prediction-ledger"),
    ("contradictions","contra-judged-latest.md",        "insight-contradictions"),
    ("stance",        "stance-judged-latest.md",        "insight-contradictions"),
    ("bridge",        "bridge-judged-latest.md",        "insight-worldview-throughlines"),
    ("recurring",     "recurring-judged-latest.md",     "insight-worldview-throughlines"),
    # ("leadsignal", ...) RETIRED 2026-07-16: 42.9% precision on Anton's etalon; leads live in /pipeline
    ("novelty",       "novelty-judged-latest.md",       "insight-novelty-ideas"),
    ("identity",      "identity-judged-latest.md",      "_Self-Bible-MOC"),
    ("openq",         "openq-judged-latest.md",         "insight-open-questions"),
    # ("orphan", ...) RETIRED 2026-07-16: 37.5% precision on Anton's etalon; orphan-weaving lives in /relink --deep
    ("lobster",       "lobster-judged-latest.md",       "LobsterDAO-Alpha MOC (community)"),
    ("sostav",        "sostav-judged-latest.md",        "🔒 Sostav-MOC (PRIVATE — high sensitivity)"),
    ("promptdesign",  "promptdesign-judged-latest.md",  "AI-tooling alpha (@prompt_design channel)"),
    ("promptchat",    "promptchat-judged-latest.md",    "AI-tooling alpha (@prompt_chat — Силиконовый Мешок discussion)"),
]

# a heading that STARTS the DROP / rejected region — the drop token must lead the
# heading (not merely appear in a summary line like "## ИТОГ: ✅2 🟡14 🗑4").
_DROP_HEAD = re.compile(r"^#{2,4}\s*(?:🗑|\bDROP\b|DROPPED|Отклонённ|Отброшенн|REJECT)", re.I)
# section / label sub-headings that are NOT items (openq "### Тема:", novelty "### OK").
_HEADING = re.compile(r"^#{1,6}\s")
_SECTION_HEAD = re.compile(
    r"^#{2,4}\s+(?:KEPT|KEEPER|OK\b|PARTIAL|DROP|DROPPED|Тема|Итог|ИТОГ|Результат|"
    r"Рекоменд|Калибров|JUDGE|SUMMARY|NOTE|Отклон|Отброш|WORTH|PREVIOUS|Предыдущ|"
    r"Историч|Сводк|Связано|Top\s*\d|Топ)", re.I)
# an item block starts with: **#4**, **1.**, **#159** ; a table row | #15 | ;
# OR a deep heading (### / ####) that is NOT a section label (### J-OK-1, ### #109, ### B-OK-01).
_BOLD_ITEM = re.compile(r"^\s*(?:\*\*#?\d+[.\)]?|\*\*\d+[.\)])")
_TABLE_ITEM = re.compile(r"^\s*\|\s*#?\d+\b")
_DEEP_HEAD = re.compile(r"^#{3,4}\s+\S")
_WIKILINK = re.compile(r"\[\[([^\]]+?)\]\]")
# per-block tokens
_DROP_TOK = re.compile(r"(?:🗑|\bDROP\b|не\s+ставка|\bшум\b|restatement|"
                       r"уже\s+(?:в\s+доме|сред))", re.I)
_PARTIAL_TOK = re.compile(r"(?:🟡|PARTIAL|частичн)", re.I)
_OK_TOK = re.compile(r"(?:✅|\bOK\b|KEEPER|KEPT|сбылось|реальн)", re.I)
_REASON = re.compile(r"^\s*[-*]?\s*(?:Причина|Reason)\s*[:：]?\s*(.+)$", re.I)


_BARE_ID = re.compile(r"^(?:[A-ZА-Я]?-?\w{0,4}-?\d+|OK|PARTIAL|miss|gold|Кандидат)\s*$", re.I)
_CONTENT_LINE = re.compile(
    r"\*\*(?:Statement|Insight|New stance|Old stance|Заявление|Мысль|Утвержд|Вопрос|Claim)"
    r"[^:]*:\*\*\s*(.+)", re.I)


def _clean_title(line):
    t = line.strip().lstrip("|").strip()
    t = re.sub(r"^\*\*#?\d+[.\)]?\*\*", "", t)        # **#4** / **1.**
    t = re.sub(r"^#{2,4}\s+", "", t)                  # leading ###
    t = re.sub(r"^[#*✅🟡🎯⚖️\s—–-]+", "", t)            # leading emoji/punct
    t = re.sub(r"^(?:#?\d+[.\)]?|[A-ZА-Я]-?\w*-?\d+|Кандидат\s*#?\d+)\s*[—–:.\-]*\s*", "", t)
    t = t.replace("**", "").strip(" |—–-:").strip()
    if "|" in t:                                       # table row: first cell
        t = t.split("|")[0].strip()
    return t[:200]


def _best_title(title_line, block):
    """Heading title if meaningful; else fall back to the block's first content line."""
    t = _clean_title(title_line)
    if t and not _BARE_ID.match(t) and len(t) >= 4:
        return t
    for bl in block.splitlines()[1:]:
        m = _CONTENT_LINE.search(bl)
        if m:
            return m.group(1).replace("**", "").strip(' "«»')[:200]
        q = re.match(r"^\s*>\s*[«\"]?(.+)", bl)         # a quote line
        if q:
            return q.group(1).strip(' "«»')[:200]
    return t or "(без заголовка)"


def _is_item_start(ln):
    if _BOLD_ITEM.match(ln):
        return True
    if _DEEP_HEAD.match(ln) and not _SECTION_HEAD.match(ln):
        return True
    return False


_SEP_ROW = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


def _parse_tables(region):
    """Column-aware extraction of verdict tables (orphan etc.). Classifies each row by
    its Verdict CELL, so DROP rows inside one big table are skipped correctly."""
    items, i, n = [], 0, len(region)
    while i < n:
        ln = region[i]
        if (ln.lstrip().startswith("|") and i + 1 < n and _SEP_ROW.match(region[i + 1])
                and set(region[i + 1].replace("|", "").strip()) <= set("-: ")):
            header = [c.strip().lower() for c in ln.strip().strip("|").split("|")]

            def col(*keys):
                for idx, h in enumerate(header):
                    if any(k in h for k in keys):
                        return idx
                return None
            ti = col("title", "назван", "кандидат", "claim", "question", "вопрос", "statement")
            vi = col("verdict", "вердикт")
            ri = col("reason", "причина")
            si = col("source", "folder", "папк", "источник", "путь")
            j = i + 2
            while j < n and region[j].lstrip().startswith("|"):
                cells = [c.strip() for c in region[j].strip().strip("|").split("|")]

                def cell(idx):
                    return cells[idx] if idx is not None and idx < len(cells) else ""
                cls = _classify(cell(vi) if vi is not None else region[j])
                if cls is not None:
                    title = (cell(ti) or "").replace("**", "").strip(" |—–-:")
                    src = cell(si).strip("`").strip()
                    wl = _WIKILINK.search(region[j])
                    if wl:
                        src = wl.group(1)
                    if title:
                        items.append({"title": title[:200], "source": src,
                                      "judge_verdict": cls,
                                      "reason": cell(ri)[:300], "raw": region[j].strip()[:1200]})
                j += 1
            i = j
        else:
            i += 1
    return items


def _keeper_region(text):
    """Lines BEFORE the drop/rejected region (default: whole file)."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if _DROP_HEAD.match(ln):
            return lines[:i]
    return lines


def _split_blocks(region):
    """Yield (title_line, block_text) for each item block in the keeper region.
    A section/label heading both ends the current block AND is itself never an item."""
    def flush(start, end, out):
        if start is not None:
            out.append((region[start], "\n".join(region[start:end])))

    blocks, cur = [], None
    for i, ln in enumerate(region):
        if _is_item_start(ln):
            flush(cur, i, blocks)
            cur = i
        elif _HEADING.match(ln):
            flush(cur, i, blocks)
            cur = None          # ANY heading ends a block (and is never an item itself)
    flush(cur, len(region), blocks)
    for b in blocks:
        yield b


def _classify(block):
    if _DROP_TOK.search(block):
        return None                      # explicit drop even inside keeper region
    if _PARTIAL_TOK.search(block):
        return "partial"
    return "ok"                          # OK token OR default keeper


def parse_file(path):
    items = []
    if not os.path.exists(path):
        return items, 0
    text = open(path, encoding="utf-8", errors="replace").read()
    region = _keeper_region(text)
    n_blocks = 0
    # pass 1 — column-aware verdict tables (orphan, etc.)
    for it in _parse_tables(region):
        n_blocks += 1
        items.append(it)
    # pass 2 — heading / bold-id blocks (everything else)
    for title_line, block in _split_blocks(region):
        n_blocks += 1
        verdict = _classify(block)
        if verdict is None:
            continue
        title = _best_title(title_line, block)
        if not title:
            continue
        wl = _WIKILINK.search(block)
        source = wl.group(1) if wl else ""
        reason = ""
        for bl in block.splitlines():
            m = _REASON.match(bl)
            if m:
                reason = m.group(1).strip()[:300]
                break
        items.append({"title": title, "source": source,
                      "judge_verdict": verdict, "reason": reason,
                      "raw": block.strip()[:1200]})
    return items, n_blocks


def _hash(miner, title, source):
    h = hashlib.sha1()
    h.update((miner + "|" + re.sub(r"\s+", " ", title.lower()) + "|" + source.lower()).encode())
    return h.hexdigest()[:16]


def ensure_db(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS items(
        item_hash TEXT PRIMARY KEY,
        miner TEXT, home TEXT,
        title TEXT, source TEXT,
        judge_verdict TEXT, reason TEXT, raw TEXT,
        first_seen TEXT, last_seen TEXT);
    CREATE TABLE IF NOT EXISTS verdicts(
        item_hash TEXT PRIMARY KEY,
        miner TEXT,
        anton_verdict TEXT,            -- 'gold' | 'miss' | 'skip'
        note TEXT,
        ts TEXT);
    CREATE INDEX IF NOT EXISTS ix_items_miner ON items(miner);
    """)
    con.commit()


def harvest(quiet=False):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = sqlite3.connect(DB)
    ensure_db(con)
    seen_hashes = set()
    per_miner = []
    for miner, fname, home in MINERS:
        path = os.path.join(CAND, fname)
        items, n_blocks = parse_file(path)
        kept = 0
        for it in items:
            ih = _hash(miner, it["title"], it["source"])
            if ih in seen_hashes:
                continue
            seen_hashes.add(ih)
            row = con.execute("SELECT item_hash FROM items WHERE item_hash=?", (ih,)).fetchone()
            if row:
                con.execute("""UPDATE items SET title=?, source=?, judge_verdict=?,
                    reason=?, raw=?, home=?, last_seen=? WHERE item_hash=?""",
                    (it["title"], it["source"], it["judge_verdict"], it["reason"],
                     it["raw"], home, now, ih))
            else:
                con.execute("""INSERT INTO items(item_hash, miner, home, title, source,
                    judge_verdict, reason, raw, first_seen, last_seen)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (ih, miner, home, it["title"], it["source"], it["judge_verdict"],
                     it["reason"], it["raw"], now, now))
            kept += 1
        per_miner.append((miner, kept, n_blocks, os.path.exists(path)))
        if not quiet:
            tag = "" if os.path.exists(path) else "  (no judged file yet)"
            print(f"  {miner:14s} kept {kept:3d} / {n_blocks:3d} blocks{tag}")
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    judged = con.execute("SELECT COUNT(*) FROM verdicts WHERE anton_verdict IN ('gold','miss')").fetchone()[0]
    con.close()
    if not quiet:
        print(f"\n  alpha_review.db: {total} keeper-items total · {judged} with Anton's verdict")
    return per_miner, total


if __name__ == "__main__":
    print("harvesting judge keepers -> alpha_review.db\n")
    harvest(quiet="--quiet" in sys.argv)
