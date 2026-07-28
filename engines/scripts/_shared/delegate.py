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
r"""delegate.py -- 0-token engine for the "04 TASKS" human-delegation lane (Anton 2026-07-14).

THE GAP: Anton says "this task is really Nina's" -> she needs ONE place where delegated
tasks arrive, plus a ready SEED so her Claude session starts instantly. A full seed is too
long for chat, so the chat carries a short CODE PHRASE ("задача НАТ-1") and the seed itself
lives as a synced vault file this script resolves.

DIVISION OF LABOUR (AK-47 / skill-design-three-layer):
  * THIS script  = deterministic brain: ids, seed files, registry, statuses. NO network, NO LLM.
  * The /task SKILL = unpacks a code phrase on the assignee's machine (get -> ack -> work -> done)
    and posts the human-readable delegation line to the 04 TASKS Telegram chat.
  * Rail: seed files sync via Syncthing (vault share); the 04 chat is the human-visible feed.

Files:
  seeds    : <VAULT>\10-Tasks\_seeds\<ID>.md     (frontmatter + seed body; synced everywhere)
  registry : <VAULT>\10-Tasks\_seeds\_registry.json  (counters + status; single JSON, AK-47)

IDs are speakable code phrases: NAT-1, RUSL-2, ANT-3 (per-person counters, case-insensitive).

Usage:
  python delegate.py new --to nat --title "..." [--from anton] [--seed-file f | --seed "text" | stdin]
  python delegate.py get <id>              # print the full seed (the "unpack" step)
  python delegate.py list [--for nat|rusl|ant] [--all]
  python delegate.py ack <id> [--by "HP17-Nina"]
  python delegate.py done <id> [--note "..."]
  python delegate.py status

Exit: 0 ok | 2 bad input | 3 not found
"""
import os, sys, json, argparse, datetime, re

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VAULT = os.environ.get("DELEGATE_VAULT", r"%VAULT%")
SEEDS = os.path.join(VAULT, "10-Tasks", "_seeds")
REG = os.path.join(SEEDS, "_registry.json")

PEOPLE = {  # slug -> (id prefix, display name, tg @username for pings — ALWAYS mention, else the message sinks)
    "nat": ("NAT", "Нина", "@teammate_n"),
    "rusl": ("RUSL", "Рита", "@teammate_r"),
    "ant": ("ANT", "Антон", "@personal_acct"),
}


def _now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _load_reg():
    if not os.path.exists(REG):
        return {"counters": {}, "tasks": {}}
    try:
        with open(REG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"counters": {}, "tasks": {}}


