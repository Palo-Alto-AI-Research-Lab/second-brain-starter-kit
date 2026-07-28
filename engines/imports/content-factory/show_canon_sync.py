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
show_canon_sync.py — ПИСАТЕЛЬ ТАБЛО канона (пара к read-only сторожу show_canon_check.py).

КОРЕНЬ, который лечит (2026-07-27): «какая арка активна» жило в ДВУХ местах —
`status:` в arcs/*.md (истина) и рукописный список `season-01.active_arcs` (копия).
Копия неизбежно отстаёт → ТАБЛО-ДРИФТ (инцидент 27.07: arc-job-hunt-in-public был
в файлах 16 дней, но не на табло). Фикс класса: табло = ПРОИЗВОДНОЕ, пересобирается
из файлов, руками не правится. Сторож show_canon_check.py остаётся — он ловит,
если этот sync перестал запускаться (§5.5: сторож не живёт в том, что сторожит).

Команды:
  board            показать до→после (НИЧЕГО не пишет, дефолт — Антон видит diff первым)
  board --apply    пересобрать season-01.active_arcs / open_loops из реальных файлов
  arcs             напечатать валидный словарь arc_id + title (контракт для сенсоров:
                   content-miner берёт related_arcs ОТСЮДА, не выдумывает свободный тег)
  loops            то же для открытых петель

Exit-коды (§5.2): 0 = отработал (для board без --apply: 0 = табло совпадает,
1 = есть расхождение = нужен --apply) · 2 = НЕ СМОГ (нет канона/парс/запись).
Read-only кроме `board --apply`. stdlib-only, 0 токенов.
"""
import os, re, sys, glob, shutil, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")  # cp1252-грабли Windows-консоли
except Exception:
    pass

VAULT = os.environ.get("OBSIDIAN_VAULT", r"%VAULT%")
CANON = os.path.join(VAULT, "04-Projects", "show-canon")
SEASON = os.path.join(CANON, "season-01.md")

# Поля табло: имя в season-01 -> (папка, префикс, ключ id, значение status, которое считаем «на табло»)
BOARD_FIELDS = {
    "active_arcs":  ("arcs",  "arc-",  "arc_id",  "active"),
    "open_loops":   ("loops", "loop-", "loop_id", "open"),
}


# Один писатель канона (урок sync-conflict root-fix 26-27.07: гейт живёт В КОДЕ, а не в
# расписании — выключенная на пире задача возвращается переустановкой/восстановлением).
# ⛔ НАМЕРЕННО НЕ вносим season-01.md в _imports/sync/derived_writers.json: любой ключ оттуда
# conflict_sweeper считает "SAFE regenerable" и выбрасывает его конфликты БЕЗ мержа, а тело
# season-01.md рукописное (производны только два поля) — потеряли бы правки Антона.
CANON_WRITER_NODE = "HUB1"  # хаб = канон-коммиттер (CLAUDE.md §7.9)


def may_write(argv):
    if "--force" in argv:
        return True
    me = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or ""
    return (not me) or me.upper() == CANON_WRITER_NODE.upper()


def die(msg):
    print("ERR %s" % msg)
    sys.exit(2)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter_block(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    return m


def scalar(fm_text, key):
    """ЕДИНЫЙ YAML-lite скаляр канона (canon_intake.py импортирует ЭТУ функцию — два своих
    парсера неизбежно разъезжаются, находка Codex T3-BREAK 27.07).
    ⚠ [ \\t], НЕ \\s: \\s включает \\n — у ПУСТОГО поля `\\s*` съедал перенос и возвращал
    СЛЕДУЮЩУЮ строку, а запись на том же regex затирала соседнее поле (тихая потеря данных).
    ⚠ Комментарий режем по ОДНОМУ пробелу перед # (как YAML), но только вне кавычек —
    иначе `summary: "взяли #хэштег"` потеряет хвост."""
    m = re.search(r"^%s:[ \t]*(.*)$" % re.escape(key), fm_text, re.M)
    if not m:
        return None
    val = m.group(1).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]          # значение в кавычках: # внутри — часть текста, не коммент
    return re.split(r"[ \t]+#", val)[0].strip()


def collect(folder, prefix, id_key, want_status):
    """Реальность = файлы. Возвращает (список id в стабильном порядке, {id: title})."""
    found, titles = [], {}
    for p in sorted(glob.glob(os.path.join(CANON, folder, prefix + "*.md"))):
        text = _read(p)
        m = frontmatter_block(text)
        if not m:
            continue
        fm = m.group(1)
        _id = scalar(fm, id_key)
        if not _id:
            continue
        if (scalar(fm, "status") or "") != want_status:
            continue
        found.append(_id)
        titles[_id] = scalar(fm, "title") or _id
    return found, titles


def board_value(fm_text, field):
    """Текущее табло: список id из inline-списка wiki-линков."""
    m = re.search(r"^%s:\s*(\[.*\])\s*$" % re.escape(field), fm_text, re.M)
    if not m:
        return None
    return re.findall(r"\[\[([^\]]+)\]\]", m.group(1))


def render(field, ids):
    return '%s: [%s]' % (field, ", ".join('"[[%s]]"' % i for i in ids))


def stable_order(current, real):
    """Порядок стабилен: что было на табло — в прежнем порядке, новое — в хвост.
    Стабильное тело файла = меньше sync-конфликтов (память single-writer-shard-pattern)."""
    keep = [i for i in (current or []) if i in real]
    add = [i for i in real if i not in keep]
    return keep + add


def cmd_board(apply_it):
    if not os.path.exists(SEASON):
        die("нет season-01.md: %s" % SEASON)
    text = _read(SEASON)
    m = frontmatter_block(text)
    if not m:
        die("season-01.md без frontmatter — парсить нечего")
    fm_text = m.group(1)

    new_fm, changes = fm_text, []
    for field, (folder, prefix, id_key, want) in BOARD_FIELDS.items():
        real, titles = collect(folder, prefix, id_key, want)
        if not real:
            die("в %s\\ нет ни одной карточки со status: %s — отказываюсь стирать табло"
                % (folder, want))
        current = board_value(fm_text, field)
        if current is None:
            print("⚠ поля %s нет на табло — пропускаю (добавь строку руками один раз)" % field)
            continue
        wanted = stable_order(current, real)
        if current == wanted:
            print("✅ %s: совпадает (%d)" % (field, len(wanted)))
            continue
        added = [i for i in wanted if i not in current]
        removed = [i for i in current if i not in wanted]
        changes.append((field, current, wanted, added, removed))
        print("⚠ %s: РАСХОЖДЕНИЕ" % field)
        print("   до:    %s" % ", ".join(current))
        print("   после: %s" % ", ".join(wanted))
        for i in added:
            print("   + %s — %s" % (i, titles.get(i, "?")))
        for i in removed:
            print("   - %s (уже не %s в файлах)" % (i, want))
        new_fm = re.sub(r"^%s:\s*\[.*\]\s*$" % re.escape(field),
                        render(field, wanted).replace("\\", "\\\\"), new_fm, count=1, flags=re.M)

    if not changes:
        print("\nИтог: табло не врёт, править нечего.")
        sys.exit(0)

    if not apply_it:
        print("\nИтог: %d поле(й) разошлось. Записать: show_canon_sync.py board --apply" % len(changes))
        sys.exit(1)

    if not may_write(sys.argv):
        print("\nSKIP: писатель канона = %s, а этот узел = %s (--force чтобы всё равно)."
              % (CANON_WRITER_NODE, os.environ.get("COMPUTERNAME", "?")))
        sys.exit(1)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SEASON + ".bak-%s" % stamp
    try:
        shutil.copy2(SEASON, bak)  # бэкап перед записью в волт (правило vault-backup-rule)
        # ротация: ночной прогон каждый день, иначе за год 365 .bak поедут по Syncthing
        old = sorted(glob.glob(SEASON + ".bak-*"))
        for stale in old[:-5]:
            try:
                os.remove(stale)
            except Exception:
                pass
        out = text[:m.start(1)] + new_fm + text[m.end(1):]
        with open(SEASON, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    except Exception as e:
        die("не смог записать season-01.md: %s" % e)
    # Слой видимости: доказательство = перечитать файл и сверить, а не «exit 0»
    check = _read(SEASON)
    cm = frontmatter_block(check)
    for field, _cur, wanted, _a, _r in changes:
        got = board_value(cm.group(1), field)
        if got != wanted:
            die("запись не подтвердилась для %s: в файле %s" % (field, got))
    print("\n✅ табло пересобрано из файлов · бэкап: %s" % bak)
    sys.exit(0)


def cmd_dict(which):
    folder, prefix, id_key, want = BOARD_FIELDS[which]
    real, titles = collect(folder, prefix, id_key, want)
    if not real:
        die("пусто в %s\\ со status: %s" % (folder, want))
    print("# валидные %s (status: %s) — БЕРИ ID ОТСЮДА, не выдумывай свободный тег" % (which, want))
    for i in real:
        print("%s\t%s" % (i, titles.get(i, "")))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "board"
    if cmd == "board":
        cmd_board("--apply" in args)
    elif cmd == "arcs":
        cmd_dict("active_arcs")
    elif cmd == "loops":
        cmd_dict("open_loops")
    else:
        die("неизвестная команда %r (жду: board [--apply] | arcs | loops)" % cmd)


if __name__ == "__main__":
    main()
