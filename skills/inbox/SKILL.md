---
name: inbox
description: Check this machine's cross-machine mailbox — messages Claude on Anton's OTHER computer left for Claude here (via the Syncthing-synced `_machine-bus` folder, no Telegram, no courier). Trigger on "/inbox", "глянь инбокс", "что мне пришло", "проверь инбокс", "сообщения от другого компа", "что в инбоксе", "check inbox", "messages from the other machine". Also how to SEND a message to Claude on another machine. The SessionStart hook already auto-shows new messages at session start; this is the on-demand re-check mid-session. Engine = ~/.claude/scripts/machine_bus.py (one source of truth, synced via claude-config). Canon: vault reglament-multi-machine-claude-i-peredacha-mezhdu-mashinami + memory machine-migration.
---

# /inbox — почта между моими машинами

Канал «Claude на одной машине → Claude на другой» через синканную папку `_machine-bus` (Syncthing, ~10 сек). Убирает Антона-курьера. Курьер (копипаст) = ТОЛЬКО аварийный канал.

## Проверить, что мне пришло (основное)
```bash
python "$USERPROFILE/.claude/scripts/machine_bus.py" read
```
Покажет только НОВОЕ для ЭТОЙ машины (по имени компа) и пометит прочитанным. Затем доложи Антону, что пришло, и при необходимости выполни/учти это.
- На старте сессии это уже делает хук `SessionStart` автоматически — `/inbox` нужен, когда Антон говорит «глянь инбокс» в середине сессии (например, новое прилетело синком).
- Пере-проверить, не помечая прочитанным: `... read --peek`.

## Послать сообщение Claude на ДРУГОЙ машине
1. Узнать имена доступных ящиков:
   ```bash
   python "$USERPROFILE/.claude/scripts/machine_bus.py" list
   ```
2. Отправить:
   ```bash
   python "$USERPROFILE/.claude/scripts/machine_bus.py" send <ИМЯ-КОМПА-ПОЛУЧАТЕЛЯ> "текст сообщения"
   ```
   Сообщение самодостаточно (у Claude на той машине нет контекста этой сессии — вложи цель, шаги, пути, значения). Долетит за ~10 сек, всплывёт у получателя на старте сессии или по `/inbox`.

## Когда какой канал
- **Авто-ящик (этот скилл + хук)** — норма для всего межмашинного.
- **Курьер (копипаст через Антона)** — ТОЛЬКО если синк лёг / нужно вне общей сети / очень срочно.

## Границы
- Не слать секреты в ящик, если файл могут увидеть третьи лица (у Антона на его машинах — ок).
- «Свежее бьёт старое»: конфликт правок решает Антон (Syncthing создаёт `*.sync-conflict-*`).
- Доставка не мгновенная: Claude — не демон; письмо ждёт, пока на той машине не откроется сессия (или не сработает рутина).
