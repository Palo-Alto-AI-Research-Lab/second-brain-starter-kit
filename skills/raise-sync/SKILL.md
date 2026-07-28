---
name: raise-sync
description: ACTIVE recovery when machines can't see each other over Syncthing — the "raise the sync" runbook as one command. Establishes ground truth AT THE HUB (live Syncthing API, NOT memory or one peer's claim), publishes the hub's VERIFIED Device ID to the Telegram bus, and guides each disconnected peer to re-pair. Trigger on "/raise-sync", "подними синк", "синк лёг", "компы не видят друг друга", "восстанови связь машин", "raise the sync", "sync down", "fix the sync", "re-pair the hub". DISTINCT from /sync-check (that is READ-ONLY status); this one drives the RECOVERY. Read-only on the machines themselves (I can't reconfigure a peer's Syncthing) + one coordination post to the bus. Canon: vault reglament-chp-poterya-sinka-mezhdu-mashinami (§4 runbook) + memory sync-loss-incident-and-monitor.
---

# /raise-sync — поднять синк, когда машины не видят друг друга

Активный runbook на ЧП «потеря синка» (полный канон + почему = Библия [[reglament-chp-poterya-sinka-mezhdu-mashinami]]). Принцип: **истину устанавливаем по ЖИВОМУ API хаба, а не по памяти и не по словам одного пира** (пир может держать устаревшую запись — так ноут однажды уверенно звал «верни 2KPYBY4», что сломало бы Нина).

Аккаунт/группа шины и ключ — из `~/.claude/tg_bus.json` (Telegram) и env `STGUIAPIKEY` (Syncthing API). Хаб LAN = `10.0.0.10:22000`.

## Шаг 0 — Детект (где болит)
```bash
APIKEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('STGUIAPIKEY','User')" | tr -d '\r')
curl -s -H "X-API-Key: $APIKEY" "http://127.0.0.1:8384/rest/system/connections" | python -c "import sys,json;d=json.load(sys.stdin);[print(k[:7], v.get('connected'), v.get('address')) for k,v in d.get('connections',{}).items()]"
```
(Или быстрый красный/зелёный — скилл `/sync-check`.) Кто `connected:false` = отвалился.

## Шаг 1 — Истина НА ХАБЕ (факты, не память)
```bash
# myID хаба (должен совпасть с machines.json HUB-1 = EEAETB6...)
curl -s -H "X-API-Key: $APIKEY" "http://127.0.0.1:8384/rest/system/status" | python -c "import sys,json;print('myID=',json.load(sys.stdin)['myID'])"
# демон серверит РЕАЛЬНЫЙ волт? (пути на %VAULT_ROOT%\..., данные есть)
curl -s -H "X-API-Key: $APIKEY" "http://127.0.0.1:8384/rest/config/folders" | python -c "import sys,json;[print(f['id'],'->',f['path']) for f in json.load(sys.stdin)]"
```
- Если `myID` НЕ совпадает с реестром / папки пустые → демон поднят на ЧУЖОМ home: **чини home (тот, где родной cert.pem + папки), НЕ пере-паривай пиров на временный ID.**
- Если `myID` совпадает и папки реальные → личность легитимна, проблема на стороне пиров (устаревшая запись хаба).

## Шаг 2 — Сверка с реестром (детект дрейфа)
Сравни live `myID` с `_machine-bus/machines.json` (поле `deviceID` хаба). Расходится без явной миграции = подозрение; совпадает = публикуем как канон.

## Шаг 3 — Опубликуй VERIFIED Device ID хаба в шину (out-of-band пруф)
Через Telegram-MCP (`chat_id`/`account` из `tg_bus.json`):
```
🤖 [<хаб> -> ALL] hub <имя> = <EEAETB6-полный-ID>, addr tcp://10.0.0.10:22000. VERIFIED живым API (серверит весь волт). Пиры: впишите этот ID, удалите устаревший, рестарт демона, рапорт connected.
```
Это снимает Tier-2-гейт пира («вписать чужой ID = отдать волт») — пир получил доказательство со стороны самого хаба.

## Шаг 4 — Веди пиров (они чинят у себя; я не могу реконфигурить чужой Syncthing)
Каждому disconnected: впиши хаб = verified ID, верный адрес, **удали устаревший ID** (частая грабля — фантомный старый → «Hello → forcibly closed / unknown device»), рестарт демона штатным сторожем → рапорт `🤖 [пир -> хаб] connected` или что мешает.

## Шаг 5 — Проверь
Повтори Шаг 0: все `connected:true`, бэклог качается (`needFiles` падает). Доложи Антону состав.

## Анти-грабли (выучено кровью 2026-06)
- НЕ верь ОДНОМУ пиру в диагнозе идентичности — источник истины = живой API хаба.
- НЕ откатывай хаб на старый ID, если другой пир уже работает на новом (сломаешь работающего).
- Сторож с «зависанием» → сперва проверь слой видимости (логи/ключ/403), а не ядро.

## Связанное
- `/sync-check` — read-only статус (детект). Этот скилл — РЕКАВЕРИ.
- Dead-man-switch `sync_monitor.py` (задача «Claude Sync Monitor») пингует Антона при отвале пира → часто `/raise-sync` стартует ПО его пингу.
- Канон: [[reglament-chp-poterya-sinka-mezhdu-mashinami]], [[machine-bus-telegram-rail]], [[syncthing-v21-gotchas]].
