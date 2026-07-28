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
"""search.py — unified chat search CLI (first brick: BM25/FTS5 lane).

Usage:
  python search.py <query words...>        # content search over all chats
  python search.py --k 20 <query>          # top-k (default 12)
  python search.py --chats <query>         # ALSO list matching chat TITLES (dialogs.db)

Lexical (BM25) lane over search_catalog.db. The vector + RRF + reranker lanes
are added next per decision-unified-search-layer; this proves the chat-content
search end to end first. 0 tokens, 0 GPU, 0 MCP.
ASCII-safe stdout (Windows cp1252).
"""
import os, sqlite3, sys, re

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "search_catalog.db")
DIALOGS = os.path.join(os.path.dirname(HERE), "dialogs", "dialogs.db")

def asc(s):
    return s or ""

def fts_query(words):
    # quote each token so punctuation/cyrillic don't break FTS5 syntax; AND-join
    toks = [t for t in re.split(r"\s+", words.strip()) if t]
    return " ".join('"%s"' % t.replace('"', '') for t in toks)

def main():
    args = sys.argv[1:]
    k = 12
    show_chats = False
    out = []
    for a in args:
        if a == "--chats":
            show_chats = True
        elif a.startswith("--k"):
            pass
        else:
            out.append(a)
    if "--k" in args:
        i = args.index("--k")
        if i + 1 < len(args):
            try: k = int(args[i + 1]); out = [x for x in out if x != args[i + 1]]
            except ValueError: pass
    q = " ".join(out).strip()
    if not q:
        print("usage: python search.py [--k N] [--chats] <query>")
        return
    if not os.path.exists(CATALOG):
        print("NO CATALOG yet -- run build_catalog_fts.py first")
        return

    con = sqlite3.connect(CATALOG)
    con.create_function("noop", 0, lambda: None)
    m = fts_query(q)
    try:
        rows = con.execute(
            "SELECT path, source, date, snippet(docs_fts, 1, '[', ']', ' ... ', 12), "
            "bm25(docs_fts) AS r, title "
            "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY r LIMIT ?",
            (m, k)).fetchall()
    except sqlite3.OperationalError as e:
        print("query error: %s" % asc(str(e)))
        con.close()
        return
    total = con.execute("SELECT v FROM meta WHERE k='doc_count'").fetchone()
    con.close()

    print("query=%s   hits(top %d of corpus %s)" % (asc(q), k, total[0] if total else "?"))
    for path, source, date, snip, r, title in rows:
        print("  [%6.1f] %s  (%s %s)" % (r, asc(title)[:60], asc(source)[:22], asc(date)[:10]))
        print("          %s" % asc(snip).replace("\n", " ")[:160])
        print("          %s" % asc(path))

    if show_chats and os.path.exists(DIALOGS):
        dq = q.lower()
        dcon = sqlite3.connect(DIALOGS)
        drows = dcon.execute("SELECT account, chat_id, type, title FROM dialogs").fetchall()
        dcon.close()
        hits = [(a, c, t, ti) for (a, c, t, ti) in drows if dq in (ti or "").lower()]
        print("\nCHAT TITLES (dialogs.db) hits=%d" % len(hits))
        for a, c, t, ti in hits[:20]:
            print("  %-12s %-14s %s" % (a, c, asc(ti)[:60]))

if __name__ == "__main__":
    main()
