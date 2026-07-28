"""wow_priority.py — priority lane ledger for /wow milestone episodes.

add  --slug S --title T   : mark episode bundle meta.json priority=milestone + append to priority.json
mark --slug S --status X  : update status in priority.json (drafted|approved|posted|skip)
list [--today]            : print queue (ASCII-safe)
"""
import argparse, json, sys, io, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CF = Path(r"%IMPORTS%\content-factory")
QUEUE = CF / "priority.json"
EPISODES = CF / "episodes"


def load_queue():
    if QUEUE.exists():
        return json.loads(QUEUE.read_text(encoding="utf-8"))
    return []


def save_queue(q):
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_add(a):
    meta_path = EPISODES / a.slug / "meta.json"
    if not meta_path.exists():
        print(f"FAIL: no bundle meta at {meta_path} (run episode_adapter.py new first)")
        return 2
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["priority"] = "milestone"
    meta["wow_date"] = a.date
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    q = load_queue()
    if any(e["slug"] == a.slug for e in q):
        print(f"OK (already queued): {a.slug}")
        return 0
    q.append({"slug": a.slug, "title": a.title, "date": a.date, "status": "drafted"})
    save_queue(q)
    print(f"OK: {a.slug} -> priority=milestone, queued ({len(q)} in queue)")
    return 0


def cmd_mark(a):
    q = load_queue()
    hits = [e for e in q if e["slug"] == a.slug]
    if not hits:
        print(f"FAIL: {a.slug} not in queue")
        return 2
    for e in hits:
        e["status"] = a.status
    save_queue(q)
    print(f"OK: {a.slug} -> {a.status}")
    return 0


def cmd_list(a):
    q = load_queue()
    if a.today:
        q = [e for e in q if e["date"] == datetime.date.today().isoformat()]
    if not q:
        print("queue empty")
        return 0
    for e in q:
        print(f"{e['date']}  {e['status']:9}  {e['slug']}  {e['title']}")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("add")
    pa.add_argument("--slug", required=True)
    pa.add_argument("--title", required=True)
    pa.add_argument("--date", default=datetime.date.today().isoformat())
    pm = sub.add_parser("mark")
    pm.add_argument("--slug", required=True)
    pm.add_argument("--status", required=True, choices=["drafted", "approved", "posted", "skip"])
    pl = sub.add_parser("list")
    pl.add_argument("--today", action="store_true")
    a = p.parse_args()
    return {"add": cmd_add, "mark": cmd_mark, "list": cmd_list}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
