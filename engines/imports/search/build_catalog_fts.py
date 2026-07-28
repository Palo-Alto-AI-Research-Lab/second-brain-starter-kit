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
"""First brick of the unified search layer: BM25/FTS5 catalog over CHAT content.

Indexes all conversation markdown in 01-Conversations/** (Telegram, Facebook,
ChatGPT, Claude, Apple-Notes, transcripts, ...) into ONE rebuildable SQLite file
search_catalog.db with an FTS5 (BM25) index over title+body. 0 GPU, deterministic.

Per decision-unified-search-layer: the index is a DERIVED, REBUILDABLE artifact
keyed by content md5 + parser version. The vector (sqlite-vec) + RRF + reranker
lanes are added in a later step; this is the lexical lane.

Single-writer: builds into search_catalog.db.tmp then atomically replaces, so a
concurrent reader/parallel session never sees a half-built DB.
ASCII-only stdout (Windows cp1252).
"""
import os, io, re, sqlite3, hashlib, time

PARSER_VERSION = "1"
VAULT = r"%VAULT%"
ROOT = os.path.join(VAULT, "01-Conversations")
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "search_catalog.db")
TMP = DB + ".tmp"

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

def split_fm(text):
    m = FM.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip().lower()] = v.strip().strip('"').strip("'")
    return fm, text[m.end():]

def main():
    print("[%s] catalog rebuild start" % time.strftime("%Y-%m-%d %H:%M:%S"))
    if os.path.exists(TMP):
        os.remove(TMP)
    con = sqlite3.connect(TMP)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE docs(
        path TEXT PRIMARY KEY, title TEXT, source TEXT, date TEXT,
        md5 TEXT, chars INTEGER)""")
    con.execute("""CREATE VIRTUAL TABLE docs_fts USING fts5(
        title, body, path UNINDEXED, source UNINDEXED, date UNINDEXED,
        tokenize='unicode61 remove_diacritics 2')""")
    con.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")

    n = 0
    skipped = 0
    batch = []
    t0 = time.time()
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                raw = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                skipped += 1
                continue
            fm, body = split_fm(raw)
            title = fm.get("title") or os.path.splitext(fn)[0]
            source = fm.get("source") or fm.get("chat") or os.path.basename(dirpath)
            date = fm.get("date") or ""
            rel = os.path.relpath(p, VAULT)
            md5 = hashlib.md5(raw.encode("utf-8", "replace")).hexdigest()
            batch.append((rel, title, source, date, md5, len(body), body))
            n += 1
            if len(batch) >= 2000:
                con.executemany("INSERT OR REPLACE INTO docs VALUES(?,?,?,?,?,?)",
                                [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in batch])
                con.executemany("INSERT INTO docs_fts(title, body, path, source, date) VALUES(?,?,?,?,?)",
                                [(r[1], r[6], r[0], r[2], r[3]) for r in batch])
                con.commit()
                batch = []
                if n % 20000 == 0:
                    print("  indexed %d ..." % n)
    if batch:
        con.executemany("INSERT OR REPLACE INTO docs VALUES(?,?,?,?,?,?)",
                        [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in batch])
        con.executemany("INSERT INTO docs_fts(title, body, path, source, date) VALUES(?,?,?,?,?)",
                        [(r[1], r[6], r[0], r[2], r[3]) for r in batch])
        con.commit()

    con.execute("INSERT OR REPLACE INTO meta VALUES('parser_version',?)", (PARSER_VERSION,))
    con.execute("INSERT OR REPLACE INTO meta VALUES('built_unixtime',?)", (str(int(t0)),))
    con.execute("INSERT OR REPLACE INTO meta VALUES('doc_count',?)", (str(n),))
    con.execute("INSERT OR REPLACE INTO meta VALUES('root',?)", (ROOT,))
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()

    # atomic replace with retry: a transient reader (search-UI query, Syncthing
    # hashing, coverage scan) holding the old DB open makes os.replace throw
    # WinError 32 for a few seconds; one weekly run must survive that.
    last_err = None
    for attempt in range(30):
        try:
            os.replace(TMP, DB)
            break
        except PermissionError as e:
            last_err = e
            print("  swap blocked (attempt %d/30): %s" % (attempt + 1, e))
            time.sleep(10)
    else:
        raise SystemExit("swap failed after 300s, old catalog kept: %s" % last_err)
    for ext in ("-wal", "-shm"):
        if os.path.exists(TMP + ext):
            try: os.remove(TMP + ext)
            except OSError: pass

    dt = time.time() - t0
    print("[%s] CATALOG OK -> search_catalog.db" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("  docs=%d skipped=%d  %.1fs" % (n, skipped, dt))

if __name__ == "__main__":
    main()
