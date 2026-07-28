---
name: fb-watch
description: >
  Мониторит стену Facebook Антона на АВТОРСКИЕ посты, к которым ещё НЕТ тизера, и сразу пишет
  тизеры (RU→@ClawRus, EN→X) — draft-first, пока не взведён авто-постинг. Конкретный FB-механизм
  под стоячее правило teaser-crosspost-clawrus. Trigger on "/fb-watch", "проверь фейсбук на тизеры",
  "посты без тизера", "добей тизеры", "fb watch", "check facebook for un-teased posts". Запуск 1×/день
  днём (рутина) или по требованию. Читает стену через Claude-in-Chrome (живая вкладка, локально на хабе);
  детектор/леджер/кап = ~/.claude/scripts/fb_teaser_watch.py (0 токенов). Голос Антона = только Opus.
  Канон: память teaser-crosspost-clawrus, fb-skill-set; reglament-tizery-krosspost-v-clawrus-i-tg.
---

# /fb-watch — добиваем тизеры на FB-посты Антона

> **Зачем.** Антон иногда пишет пост ПРЯМО на стену FB, минуя пайплайн (голос→эпизод→тиры).
> Такой пост остаётся БЕЗ тизера в @ClawRus(RU)/X(EN) → охват теряется. Этот сторож ловит
> «есть авторский FB-пост, тизера ещё не было» и сразу пишет тизеры. Draft-first, пока не взведён.

