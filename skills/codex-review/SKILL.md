---
name: codex-review
description: "Двусторонняя гетеро-пара ревью кода: Claude ревьюит дифф Codex И Codex ревьюит дифф Claude — финальную проверку делает ДРУГОЙ вендор (исследование `tap`: 69.8% против 53.1% у однородной пары). Оба движка собраны и /tt'd (cc_review.py 07.07 + codex_review.py, нативный codex exec без WSL2). ✅ На хабе HUB-1 обе стороны РАБОТАЮТ: Codex CLI 0.144.4 установлен и smoke-тест прогнан 14.07 (баги→REQUEST_CHANGES за 16с, чистый→APPROVE, пустой→graceful). Вердикт APPROVE / REQUEST_CHANGES + review-*.md. Триггеры: «/codex-review», «проверь кодекс», «claude проверь codex», «codex проверь claude», «отревьюй дифф», «двусторонняя пара», «review the diff», «review codex», «вторая пара глаз». Движки: ~/.claude/scripts/cc-review/cc_review.py (Claude→Codex) + codex_review.py (Codex→Claude). Канон: decision-hermes-multivendor-arbitrage-rejected (вариант B), [[any-llm-vault-actor]] Phase 3."
---

# codex-review — «Claude проверяет Codex»

Тонкий брокер ревью-пары. Codex пишет код; Claude независимо ревьюит его дифф. (Старая заметка «`codex exec` headless на Windows виснет» устарела: на codex-cli 0.141+ headless работает нативно — проверено 07.07 на ноуте и 14.07 на хабе.) Файловый хэндофф, без общих кредов, подписка (не платный API).

## Когда запускать
Антон сделал изменение через Codex (или просто есть дифф/правка в репозитории) и хочет независимую проверку «второй парой глаз». Триггеры см. в `description`.

## Что делаю
1. **Определяю цель.** Спрашиваю/беру путь к репозиторию, где Codex внёс изменение (или путь к патч-файлу). По умолчанию — рабочий репозиторий, который Антон назвал.
2. **Запускаю движок** (детерминированно, 0 моих токенов на сам прогон — ревью делает headless `claude -p`):
   ```
   python "%USERPROFILE%\.claude\scripts\cc-review\cc_review.py" --repo "<путь к репо>" --model sonnet
   ```
   - модель: **Sonnet по умолчанию** (бесплатный бак подписки, на тесте поймал оба бага за 25с); **Opus** для трудных/safety-critical изменений (`--model opus`) — гейт качества.
   - другие режимы: `--range "HEAD~1 HEAD"` (конкретный коммит), `--diff "<патч.diff>"` (готовый патч), `--task "<task.md>"` (что Codex просили сделать — даёт ревьюеру контекст).
3. **Подаю результат Антону:** вердикт (`APPROVE` / `REQUEST_CHANGES`), список находок (file:line · severity · что не так · фикс), и путь к `review-<ts>.md`. Если REQUEST_CHANGES — предлагаю починить корень (а не симптом).

## Границы
- Движок принудительно гасит `ANTHROPIC_API_KEY` → ревью идёт по подписке, не по платному ключу.
- Гигантский дифф обрезается до 120k символов (с пометкой) — если упёрлись, ревьюить по частям/по файлам.
- Это РЕВЬЮ, не авто-правка: фиксы предлагаю/делаю отдельно по AK-47 (легко-обратимое — сам; развилка — спрашиваю).
- Полную авто-пару (Codex headless тоже) можно достроить позже под WSL2/Docker — отдельный шаг (сейчас не нужно).

> **2026-06-28 (хаб HUB-1):** движок `cc_review.py` был утрачен (нет в git/`.stversions`/на дисках) → **пересобран** как простой Windows-нативный «обычный режим» (вызов выше). Прогнан вживую (`/tt`): баги→`REQUEST_CHANGES`, чистый→`APPROVE`, пустой/не-репо→graceful. Артефакты вне волта (`reviews/`), счётчик `reviews/_log.jsonl`. ⚠️ Канон-обновление в [[decision-hermes-multivendor-arbitrage-rejected]] (аддендум 28.06).

## ⭐ Двусторонняя гетеро-пара (обе стороны работают на хабе)
Полная симметрия: обе стороны ревьюят друг друга, финальную проверку всегда делает ДРУГОЙ вендор.
- **Claude → ревьюит Codex** (прямой) — РАБОТАЕТ: `python "%USERPROFILE%\.claude\scripts\cc-review\cc_review.py" --repo "<репо>" --model sonnet` (см. выше).
- **Codex → ревьюит Claude** (обратный, зеркало) — РАБОТАЕТ И НА ХАБЕ: `python "%USERPROFILE%\.claude\scripts\cc-review\codex_review.py" --repo "<репо>"` — движок /tt-проверен 2026-07-07 (ноут, codex-cli 0.141.0) и 2026-07-14 (хаб `HUB-1`, codex-cli 0.144.4: `npm i -g @openai/codex`, логин ChatGPT-подписка уже был в `~/.codex/auth.json`; smoke: подложенные баги→REQUEST_CHANGES с точными file:line за 16с · чистый дифф→APPROVE · пустой дифф→graceful без вызова Codex). Нативный `codex exec -s read-only` на Windows без WSL2. Флаги: `--range "HEAD~1 HEAD"`, `--diff <патч>`, `--task <task.md>`, `--timeout 300`. Read-only песочница: Codex только рассуждает над диффом. Вывод: `review-codex-<ts>.md` + `VERDICT: APPROVE|REQUEST_CHANGES`.

## Полный авто-режим WSL2 (архивный путь — НЕ развёрнут на хабе)
⚠️ Оркестратор `codex_pair.py` на хабе `HUB-1` отсутствует в живом дереве (уцелел лишь в снапшоте `_config-backup\snapshot-2026-07-04`), WSL2 тут не установлен → режим не запускается. Чтобы поднять: восстановить `codex_pair.py` из снапшота + поставить WSL2/Codex, затем `/tt`.
Исторический контекст (машина, где строили 2026-06-22): WSL2 Ubuntu-24.04 + Node22 + Codex 0.142.3 (залогинен ChatGPT), `codex exec --full-auto` headless. Что делал: Codex реализует задачу headless в WSL → берёт git-дифф → Claude ревьюит (`cc_review.py`) → вердикт + `codex-change-*.diff` + `review-*.md`. Репо в Linux-fs WSL (`/root/...`); нормализатор путей выправлял искажение Git-Bash `/root/...`.

## Расширение — обратная сторона ГОТОВА (хаб полностью двусторонний с 2026-07-14)
Обратная сторона (Codex ревьюит Claude) построена = `codex_review.py` (см. блок «Двусторонняя гетеро-пара»), нативный `codex exec` на Windows. Codex CLI установлен на хаб `HUB-1` 2026-07-14 (`npm i -g @openai/codex`, v0.144.4, логин по ChatGPT-подписке) и smoke-тест пройден — гетеро-пара работает в обе стороны. Тем же днём развёрнут и на **Якорье** (ANCHOR-1, headless: `auth.json` переносим scp'ом, browser-OAuth не нужен; оба движка + smoke ✅) — Якорь = дополнительный узел, живые тесты дуэта только в чате 04 с хаба.
