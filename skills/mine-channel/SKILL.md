---
name: mine-channel
description: Mine ANY Telegram channel/chat for alpha in one command — scrape (0-token Telethon) → deterministic detector shortlist → Sonnet judge (real alpha FOR Anton) → well-linked vault notes + db + MOC + reindex. Trigger on "/mine-channel <@channel|id>", "затащи канал <X>", "отожми альфу из <канал>", "намайни <канал>", "разбери канал <X>", "mine this channel", "alpha from <channel>". The generalised version of the proven Fox / prompt_design / Силиконовый Мешок / Состав / Lobster runs (done manually 5×). THIN wrapper over $IMPORTS_ROOT/alpha/mine_channel.py + the alpha-judge skill + obsidian-ingest — does NOT re-implement them. Canon: memory alpha-extraction-engine, sostav-community-import, promptdesign-mine, foxpod-mine.
---

# /mine-channel — затащить канал и отжать альфу одной командой

> 🧒 В конце ответа Антону — простой recap «Простыми словами» (memory `eli5-always`).

Обобщает повторённый ≥5 раз вручную паттерн (Фокс · prompt_design · Состав · Lobster). Лестница стоимости [[vault-data-architecture]]: детерминированный детектор (0 токенов) → LLM-судья только по шортлисту → волт.

## Шаги

**0. RECALL (не дублируй).** Канал уже майнили? Проверь `$IMPORTS_ROOT/alpha/<slug>\` и память (`*-mine`, `sostav-community-import`). Если да — это ДОЗАБОР: тот же slug, инкремент.

**1. Резолв канала.** Юзернейм (`@prompt_design` / `prompt_design`) или числовой id (`-1000800842092`). Если не знаешь id — `mcp__telegram__search_dialogs` или `/chat <имя>`. Выбери короткий латинский **slug** (напр. `silmeshok`).

**2. Скрейп + детектор (0 токенов, 0 GPU):**
```
set PYTHONIOENCODING=utf-8
python $IMPORTS_ROOT/alpha/mine_channel.py --channel <name|id> --slug <slug> [--limit N] [--top 40] [--since YYYY-MM-DD --until YYYY-MM-DD]
```
→ `_imports\alpha\<slug>\<slug>.jsonl` + `<slug>.db` + шортлист `_imports\alpha\candidates\<slug>-report.md`.
(Скрейп идёт через подписочную Telethon-сессию `C:/mcp/telegram-mcp/.env` work_acct_a — НЕ платный API [[prefer-included-limits-before-paid-api]]. Повторный запуск без `--channel` + `--detect-only` = пере-детект без пере-скрейпа.)

**3. Судья (LLM, только по шортлисту).** Прогони шортлист через **Sonnet** (грунт → Sonnet [[model-routing-sonnet-grunt]]; субагент `model:'sonnet'` или skill `alpha-judge`): оставь только РЕАЛЬНУЮ альфу ДЛЯ АНТОНА (инструмент/модель/сделка · техника/воркфлоу · ментальная модель · пруф-поинт/бенчмарк · билд-паттерн), выкинь промо/баянтер/то-что-мы-уже-делаем-лучше. Вердикт ✅ alpha · 🟡 watch · 🗑 шум.

**4. В волт (obsidian-ingest).** Бэкап-фёрст [[vault-backup-rule]]. ✅-альфу → атомарные заметки + концепт-линки ([[no-orphan-notes-rule]]) + MOC `_<Slug>-MOC`; чувствительный канал → `#private`. Оригинал jsonl остаётся в `_imports\alpha\<slug>\` (это и есть _originals для канала). Реиндекс [[reindex-routine]] (или ночной подхват).

**5. На рутину? ([[evaluate-recurring-into-routine]])** Ценный канал → предложи еженедельный дозабор (ночное окно [[routines-run-at-night]]).

## Границы
Детектор обобщённый (AI/tool/deal/стартап-ключи); под конкретный канал KW/PROMO тюнятся в `mine_channel.py`. Чувствительность: закрытые/adult/личные каналы → `#private`, не светить наружу. Только чтение канала, ничего туда не слать.
