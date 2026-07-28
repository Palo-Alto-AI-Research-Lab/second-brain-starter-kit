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
r"""brain_health.py — one-glance health of Anton's "second brain" so failures aren't SILENT.
Read-only, 0 LLM tokens. Checks the pieces that broke repeatedly this month (reindex, the
:8770 search server, the memory pilot) and writes a red/green dashboard.

  python brain_health.py            # console report + dashboard
  python brain_health.py --quiet    # dashboard only (for a scheduled run)

Backs the `/brain` skill. Canon: memory always-on-memory-pilot, reindex-routine.
"""
import os, sys, sqlite3, time, json, urllib.request
from pathlib import Path
from datetime import datetime

IMP = Path(r"%IMPORTS%")
EMB = IMP / "_brain_e5.npy"
META = IMP / "_brain_e5_meta.pkl"
TS = IMP / "turnstate" / "turnstate.db"
DREAM_LOG = IMP / "turnstate" / "dream.log"
ABEVAL_LOG = IMP / "turnstate" / "ab_eval.log"
DASH = Path(r"%VAULT%\_Dashboards\Brain-Health.html")
SERVER = "http://127.0.0.1:8770/api?q=ping"

# Coverage floors ride a HIGH-WATER MARK instead of frozen literals (root-fix 2026-07-25,
# same class as bus_wipe_guard): `total < 1000` was written when the essence index was small,
# and by 25.07 the live index held 8210 -- a collapse 8210 -> 1500 (-82%) would have read GREEN.
# The mark grows with the corpus and never shrinks on its own; HARD_MIN stays the backstop.
COVER_HW = IMP / "_brain_coverage_hw.json"
HARD_MIN_TOTAL, HARD_MIN_CONCEPT, DROP_FRAC, WARN_FRAC = 1000, 100, 0.6, 0.85

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def age_h(p):
    try:
        return (time.time() - os.path.getmtime(p)) / 3600.0
    except Exception:
        return None


def fmt_age(h):
    if h is None:
        return "—"
    if h < 1:
        return "%d мин" % int(h * 60)
    if h < 48:
        return "%.1f ч" % h
    return "%.1f дн" % (h / 24.0)


