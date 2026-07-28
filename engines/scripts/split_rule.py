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
"""split_rule.py - ТЕНЕВОЙ замер правила разрыва «чиню здесь vs выношу в отдельную сессию».

Правило (черновик, Антон «+» 2026-07-28, режим ТЕНЬ - считаем, но не командуем):
выносить в отдельную сессию, если сработал ЛЮБОЙ сигнал:
  A. две попытки фикса не помогли            (--attempts >= 2)
  B. корень задевает > 2 файлов или смежную систему (--files > 2 или --shared)
  C. воспроизвести баг за 10 минут не вышло  (--repro-min > 10)
  D. контекст сессии съеден >= 70%           (--context-pct >= 70)

Тень = я логирую вердикт правила И то, что реально сделал, но решение остаётся за живой сессией.
Через 14 дней смотрим расхождение (см. критерии флипа в 00-System/Split-Rule-Shadow.md).

  python split_rule.py log --what "inbox-робот молчит" --attempts 2 --files 4 --repro-min 15 \
      --context-pct 55 --decision stay --note "чинил на месте, 40 минут"
  python split_rule.py summary          # цифры за всё время
  python split_rule.py summary --days 14
"""
import os
import sys
import json
import time
import argparse

LOG_DIR = os.path.expanduser(os.path.join("~", ".claude", "logs"))
LOG = os.path.join(LOG_DIR, "split_rule_shadow.jsonl")


def machine_name():
    """Имя машины. ⚠️ Первая версия писала всегда 'unknown': выражение
    `A or B if hasattr(...) else C` из-за приоритетов сворачивалось в `(A or B) if ... else C`,
    и на Windows (нет os.uname) всегда уходило в else. Ловится только живым прогоном."""
    v = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME")
    if v:
        return v
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "unknown"


def verdict(attempts, files, repro_min, context_pct, shared):
    """Что СКАЗАЛО БЫ правило. Возвращает (split: bool, сработавшие сигналы)."""
    fired = []
    if attempts >= 2:
        fired.append("A:попыток=" + str(attempts))
    if files > 2:
        fired.append("B:файлов=" + str(files))
    if shared:
        fired.append("B:смежная-система")
    if repro_min > 10:
        fired.append("C:воспроизведение=" + str(repro_min) + "мин")
    if context_pct >= 70:
        fired.append("D:контекст=" + str(context_pct) + "%")
    return (len(fired) > 0), fired


