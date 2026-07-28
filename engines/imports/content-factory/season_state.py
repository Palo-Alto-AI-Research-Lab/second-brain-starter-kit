#!/usr/bin/env python3
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
season_state.py — season-bible контент-фабрики v2 (S3 reality-show континьюити-слой).
Держит состояние СЕЗОНА, чтобы серии сцеплялись в сериал, а не были разрозненными постами:
открытые арки, висящие клиффхэнгеры, счётчик эпизодов, каст, сквозные мотивы.
Детерминированно, 0 токенов. Стор: season-state.json рядом с episode_adapter.py.
Нарративное СУЖДЕНИЕ (какой бит писать) делает скилл /reality-show (Opus), читая этот status.

Команды:
  status [--json]              обзор сезона (для /reality-show status и writer-Opus)
  arc-open   --id --title [--cliff TEXT]
  arc-escalate --id [--cliff TEXT]
  arc-resolve --id
  cliff-open --arc --text TEXT
  cliff-resolve --arc [--text TEXT]     (без --text снимает последний висящий)
  link --arc --episode SLUG             привязать эпизод к арке + episode_counter += 1
  recap --arc                           «ранее в сериале»: эпизоды арки + клиффхэнгеры
  cast-add --name TEXT | motif-add --text TEXT
"""
import argparse, json, os, sys

# cp1252-грабли: печатаем кириллицу в stdout как UTF-8 (root-fix, не обход)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "season-state.json")


def load():
    if not os.path.exists(STORE):
        print("ERR no season-state.json at %s" % STORE); sys.exit(2)
    with open(STORE, encoding="utf-8") as f:
        d = json.load(f)
    if "_FROZEN" in d:
        # Зомби-guard (инцидент 2026-07-25): стор заморожен 2026-07-10, истина = show-canon.
        # Любой вызов по нему = ложный пульс, поэтому громко падаем, а не рапортуем зелёное.
        print("⛔ DEPRECATED: season-state.json ЗАМОРОЖЕН — %s" % d["_FROZEN"])
        print("   Живой канон: %s" % os.path.join(
            os.environ.get("OBSIDIAN_VAULT", r"%VAULT%"), "04-Projects", "show-canon"))
        print("   Медосмотр: python %s check" % os.path.join(HERE, "show_canon_check.py"))
        sys.exit(3)
    return d


def save(d):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def find_arc(d, aid):
    for a in d["arcs"]:
        if a["id"] == aid:
            return a
    return None


def cmd_status(a):
    d = load()
    if a.json:
        print(json.dumps(d, ensure_ascii=False)); return
    s = d["season"]
    print("== СЕЗОН %s: %s ==" % (s["no"], s["title"]))
    print("   обещание: %s" % s.get("promise", ""))
    print("   эпизодов снято: %d  ·  начат: %s" % (d.get("episode_counter", 0), s.get("started", "?")))
    openarcs = [x for x in d["arcs"] if x["status"] == "open"]
    print("\n-- ОТКРЫТЫЕ АРКИ (%d) --" % len(openarcs))
    for x in openarcs:
        print("  • [%s] %s  (бит: %s, эпизодов: %d)" % (x["id"], x["title"], x.get("beat", "?"), len(x.get("episodes", []))))
        for c in x.get("open_cliffhangers", []):
            print("      ⤷ висит: %s" % c)
    closed = [x for x in d["arcs"] if x["status"] != "open"]
    if closed:
        print("\n-- закрытые арки: %s" % ", ".join(x["id"] for x in closed))
    print("\n-- КАСТ: %s" % " · ".join(d.get("cast", [])))
    print("-- МОТИВЫ: %s" % " · ".join('«%s»' % m for m in d.get("recurring_motifs", [])))


def cmd_arc_open(a):
    d = load()
    if find_arc(d, a.id):
        print("ERR arc exists: %s" % a.id); sys.exit(2)
    arc = {"id": a.id, "title": a.title, "status": "open", "beat": "open",
           "episodes": [], "open_cliffhangers": ([a.cliff] if a.cliff else [])}
    d["arcs"].append(arc); save(d)
    print("открыта арка [%s] %s" % (a.id, a.title))


def cmd_arc_escalate(a):
    d = load(); arc = find_arc(d, a.id)
    if not arc: print("ERR no arc: %s" % a.id); sys.exit(2)
    arc["beat"] = "escalate"
    if a.cliff: arc.setdefault("open_cliffhangers", []).append(a.cliff)
    save(d); print("арка [%s] → escalate%s" % (a.id, " (+клиффхэнгер)" if a.cliff else ""))


def cmd_arc_resolve(a):
    d = load(); arc = find_arc(d, a.id)
    if not arc: print("ERR no arc: %s" % a.id); sys.exit(2)
    arc["status"] = "resolved"; arc["beat"] = "resolve"; arc["open_cliffhangers"] = []
    save(d); print("арка [%s] ЗАКРЫТА" % a.id)


def cmd_cliff_open(a):
    d = load(); arc = find_arc(d, a.arc)
    if not arc: print("ERR no arc: %s" % a.arc); sys.exit(2)
    arc.setdefault("open_cliffhangers", []).append(a.text)
    save(d); print("клиффхэнгер открыт в [%s]: %s" % (a.arc, a.text))


def cmd_cliff_resolve(a):
    d = load(); arc = find_arc(d, a.arc)
    if not arc: print("ERR no arc: %s" % a.arc); sys.exit(2)
    cl = arc.get("open_cliffhangers", [])
    if not cl: print("(в [%s] нет висящих клиффхэнгеров)" % a.arc); return
    if a.text and a.text in cl:
        cl.remove(a.text); removed = a.text
    else:
        removed = cl.pop()  # последний
    save(d); print("клиффхэнгер снят в [%s]: %s" % (a.arc, removed))


def cmd_link(a):
    d = load(); arc = find_arc(d, a.arc)
    if not arc: print("ERR no arc: %s" % a.arc); sys.exit(2)
    eps = arc.setdefault("episodes", [])
    if a.episode in eps:
        print("(эпизод %s уже привязан к [%s])" % (a.episode, a.arc)); return
    eps.append(a.episode)
    d["episode_counter"] = d.get("episode_counter", 0) + 1
    save(d)
    print("эпизод %s → арка [%s]  ·  всего снято: %d" % (a.episode, a.arc, d["episode_counter"]))


def cmd_recap(a):
    d = load(); arc = find_arc(d, a.arc)
    if not arc: print("ERR no arc: %s" % a.arc); sys.exit(2)
    print("== РАНЕЕ В СЕРИАЛЕ — [%s] %s ==" % (arc["id"], arc["title"]))
    print("   статус: %s · бит: %s" % (arc["status"], arc.get("beat", "?")))
    eps = arc.get("episodes", [])
    print("   эпизоды (%d): %s" % (len(eps), ", ".join(eps) if eps else "(пока нет)"))
    cl = arc.get("open_cliffhangers", [])
    if cl:
        print("   висит: %s" % " · ".join(cl))


def cmd_check(a):
    # 4 недельные проверки здоровья сериала (DR-2026-07-01). Детерминированные сигналы;
    # континьюити/доверие судит Opus в /reality-show, читая эти числа.
    d = load()
    s = d["season"]
    openarcs = [x for x in d["arcs"] if x["status"] == "open"]
    total_eps = d.get("episode_counter", 0)
    open_loops = sum(len(x.get("open_cliffhangers", [])) for x in openarcs)
    arcs_with_eps = [x for x in openarcs if x.get("episodes")]
    stalled = [x for x in openarcs if x.get("open_cliffhangers") and not x.get("episodes")]
    congested = [x for x in openarcs if len(x.get("open_cliffhangers", [])) > 2]

    print("== ПРОВЕРКА ЗДОРОВЬЯ СЕРИАЛА (DR: 4 оси) ==")
    # Q1 Континьюити
    q1 = "OK" if s.get("question") and total_eps >= 3 else "FLAG"
    print("1) КОНТИНЬЮИТИ [%s]: вопрос сезона %s · эпизодов снято %d (нужно ≥3 для узнавания)" % (
        q1, "задан" if s.get("question") else "НЕ ЗАДАН", total_eps))
    if not s.get("question"):
        print("     ⚠ задай season.question — иначе новичок не поймёт, о чём сезон")
    # Q2 Изменение состояния
    ratio = "%d/%d арок с эпизодами" % (len(arcs_with_eps), len(openarcs)) if openarcs else "нет открытых арок"
    q2 = "OK" if openarcs and len(arcs_with_eps) >= max(1, len(openarcs) // 2) else "FLAG"
    print("2) ИЗМЕНЕНИЕ СОСТОЯНИЯ [%s]: %s" % (q2, ratio))
    if stalled:
        print("     ⚠ петля открыта, но арка не двигалась: %s" % ", ".join(x["id"] for x in stalled))
    # Q3 Здоровье петель
    q3 = "FLAG" if open_loops > 4 or congested else "OK"
    print("3) ЗДОРОВЬЕ ПЕТЕЛЬ [%s]: открытых клиффхэнгеров %d (порог >4 = затор)" % (q3, open_loops))
    if congested:
        print("     ⚠ перегруз (>2 в одной арке): %s — закрой часть, не копи" % ", ".join(x["id"] for x in congested))
    # Q4 Доверие — не измеримо детерминированно
    print("4) ДОВЕРИЕ [manual]: показал ли достаточно улик (лог/скрин/дифф/«было→стало»)? — судит Opus/Антон")
    print("\nИтог флагов: " + " ".join(t for t in [
        "Q1-FLAG" if q1 == "FLAG" else "", "Q2-FLAG" if q2 == "FLAG" else "",
        "Q3-FLAG" if q3 == "FLAG" else ""] if t) or "все детерминированные оси OK")


def cmd_cast_add(a):
    d = load(); d.setdefault("cast", []).append(a.name); save(d)
    print("+ каст: %s" % a.name)


def cmd_motif_add(a):
    d = load(); d.setdefault("recurring_motifs", []).append(a.text); save(d)
    print("+ мотив: %s" % a.text)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("status"); q.add_argument("--json", action="store_true"); q.set_defaults(fn=cmd_status)
    q = sub.add_parser("arc-open"); q.add_argument("--id", required=True); q.add_argument("--title", required=True); q.add_argument("--cliff"); q.set_defaults(fn=cmd_arc_open)
    q = sub.add_parser("arc-escalate"); q.add_argument("--id", required=True); q.add_argument("--cliff"); q.set_defaults(fn=cmd_arc_escalate)
    q = sub.add_parser("arc-resolve"); q.add_argument("--id", required=True); q.set_defaults(fn=cmd_arc_resolve)
    q = sub.add_parser("cliff-open"); q.add_argument("--arc", required=True); q.add_argument("--text", required=True); q.set_defaults(fn=cmd_cliff_open)
    q = sub.add_parser("cliff-resolve"); q.add_argument("--arc", required=True); q.add_argument("--text"); q.set_defaults(fn=cmd_cliff_resolve)
    q = sub.add_parser("link"); q.add_argument("--arc", required=True); q.add_argument("--episode", required=True); q.set_defaults(fn=cmd_link)
    q = sub.add_parser("recap"); q.add_argument("--arc", required=True); q.set_defaults(fn=cmd_recap)
    q = sub.add_parser("check"); q.set_defaults(fn=cmd_check)
    q = sub.add_parser("cast-add"); q.add_argument("--name", required=True); q.set_defaults(fn=cmd_cast_add)
    q = sub.add_parser("motif-add"); q.add_argument("--text", required=True); q.set_defaults(fn=cmd_motif_add)

    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
