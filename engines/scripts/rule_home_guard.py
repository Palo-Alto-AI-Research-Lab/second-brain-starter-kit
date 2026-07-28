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
"""rule_home_guard.py -- счётчик покрытия правила в always-loaded слое.

Канон: reglament-vyuchennoe-zapisyvaetsya-vo-vse-doma-matritsa (anton 2026-07-14).
Правило «само всплывает» в новых сессиях ТОЛЬКО если оставило след в always-loaded
слое: CLAUDE.md или MEMORY.md. Этот скрипт детерминированно проверяет след.

Usage:  python rule_home_guard.py <slug-или-ключевые-слова> [ещё-термины...]
Exit:   0 = след найден хотя бы в одном always-loaded доме
        1 = следа нет -> нарушен Шаг 2 /intake, чинить до слова «готово»

Ищем каждый термин (case-insensitive, подстрока) в:
  - ~/.claude/CLAUDE.md
  - ~/.claude/projects/*/memory/MEMORY.md  (все проекты)
Достаточно попадания ЛЮБОГО термина в ЛЮБОЙ из файлов.
"""
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    terms = [t.strip() for t in sys.argv[1:] if t.strip()]
    if not terms:
        print("usage: rule_home_guard.py <slug-or-keywords> [more terms...]")
        return 2

    home = Path.home() / ".claude"
    targets = [home / "CLAUDE.md"]
    targets += sorted((home / "projects").glob("*/memory/MEMORY.md"))

    total_hits = 0
    for f in targets:
        if not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace").lower()
        except OSError as e:
            print(f"  ?? {f}  ({e})")
            continue
        hits = [t for t in terms if t.lower() in text]
        mark = "OK" if hits else "--"
        print(f"  {mark} {f}" + (f"  <- {', '.join(hits)}" if hits else ""))
        total_hits += len(hits)

    if total_hits:
        print(f"GREEN: след в always-loaded слое есть ({total_hits} попаданий).")
        return 0
    print("RED: следа в CLAUDE.md / MEMORY.md НЕТ -> правило не всплывёт само. Чинить.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