## Инструменты (тонкий оркестратор, AK-47)
- **Чтение стены** = Claude-in-Chrome MCP (живая залогиненная вкладка FB, локально на хабе). Реюз паттерна из `/fb-reply` (in-page `javascript_tool`, FB прячет имена за MCP-границей).
  - ⛔ **НЕ читай ленту профиля `/OwnerProfile`** (консенсус #0223a74a, 20.07): она виртуализирована и рендерит ОДИН пост — соседи висят вечными скелетонами, `scrollHeight` константа, реальный скролл не помогает. Один прогон так спрятал 2 контентных поста из 5.
  - ✅ **Рельс жатвы = Content Library**: `https://www.facebook.com/professional_dashboard/content/content_library/` → таблица постов, ПОЛНЫЙ текст (обрезка только CSS), точная дата-время, метрики. Парс: `document.body.innerText` → строки, якорь `"Published"`, текст = строка перед, дата = строка после; накапливать между прокрутками (дубли гасить по первым 60 символам).
  - ⚠️ **Permalink Content Library НЕ отдаёт** (в меню строки только Edit/Delete). Добор: на стене реальный `computer hover` по таймстампу поста → FB подставляет `pfbid` в `href` (до наведения href пустой; синтетические MouseEvent и React-fiber НЕ работают — у FB кастомный ключ рендерера).
  - **АПГРЕЙД (Антон одобрил 2026-06-30, ждёт креды):** как только есть `secrets\fb_graph.env` (FB_USER_TOKEN, `user_posts`) и `python ~/.claude/scripts/fb_posts_poll.py check` зелёный → читай стену через `python ~/.claude/scripts/fb_posts_poll.py posts --limit 10 --out posts.json` (Graph API, надёжнее браузера, без риска бана) ВМЕСТО Claude-in-Chrome. См. [[decision-social-posting-stack]] §6.
- **Детектор/леджер/кап** = `python ~/.claude/scripts/fb_teaser_watch.py` (0 токенов, дедуп + дневной кап + kill-switch). Состояние: `$IMPORTS_ROOT/content-factory/fb_teaser_ledger.json` + `fb_watch_config.json`.
- **Тизеры** пишет Opus в сессии (голос Антона), палитры: `_STYLE.md`/`_CRAFT.md` + `style-reality-show.md`. Черновики → `_imports\content-factory\fb-teasers\<id>.md`.
- **Постинг RU** = Telegram MCP `send_message`, аккаунт **work_acct_b** (создатель), чат **-1006847702008** (@ClawRus). **EN/X** = пока нет постера → ВСЕГДА черновик (ждёт social-tools DR).

## Процедура
1. **Готовность Chrome.** Проверь живую вкладку FB (Claude-in-Chrome). Не готов/не залогинен → **флагни в чат 03** («fb-watch: Chrome/FB не готов, стену не прочитал») и СТОП. Не делать вид, что «постов нет» (слой видимости — тихий ноль = поломка).
2. **Извлеки авторские посты** со стены Антона (последние ~10): для каждого `{id, permalink, text, ts}`. `id` = стабильный story/permalink id. Только ЕГО авторские (не репосты/чужое). Текст наружу из страницы — безопасный (без скрытых имён).
   ⛔ **`text` = ПОЛНЫЙ текст поста, ОБЯЗАТЕЛЕН** (разверни «See more» перед съёмом): pfbid ротируется при каждом харвесте (доказано 05.07), идентичность поста живёт на `text_hash`. Пост без text = дедуп по нему слепой (движок ругнётся WARN в stderr — не игнорируй, дособери текст).
3. **Детектор:** запиши список в `posts.json` → `python fb_teaser_watch.py unteased --in posts.json`. На выходе — посты БЕЗ тизера.
   🚨 **exit 4 = `HARVEST-THIN`** (собрано <3 постов, порог `FB_TEASER_MIN_HARVEST`): это НЕ «постов нет», это СБОЙ ЖАТВЫ → пережни через Content Library и флагни в 03. Тихий ноль запрещён (консенсус #0223a74a). **Правило: 1 тизер на КАЖДЫЙ такой пост** (нашёл 5 — пиши 5; это не дневной кап).
   🛡️ **Freshness-гард (14.07):** незнакомый пост старше 72ч (`--max-age-hours`) движок сам засевает как skip со stable-ключами — бэклог стены и ротация pfbid флуд дать не могут; в stderr это `stale-auto-skipped=N`. Отключается `--no-auto-skip` (не отключай в рутине).
   - **FORWARD-ONLY первый прогон:** `python fb_teaser_watch.py backfill-status` → если NOT DONE (exit 1) и список длинный (это весь бэклог стены) → НЕ публикуй массой: пометь каждый существующий пост `seed-skip --id <id>`, затем `mark-backfill-done`, доложи «forward-only: N постов засеяно как skip, с этого момента каждый НОВЫЙ пост получает тизер». Дальше — только реально новые посты.
4. **Для каждого un-teased поста** напиши 2 тизера (Opus, голос Антона) **строго по плейбуку** `08-Templates\teaser-writing-playbook.md` (крючок в 1-ю строку, ОДИН приём, 4U-чек, клиффхэнгер + «полное → [ссылка на FB-пост]»):
   - **RU** — тёплый, для @ClawRus, **240–370 знаков (HARD)**.
   - **EN** — для X, **≤280 знаков**.
   - Приватность HARD: ни чужих имён/@/сумм/секретов. CTA co-founder тут НЕ нужен (он в среднем/лонге). Сохрани оба в `fb-teasers\<id>.md`.
5. **Распубликуй:**
   - **RU:** `python fb_teaser_watch.py can-post --rail ru` → exit 0 (взведён + под капом) → запость текст в @ClawRus (Telegram MCP, work_acct_b, chat -1006847702008) → `mark-posted --id <id> --rail ru`. Exit 3 (disarmed/кап) → оставь черновиком.
   - **EN:** `x_poster_ready` в `fb_watch_config.json` решает. `false` → черновик. `true` → `python ~/.claude/scripts/x_post.py post "<en teaser>"` (X API v2, OAuth1; exit 0 = запостил, печатает url). Постер взводится, когда у Антона есть X dev-креды в `secrets\x_api.env` и `x_post.py check` зелёный (см. [[decision-social-posting-stack]] §6).
   - Затем `python fb_teaser_watch.py record-draft --id <id>` (чтобы пост не всплывал снова).
6. **Доложи Антону.** СТАТУС-ОТЧЁТ (сколько найдено, что запостил RU, что в черновике) — это отчёт, не вопрос → в чат 03 / TG-папку, как обычно.
   **Если нужен ЕГО ОК** (режим проверки/disarmed: «публикуем И взвести авто?») — ⛔ НЕ пиши вопрос в 03 руками (там heartbeat-шум хоронит аски, Антон не увидит). Подними аск через движок remote-approval, который сам шлёт в **02-POLICE ПЕРВЫМ** + дублирует в 03/личку:
   `python ~/.claude/scripts/approval.py ask "fb-watch: N черновиков готовы. Публикуем И взводим авто-arm? QQQ=да,публикуем+arm · NO=оставить черновиками"` → вернёт `{id, ask_text, targets}`. Затем ОТПРАВЬ `ask_text` по `targets` **строго по порядку** (Telegram MCP; targets[0] = 02-POLICE = первым). Проверка ответа: `python ~/.claude/scripts/approval.py check`. Канон [[remote-approval-qqq]] («QQQ-аск → 02-POLICE first»); гейт `lint_approval_routing.py` следит, чтоб этот шаг не разъехался снова.

## Границы (Tier-2 / безопасность)
- **Авторизация Антона (2026-06-30):** RU-авто-постинг в @ClawRus **ВЗВЕДЁН** (`armed=true`) — Антон дал стоячую авторизацию (тизер = указатель на уже публичный FB-пост, риск минимальный). Kill-switch: `disarm` в любой момент.
- **1 тизер на каждый пост без тизера** (НЕ дневная квота). Дедуп по леджеру → двойного поста не будет. `daily_hard_cap` (25) — только страховка от бага-флуда.
- **Forward-only:** первый взведённый прогон засевает существующую стену как `skip` и НЕ постит — чтобы не залить @ClawRus бэклогом; дальше тизер получает каждый НОВЫЙ пост.
- Только ЕГО собственные посты и его собственные каналы. Никакого блайнд-автопоста в чужое.
- Авторский голос = **только Opus**. Грунт (детектор) = 0 токенов.
- Браузерная работа строго ЛОКАЛЬНО на хабе ([[browser-work-on-peers-not-hub]]).

## Связь
Канон правила: память [[teaser-crosspost-clawrus]] + `reglament-tizery-krosspost-v-clawrus-i-tg`. Родня: [[fb-skill-set]] (/fb-post, /fb-reply, fb_guard), [[content-factory]] (Distribute-стадия), [[short-text-when-unreviewed]]. Рутина-двойник: scheduled-task `fb-watch-daily` (1×/день днём).
