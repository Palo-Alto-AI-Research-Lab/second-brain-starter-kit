---
name: fireflies-sync
description: On-demand подтягивание свежих звонков из Fireflies.ai (автозапись-бот, реальные имена спикеров) в Obsidian-волт через официальный GraphQL API (ключ в secrets\fireflies.env) + прогон дистилляции (alpha/commitments) + реиндекс. Инкрементально + идемпотентно (state.json по transcript id) — безопасно гонять повторно. Trigger on "/fireflies-sync", "подтяни fireflies", "забери звонки из fireflies", "sync fireflies", "обнови файрфлайз", "планёрки в волт". Ночной двойник живёт на ЯкорьЕ (cron ~03:00; задача хаба "Fireflies Nightly Pull" = Disabled by migration, НЕ чинить). Sibling: [[granola-sync]]. Канон: память [[hub-connectors]] (Fireflies bullet) + [[vps-anchor-node]].
---

OBJECTIVE: Инкрементально втянуть свежие звонки из Fireflies в волт (заметка с диаризованными ИМЕНАМИ спикеров + саммари + action items), догнать дистилляцию (alpha/commitments/facts) и убедиться, что попадёт в индекс.

CONTEXT:
- Транспорт: официальный Fireflies GraphQL API `https://api.fireflies.ai/graphql`. Ключ: `FIREFLIES_API_KEY` в `secrets\fireflies.env` (bbplatinum SSO, тариф PRO). Autojoin ON — бот сам заходит в календарные звонки (ловит планёрки/корпоративные, которые Granola с ручным стартом пропускает).
- Движок (вся логика там, скилл — тонкая обёртка): `$IMPORTS_ROOT/fireflies\fireflies_pull.py`. Один скрипт = бэкфилл и инкремент.
- Дом заметок: `$OBSIDIAN_VAULT/04-Projects\fireflies-meetings\` (auto_generated — руками не править). Raw JSON (Granola-СОВМЕСТИМЫЕ ключи, их ест call_distill.py): `$IMPORTS_ROOT/fireflies\raw\`. State: `$IMPORTS_ROOT/fireflies\state.json`. Лог: `pull.log`.
- ⚠️ Ночной pull работает на ЯкорьЕ: заметки волта доезжают синком, но raw-JSON на хаб НЕ доезжает → дистиллер хаба свежие Fireflies-звонки не видит. Этот скилл на хабе ЗАКРЫВАЕТ дыру: локальный state отстаёт от Якорьовского → pull дотянет пропущенные raw сюда (идемпотентно, заметки перепишутся идентичным содержимым).
- Дистилляция: `$IMPORTS_ROOT/granola\call_distill.py` читает ОБА raw-каталога (granola + fireflies) → `_distilled\` + commitments.jsonl.

STEPS:
1. BACKUP FIRST ([[vault-backup-rule]]): `python $IMPORTS_ROOT/vault_backup.py` ДО запуска.
2. Pull: `python $IMPORTS_ROOT/fireflies\fireflies_pull.py` (опции: `--dry`, `--limit N`). Счётчики stdout: `DONE new=X errors=Y state_total=N`.
3. Distill (если new>0): `python $IMPORTS_ROOT/granola\call_distill.py` — счётчики `DONE distilled=M commitments=C errors=Z`.
4. Доложить список свежих звонков (титулы/даты). errors>0 → глянуть лог, чаще сеть/429 (скрипт ретраит сам).
5. Реиндекс: ночной `brain_embed_update.py` подхватит сам; после большого бэкфилла — прогнать вручную. ⚠️ Пока `_distilled` не помечен `layer: essence`, в курируемый индекс дистилляты не попадают (гэп в работе, задача RUSL-1).

CONSTRAINTS:
- Windows cp1252: stdout ASCII-only (скрипт уже соблюдает).
- INCREMENTAL ONLY — `state.json` не удалять (иначе перекачает всё).
- Provenance: origin: mixed, authored_by: hybrid — НЕ #anton-original (чужая речь).
- Tier-2: ничего наружу; только чтение API + запись в волт.
- 401 от API → ключ отозван: новый в Fireflies dashboard (Integrations → API), обновить `secrets\fireflies.env`. ⚠️ CRLF-грабля: `\r` в конце строки ломает Bearer (движок уже strip'ает).
- Задачу хаба "Fireflies Nightly Pull" НЕ включать обратно без консенсуса — она сознательно Disabled (мигрирована на Якорь, см. fleet_migration_dashboard.py migrated_markers).

OUTPUT: счётчики pull (new) + distill (distilled/commitments) + период; пусто — «Новых звонков нет». Заверши 🧒 «Простыми словами».

RELATION (не дублировать): Granola-рельса = skill [[granola-sync]]; сравнение двух рельс + карта «куда падает контент» = волт `00-System` / задача RUSL-1; экран альфы = `/alpha-review`.
