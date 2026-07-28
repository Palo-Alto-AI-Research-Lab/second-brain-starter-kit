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
show_canon_check.py — недельный медосмотр сериала по ЖИВОМУ канону show-canon.
Заменил season_state.py check (тот мерял замороженный season-state.json — зомби-сторож,
инцидент 2026-07-25). Истина = %VAULT%\\04-Projects\\show-canon\\
(decision-single-canon-story-state, DR26-07-08-HUB-01). Read-only, 0 токенов, stdlib-only.

Команды:
  check    4 оси здоровья (DR «Authentic Narrative Engineering»):
           Q1 континьюити · Q2 изменение состояния · Q3 здоровье петель · Q4 доверие [manual]
           + табло-дрифт (season-01 vs реальные loop-файлы) + затор beats-inbox
  status   краткий дайджест сезона (вопрос, арки, открытые петли) — контекст для LLM-вердикта

Exit-коды (карта исключений, §5.2): 0 = отработал, все детерминированные оси OK ·
1 = отработал, есть FLAG (это ДИАГНОЗ, не сбой) · 2 = НЕ СМОГ померить (нет канона/парс).
"""
import os, re, sys, glob, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")  # cp1252-грабли Windows-консоли
except Exception:
    pass

VAULT = os.environ.get("OBSIDIAN_VAULT", r"%VAULT%")
CANON = os.path.join(VAULT, "04-Projects", "show-canon")

LOOPS_OVERLOAD_TOTAL = 4    # >4 открытых петель всего = затор
LOOPS_OVERLOAD_PER_ARC = 2  # >2 петель на одну арку = перегруз
BEATS_MIN_CONTINUITY = 3    # <3 битов happened = новичок сериал не узнает
INBOX_BACKLOG_FLAG = 10     # >10 неразобранных бит-кандидатов = сенсор копит, писатель молчит


def die(msg):
    print("ERR %s" % msg)
    sys.exit(2)


def read_frontmatter(path):
    """Толерантный YAML-lite: скаляры + inline-списки [..] + блочные '- item'. Без PyYAML."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^\s*-\s+", line) and key:  # блочный список под последним ключом
            if not isinstance(fm.get(key), list):
                fm[key] = [] if fm.get(key) in ("", None) else [fm[key]]
            fm[key].append(_unquote(line.split("-", 1)[1].strip()))
            continue
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).split("  #")[0].strip()
        if val.startswith("["):
            fm[key] = _parse_inline_list(val)
        else:
            fm[key] = _unquote(val)
    return fm


def _unquote(s):
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\\\', '\\').replace('\\"', '"')
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _parse_inline_list(val):
    """[..] → список. Кавычки уважаем (запятая внутри — не разделитель); wiki-скобки чистим по-элементно."""
    inner = val.strip()
    if inner.startswith("["):
        inner = inner[1:]
    if inner.endswith("]"):
        inner = inner[:-1]  # лишняя скобка у wiki-линка безвредна: чистка по-элементно ниже
    inner = inner.strip()
    if not inner:
        return []
    items, buf, quote = [], "", None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < len(inner):
                buf += ch + inner[i + 1]; i += 2; continue
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch; buf += ch
        elif ch == ",":
            items.append(buf.strip()); buf = ""
        else:
            buf += ch
        i += 1
    if buf.strip():
        items.append(buf.strip())
    out = []
    for x in items:
        if not x:
            continue
        m = re.findall(r"\[\[([^\]]+)\]\]", x)
        out.append(m[0] if m else _unquote(x))
    return out


def load_canon():
    if not os.path.isdir(CANON):
        die("канон не найден: %s (OBSIDIAN_VAULT=%s)" % (CANON, os.environ.get("OBSIDIAN_VAULT", "<unset>")))
    season_path = os.path.join(CANON, "season-01.md")
    if not os.path.exists(season_path):
        die("нет season-01.md в %s" % CANON)
    season = read_frontmatter(season_path)
    arcs, loops, beats = {}, {}, []
    for p in glob.glob(os.path.join(CANON, "arcs", "arc-*.md")):
        fm = read_frontmatter(p)
        if fm.get("arc_id"):
            arcs[fm["arc_id"]] = fm
    for p in glob.glob(os.path.join(CANON, "loops", "loop-*.md")):
        fm = read_frontmatter(p)
        if fm.get("loop_id"):
            loops[fm["loop_id"]] = fm
    for p in glob.glob(os.path.join(CANON, "beats", "beat-*.md")):
        fm = read_frontmatter(p)
        if fm:
            beats.append(fm)
    inbox = [p for p in glob.glob(os.path.join(CANON, "beats-inbox", "beat-*.md"))]
    return season, arcs, loops, beats, inbox


def cmd_status():
    season, arcs, loops, beats, inbox = load_canon()
    active_arcs = {k: v for k, v in arcs.items() if v.get("status") == "active"}
    open_loops = {k: v for k, v in loops.items() if v.get("status") == "open"}
    happened = [b for b in beats if b.get("world_status") in ("happened", "corrected")]
    print("== КАНОН: %s ==" % season.get("title", "?"))
    print("   вопрос сезона: %s" % season.get("season_question", "НЕ ЗАДАН"))
    print("   story_day: %s · битов happened: %d (+%d в inbox)" % (
        season.get("current_story_day", "?"), len(happened), len(inbox)))
    print("\n-- АКТИВНЫЕ АРКИ (%d) --" % len(active_arcs))
    for aid, a in sorted(active_arcs.items()):
        print("  • [%s] %s (битов: %d)" % (aid, a.get("title", aid), len(a.get("beats", []))))
        if a.get("current_state"):
            print("      сейчас: %s" % a["current_state"])
    print("\n-- ОТКРЫТЫЕ ПЕТЛИ (%d) --" % len(open_loops))
    for lid, l in sorted(open_loops.items()):
        print("  ⤷ [%s] %s" % (lid, l.get("question", "?")))


