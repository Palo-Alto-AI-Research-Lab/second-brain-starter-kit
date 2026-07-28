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
canon_intake.py — ПРИЁМКА бит-кандидатов из beats-inbox в канон (механика разбора).

КОРЕНЬ, который лечит (2026-07-27): сенсор (content-miner-nightly) клал биты в
beats-inbox КАЖДУЮ НОЧЬ, а «писатель канона» был живой сессией без триггера —
мост построен, берега нет (§4.2 Connect). Накопилось 20 при пороге 10.
Плюс разбор был дорогим руками: сенсор пишет related_arcs СВОБОДНЫМ тегом
(second-brain, mission-get-noticed — таких арок в каноне нет), story_day забывает.

Разделение труда: LLM СУДИТ (в какую арку бит, годен ли), скрипт ДЕЛАЕТ механику
(валидация словаря, story_day, перенос, обратная ссылка в арку, чистка README) — 0 токенов.

Команды:
  list                       что лежит в инбоксе + живой словарь арок
  accept <beat_id> --arcs arc-a[,arc-b]   принять в канон (валидирует arc_id по файлам!)
  reject <beat_id> --why "..."            выбросить кандидата (с записью причины в лог)

Exit-коды (§5.2): 0 = сделал · 1 = отказ по валидации (невалидная арка / дубль) · 2 = не смог.
"""
import os, re, sys, glob, shutil, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

VAULT = os.environ.get("OBSIDIAN_VAULT", r"%VAULT%")
CANON = os.path.join(VAULT, "04-Projects", "show-canon")
INBOX = os.path.join(CANON, "beats-inbox")
BEATS = os.path.join(CANON, "beats")
ARCS = os.path.join(CANON, "arcs")
SEASON = os.path.join(CANON, "season-01.md")
README = os.path.join(INBOX, "_README.md")
REJECT_LOG = os.path.join(INBOX, "_rejected.log")


def die(msg, code=2):
    print("ERR %s" % msg)
    sys.exit(code)


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _write(p, text):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def fm_of(text):
    return re.match(r"^---\s*\n(.*?)\n---", text, re.S)


from show_canon_sync import scalar, may_write, CANON_WRITER_NODE  # ЕДИНЫЙ парсер и ЕДИНЫЙ гейт
# писателя на оба скрипта: свои копии разъезжаются (находка Codex T3-BREAK 27.07). Правишь — там.


def live_arcs():
    """Словарь = ФАЙЛЫ (status: active), не рукописный список. Один источник истины."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ARCS, "arc-*.md"))):
        fm = fm_of(_read(p))
        if not fm:
            continue
        aid = scalar(fm.group(1), "arc_id")
        if aid and (scalar(fm.group(1), "status") or "") == "active":
            out[aid] = p
    return out


def story_day_for(occurred_on):
    """story_day — ПРОИЗВОДНОЕ от даты. Якорь читаем из season-01 (не хардкод):
    live_as_of ↔ current_story_day. Проверено на живых битах (07-10→40, 07-14→44, 07-27→57)."""
    fm = fm_of(_read(SEASON))
    if not fm:
        return None
    anchor_date = scalar(fm.group(1), "live_as_of")
    anchor_day = scalar(fm.group(1), "current_story_day")
    try:
        a_d = datetime.date.fromisoformat(str(anchor_date)[:10])
        occ = datetime.date.fromisoformat(str(occurred_on)[:10])
        return int(anchor_day) + (occ - a_d).days
    except Exception:
        return None


def set_field(fm_text, key, rendered_line):
    # [ \t] а не \s — см. граблю в scalar(): \s* съедает \n и затирает соседнюю строку
    if re.search(r"^%s:[ \t]*.*$" % re.escape(key), fm_text, re.M):
        return re.sub(r"^%s:[ \t]*.*$" % re.escape(key),
                      rendered_line.replace("\\", "\\\\"), fm_text, count=1, flags=re.M)
    return fm_text + "\n" + rendered_line


def ensure_canon():
    """«Пусто» обязано отличаться от «не туда посмотрел» (§5.4 + deterministic-script-gotchas).
    Без этой проверки list на кривом OBSIDIAN_VAULT печатал «0 кандидатов» и выходил 0 —
    ночная рутина прочитала бы это как «чисто» и промолчала (поймано /tt 27.07)."""
    for p in (CANON, INBOX, BEATS, ARCS):
        if not os.path.isdir(p):
            die("канон не найден: %s (OBSIDIAN_VAULT=%s) — это НЕ «пусто», это не тот диск"
                % (p, os.environ.get("OBSIDIAN_VAULT", "<unset>")))


