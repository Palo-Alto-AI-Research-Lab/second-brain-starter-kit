---
name: five-hard
description: >-
  Five Hard Questions — раз в месяц (или по запросу) брейн САМ задаёт Антону 5 трудных вопросов
  по его же убеждениям и кодексу (belief-* + concept-bible-*), где он давно НЕ пересматривал
  позицию. Не дать assumptions окаменеть. Trigger on "/five-hard", "5 hard", "пять трудных",
  "задай мне трудные вопросы", "challenge my beliefs", "pressure-test my views".
  Часть «активного брейна» (B из карты A–E). DISTINCT from /coach (день) — тут ДАВНИЕ позиции.
---

# /five-hard — пять трудных вопросов

> 🧒 К Антону — в конце recap «Простыми словами».

**Зачем:** identity-слой (`belief-*` + `concept-bible-*`, ~24 заметки) = «как я думаю».
Опасно, если часть уже неверна, а никто не проверил. Брейн сам инициирует pressure-test.

## Run
`python "$IMPORTS_ROOT/five_hard_pick.py"` → 5 самых застоявшихся (oldest mtime) заметок
→ `$IMPORTS_ROOT/_five_hard_pick.json`. Override: env `FIVE_HARD_N=7`.

## Вопросы (Opus-качество — identity-синтез, не грунт)
Прочитай каждую заметку ЦЕЛИКОМ и дай ОДИН трудный вопрос на каждую:
```
N. **[<stem>]** — <тезис Антона своими словами>
   Вопрос: <острый сократический, способный заставить пересмотреть>
   Почему трудно: <какой контр-факт/тенденция могла бы перевернуть>
```
Стиль: сократично, не «ты неправ», а «откуда уверен сегодня?»; опирайся на КОНКРЕТНЫЕ свежие
сигналы; `epistemic-neutrality`; бей в НЕПРОВЕРЕННУЮ грань (секция «Напряжение / нюанс»),
не в отрефлексированную. Валидный ответ: «правило стоит» (`bible-as-prompt`).

## Запись ответа (длинная память; backup-first: vault_backup.py)
→ `$OBSIDIAN_VAULT/04-Coach/_Five-Hard/five-hard-YYYY-MM-DD.md`
Frontmatter: title, date, `type: five-hard`, `source: claude-session`,
`tags: [five-hard, coach, identity-layer]`. Тело: вопросы + ответы Антона дословно;
изменил позицию → предложи diff к belief/bible с `supersedes:` (через `/intake`). NO 🧒 в заметке.

## Scheduled twin
Cron `five-hard-monthly`: 1-е число 05:25 Lisbon (окно брифингов, `routines-run-at-night`).
Picker → вопросы (Opus-субагент) → **TG чат 03** через `python $USERPROFILE/.claude/scripts/bus_ping.py --post "..."`
(канон `cc-alerts-to-chat-03`; Saved ⛔) + «отвечай голосом/текстом — запишу в волт».
Manual twin = этот скилл; single source of truth = picker.

## Связано
[[self-bible-identity-layer]] · [[bible-as-prompt]] · [[epistemic-neutrality]] · /coach (день) vs
/five-hard (месяц). Карта A–E: пункт B. ⚠️ Восстановлен 2026-07-04 после migration-wipe 24.06.
