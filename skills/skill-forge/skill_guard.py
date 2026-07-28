#!/usr/bin/env python3
"""skill_guard.py — детерминированный привратник скиллов флота (0-LLM).

Реализует рельсы безопасности из decision-2026-07-14-fleet-skill-autonomy-local-namespace
+ DR26-07-14-MAC-1-01 (3 вендора). Вызывается вручную, из /skill-promote и (позже) из хука.

Проверки:
  РЕЛЬС 1  collision   local-X И shared-X одновременно → HARD FAIL (анти-shadowing).
  РЕЛЬС 3  conflict    *.sync-conflict-* в наборе скиллов → FAIL (битые склеенные инструкции).
  Step 2   name        local-скилл обязан называться local-<slug> ([a-z0-9-]).
  РЕЛЬС 6  leak (opt)   grep-скан секретов в SKILL.md перед промоушеном (--leak).

Exit 0 = чисто · Exit 1 = найдена проблема (гейт закрыт). AK-47: stdlib only.
"""
import argparse
import os
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(os.path.expanduser("~/.claude/skills"))
NAME_RE = re.compile(r"^local-[a-z0-9][a-z0-9-]*$")
# грубый но полезный скан секретов (рельс 6, дешёвый префильтр — не замена gitleaks)
SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?[A-Za-z0-9/\+_\-]{16,}"), "key/secret literal"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style key"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "Slack token"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
]


def list_skill_names():
    """Верхнеуровневые папки скиллов (у каждой SKILL.md)."""
    names = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if p.is_dir() and (p / "SKILL.md").exists():
            names.append(p.name)
    return names


def check_collision(names):
    """РЕЛЬС 1: local-X + X одновременно = fatal."""
    problems = []
    shared = {n for n in names if not n.startswith("local-")}
    for n in names:
        if n.startswith("local-"):
            base = n[len("local-"):]
            if base in shared:
                problems.append(f"COLLISION: '{n}' и общий '{base}' существуют одновременно (shadowing-trap)")
    return problems


def check_sync_conflicts():
    """РЕЛЬС 3: любой *.sync-conflict-* среди скиллов."""
    hits = [str(p.relative_to(SKILLS_DIR)) for p in SKILLS_DIR.rglob("*.sync-conflict-*")]
    return [f"SYNC-CONFLICT: {h} (битые склеенные инструкции — разрули/удали перед загрузкой)" for h in hits]


def check_name(name):
    """Step 2: конвенция имени local-скилла."""
    if not NAME_RE.match(name):
        return [f"NAME: '{name}' не матчит local-<slug> ([a-z0-9-], без заглавных/подчёркиваний)"]
    return []


def check_leak(name):
    """РЕЛЬС 6: дешёвый скан секретов в SKILL.md (+ файлах бандла)."""
    d = SKILLS_DIR / name
    problems = []
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for pat, label in SECRET_PATTERNS:
            if pat.search(text):
                problems.append(f"LEAK: возможный секрет в {f.relative_to(SKILLS_DIR)} ({label})")
    return problems


def main():
    ap = argparse.ArgumentParser(description="Привратник скиллов флота")
    ap.add_argument("--check-name", metavar="local-slug", help="проверить конвенцию имени")
    ap.add_argument("--leak", metavar="skill-name", help="скан секретов в скилле (рельс 6)")
    ap.add_argument("--quiet", action="store_true", help="только код возврата")
    args = ap.parse_args()

    if not SKILLS_DIR.exists():
        print(f"skill_guard: нет каталога скиллов {SKILLS_DIR}", file=sys.stderr)
        return 1

    names = list_skill_names()
    problems = []
    problems += check_collision(names)          # рельс 1 — всегда
    problems += check_sync_conflicts()          # рельс 3 — всегда
    if args.check_name:
        problems += check_name(args.check_name)  # step 2
    if args.leak:
        problems += check_leak(args.leak)        # рельс 6

    if problems:
        if not args.quiet:
            print(f"🔴 skill_guard: {len(problems)} проблем(а) — гейт ЗАКРЫТ:")
            for p in problems:
                print(f"  • {p}")
        return 1
    if not args.quiet:
        print(f"🟢 skill_guard: чисто ({len(names)} скиллов, collision/sync-conflict пройдены)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