def cmd_list():
    ensure_canon()
    cands = sorted(glob.glob(os.path.join(INBOX, "beat-*.md")))
    arcs = live_arcs()
    print("== BEATS-INBOX: %d кандидатов ==" % len(cands))
    for p in cands:
        fm = fm_of(_read(p))
        f = fm.group(1) if fm else ""
        print("  • %s [%s] %s" % (
            os.path.basename(p)[:-3], scalar(f, "beat_kind") or "?",
            (scalar(f, "summary") or "")[:90]))
        print("      сенсор предложил related_arcs: %s" % (scalar(f, "related_arcs") or "[]"))
    print("\n== ВАЛИДНЫЕ arc_id (бери ТОЛЬКО отсюда) ==")
    for a in arcs:
        print("  %s" % a)


def cmd_accept(beat_id, arc_ids):
    ensure_canon()  # иначе «нет кандидата» соврёт про причину: на деле нет всего волта
    if not may_write(sys.argv):  # один писатель канона, гейт в коде (см. show_canon_sync.py)
        die("писатель канона = %s, этот узел = %s (--force чтобы всё равно)"
            % (CANON_WRITER_NODE, os.environ.get("COMPUTERNAME", "?")), 1)
    src = os.path.join(INBOX, beat_id + ".md")
    if not os.path.exists(src):
        die("нет кандидата %s в инбоксе" % beat_id)
    dst = os.path.join(BEATS, beat_id + ".md")
    if os.path.exists(dst):
        die("ДУБЛЬ: %s уже в beats/ — разбирайся руками (reject или переименуй)" % beat_id, 1)

    arcs = live_arcs()
    bad = [a for a in arc_ids if a not in arcs]
    if bad:
        die("невалидные arc_id: %s · валидные: %s" % (", ".join(bad), ", ".join(arcs)), 1)

    text = _read(src)
    fm = fm_of(text)
    if not fm:
        die("у %s нет frontmatter" % beat_id)
    fm_text = fm.group(1)

    # story_day: производное, если пусто/0
    cur_day = (scalar(fm_text, "story_day") or "").strip()
    if cur_day in ("", "0"):
        sd = story_day_for(scalar(fm_text, "occurred_on") or "")
        if sd is not None:
            fm_text = set_field(fm_text, "story_day", "story_day: %d" % sd)

    # related_arcs: свободный тег сенсора -> канонные id
    fm_text = set_field(fm_text, "related_arcs",
                        "related_arcs: [%s]" % ", ".join('"[[%s]]"' % a for a in arc_ids))
    fm_text = set_field(fm_text, "accepted_by", "accepted_by: canon-intake")
    fm_text = set_field(fm_text, "accepted_on",
                        "accepted_on: %s" % datetime.date.today().isoformat())

    # Инвариант против класса «правка тихо съела соседнюю строку» (грабля \s* , /tt 27.07):
    # frontmatter не имеет права ПОХУДЕТЬ при приёмке — только вырасти или остаться.
    before_keys = len([l for l in fm.group(1).splitlines() if re.match(r"^[A-Za-z_][\w-]*:", l)])
    after_keys = len([l for l in fm_text.splitlines() if re.match(r"^[A-Za-z_][\w-]*:", l)])
    if after_keys < before_keys:
        die("приёмка съела поля frontmatter (%d → %d) — правка отменена" % (before_keys, after_keys))

    out = text[:fm.start(1)] + fm_text + text[fm.end(1):]
    _write(src, out)
    shutil.move(src, dst)

    # обратная ссылка в каждой арке (arc.beats[]) — иначе ось Q2 не увидит движения
    for a in arc_ids:
        ap = arcs[a]
        atext = _read(ap)
        afm = fm_of(atext)
        if not afm:
            continue
        af = afm.group(1)
        if beat_id in af:
            continue
        m = re.search(r"^beats:\s*\[(.*)\]\s*$", af, re.M)
        if m:
            inner = m.group(1).strip()
            new_inner = (inner + ", " if inner else "") + '"[[%s]]"' % beat_id
            af = af[:m.start()] + "beats: [%s]" % new_inner + af[m.end():]
        else:
            af = af + "\nbeats: [\"[[%s]]\"]" % beat_id
        _write(ap, atext[:afm.start(1)] + af + atext[afm.end(1):])

    # README: вычеркнуть строку ожидания (слой видимости не должен врать)
    if os.path.exists(README):
        rt = _read(README)
        new_rt = "\n".join(l for l in rt.splitlines() if beat_id not in l)
        if new_rt != rt:
            _write(README, new_rt + "\n")

    # доказательство, а не «exit 0»
    if not os.path.exists(dst):
        die("перенос не подтвердился: нет %s" % dst)
    for a in arc_ids:
        if beat_id not in _read(arcs[a]):
            die("обратная ссылка не подтвердилась в %s" % a)
    print("✅ %s → beats/ · арки: %s" % (beat_id, ", ".join(arc_ids)))
    sys.exit(0)


