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
r"""last30days.py — deterministic "what's NEW in the last N days on topic X" trend-watch.

WHY: before any strategic decision (the GAP phase of Anton's Alpha Protocol) we want a
tight, FRESH read of what moved on a topic — without re-scraping. Anton already has 8
nightly channel watchers whose per-slug DBs (%IMPORTS%\alpha\<slug>\<slug>.db)
accumulate every message forever. This 0-token engine just SLICES those DBs by
(date window x topic keywords), REUSES the proven mine_channel.score detector so scoring
never drifts, dedups near-duplicate posts, and emits ONE tight digest.

0 LLM tokens, 0 GPU, 0 network. Reads only the existing channel DBs + watchers.json.
Writes only the digest file. Re-scraping is NOT this engine's job (watch_run.py does that
nightly); pass --refresh to freshen first if you must.

The LLM synthesis (cluster into themes, dedup vs web, "what changed / what to watch") is
the /last30days SKILL's job (Sonnet) — kept OUT of here so this stays deterministic.

Run:
  set PYTHONIOENCODING=utf-8
  python last30days.py --topic "mcp, sub-agent, агент" [--days 30] [--top 25] [--json]
  python last30days.py --topic claude --days 14 --refresh   # nightly-fetch first, then slice
"""
import sys, re, json, sqlite3, datetime, argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(r"%IMPORTS%\watchers")
ALPHA = Path(r"%IMPORTS%\alpha")
CAND = ALPHA / "candidates"
REGISTRY = HERE / "watchers.json"
sys.path.insert(0, str(ALPHA))          # reuse the shared detector's scorer
import mine_channel                       # score()  (0-token signal ranker)


def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)


def slugify(topic):
    # keep unicode letters+digits (Anton's topics are often Cyrillic) so distinct
    # topics get distinct digest files — ASCII-only would collapse all RU → "topic".
    s = re.sub(r"[^\w]+", "-", topic.lower(), flags=re.UNICODE).strip("-_")[:40]
    return s or "topic"


def parse_terms(topic):
    """'mcp, sub-agent; агент' -> ['mcp','sub-agent','агент'] (lowered, deduped)."""
    raw = re.split(r"[,;]| или | or ", topic, flags=re.I)
    terms, seen = [], set()
    for t in raw:
        t = t.strip().lower()
        if t and t not in seen:
            seen.add(t)
            terms.append(t)
    return terms


def load_watchers():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [w for w in reg.get("watchers", []) if w.get("active")]


def slice_db(w, terms, since, until):
    """Return scored, topic-matching rows from one channel DB in the window."""
    slug = w["slug"]
    db = ALPHA / slug / f"{slug}.db"
    if not db.exists():
        return slug, None, []
    con = sqlite3.connect(db)
    like = " OR ".join(["lower(text) LIKE ?"] * len(terms))
    params = [f"%{t}%" for t in terms] + [since, until]
    try:
        rows = con.execute(
            f"SELECT id,date,day,text,views,forwards,reactions,file,urls FROM messages "
            f"WHERE ({like}) AND day>=? AND day<? AND length(text)>=60 ORDER BY date",
            params).fetchall()
    except sqlite3.OperationalError as e:
        con.close()
        return slug, f"db error: {e}", []
    con.close()
    out = []
    for r in rows:
        mid, date, day, text, views, fwd, rx, file, urls = r
        s, nl = mine_channel.score(text, views, fwd, rx, file, urls)
        low = (text or "").lower()
        hits = [t for t in terms if t in low]
        s += 3 * (len(hits) - 1)          # reward on-topic density (multi-term posts)
        out.append({"slug": slug, "label": w.get("username") or slug, "chan": w.get("username") or w["chat_id"],
                    "id": mid, "day": day, "text": text, "views": views or 0, "fwd": fwd or 0,
                    "rx": rx or 0, "file": file, "score": s, "hits": hits})
    return slug, None, out


