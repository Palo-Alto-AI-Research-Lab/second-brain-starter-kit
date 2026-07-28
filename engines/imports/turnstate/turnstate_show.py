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
Viewer for the per-turn semantic-state ledger (Phase 1 of always-on memory).
Read-only. 0 tokens. See decision-always-on-memory-architecture.md.

Usage:
  python turnstate_show.py                 # last 15 turns (all sessions)
  python turnstate_show.py --session <id>  # one session
  python turnstate_show.py --n 40          # last N
  python turnstate_show.py --stats         # totals
"""
import sqlite3, json, os, sys, argparse

def _machine_env():
    d = {}
    try:
        p = os.path.join(os.path.expanduser("~"), ".claude", "machine.env")
        with open(p, encoding="utf-8", errors="ignore") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1)
                    d[k.strip()] = v.strip()
    except Exception:
        pass
    return d


def _db_candidates():
    # SAME resolution order as the writer (~/.claude/hooks/turnstate_hook.py :db_path).
    # They must not drift: a reader looking elsewhere reports "no ledger" while the
    # ledger is being written fine — silent blindness, not emptiness.
    bases = []
    imp = os.environ.get("IMPORTS_ROOT") or _machine_env().get("IMPORTS_ROOT")
    if imp:
        bases.append(os.path.join(imp, "turnstate"))
    if os.name == "nt":
        bases.append(r"%IMPORTS%\turnstate")   # hub/HP17 legacy fallback
    bases.append(os.path.join(os.path.expanduser("~"), ".claude", "turnstate"))
    return [os.path.join(b, "turnstate.db") for b in bases]


_cands = _db_candidates()
DB = next((p for p in _cands if os.path.isfile(p)), None)
if DB is None:
    # Loud: a path hiccup must never masquerade as "no ledger yet".
    print("⚠ ledger not found in any known home: " + " | ".join(_cands), file=sys.stderr)
    DB = _cands[-1]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def jl(s):
    try:
        return json.loads(s or "[]")
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--dream", action="store_true", help="review Phase-3 quarantine candidates")
    a = ap.parse_args()

    if not os.path.isfile(DB):
        print("(no ledger yet:", DB, ")"); return
    c = sqlite3.connect(DB)

    if a.dream:
        try:
            rt = c.execute("select max(run_ts) from consolidation_candidates").fetchone()[0]
        except Exception:
            print("(no dream run yet — run dream_consolidate.py)"); return
        print("🌙 DREAM quarantine (run %s) — review only, nothing is in real memory yet" % rt)
        try:
            pk = {(k, l) for k, l in c.execute("select kind,label from promoted_candidates")}
        except Exception:
            pk = set()
        for kind in ("file", "decision", "topic"):
            top = c.execute("select id,label,repetition,sessions,score,tier from consolidation_candidates "
                            "where kind=? order by score desc limit 10", (kind,)).fetchall()
            if top:
                print("\n[%s]" % kind)
                for cid, lab, rep, ns, sc, tr in top:
                    mark = " ✓approved" if (kind, lab) in pk else ""
                    print("  #%-3d %-5s s=%-5.1f rep=%d sess=%d  %s%s" % (cid, tr, sc, rep, ns, lab[:66], mark))
        print("\nGUARD: promotion is human-gated -> `python dream_promote.py --promote <id ...>` (lands in _drafts, not live).")
        return

    if a.stats:
        tot = c.execute("select count(*) from turns").fetchone()[0]
        sess = c.execute("select count(distinct session_id) from turns").fetchone()[0]
        files = c.execute("select count(*) from turns where files != '[]'").fetchone()[0]
        print("ledger:", DB)
        print("turns: %d | sessions: %d | turns-that-touched-files: %d" % (tot, sess, files))
        for sid, n, last in c.execute(
                "select session_id,count(*),max(ts) from turns group by session_id "
                "order by max(ts) desc limit 12"):
            print("  %-38s %4d turns  last %s" % (sid[:38], n, last))
        return

    q = ("select ts,project,ask,summary,files,tools,commands,decisions,session_id "
         "from turns ")
    args = ()
    if a.session:
        q += "where session_id=? "; args = (a.session,)
    q += "order by id desc limit ?"; args = args + (a.n,)

    rows = c.execute(q, args).fetchall()
    for ts, project, ask, summary, files, tools, commands, decisions, sid in reversed(rows):
        print("=" * 78)
        print("🕒 %s   [%s]   sid %s" % (ts, project, sid[:12]))
        if ask:
            print("❓ ask: %s" % ask.replace("\n", " ")[:160])
        f, t, cm, d = jl(files), jl(tools), jl(commands), jl(decisions)
        if f:
            print("📝 files: %s" % ", ".join(os.path.basename(x) for x in f[:6]))
        if t:
            print("🔧 tools: %s" % ", ".join(t[:12]))
        if cm:
            print("⌨  cmds: %d (%s ...)" % (len(cm), (cm[0][:60] if cm else "")))
        if d:
            print("✅ decisions:")
            for x in d[:6]:
                print("     - %s" % x)
        if summary:
            print("💬 summary: %s" % summary.replace("\n", " ")[:200])


if __name__ == "__main__":
    main()
