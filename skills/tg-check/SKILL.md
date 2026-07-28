---
name: tg-check
description: Per-machine self-test of BOTH Telegram channels (MCP + Telethon rail) — does THIS computer's Telegram work on both rails? Trigger on "/tg-check", "/tgcheck", "проверь телеграм каналы", "оба канала телеги работают?", "проверь mcp и telethon", "телега жива на этом компе?", "check telegram channels", "are both tg rails up". Runs the deterministic detector (0 tokens) AND the TRUE in-session MCP probe (a script can't test the MCP — only an in-session tool call can). Reports a 🟢/🔴 matrix per channel + the runbook on RED. Local per-machine twin of the hub-only connector-health-daily watchdog.
---

# /tg-check — оба канала Telegram на ЭТОЙ машине

Антон (2026-06-27): «каждый комп проверяет РАБОТАЕТ ли у него ОБА канала телеграм MCP / telethon».
Локальный само-тест: **этот** компьютер проверяет **свои** два телеграм-рельса. Не путать с
хаб-only `connector-health-daily` (централизованный). Канон корня = Библия
`reglament-shina-telegram-bez-mcp-i-svoya-sessiya-na-mashinu`.

## Почему два шага (важно, не срезать)
- **Telethon-рельс** проверяется ДЕТЕРМИНИРОВАННО и БЕЗОПАСНО (общий лок `_refresh_work_acct_a.lock` → без `AUTH_KEY_DUPLICATED`).
- **MCP скриптом честно НЕ проверить** — это stdio-сервер харнесса, доступен только LLM в сессии.
  Скрипт даёт лучший детерминированный сигнал (процесс жив? свежий фатал в логе?), а НАСТОЯЩИЙ
  вердикт MCP даёт ЭТОТ скилл — пробой инструмента в сессии. Память `mcp-health-check`:
  НИКОГДА не поднимать второй Telethon-клиент как health-check (AUTH_KEY_DUPLICATED).

## Шаг 1 — детерминированный детектор (0 токенов)
```bash
PYTHONIOENCODING=utf-8 python "$USERPROFILE/.claude/scripts/tg_channels_check.py"
```
Печатает матрицу по машине: MCP (по процессу + хвосту `mcp_errors.log` — свежий `AuthKeyDuplicated`
= RED-корень; `TypeNotFound` = устаревшая telethon) и Telethon-рельс (GREEN/RED через
`tg_bus_read.py --check`). Exit 1 = что-то RED. Флаги: `--json`, `--notify` (на RED пингует шину).

## Шаг 2 — НАСТОЯЩИЙ тест MCP в сессии (решает вердикт MCP)
- **Есть ли инструменты Telegram MCP в этой сессии?** Если `mcp__telegram__*` НЕ загружены вовсе
  (нет в списке инструментов / ToolSearch их не находит) → MCP **RED: не загружен в сессию**.
- Если есть — вызвать ОДИН дешёвый read-инструмент: `mcp__telegram__list_accounts` (или `get_me`,
  ждём Tony/@work_acct_a). Ответил без ошибки → MCP **GREEN**. Ошибка (AuthKeyDuplicated / timeout) →
  **RED** + причина из ошибки.
- ⚠️ Ровно ОДИН дешёвый вызов. Не звать `get_history`/`search_dialogs` (тяжёлые → могут уронить MCP).

## Шаг 3 — объединить и доложить (🟢/🔴 матрица)
Слить детектор (Шаг 1) + живой MCP-пробой (Шаг 2) в один вердикт на машину:
```
=== Telegram: оба канала @ <машина> ===
🟢/🔴  MCP (chigwell)  : <вердикт Шага 2 — он главный> — <причина>
🟢/🔴  Telethon-рельс   : <вердикт Шага 1>
```
- Вердикт MCP из Шага 2 (живой) БЬЁТ деттектор Шага 1 (косвенный) — лог может отставать.
- На RED — дать рунбук (ниже). На обоих 🟢 — одна строка «оба канала живы».

## Рунбук на RED (из Библии)
- **MCP RED + `AuthKeyDuplicated`** → КОРЕНЬ: одна TG-сессия на 2+ машинах. Пластырь = перезапустить
  Claude Code (харнесс поднимет MCP заново; снова словит корень). Durable = у каждой машины СВОЯ
  TG-сессия (Правило B Библии) — координирует хаб, оператор логинится локально.
- **MCP RED + `TypeNotFound`** → устаревшая telethon в `C:\mcp\telegram-mcp\.venv` → обновить.
- **MCP «не загружен в сессию»** → перезапустить Claude Code (или открыть сессию, что грузит MCP).
- **Telethon-рельс RED** → нет/битая `REFRESH_*` в `$IMPORTS_ROOT/dialogs/.env` на этой машине,
  либо группа недоступна → проверить `.env`/доступ к группе `-815238009`.
- **Шина всё равно жива через рельс** (если он 🟢): `tg_bus_read.py` / `tg_bus_send.py` — MCP не нужен.

## На рутину? (предложить, не навязывать — правило «recurring → routine»)
Если Антон хочет, чтобы КАЖДЫЙ комп сам сторожил оба канала — оформить ночную задачу (окно
23:00–06:00 Лиссабон) `python tg_channels_check.py --notify` на каждой машине: молча зелёное,
на RED пинг в шину/Saved. Это локальный страж (детерминированный, без LLM); хаб-страж
`connector-health-daily` остаётся централизованным. Решает Антон.

## Границы
- Только чтение/диагностика. Реконнект MCP = перезапуск Claude Code (из сессии stdio-MCP не поднять).
- Развод TG-сессий по машинам = мульти-машинное (Tier-2) → координировать с хабом.
- Канон: Библия `reglament-shina-telegram-bez-mcp-i-svoya-sessiya-na-mashinu`, память
  `machine-bus-telegram-rail`, `connector-health-watchdog`, `mcp-health-check`.
