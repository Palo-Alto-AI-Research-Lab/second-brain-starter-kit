---
name: wisdom-distill
description: >-
  Weekly Wisdom Distill - раз в неделю выжать из собственных слов Антона за 7 дней (origin: anton)
  3-5 durable-уроков в заметку недели в 03-Insights. Trigger on "/wisdom-distill",
  "выжми мудрость недели", "что я понял за неделю", "weekly wisdom", "distill my week".
  Часть активного брейна (D из карты A-E). LLM читает только дайджест сборщика.
---

# /wisdom-distill — мудрость недели

> 🧒 К Антону — в конце recap «Простыми словами».

## Run (deterministic first — 0 токенов)
`python "$IMPORTS_ROOT\wisdom_week_gather.py"` (или `... 14` для окна 14 дней) →
заметки `origin: anton`/`#anton-original` за окно (date-поле, fallback mtime), кроме
`_originals/_imports/_Dashboards`, cap 60 × 500 симв. → `$IMPORTS_ROOT\_wisdom_week_digest.md`.
**LLM читает только дайджест, не корпус.**

## Distill (Opus — синтез, не грунт)
Из дайджеста — 3–5 durable-уроков недели (переживёт месяц; «как Антон теперь думает/решает»).
Формат: урок одной строкой голосом Антона · Откуда: note-a [internal], note-b [internal] (2+ = сильнее) ·
Что меняет: в каком решении проявится. Отбрось транзиты, чужие идеи, само-очевидное.
Неделя тонкая (<3) — так и скажи, не выдумывай.

## Save (backup-first: vault_backup.py)
Заметка: $OBSIDIAN_VAULT\03-Insights\insight-weekly-wisdom-YYYY-Www.md
Frontmatter: title, date, type: insight, origin: anton, authored_by: hybrid,
tags: [insight, weekly-wisdom, anton-original], summary. Линки на источники
(no-orphan-notes-rule); затронуты убеждения — линк belief-*. NO 🧒 в заметке.

## Scheduled twin
Cron `wisdom-distill-weekly`: Вс 23:20 Lisbon (routines-run-at-night). Сборщик →
дистилляция (Opus-субагент) → заметка → анонс в TG чат 03 (bus_ping.py --post).
Manual twin = этот скилл. Single source of truth = wisdom_week_gather.py.

## Связано
Карта A–E: пункт D · /five-hard (месяц) · /precedent (решения) · recurring_scan.py
(весь корпус) · vault-backup-rule · model-routing (синтез → Opus).
