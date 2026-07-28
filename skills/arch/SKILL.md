---
name: arch
description: Read Anton's "System Architect" map — the deterministic catalog of EVERYTHING the system is made of (vault + _imports scripts + scheduled tasks + MCP + SQLite DBs + hooks + skills + dashboards), what's healthy, and what fell off. Trigger on "/arch", "/arch broken", "/arch scan", "/arch dead", "проверь систему", "что сломалось в системе", "карта системы", "статус системы", "arch status", "system health", "what's broken". READ-ONLY by default (`/arch scan` re-catalogs). The STANDING rule: consult /arch BEFORE changing shared infrastructure, run /arch scan AFTER. Wraps $IMPORTS_ROOT/arch/ (sys_scan.py → system.db → arch_status.py). Canon = memory system-architect + decision-architect-system-platform + Bible reglament-pered-izmeneniem-sistemy-sverstis-s-kartoy-arch.
---

<!-- RECONSTRUCTED 2026-06-24 on hub HUB-1 from the live engine ($IMPORTS_ROOT/arch) + memory system-architect, because the authoritative SKILL.md lives only on laptop LAPTOP-1 (~/.claude/skills/arch, not synced). When the laptop's copy arrives via _machine-bus, RECONCILE and replace if it differs. -->

# /arch — System Architect (карта и здоровье всей системы)

Одно место, которое знает: из чего система состоит, что здорово, что отвалилось — и тестирует это. Детерминированно, 0 токенов, READ-ONLY. Это **RECALL для инфра-слоя**: смотреть ДО изменения общей инфраструктуры, пересканировать ПОСЛЕ.

**Движок:** `$IMPORTS_ROOT/arch/` (git-бэкап в `_imports`). Источник истины — `system.db` (строит ночной скан 05:45). Дашборд `_Dashboards\System-Health.html`, MOC `00-System\_System-MOC.md`, авто-инвентарь `00-System\System-Automations.md` (заменяет ручной [[automation-inventory]]).

## Команды

```bash
# статус (по умолчанию) — сводка здоровья + score
python "$IMPORTS_ROOT/arch/arch_status.py"

# только сломанное / красное
python "$IMPORTS_ROOT/arch/arch_status.py" broken

# мёртвый код — скрипты, ни к чему не подключённые
python "$IMPORTS_ROOT/arch/arch_status.py" dead
```

- **`/arch`** → `arch_status.py` (статус).
- **`/arch broken`** → `arch_status.py broken`.
- **`/arch dead`** → `arch_status.py dead`.
- **`/arch scan`** (форс свежий скан, ПОСЛЕ изменения инфраструктуры) → перекатать каталог:
  ```bash
  cd /d $IMPORTS_ROOT/arch
  python sys_scan.py && python sys_coverage.py && python build_system_docs.py && python build_arch_map.py && python sys_check.py
  ```
  (Это и есть пайплайн `run_architect.cmd` без финального `vault_backup.py`. Полный ночной прогон = `run_architect.cmd`, задача «System Architect Nightly» 05:45.)

## Когда применять (STANDING — always-loaded правило)
- **ПЕРЕД** добавлением/удалением/изменением общей инфраструктуры (scheduled-задача, скрипт `_imports`, MCP, БД, хук, скилл, пайплайн) → `/arch` / `/arch broken`: что есть и что от этого зависит — не сломаю ли смежное.
- **ПОСЛЕ** изменения → `/arch scan`, чтобы карта не отстала от реальности.
- **RED** → сперва разберись с красным; `result!=0` у задачи ≠ всегда «сломано» (бывает доброкачественная lock-коллизия — проверь источник). Не удаляй `active`/`critical`-актив, не разобравшись в зависимостях.

## Грабли (из памяти)
- Метрика покрытия должна ИЗМЕРЯТЬ артефакт, а не хардкодить вердикт (ложная тревога backup-строки, 2026-06-22).
- `RED.flag` пишется только на critical/daily-fail (SRE: алертим на симптом). Phase-5 routine `system-architect-red-alert` (06:21) пингует Telegram Saved 226258979 при красном, молчит при зелёном.

## Канон
Память [[system-architect]] · решение `decision-architect-system-platform` · Библия `reglament-pered-izmeneniem-sistemy-sverstis-s-kartoy-arch` (для людей-ассистентов и LLM тоже). Связано: [[verify-existing-before-proposing]], [[automation-inventory]], [[vault-data-architecture]].
