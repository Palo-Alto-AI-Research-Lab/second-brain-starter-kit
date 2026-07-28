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
r"""alpha_tune.py — the active-learning closer of the alpha-extraction loop.

The review screen captures Anton's gold/miss verdicts on judge KEEPERS. This tool turns
that signal into CONCRETE per-miner detector adjustments — the mechanism the Decision Memo
`decision-alpha-engine-grow-by-corpora-not-miners` calls for. It NEVER edits a detector
itself; it READS the labels and PRINTS evidence-grounded recommendations for Anton to apply.

Three moves (grounded in retrieval-AL technique — hard-neg mining / positive-aware thresholds
/ uncertainty sampling):
  1. PRECISION per miner = gold / (gold+miss)  — where is the judge weak?
  2. HARD-NEGATIVE mining: from the MISS keepers, surface what they share (judge_verdict
     skew, common tokens) that gold keepers do NOT → a candidate negative filter / cutoff.
  3. UNCERTAINTY sampling: list the highest-value STILL-UNLABELED items to review next
     (PARTIAL verdicts first — that's where a label moves precision the most).

  set PYTHONIOENCODING=utf-8
  python alpha_tune.py                # all miners
  python alpha_tune.py --miner lobster
  python alpha_tune.py --min 8        # min labels per miner before tuning (default 8)

0 LLM tokens. Reads only alpha_review.db. Needs ~8-20 labels/miner to fire (it says so).
"""
import sqlite3, re, sys, os
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "alpha_review.db")
STOP = set("the a an of to in on for and or is are be it this that with как что для это и в на "
           "по не из за судья ok alpha watch при про над под нов лет the для".split())


def tokens(s):
    return [w for w in re.findall(r"[a-zа-яё0-9]{4,}", (s or "").lower()) if w not in STOP]


def load(miner=None):
    con = sqlite3.connect(DB)
    q = """SELECT i.miner, i.item_hash, i.title, i.judge_verdict, v.anton_verdict
           FROM items i LEFT JOIN verdicts v ON v.item_hash=i.item_hash"""
    rows = con.execute(q).fetchall()
    con.close()
    by = {}
    for m, h, title, jv, av in rows:
        if miner and m != miner:
            continue
        by.setdefault(m, []).append({"hash": h, "title": title, "judge": jv,
                                     "anton": av or ""})
    return by


def tune(min_labels=8, miner=None):
    by = load(miner)
    if not by:
        print("no items. run alpha_harvest first."); return
    print(f"active-learning tuning (min {min_labels} labels/miner)\n" + "=" * 56)
    for m in sorted(by):
        items = by[m]
        gold = [x for x in items if x["anton"] == "gold"]
        miss = [x for x in items if x["anton"] == "miss"]
        unl = [x for x in items if x["anton"] not in ("gold", "miss")]
        labeled = len(gold) + len(miss)
        print(f"\n### {m}  ({len(items)} surfaced · {labeled} labeled · {len(unl)} unlabeled)")
        if labeled == 0:
            # uncertainty sampling: what to label first (PARTIAL = most informative)
            nxt = [x for x in unl if x["judge"] == "partial"][:3] or unl[:3]
            print("  no labels yet → label these first (uncertainty sampling, PARTIAL first):")
            for x in nxt:
                print(f"    · [{x['judge']}] {x['title'][:70]}")
            continue
        prec = round(len(gold) / labeled, 2) if labeled else None
        verdict = "OK" if (prec or 0) >= 0.6 else "WEAK — tune"
        print(f"  precision@labeled = {prec}  ({len(gold)}✅ / {len(miss)}❌)  → {verdict}")
        if labeled < min_labels:
            print(f"  ⏳ need {min_labels - labeled} more labels before a confident threshold change.")
        # hard-negative mining: tokens over-represented in MISS vs GOLD
        if miss:
            gt = Counter(t for x in gold for t in set(tokens(x["title"])))
            mt = Counter(t for x in miss for t in set(tokens(x["title"])))
            hard = [(t, c) for t, c in mt.most_common()
                    if c >= 2 and gt.get(t, 0) == 0]
            jv_miss = Counter(x["judge"] for x in miss)
            if jv_miss.get("partial", 0) >= max(2, len(miss) * 0.6):
                print(f"  💡 hard-neg: {jv_miss['partial']}/{len(miss)} misses are PARTIAL "
                      f"→ consider dropping PARTIAL from `{m}` (keep only ✅ OK).")
            if hard:
                print("  💡 hard-neg tokens (in misses, never in gold) → candidate negative filter:")
                print("     " + ", ".join(f"{t}×{c}" for t, c in hard[:8]))
            if not hard and jv_miss.get("partial", 0) < 2:
                print("  (misses don't share an obvious pattern — review them individually.)")
    print("\n" + "=" * 56)
    print("Apply: edit the miner's *_scan.py (raise cutoff / add negative token) OR drop PARTIAL"
          " at the judge. Re-harvest → re-label → re-run to confirm precision moved.")


if __name__ == "__main__":
    a = sys.argv
    mn = int(a[a.index("--min") + 1]) if "--min" in a else 8
    miner = a[a.index("--miner") + 1] if "--miner" in a else None
    tune(mn, miner)