def append(rec):
    """Одна запись в общий лог. Пишут параллельные сессии, поэтому лок обязателен.

    ⚠️ Грабля, пойманная живым тестом 2026-07-28: НЕЛЬЗЯ лочить байт в том же файле, в который
    пишешь. msvcrt.locking лочит диапазон ОТ ТЕКУЩЕЙ ПОЗИЦИИ; после write позиция уехала, и unlock
    падает PermissionError. Если вокруг стоит except с повторной записью, строка дублируется
    (ровно это и случилось: 1 вызов = 2 строки в логе). Лечение класса: лок живёт в ОТДЕЛЬНОМ
    файле-замке, позиция которого не двигается; запись в лог происходит ровно один раз.
    См. [[deterministic-script-gotchas]].
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    lock_path = LOG + ".lock"
    lock = None
    try:
        # ⚠️ Находка внешнего ломателя (Gemini, 28.07): если открыть файл-замок нельзя (нет прав),
        # исключение улетало наружу, запись в лог пропускалась, а скрипт всё равно печатал
        # «записано» = ТИХАЯ ПОТЕРЯ. Замок необязателен, запись обязательна.
        try:
            lock = open(lock_path, "a+")
        except Exception:
            lock = None
        try:
            if lock is None:
                raise RuntimeError("no lock file")
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass  # лок не взялся: пишем всё равно, потеря записи хуже гонки
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
    finally:
        if lock is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            lock.close()


def cmd_log(a):
    split, fired = verdict(a.attempts, a.files, a.repro_min, a.context_pct, a.shared)
    rec = {
        # ⚠️ Ломатель (Gemini, 28.07): наивный ISO без офсета едет по флоту между часовыми поясами,
        # и окно --days считалось в поясе ЧИТАЮЩЕЙ машины. Поэтому фильтруем по ts_epoch (UTC),
        # а человекочитаемый ts остаётся местным.
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts_epoch": int(time.time()),
        "machine": machine_name(),
        "what": a.what,
        "attempts": a.attempts,
        "files": a.files,
        "repro_min": a.repro_min,
        "context_pct": a.context_pct,
        "shared": bool(a.shared),
        "rule_says": "split" if split else "stay",
        "fired": fired,
        "decision": a.decision,
        "minutes_spent": a.minutes,
        "note": a.note or "",
        "agree": (("split" if split else "stay") == a.decision),
    }
    append(rec)
    mark = "совпало" if rec["agree"] else "РАСХОЖДЕНИЕ"
    print("правило: " + rec["rule_says"] + " | сделали: " + a.decision + " | " + mark)
    if fired:
        print("сигналы: " + ", ".join(fired))
    print("записано -> " + LOG)
    return 0


def load(days=None):
    if not os.path.isfile(LOG):
        return []
    cutoff = time.time() - days * 86400 if days else None
    out = []
    for line in open(LOG, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if cutoff:
            t = rec.get("ts_epoch")
            if t is None:
                try:
                    t = time.mktime(time.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%S"))
                except Exception:
                    t = None
            # ⚠️ Ломатель (Gemini, 28.07): битый штамп раньше НЕ выкидывал запись из окна
            # (except гасил, continue не выполнялся) и портил счёт за период. Теперь выкидывает.
            if t is None or t < cutoff:
                continue
        out.append(rec)
    return out


def cmd_summary(a):
    rows = load(a.days)
    if not rows:
        print("инцидентов не залогировано" + (" за " + str(a.days) + " дней" if a.days else "") + ".")
        print("ТЕНЬ БЕЗ ДАННЫХ = правило не проверено, а не «работает».")
        return 0
    n = len(rows)
    said_split = sum(1 for r in rows if r["rule_says"] == "split")
    did_split = sum(1 for r in rows if r["decision"] == "split")
    agree = sum(1 for r in rows if r.get("agree"))
    # ⚠️ Ломатель (Gemini, 28.07): фильтр `and r.get("minutes_spent")` выбрасывал записи с 0 минут
    # (0 ложно ведёт себя как False) и тихо кривил медиану. Теперь 0 = «время не указано»,
    # считаем такие ОТДЕЛЬНО и говорим об этом вслух, а не прячем.
    against = [r for r in rows if r["decision"] == "stay" and r["rule_says"] == "split"]
    mins_stay = [r["minutes_spent"] for r in against if (r.get("minutes_spent") or 0) > 0]
    no_time = len(against) - len(mins_stay)
    print("инцидентов: " + str(n))
    print("правило сказало «выноси»: " + str(said_split) + " | реально вынесли: " + str(did_split))
    print("совпадений правила и решения: " + str(agree) + " (" + str(round(100.0 * agree / n)) + "%)")
    if mins_stay:
        mins_stay.sort()
        med = mins_stay[len(mins_stay) // 2]
        print("остались чинить вопреки правилу: " + str(len(mins_stay)) + " раз, медиана " + str(med) + " мин")
        print("(порог флипа: медиана > 20 мин = правило право, надо armить)")
    if no_time:
        print("⚠️ без указанного времени: " + str(no_time) + " инцидентов вопреки правилу -> в медиану НЕ вошли")
    if n < 8:
        print("⚠️ инцидентов меньше 8: выборки нет, окно продлеваем, а не «внедряем на глаз»")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Теневой замер правила разрыва сессии")
    sub = ap.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="залогировать инцидент отладки")
    lg.add_argument("--what", required=True, help="что чиним, одной строкой")
    lg.add_argument("--attempts", type=int, default=1, help="сколько попыток фикса уже провалилось")
    lg.add_argument("--files", type=int, default=1, help="сколько файлов задевает корень")
    lg.add_argument("--repro-min", type=int, default=0, help="минут ушло на воспроизведение")
    lg.add_argument("--context-pct", type=int, default=0, help="процент съеденного контекста сессии")
    lg.add_argument("--shared", action="store_true", help="задета смежная система (шина/канон/планировщик/auth)")
    lg.add_argument("--decision", choices=["stay", "split"], required=True, help="что реально сделали")
    lg.add_argument("--minutes", type=int, default=0, help="сколько минут в итоге потратили")
    lg.add_argument("--note", default="", help="комментарий")
    lg.set_defaults(func=cmd_log)

    sm = sub.add_parser("summary", help="цифры теневого замера")
    sm.add_argument("--days", type=int, default=None)
    sm.set_defaults(func=cmd_summary)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
