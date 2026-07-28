---
name: brain
description: One-glance health of Anton's "second brain" so failures aren't SILENT — is the :8770 search server alive, is the RAG index fresh (reindex running), is the TurnState memory ledger filling, did the nightly dream run, what's the A/B (Прямая↔Ассоциативная) status. Trigger on "/brain", "/memory", "здоровье мозга", "мозг жив?", "проверь память", "реиндекс жив?", "сервер поиска жив", "brain health", "is my brain ok", "memory health". READ-ONLY (no writes, 0 LLM tokens). Built 2026-06-25 because "чиним реиндекс / сервер 8770 лёг" recurred ~5× — silent failures. Sibling of /arch (system map) but focused on the memory/RAG stack. Canon: memory always-on-memory-pilot, reindex-routine.
---

# /brain — здоровье «второго мозга» одним взглядом

> 🧒 В конце ответа Антону — простой recap «Простыми словами» (memory `eli5-always`).

Ловит ТИХИЕ поломки memory/RAG-стека (то, что в этом месяце ломалось снова и снова: реиндекс, сервер :8770, пилот памяти). Read-only, 0 токенов.

## Что делает (один скрипт)
`python $IMPORTS_ROOT/brain_health.py`

Проверяет 5 вещей и красит 🟢/🟡/🔴:
1. **Поисковый сервер** :8770 — жив ли (если лёг → авто-recall молча пропадает); показывает, включена ли Ассоциативная (граф).
2. **Индекс** `_brain_e5.npy` — насколько свежий (🟡 если реиндекс отстал >48ч).
3. **TurnState-леджер** — сколько ходов записано (Phase 1 памяти), последний когда.
4. **Ночной сон** — кандидаты в карантине + когда последний прогон.
5. **A/B Прямая↔Ассоциативная** — сколько прогонов + твои вердикты (👍/👎).

Пишет дашборд `$OBSIDIAN_VAULT/_Dashboards/Brain-Health.html` (Антон смотрит глазами, [[prefer-visual-dashboards]]). Exit-код 0/1/2 = ok/warn/red (для скриптов).

## Когда чинить (если 🔴/🟡)
- **🔴 сервер :8770** → `restart_brain_server.cmd` (от админа, см. [[always-on-memory-pilot]]); или ребут (AtLogon поднимет).
- **🟡 индекс отстал** → `gpu_check.py [--kill]` затем `brain_embed_update.py [--wait-gpu 10]` ([[reindex-routine]]).
- **🟡 леджер пуст** → норм, если Phase 1 только включился (заполнится со следующих сессий).

## Что НЕ делает
Не чинит сам и не пишет в волт. Это диагностика. Чинит — отдельный явный шаг (правило «прочитай перед починкой» [[verify-existing-before-proposing]]).