def _save_reg(reg):
    os.makedirs(SEEDS, exist_ok=True)
    with open(REG, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _norm_id(s):
    """NAT-1 / нат-1 / nat1 -> NAT-1; RU letters НАТ/РУСЛ/АНТ accepted."""
    s = (s or "").strip().upper().replace("_", "-")
    ru = {"НАТ": "NAT", "РУСЛ": "RUSL", "АНТ": "ANT"}
    m = re.match(r"^([A-ZА-Я]+)[-\s]?(\d+)$", s)
    if not m:
        return None
    pref = ru.get(m.group(1), m.group(1))
    return "%s-%s" % (pref, int(m.group(2)))


def cmd_new(a):
    to = a.to.lower()
    if to not in PEOPLE:
        print("ERR unknown --to '%s' (nat|rusl|ant)" % a.to); sys.exit(2)
    pref, disp, mention = PEOPLE[to]
    if a.seed_file:
        body = open(a.seed_file, "r", encoding="utf-8").read()
    elif a.seed is not None:
        body = a.seed
    else:
        body = sys.stdin.read()
    if not body.strip():
        print("ERR empty seed (use --seed / --seed-file / stdin)"); sys.exit(2)
    reg = _load_reg()
    n = int(reg["counters"].get(pref, 0)) + 1
    reg["counters"][pref] = n
    tid = "%s-%d" % (pref, n)
    path = os.path.join(SEEDS, tid + ".md")
    fm = ("---\n"
          "id: %s\nto: %s\nfrom: %s\ntitle: \"%s\"\nstatus: open\ncreated: %s\n"
          "---\n\n" % (tid, disp, a.frm, a.title.replace('"', "'"), _now()))
    os.makedirs(SEEDS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n")
    reg["tasks"][tid] = {"to": to, "title": a.title, "status": "open",
                         "created": _now(), "file": path}
    _save_reg(reg)
    print(tid)
    print("seed: %s" % path)
    print("--- TG message for 04 TASKS ---")
    print("📌 %s %s · %s · от %s\nКодовая фраза для твоего Клода: «задача %s»"
          % (disp.upper(), mention, a.title, a.frm, tid))


def _find(reg, raw):
    tid = _norm_id(raw)
    if not tid or tid not in reg["tasks"]:
        print("ERR task not found: %s (list: delegate.py list --all)" % raw); sys.exit(3)
    return tid


def cmd_get(a):
    reg = _load_reg(); tid = _find(reg, a.id)
    path = reg["tasks"][tid].get("file", os.path.join(SEEDS, tid + ".md"))
    if not os.path.exists(path):
        # file may still be syncing to this machine -- say so, do not pretend "no task"
        print("ERR seed file not here yet (Syncthing lag?): %s" % path); sys.exit(3)
    print(open(path, "r", encoding="utf-8").read())


def cmd_list(a):
    reg = _load_reg()
    rows = []
    for tid, t in sorted(reg["tasks"].items()):
        if not a.all and t["status"] not in ("open", "ack"):
            continue
        if a.fr and t["to"] != a.fr.lower():
            continue
        rows.append("%-8s %-5s %-8s %s" % (tid, t["to"], t["status"], t["title"]))
    print("\n".join(rows) if rows else "(no matching tasks)")


def _set_status(a, st, extra=None):
    reg = _load_reg(); tid = _find(reg, a.id)
    t = reg["tasks"][tid]; t["status"] = st; t[st + "_at"] = _now()
    if extra:
        t.update(extra)
    _save_reg(reg)
    # mirror into the seed file frontmatter (grep-able truth on every machine)
    path = t.get("file", os.path.join(SEEDS, tid + ".md"))
    if os.path.exists(path):
        txt = open(path, "r", encoding="utf-8").read()
        txt = re.sub(r"(?m)^status: .*$", "status: " + st, txt, count=1)
        open(path, "w", encoding="utf-8").write(txt)
    print("%s -> %s" % (tid, st))


def cmd_ack(a):
    _set_status(a, "ack", {"ack_by": a.by} if a.by else None)


def cmd_done(a):
    _set_status(a, "done", {"done_note": a.note} if a.note else None)


def cmd_status(_):
    reg = _load_reg()
    c = {}
    for t in reg["tasks"].values():
        c[t["status"]] = c.get(t["status"], 0) + 1
    print("delegate status: %d tasks | %s" % (len(reg["tasks"]),
          " ".join("%s=%d" % kv for kv in sorted(c.items())) or "none"))
    print("seeds dir: %s" % SEEDS)


def main():
    ap = argparse.ArgumentParser(prog="delegate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("--to", required=True)
    p.add_argument("--title", required=True); p.add_argument("--from", dest="frm", default="Антона")
    p.add_argument("--seed", default=None); p.add_argument("--seed-file", default=None)
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("get"); p.add_argument("id"); p.set_defaults(fn=cmd_get)
    p = sub.add_parser("list"); p.add_argument("--for", dest="fr", default=None)
    p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("ack"); p.add_argument("id"); p.add_argument("--by", default=None); p.set_defaults(fn=cmd_ack)
    p = sub.add_parser("done"); p.add_argument("id"); p.add_argument("--note", default=None); p.set_defaults(fn=cmd_done)
    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
