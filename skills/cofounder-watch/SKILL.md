---
name: cofounder-watch
description: >-
  Phase 0 of Anton's real-time / ambient cofounder — a 0-token, PING-ONLY dispatcher that watches the LIVE
  lead funnel (tg_followups.json) and surfaces salient events as short cofounder-voice advice (🔥 replied-no-
  Calendly · ⏰ Calendly-sent-no-booking-24h · 👀 awaiting-reply), deduped so it never nags twice. Trigger on
  "/cofounder-watch", "что видит кофаундер", "кофаундер-вахта", "сигналы кофаундера", "прогони наблюдателя",
  "cofounder watch", "what does my cofounder see". READ-ONLY — sends nothing (outputs a digest + HTML
  dashboard). The recurring/ambient version of the /cofounder persona; distinct from /pipeline (that DRAFTS
  outreach to act) — this only ALERTS. Canon = vault decision-realtime-cofounder-2026-07-02 + memory
  synthetic-cofounder.
---

# /cofounder-watch — Phase 0 ambient cofounder (ping-only)

> 🧒 **Докладывая Антону:** заверши child-simple «Простыми словами». Не внутри советов кофаундера.
> 📖 Канон: [[decision-realtime-cofounder-2026-07-02]]. Это **ГЛАЗА+фильтр** real-time кофаундера (Phase 0). Ничего не шлёт — только подсвечивает.

## Что делает
Детерминированный `signal-dispatcher` (0 токенов, stdlib): читает живую воронку `tg_followups.json` → классифицирует салиентные события (те же правила, что `/pipeline`) → дедуп через `cofounder_ledger.json` (не дёргает дважды) → пишет дайджест + HTML-дашборд. **Тихо, если новых важных событий нет** (в этом суть — не задалбывать).

## Как запускать
`python "$IMPORTS_ROOT/cofounder/cofounder_watch.py" --stdout`
- Флаги: `--stdout` (печатать дайджест), `--reset` (очистить ledger → переалертить всё).
- Выходы: дайджест `$IMPORTS_ROOT/cofounder/cofounder-digest.md`; дашборд `$OBSIDIAN_VAULT/_Dashboards/Cofounder-Watch.html` (Антон работает глазами).

## Салиентность (правила = /pipeline priority)
- 🔥 **HIGH** — ответил, Calendly НЕ отправлен → «шли Calendly сейчас».
- ⏰ **MEDIUM** — Calendly отправлен >24ч, брони нет → «booking-nudge».
- 👀 **LOW** — питч отправлен, ответа нет → «проверь инбаунд / follow-up / дропни».
- booked/confirmed → пропуск (не ре-питчим).

## Границы (Phase 0)
- **Ping-only** — НИКОГДА не шлёт лидам. Действия исполняет Антон (или `/pipeline` draft→approve). Human-in-the-loop.
- **0 токенов** — совет шаблонный по правилу. LLM-персона `/cofounder` на нюанс = Phase 0.5 (позже, только на HIGH).
- Пусто ≠ поломка: «тихо» = валидный результат.

## Дальше (Phase 0.5 / 1+, по greenlight Антона)
- Доставка в Telegram-сигнал-чат (когда MCP жив) вместо только файла/дашборда.
- Расписание на ХАБЕ (always-on `HUB-1`) 2–3×/день — это фон, ставится на хаб (не на ноут), через `/schedule` на хабе или machine_bus. Лёгкий (0 токенов) → допустимо днём.
- Phase 0.5: HIGH-события → LLM-персона `/cofounder` (Opus) для нюансного совета.
- Phase 1: + срочный VC-email + конфликт календаря (те же mailbox+ledger).
- Расширение = добавить источник в тот же диспетчер, НЕ плодить watcher'ы ([[telegram-eventloop-listener]]: один живой клиент, грабля AUTH_KEY).