def cmd_check():
    season, arcs, loops, beats, inbox = load_canon()
    active_arcs = {k: v for k, v in arcs.items() if v.get("status") == "active"}
    open_loops = {k: v for k, v in loops.items() if v.get("status") == "open"}
    happened = [b for b in beats if b.get("world_status") in ("happened", "corrected")]
    flags = []

    print("== ПРОВЕРКА ЗДОРОВЬЯ СЕРИАЛА по show-canon (DR: 4 оси) ==")
    print("   стор: %s" % CANON)

    # Q1 Континьюити: вопрос сезона задан + >=3 бита happened
    q1 = "OK" if season.get("season_question") and len(happened) >= BEATS_MIN_CONTINUITY else "FLAG"
    if q1 == "FLAG":
        flags.append("Q1")
    print("1) КОНТИНЬЮИТИ [%s]: вопрос сезона %s · битов happened %d (нужно ≥%d)" % (
        q1, "задан" if season.get("season_question") else "НЕ ЗАДАН", len(happened), BEATS_MIN_CONTINUITY))

    # Q2 Изменение состояния: доля активных арок с битами; стоячие арки с открытой петлёй
    arcs_with_beats = [k for k, v in active_arcs.items() if v.get("beats")]
    q2 = "OK" if active_arcs and len(arcs_with_beats) >= max(1, len(active_arcs) // 2) else "FLAG"
    if q2 == "FLAG":
        flags.append("Q2")
    print("2) ИЗМЕНЕНИЕ СОСТОЯНИЯ [%s]: %d/%d активных арок с битами" % (
        q2, len(arcs_with_beats), len(active_arcs)))
    loops_per_arc = {}
    for lid, l in open_loops.items():
        for arc in l.get("related_arcs", []):
            loops_per_arc.setdefault(arc, []).append(lid)
    stalled = [a for a in loops_per_arc if a in active_arcs and not active_arcs[a].get("beats")]
    if stalled:
        print("     ⚠ петля открыта, а арка без битов (стоит): %s" % ", ".join(sorted(stalled)))

    # Q3 Здоровье петель: всего открытых и перегруз на арку
    congested = {a: ls for a, ls in loops_per_arc.items() if len(ls) > LOOPS_OVERLOAD_PER_ARC}
    q3 = "FLAG" if len(open_loops) > LOOPS_OVERLOAD_TOTAL or congested else "OK"
    if q3 == "FLAG":
        flags.append("Q3")
    print("3) ЗДОРОВЬЕ ПЕТЕЛЬ [%s]: открытых %d (порог >%d = затор)" % (
        q3, len(open_loops), LOOPS_OVERLOAD_TOTAL))
    for a, ls in sorted(congested.items()):
        print("     ⚠ перегруз арки %s: %d петель (%s) — закрой часть" % (a, len(ls), ", ".join(ls)))

    # Q4 Доверие: manual, но считаем долю свежих битов с уликами (подсказка судье)
    today = datetime.date.today()
    recent = [b for b in happened if _recent(b.get("occurred_on", ""), today, 14)]
    with_ev = [b for b in recent if b.get("evidence_refs") and b["evidence_refs"] != []]
    hint = "%d/%d свежих битов (14д) с evidence_refs" % (len(with_ev), len(recent)) if recent else "свежих битов нет"
    print("4) ДОВЕРИЕ [manual]: судит Антон/Opus по receipts · подсказка: %s" % hint)

    # Слой видимости: табло season-01 не должно врать (сторож табло, §5.5)
    for label, board_list, real_set in (
            ("open_loops", season.get("open_loops", []), set(open_loops.keys())),
            ("active_arcs", season.get("active_arcs", []), set(active_arcs.keys()))):
        board = set(board_list)
        if board != real_set:
            extra, missing = board - real_set, real_set - board
            parts = []
            if extra:
                parts.append("на табло, но НЕ в этом статусе: %s" % ", ".join(sorted(extra)))
            if missing:
                parts.append("в файлах, но НЕ на табло: %s" % ", ".join(sorted(missing)))
            print("⚠ ТАБЛО-ДРИФТ season-01.%s: %s" % (label, " · ".join(parts)))
            if "DRIFT" not in flags:
                flags.append("DRIFT")

    # Затор сенсора: beats-inbox копится, писатель канона не разбирает
    inbox_mark = "FLAG" if len(inbox) > INBOX_BACKLOG_FLAG else "OK"
    if inbox_mark == "FLAG":
        flags.append("INBOX")
    print("5) BEATS-INBOX [%s]: %d неразобранных кандидатов (порог >%d)" % (
        inbox_mark, len(inbox), INBOX_BACKLOG_FLAG))

    print("\nИтог: %s" % (" ".join("%s-FLAG" % f for f in flags) if flags else "все детерминированные оси OK"))
    sys.exit(1 if flags else 0)


def _recent(datestr, today, days):
    try:
        d = datetime.date.fromisoformat(str(datestr)[:10])
        return (today - d).days <= days
    except Exception:
        return False


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        cmd_check()
    elif cmd == "status":
        cmd_status()
    else:
        die("неизвестная команда %r (жду: check | status)" % cmd)


if __name__ == "__main__":
    main()