def cmd_verify():
    """Детектор ПОЛОВИНЧАТОЙ приёмки (VERIFY Codex 27.07: обрыв между move и правкой арки,
    либо гонка двух писателей, оставят бит в beats/ без обратной ссылки — и сторож этого
    НЕ увидит). Инвариант узкий, чтобы не шуметь: проверяем ТОЛЬКО биты, принятые скриптом
    (accepted_by: canon-intake) — у них обратная ссылка обязана быть. Старые биты без арок
    (их 57 из 96) — легальная норма канона, их не трогаем."""
    ensure_canon()
    # по КАЖДОЙ арке отдельно, не «хоть где-то»: обрыв на второй из двух арок иначе
    # маскируется первой (поймано /tt 27.07 — первый вариант детектора был декорацией)
    arc_files = {}
    for p in glob.glob(os.path.join(ARCS, "arc-*.md")):
        fm = fm_of(_read(p))
        if fm:
            aid = scalar(fm.group(1), "arc_id")
            if aid:
                arc_files[aid] = _read(p)
    broken = []
    checked = 0
    for p in sorted(glob.glob(os.path.join(BEATS, "beat-*.md"))):
        fm = fm_of(_read(p))
        if not fm or scalar(fm.group(1), "accepted_by") != "canon-intake":
            continue
        checked += 1
        bid = os.path.basename(p)[:-3]
        want = re.findall(r"\[\[([^\]]+)\]\]", scalar(fm.group(1), "related_arcs") or "")
        for a in want:
            if a not in arc_files:
                broken.append("%s → арки %s больше нет" % (bid, a))
            elif bid not in arc_files[a]:
                broken.append("%s → %s не ссылается обратно" % (bid, a))
    print("== VERIFY приёмки: проверено %d принятых битов ==" % checked)
    if broken:
        print("❌ приняты, но арка на них НЕ ссылается (половинчатая приёмка):")
        for b in broken:
            print("   - %s" % b)
        print("Лечение: дописать бит в beats[] нужной арки (или re-accept после возврата в инбокс).")
        sys.exit(1)
    print("✅ все принятые биты имеют обратную ссылку в арке")
    sys.exit(0)


def cmd_reject(beat_id, why):
    ensure_canon()
    src = os.path.join(INBOX, beat_id + ".md")
    if not os.path.exists(src):
        die("нет кандидата %s в инбоксе" % beat_id)
    with open(REJECT_LOG, "a", encoding="utf-8") as f:
        f.write("%s\t%s\t%s\n" % (datetime.date.today().isoformat(), beat_id, why))
    os.remove(src)
    if os.path.exists(README):
        rt = _read(README)
        new_rt = "\n".join(l for l in rt.splitlines() if beat_id not in l)
        if new_rt != rt:
            _write(README, new_rt + "\n")
    print("🗑 %s отклонён: %s" % (beat_id, why))
    sys.exit(0)


def main():
    args = sys.argv[1:]
    if not args or args[0] == "list":
        cmd_list(); return
    cmd = args[0]
    if cmd == "verify":
        cmd_verify()
    if cmd == "accept":
        if len(args) < 2:
            die("accept <beat_id> --arcs arc-a,arc-b")
        beat_id = args[1]
        arcs_arg = ""
        if "--arcs" in args:
            arcs_arg = args[args.index("--arcs") + 1]
        arc_ids = [a.strip() for a in arcs_arg.split(",") if a.strip()]
        if not arc_ids:
            die("нужен --arcs (хотя бы одна арка) — бит без арки не двигает сюжет", 1)
        cmd_accept(beat_id, arc_ids)
    elif cmd == "reject":
        if len(args) < 2:
            die("reject <beat_id> --why \"...\"")
        why = args[args.index("--why") + 1] if "--why" in args else "без причины"
        cmd_reject(args[1], why)
    else:
        die("неизвестная команда %r (жду: list | accept | reject)" % cmd)


if __name__ == "__main__":
    main()
