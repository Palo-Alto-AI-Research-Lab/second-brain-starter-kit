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
r"""social_guard.py — единый rate-guard публикаций в соцсети (TG / X / FB).

Обобщение fb_guard.py на все площадки (fb_guard остаётся на хабе для /fb-post;
новые скиллы /tg-post и /x-post используют этот гейт). Живёт в scripts\_shared\
=> синкается на весь флот; состояние — пер-машинное (постим с конкретной машины).

Использование:
    python social_guard.py check  <tg|x|fb> [--text "..."]   # можно ли постить
    python social_guard.py record <tg|x|fb> [--text "..."]   # зафиксировать пост
    python social_guard.py status                            # счётчики за сегодня

Контракт как у fb_guard: stdout "OK ..." + exit 0 / "BLOCKED ..." + exit 3.
--text включает анти-дубль: одинаковый текст на одной площадке в течение 7 дней
= BLOCKED (спам-флаг платформ). День считается по локальным часам машины
(флот живёт по Лиссабону).

Переопределения для тестов: SOCIAL_GUARD_STATE=<путь к json>.
"""
import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta

CAPS = {"tg": 10, "x": 6, "fb": 8}   # постов/день с этой машины
DUP_WINDOW_DAYS = 7

STATE_PATH = os.environ.get("SOCIAL_GUARD_STATE") or os.path.join(
    os.path.expanduser("~"), ".claude", "scripts", "_social_guard_state.json")


def _load():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"counts": {}, "hashes": {}}


def _save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def _prune(state):
    today = date.today()
    keep_from = (today - timedelta(days=DUP_WINDOW_DAYS)).isoformat()
    state["counts"] = {d: v for d, v in state["counts"].items()
                       if d >= (today - timedelta(days=2)).isoformat()}
    for platform in list(state["hashes"]):
        state["hashes"][platform] = {h: d for h, d in state["hashes"][platform].items()
                                     if d >= keep_from}


def _text_hash(text):
    norm = " ".join(text.split()).lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _today_count(state, platform):
    return state["counts"].get(date.today().isoformat(), {}).get(platform, 0)


def check(platform, text=None):
    state = _load()
    cap = CAPS[platform]
    n = _today_count(state, platform)
    if n >= cap:
        print(f"BLOCKED {platform}: дневной лимит {cap} исчерпан ({n}/{cap})")
        return 3
    if text:
        h = _text_hash(text)
        seen = state["hashes"].get(platform, {}).get(h)
        if seen:
            print(f"BLOCKED {platform}: идентичный текст уже публиковался {seen} (анти-дубль {DUP_WINDOW_DAYS}д)")
            return 3
    print(f"OK {platform} ({n}/{cap} сегодня)")
    return 0


def record(platform, text=None):
    state = _load()
    _prune(state)
    today = date.today().isoformat()
    state["counts"].setdefault(today, {})
    state["counts"][today][platform] = state["counts"][today].get(platform, 0) + 1
    if text:
        state["hashes"].setdefault(platform, {})[_text_hash(text)] = today
    _save(state)
    n = state["counts"][today][platform]
    print(f"RECORDED {platform} ({n}/{CAPS[platform]} сегодня)")
    return 0


def status():
    state = _load()
    today = date.today().isoformat()
    counts = state["counts"].get(today, {})
    parts = [f"{p}={counts.get(p, 0)}/{CAPS[p]}" for p in CAPS]
    print(f"{today}: " + " · ".join(parts) + f"  [{datetime.now():%H:%M}]")
    return 0


def main(argv):
    if len(argv) >= 1 and argv[0] == "status":
        return status()
    if len(argv) < 2 or argv[0] not in ("check", "record") or argv[1] not in CAPS:
        print("usage: social_guard.py check|record <tg|x|fb> [--text \"...\"] | status")
        return 2
    text = None
    if "--text" in argv:
        i = argv.index("--text")
        if i + 1 >= len(argv):
            print("usage: --text требует аргумент")
            return 2
        text = argv[i + 1]
    fn = check if argv[0] == "check" else record
    return fn(argv[1], text)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
