---
name: watch-channel
description: Put a NIGHTLY alpha watcher on ANY Telegram channel/chat in one command - the "make /mine-channel a routine" button. Registers the channel and a single nightly job on the HUB that does incremental fetch (0-token Telethon, min_id) + the shared detector -> a PRIVATE shortlist report. Trigger on "/watch-channel <@channel|id>", "следи за каналом <X>", "поставь ночной watcher на <канал>", "мониторь канал <X>", "watch this channel nightly", "ночной майнер на <канал>". DISTINCT from /mine-channel (one-shot mine) - this is the recurring version. Engine = $IMPORTS_ROOT/watchers/watch_run.py (reuses mine_channel.detect). Canon: memory alpha-extraction-engine, evaluate-recurring-into-routine, deterministic-script-gotchas (AuthKey).
---

# /watch-channel - поставить ночной watcher на канал одной командой

> 🧒 В конце ответа Антону - простой recap «Простыми словами» (memory `eli5-always`).

Это «кнопка превратить `/mine-channel` в ночную рутину» (его Шаг 5 «на рутину?»). Один параметрический раннер + реестр + ОДНА ночная задача на хабе - не пишем новый движок под каждый канал. Лестница стоимости [[vault-data-architecture]]: инкрементальный детектор (0 токенов) ночью → LLM-судья ТОЛЬКО по запросу (`/alpha-judge`), НЕ в кроне.

Граница с соседями: **`/mine-channel`** = разовый майн (полный скрейп + судья + волт). **`/watch-channel`** = поставить на ночной автопилот (инкремент + детектор → приватный отчёт; судья остаётся ручным). **`/chat`** = найти id канала.

## Шаги

**0. RECALL (не дублируй).** Канал уже под watcher'ом? Прочитай `$IMPORTS_ROOT/watchers/watchers.json` - если slug есть и `active:true`, это уже работает (скажи Антону, не плоди второй). Легаси Состав/Lobster - свои движки, НЕ через этот реестр.

**1. Резолв канала → id + slug.** Юзернейм (`@prompt_design`) или числовой id. Не знаешь id - `/chat <имя>` или `mcp__telegram__search_dialogs`. Выбери короткий латинский **slug** (он же папка `_imports\alpha\<slug>`).

**2. Развилка-подтверждение (показать ДО→ПОСЛЕ, дождаться `+`).** Спроси/подтверди 3 вещи, потому что тут есть нетривиальные выборы (это не «слепое да», [[informed-consent-explain-why]]):
- **аккаунт-сессия** - под каким TG-аккаунтом читаем (этот аккаунт должен быть подписан/иметь доступ к каналу). Дефолт `TELEGRAM_SESSION_STRING_WORK_ACCT_A`. ⚠️ **AuthKey-инвариант** ([[deterministic-script-gotchas]]): сессия watcher'ов НЕ должна одновременно использоваться живым MCP с другого IP - иначе Telegram аннулирует ключ. Все watcher'ы крутятся **последовательно на ХАБЕ под одной сессией** - безопасно; но если выбранный аккаунт = тот, под которым висит живой listener, выбери выделенный `..._WATCH`-сейф.
- **чувствительность** - закрытый/деликатный канал → `sensitivity:"private"` (анти-утечка на ВЫХОДЕ - отчёт никогда наружу/публично, [[telegram-safety]]).
- **окно/топ** - `window_days` (дефолт 3), `top` (дефолт 25).

**3. Зарегистрировать.** Допиши объект в `watchers.json → watchers[]` (поля - в `_fields` файла), `active:true`. Это весь «код» нового канала - новой задачи планировщика заводить НЕ нужно (одна общая задача гоняет весь реестр).

**4. Поставить/убедиться в ночной задаче - НА ХАБЕ** ([[hub-master-machine]], [[desktop-max-laptop-min]]; ночное окно [[routines-run-at-night]]). Все авто-телеграм-джобы консолидированы на always-on хабе. Если `WatchChannelsNightly` ещё нет - завести её там (через `_machine-bus` задачу хабу, [[machine-bus-telegram-rail]]):
- команда: `watch_run.cmd` → `python $IMPORTS_ROOT/watchers/watch_run.py` (PYTHONUTF8=1, PYTHONIOENCODING=utf-8, лог в `_watch_run_log.txt`);
- слот в ночном окне, **разнесён** от Состав 03:30 / Lobster 04:15 / voice - напр. **04:45**;
- `_imports` НЕ синкается → застейджить движок в `_machine-bus\_transit\_imports-engines\watchers\` и попросить хаб скопировать.
Если задача уже есть - просто реестр обновился, новый канал подхватится следующей ночью.

**5. Доказать (`/tt`), когда сессия жива.** Разовый прогон одного канала: `python $IMPORTS_ROOT/watchers/watch_run.py <slug>` → проверь, что появился `_imports\alpha\candidates\<slug>-report.md` и счётчик `+N new`. Повторный прогон = `+0` (идемпотентно). ⚠️ Проверяй и СОДЕРЖИМОЕ отчёта, не только счётчики: в нём должны быть кликабельные `t.me/...`-ссылки (для этого в реестре у канала поле `username` - без него detect() получает числовой id и ссылок не пишет; грабли поймали 2026-07-04). На ноуте с мёртвой/чужой сессией live-тест пропусти - первый прогон на хабе.

## Управление
- **список:** прочитать `watchers.json` (или `/arch`).
- **снять/пауза:** `active:false` (не удаляй - история и db остаются).
- **отчёты:** `_imports\alpha\candidates\<slug>-report.md` (перезаписывается ночью, последний - свежий). Хочешь в волт - прогони `/alpha-judge` или Шаг 4 `/mine-channel` (судья → atomic-заметки + концепт-линки).

## Границы
Только ЧТЕНИЕ канала, ничего туда не слать. Детектор обобщённый (KW/PROMO/BANTER в `mine_channel.py`); под конкретный канал тюнится там же. Чувствительные каналы → `#private`, никогда наружу. Судья (LLM) - ТОЛЬКО по запросу, не в ночном кроне (токен-экономия).
