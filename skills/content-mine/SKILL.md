---
name: content-mine
description: "Ручной прогон КОНТЕНТ-МАЙНЕРА — вычитать наши сессии Claude Code и положить контентно-достойные моменты ЧЕРНОВИКАМИ в воронку (draft-first). Триггеры: /content-mine, «намайни контент», «прочеши сессии на контент», «что достойно поста из сессий», «mine sessions for content». Тонкая обёртка над content_miner.py (детектор 0 токенов → судья-вкус → capture в posts.jsonl source_kind session). Ручной аналог ночного backstop content-miner-nightly. НЕ путать с /episode (сборка эпизода из готового пост-материала), /wow (веха вне очереди), voice-triage (голос чата 00). Канон: память [[content-miner-reflex]], [[everything-becomes-content]]; движок $IMPORTS_ROOT/content-factory/content_miner.py."
---

CONTENT_MINE — sessions → funnel drafts (draft-first, вкус за мной)

ЦЕЛЬ: намайнить из наших сессий Claude Code контентно-достойные МОМЕНТЫ и сложить их ЧЕРНОВИКАМИ в воронку контент-фабрики. Публикация — только «+» Антона через /episode. Ничего наружу.

Антон делегировал вкус «что достойно контента» мне (2026-07-08). Не переспрашиваю, что добавить — решаю сам.

ПУТИ:
- Движок: `$IMPORTS_ROOT/content-factory\content_miner.py` (семья alpha-extraction / intention_mine; читает живой пул `vault_sessions`).
- Воронка (интейк): `content-factory\triage\posts.jsonl` (+ `posts.md`), `source_kind: session`. Пишет через `voice_triage.py append` (дедуп/upsert).
- Дайджест: `content-factory\miner\candidates\cand-latest.md`. Леджер: `miner\captured.jsonl`.

ШАГИ:
1. СКАН (детерминированно, 0 токенов). По умолчанию свежее: `python content_miner.py mine --days 7`. Долг/весь архив: `mine --all --operator Anton --cap 150`. Флаги: `--day YYYY-MM-DD`, `--operator all`, `--cap N`. Запомни `OVER_THRESHOLD` и `OUT`.
2. Пусто (SESSIONS=0 / OVER_THRESHOLD=0) → скажи «свежих достойных моментов нет» и стоп.
3. ЧИТАЙ дайджест `cand-latest.md` (или `OUT`). Каждый ### = сессия `src | дата | машина | оператор [PRIV] {score · tags}` + заголовок + сниппеты ([U]=Антон, [A]=Claude). Смотри верхние (HOT→WARM); при большом объёме — фан-аут Sonnet-судей по слайсам (см. `miner\slices\`), они возвращают JSON-вердикты, ты дедупишь и захватываешь.
4. СУДИ ВКУСОМ: оставь по-настоящему достойные РАЗНЫЕ истории (собрал/зашипил · война с багом/root-cause · human+AI/мультимашинный/консенсус приём · острый инсайт · «вау»). Отбрось рутину, тонкое, форки-дубли (похожий заголовок → одна история), чисто приватное. Позиционирование: не-кодер+AI = козырь, цель — оффер от LLM-компании + аудитория билдеров.
5. ЗАХВАТИ достойные: `python content_miner.py capture --src <cc:xxxxxxxx> --title "<хук>" --note "<суть>" --tier teaser|medium|longread|dev-log --angle "<угол>" --visibility public|personal|private`. Тир: teaser=хук; medium=дневник FB; longread=нарратив; dev-log=сухой технический. [PRIV]/неочищаемое → `--visibility personal`. Движок блокирует секрет-токены и дедупит по src.
6. МОСТ В КАНОН (закон «событие → сначала бит → потом пост», [[show-canon-single-source]]): для 1–2 самых сильных public-моментов создай черновик БИТА в `04-Projects\show-canon\beats-inbox\` по шаблону `beats\_TEMPLATE-beat.md` (+`authored_by: content-miner`); в `beats\` напрямую НЕ писать — переносит писатель канона. Прошлые (pre-canon, до 08.07) события — backfill-бит только при реальной сборке эпизода из них.
7. ОТЧЁТ Антону (ELI5): сколько сессий просканил → сколько черновиков в воронку (с тирами) → сколько бит-кандидатов в инбокс канона; что дальше = /episode по «+», очередь наружу = `registry\pub_registry.py` (queue → next → posted, лимиты в limits.json). Показать `python content_miner.py captured --limit N`.

ГРАНИЦЫ (AK-47):
- Draft-first ЖЕЛЕЗНО: только черновики; авто-паблиша нет; наружу ничего.
- Секреты/приватное/CRM/лиды не в контент (гейт движка + [[credential-store]]).
- Не строй параллельный монолит — переиспользуй content_miner + voice_triage + /episode.
- Грунт (детект/классификация) = Sonnet; авторский текст поста = Opus (это делает уже /episode, не тут).
- Ручной аналог ночного `content-miner-nightly`; долг по архиву закрыт разово 2026-07-09 (`miner\debt-log.md`).