def dedup(items):
    """Drop near-duplicate posts (same first 120 normalised chars). Keep higher score."""
    items.sort(key=lambda x: -x["score"])
    seen, keep = set(), []
    for it in items:
        k = re.sub(r"\s+", " ", (it["text"] or "").lower())[:120]
        if k in seen:
            continue
        seen.add(k)
        keep.append(it)
    return keep


def link_for(it):
    chan = str(it["chan"])
    if chan.startswith("@") or not chan.lstrip("-").isdigit():
        return f"https://t.me/{chan.lstrip('@')}/{it['id']}"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, help="comma/semicolon-separated terms, RU+EN")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--refresh", action="store_true", help="run watch_run.py first (network)")
    ap.add_argument("--json", action="store_true", help="also print machine-readable JSON")
    a = ap.parse_args()

    terms = parse_terms(a.topic)
    if not terms:
        sys.exit("empty --topic")
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=a.days)).isoformat()
    until = (today + datetime.timedelta(days=1)).isoformat()

    if a.refresh:
        import subprocess
        log("--refresh: nightly incremental fetch (watch_run.py) ...")
        subprocess.run([sys.executable, str(HERE / "watch_run.py")], check=False)

    watchers = load_watchers()
    all_items, per_chan = [], []
    for w in watchers:
        slug, err, items = slice_db(w, terms, since, until)
        per_chan.append((w.get("username") or slug, len(items), err))
        all_items.extend(items)

    kept = dedup(all_items)
    top = kept[:a.top]

    # ---- digest file (markdown mirror; the SKILL's LLM reads this to synthesise) ----
    tslug = slugify(a.topic)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# 🗓 Last {a.days} days — «{a.topic}»", "",
          f"_0-token slice of {len(watchers)} channel DBs · window {since}…{today.isoformat()} · "
          f"{len(all_items)} topic-matching posts → {len(kept)} after dedup → top {len(top)}. Собрано {now}._",
          f"_Terms: {', '.join(terms)}. Next: LLM (Sonnet) clusters into themes + «что нового / что изменилось / за чем следить»._",
          "", "## По каналам"]
    for label, n, err in sorted(per_chan, key=lambda x: -x[1]):
        md.append(f"- **{label}**: {n}" + (f"  ⚠️ {err}" if err else ""))
    md += ["", "## 🔥 Топ сигналов", ""]
    for i, it in enumerate(top, 1):
        link = link_for(it)
        md.append(f"### #{i} · {it['label']} ({it['day']} · {it['fwd']}fwd · {it['rx']}rx · "
                  f"{it['views']}v · score {int(it['score'])})")
        if link:
            md.append(f"- **Link:** {link}")
        if it["file"]:
            md.append(f"- **Guide:** {it['file']}")
        if it["hits"]:
            md.append(f"- **Matched:** {', '.join(it['hits'])}")
        body = re.sub(r"\s+", " ", it["text"] or "").strip()
        md.append(f"- **Text:** {body[:600]}")
        md.append("")

    CAND.mkdir(parents=True, exist_ok=True)
    out = CAND / f"_last30days-{tslug}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")

    log(f"topic «{a.topic}» · {a.days}d · {len(all_items)} matches → {len(kept)} dedup → top {len(top)}")
    log(f"digest -> {out}")
    if len(top) == 0:
        log("⚠️ 0 signals — broaden --topic terms, raise --days, or check DBs are fresh (watch_run).")

    if a.json:
        print(json.dumps({"topic": a.topic, "terms": terms, "days": a.days,
                          "window": [since, today.isoformat()], "matches": len(all_items),
                          "kept": len(kept), "digest": str(out),
                          "top": [{"label": it["label"], "day": it["day"], "score": int(it["score"]),
                                   "link": link_for(it), "file": it["file"],
                                   "text": re.sub(r"\s+", " ", it["text"] or "").strip()[:300]}
                                  for it in top]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