def check_server():
    try:
        req = urllib.request.Request(SERVER, headers={"User-Agent": "brain-health"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
        graph = "/graph" in (j.get("scope", "") or "")
        return "OK", "сервер :8770 жив%s" % (" (Ассоциативная вкл)" if graph else " (Прямая)")
    except Exception as e:
        return "RED", "сервер :8770 НЕ отвечает (%s) — авто-recall молчит" % str(e)[:60]


def check_index():
    if not EMB.exists():
        return "RED", "индекс _brain_e5.npy НЕ найден"
    h = age_h(EMB)
    sz = os.path.getsize(EMB) / (1024 * 1024)
    st = "OK" if h is not None and h < 48 else "WARN"
    return st, "индекс обновлён %s назад, %.0f МБ%s" % (
        fmt_age(h), sz, "" if st == "OK" else " — реиндекс отстал (>48ч)")


def check_rag_backend():
    """Show which RAG backend is ACTUALLY live so e5-fallback isn't SILENT (Anton 2026-07-04).
    Source of truth = brain_ask.resolve_backend() (imported, no drift)."""
    try:
        sys.path.insert(0, str(IMP))
        import brain_ask
        backend = brain_ask.BACKEND
    except Exception as e:
        return "WARN", "бэкенд не определён (brain_ask не импортируется: %s)" % str(e)[:50]
    want = os.getenv("BRAIN_EMB_BACKEND", "openai").lower()
    if backend == "openai":
        return "OK", "RAG-бэкенд: openai (прод-дефолт)"
    if want == "openai":
        return "WARN", "RAG-бэкенд: e5 (FALLBACK — openai-индекс/ключ отсутствует, не прод-дефолт)"
    return "OK", "RAG-бэкенд: e5 (осознанно, BRAIN_EMB_BACKEND=e5)"


def _count(con, sql):
    try:
        return con.execute(sql).fetchone()[0]
    except Exception:
        return None


def check_turnstate():
    if not TS.exists():
        return "WARN", "леджер пуст (turnstate.db ещё нет — заполнится с сессиями)"
    con = sqlite3.connect(str(TS))
    n = _count(con, "select count(*) from turns")
    last = None
    try:
        last = con.execute("select max(ts) from turns").fetchone()[0]
    except Exception:
        pass
    con.close()
    st = "OK" if n else "WARN"
    return st, "TurnState: %s ходов записано, последний %s" % (n if n is not None else 0, last or "—")


def check_dream():
    if not TS.exists():
        return "WARN", "сон ещё не запускался"
    con = sqlite3.connect(str(TS))
    cand = _count(con, "select count(*) from consolidation_candidates")
    con.close()
    h = age_h(DREAM_LOG)
    st = "OK" if h is not None and h < 30 else "WARN"
    return st, "сон: %s кандидатов в карантине, последний прогон %s назад" % (
        cand if cand is not None else 0, fmt_age(h))


def check_ab():
    if not TS.exists():
        return "WARN", "A/B ещё нет данных"
    con = sqlite3.connect(str(TS))
    n = _count(con, "select count(*) from ab_recall")
    g = _count(con, "select count(*) from ab_verdicts where verdict='good'")
    nz = _count(con, "select count(*) from ab_verdicts where verdict='noise'")
    con.close()
    return "OK", "A/B: %s прогонов, вердикты 👍%s/👎%s (суди: ab_eval.py --judge)" % (
        n or 0, g or 0, nz or 0)


def _cover_floors(total, concept):
    """Self-adjusting floors: remember the best-ever sizes, alarm on losing >40% of them.
    RED floor = 60% of high-water (or HARD_MIN, whichever is larger); WARN = 85%.
    A partial reindex writes a SMALLER meta, so it never inflates the mark -- the mark only
    rises on a genuinely bigger corpus, which is exactly when the old frozen floor went stale.
    Env BRAIN_COVER_HW overrides the state file (used by the break-test)."""
    hw = {"total": 0, "concept": 0}
    p = Path(os.environ.get("BRAIN_COVER_HW") or COVER_HW)
    try:
        hw.update(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        pass
    if total > hw.get("total", 0) or concept > hw.get("concept", 0):
        hw["total"] = max(hw.get("total", 0), total)
        hw["concept"] = max(hw.get("concept", 0), concept)
        try:
            p.write_text(json.dumps(hw), encoding="utf-8")
        except Exception:
            pass
    return {
        "total": max(HARD_MIN_TOTAL, int(hw["total"] * DROP_FRAC)),
        "concept": max(HARD_MIN_CONCEPT, int(hw["concept"] * DROP_FRAC)),
        "warn": int(hw["concept"] * WARN_FRAC),
        "hw_total": hw["total"], "hw_concept": hw["concept"],
    }


def check_coverage():
    """Catch the SILENT mind-break: essence collapsed (concept->0, like 2026-06-25 truncated
    reindex) OR raw leaked back into the curated essence-only index. Canon: essence-index-live."""
    if not META.exists():
        return "RED", "мета индекса не найдена"
    try:
        import pickle
        from collections import Counter
        m = pickle.loads(META.read_bytes())
        st = Counter(x.get("source_type", "?") for x in m)
    except Exception as e:
        return "RED", "мета не читается: %s" % str(e)[:50]
    concept = st.get("concept", 0); insight = st.get("insight", 0); total = len(m)
    raw = st.get("conversation", 0) + st.get("lead", 0) + st.get("session", 0) + st.get("person", 0)
    fl = _cover_floors(total, concept)
    if concept < fl["concept"] or total < fl["total"]:
        # The alarm carries its own CURE: a self-adjusting floor that cannot be accepted would
        # stick RED forever after a LEGITIMATE shrink (big dedup/quarantine) -- Codex T3 #3.
        return "RED", ("ум ПОТЕРЯЛ суть: concept=%d (пол %d) total=%d (пол %d), рекорд %d/%d — "
                       "реиндекс не дозавершился? Если усадка ЗАКОННАЯ (чистка/дедуп) — удали "
                       "%s, рекорд перепишется со следующего прогона."
                       % (concept, fl["concept"], total, fl["total"],
                          fl["hw_concept"], fl["hw_total"], COVER_HW))
    if raw > 1000:
        return "WARN", "СЫРЬЁ протекло в курированный индекс: raw=%d (essence-гейт сломан?)" % raw
    if concept < fl["warn"]:
        return "WARN", "concept=%d (ниже %d = 85%% от рекорда %d) — проверь покрытие концептов" % (
            concept, fl["warn"], fl["hw_concept"])
    return "OK", "essence: concept=%d insight=%d note=%d, total=%d (сырьё 0, пол %d/%d)" % (
        concept, insight, st.get("note", 0), total, fl["concept"], fl["total"])


CHECKS = [
    ("Поисковый сервер", check_server),
    ("Индекс (реиндекс)", check_index),
    ("RAG-бэкенд", check_rag_backend),
    ("Покрытие (essence)", check_coverage),
    ("TurnState-леджер", check_turnstate),
    ("Ночной сон", check_dream),
    ("A/B Прямая↔Ассоц", check_ab),
]

COLOR = {"OK": "#37d399", "WARN": "#ffb454", "RED": "#ff6b8b"}
ICON = {"OK": "🟢", "WARN": "🟡", "RED": "🔴"}


def main():
    quiet = "--quiet" in sys.argv
    results = []
    for name, fn in CHECKS:
        try:
            st, detail = fn()
        except Exception as e:
            st, detail = "RED", "проверка упала: %s" % str(e)[:60]
        results.append((name, st, detail))

    worst = "RED" if any(r[1] == "RED" for r in results) else (
        "WARN" if any(r[1] == "WARN" for r in results) else "OK")

    if not quiet:
        print("🧠 BRAIN HEALTH —", {"OK": "всё зелено", "WARN": "есть жёлтое", "RED": "ЕСТЬ КРАСНОЕ"}[worst])
        for name, st, detail in results:
            print("  %s %-22s %s" % (ICON[st], name, detail))

    rows = "\n".join(
        '<div class="row %s"><span class="ic">%s</span><span class="nm">%s</span>'
        '<span class="dt">%s</span></div>' % (st.lower(), ICON[st], name, detail)
        for name, st, detail in results)
    page = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>Brain Health</title><style>
:root{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial}
.wrap{max-width:760px;margin:0 auto;padding:28px 20px}
h1{font-size:22px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.row{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);
border-left-width:4px;border-radius:11px;padding:12px 15px;margin-bottom:9px}
.row.ok{border-left-color:#37d399}.row.warn{border-left-color:#ffb454}.row.red{border-left-color:#ff6b8b}
.ic{font-size:16px}.nm{font-weight:650;min-width:180px}.dt{color:var(--mut);font-size:13.5px}
.ts{color:var(--mut);font-size:12px;margin-top:14px}
</style></head><body><div class="wrap">
<h1>🧠 Здоровье мозга</h1>
<div class="sub">Один взгляд: жив ли поиск, свежий ли индекс, пишется ли память. Красное = чини.</div>
__ROWS__
<div class="ts">Обновлено: __TS__ · обнови: <code>python %IMPORTS%\\brain_health.py</code></div>
</div></body></html>"""
    try:
        DASH.parent.mkdir(parents=True, exist_ok=True)
        DASH.write_text(page.replace("__ROWS__", rows).replace(
            "__TS__", datetime.now().strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
        if not quiet:
            print("\nдашборд:", DASH)
    except Exception as e:
        if not quiet:
            print("dashboard write failed:", e)
    # exit code signals worst state (0 ok, 1 warn, 2 red) for scripted callers
    sys.exit({"OK": 0, "WARN": 1, "RED": 2}[worst])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write("brain_health error: %s\n" % e)
        sys.exit(0)
