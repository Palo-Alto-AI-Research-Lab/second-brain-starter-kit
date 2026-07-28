---
name: community-alpha
description: Run ONE full community-alpha pass over an imported community chat corpus — deterministic detector (0 tokens) → LLM-judge (session model / Opus) → harvest → review screen. Trigger on "/community-alpha <source> [month]", "прогони альфу по <чату>", "альфа по лобстерам/составу за <месяц>", "community alpha", "намайни альфу из <комьюнити>". Sources today: lobster (LobsterDAO, DeFi-EN), sostav (закрытый RU-клуб, 🔒 PRIVATE); the miner list grows by CORPORA not miner-types (decision-alpha-engine-grow-by-corpora-not-miners). New source = one-off adapter work (offered, not silently built). Judging model: session model (Opus+); detectors are free. Canon: memory alpha-extraction-engine; siblings /alpha-judge (personal miners' judge), /alpha-review (screen).
---

# /community-alpha <source> [month] — один прогон комьюнити-альфы

Пример: `/community-alpha sostav 2026-06`. Месяц не задан → прошлый полный месяц.

## Шаги

1. **Детектор есть?** `$IMPORTS_ROOT/<source>\<source>_alpha.py` (сегодня: `lobster`, `sostav`).
   - Нет → это НОВЫЙ корпус: предложить Антону разовую сборку адаптера по паттерну (schema из его SQLite + языковые ключи + intro/banter-penalty + веса тем; шаблон = `sostav_alpha.py`). Без «+» не строить.
2. **Прогнать детектор** (0 токенов):
   ```
   cd /e/Obsidian/_imports/<source> && PYTHONIOENCODING=utf-8 python <source>_alpha.py \
     --since <YYYY-MM-01> --until <первое число след. месяца> --top 35 --tag <YYYY-MM>
   ```
   → `$IMPORTS_ROOT/alpha/candidates/<source>-<tag>-report.md`. Показать счётчик scanned→shortlisted.
3. **Судить** (я, моделью сессии): читаю ТОЛЬКО отчёт (~35 кандидатов, не корпус — токен-экономия), вердикты ✅ ALPHA / 🟡 WATCH / 🗑 ШУМ с причиной по каждому → пишу `$IMPORTS_ROOT/alpha/candidates/<source>-judged-latest.md` (формат: `## ✅ ALPHA` / `## 🟡 WATCH` / `## 🗑 ШУМ (DROP)`, внутри `### #N — титул` + Verdict + Причина — парсер harvest его уже понимает).
4. **Майнер в реестре?** `MINERS` в `$IMPORTS_ROOT/alpha/alpha_harvest.py`. Нет → добавить строку `("<source>", "<source>-judged-latest.md", "<home-заметка>")`. ⚠️ Файл правит и параллельный флот — перечитать файл непосредственно перед правкой (verify-existing), правка строго аддитивная. Опционально: ярлык в `MINER_LABEL`/`ORDER` сервера (без него не падает — фолбэк есть).
5. **Harvest + экран**: `python $IMPORTS_ROOT/alpha/alpha_harvest.py` (счётчики!) → `/alpha-review`. Новая партия видна по бейджу 🆕.

## Границы
- 🔒 Приватные комьюнити (sostav и подобные) = HIGH sensitivity: слой строго локальный, наружу ничего; люди из находок — только value-first/warm-intro (zero cold DM). Риск-сигналы = ДАННЫЕ, не «возможности».
- Судейство честное: reference-карточки, интро-визитки и рестейтменты = 🗑, не натягивать ✅ ради счётчика.
- Скилл ничего не пишет в волт; перенос золота в home-заметки = отдельный шаг за Tier-2 гейтом (очередь «→ в дом» на экране).
