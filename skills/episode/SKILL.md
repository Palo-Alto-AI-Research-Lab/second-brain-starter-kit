---
name: episode
description: "Адаптеры публикации по ТИРАМ (контент-фабрика v2, S5) — контракт §7.2 решения reality-show 1:1: взять один пост-материал и разложить его на черновики teaser(240–370, @ClawRus RU / X EN) · medium(FB RU, ссылка в 1-м комменте) · longread(4000+, @ClawRus RU / GitHub EN) · dev-log(GitHub EN, технический), кросс-ссылки вниз + canonical→GitHub, draft-first. Триггеры: /episode, /adapt, «собери эпизод <тема>», «разложи пост по тирам/площадкам», «сделай тизеры и лонгрид», «adapt this post», «make an episode». Голос Антона = ТОЛЬКО Opus; dev-log = Sonnet-скаффолд + Opus-связность. Ничего наружу не публикуется."
---

EPISODE_ADAPTER (S5 контент-фабрики v2 — контракт [[decision-content-pipeline-reality-show]] §7.2)

ЦЕЛЬ: ОДИН пост-материал → «эпизод» = по одному черновику НА (тир × площадку) из §7.2, кросс-ссылки вниз + canonical→GitHub зашиты. Draft-first: пишем черновики, НИЧЕГО не публикуем.

КОНТРАКТ §7.2 (реализован 1:1):
```
тир       длина          площадки (фаза 1)                      язык     голос/модель
teaser    240–370 (HARD) @ClawRus(RU) · X(EN)                   RU TG/EN X  авторский · Opus
medium    800–2500       FB(RU)                                 RU          авторский дневник · Opus · ССЫЛКА В 1-М КОММЕНТЕ (не в теле) + вопрос
longread  4000+ нарратив @ClawRus·VC.ru·Хабр(RU) · GitHub(EN)   RU и EN    авторский reality-show · Opus
dev-log   сухой лог      GitHub(EN, канон)                      EN          технический безличный · Sonnet-скаффолд + Opus-связность
```
- Голос Антона (`авторский`) = **ТОЛЬКО Opus**. dev-log НЕ авторский — Sonnet собирает, Opus сшивает.
- **canonical = GitHub-markdown** на каждой площадке (один источник истины для AI). Репо: `github.com/Palo-Alto-AI-Research-Lab/clawrush`.
- **НИКАКОГО copy-paste** — каждый файл = НАТИВНЫЙ рерайт под площадку.
- Кросс-ссылки вниз: teaser→longread; medium→longread (в 1-м комменте); longread ←teaser →dev-log; dev-log→longread + anchor на наши Deep Research.
- ЯЗЫК РЕШАЕТ ПЛОЩАДКА (нет билингва на каждом тире).
- Нарратив S3 ([[style-reality-show]]) по тирам: teaser=cold open+клиффхэнгер; medium=полный эпизод-дуга; longread=расширенная серия+recap; dev-log=сырьё, без драмы.
- CTA co-founder (medium+longread, правило Антона, память [[cofounder-cta-public-contact]]): WhatsApp **+1 341 222 9178** = авторизованный ПУБЛИЧНЫЙ контакт (карв-аут приватности), не вырезать.
- **VC.ru + Хабр (RU GEO longread)** = фаза 1 с 2026-07-04 (style-файлы `_STYLE-vcru.md`/`_STYLE-habr.md` собраны, лежат в `content-factory\`; писатель подгружает по пойнтеру в плейсхолдере). **ФАЗА 2** (отложено): только `Reddit` (EN GEO дев-лог) — скаффолдится флагом `--with-phase2`.

ПУТИ:
- ⭐ ФАКТЫ И НЕПРЕРЫВНОСТЬ (v2, 2026-07-10) = ЕДИНЫЙ КАНОН `$OBSIDIAN_VAULT/04-Projects\show-canon\`: перед сборкой эпизода прочитать бит-опору (`beats\`) + его арки/петли — «ранее в сериале», клиффхэнгер и вопрос сезона берутся ОТТУДА (не из памяти, не из SHOW-STATE — тот заморожен). Ось `reveal` бита уважать: live_hold/spoiler_until не палить. Выбор хода = `/reality-show next`. После публикации — последствия в бит (consequences) + `canon_render.py`.
- Источник пост-материала: `$IMPORTS_ROOT/content-factory/triage/posts.md` (📝) — или тема Антона.
- Скаффолдер (детерминированный, 0 токенов): `$IMPORTS_ROOT/content-factory/episode_adapter.py`.
- Бандлы: `episodes\<slug>\` (8 .md фаза-1 / 9 с `--with-phase2` + meta.json; все поля §7.2 зашиты в плейсхолдеры).
- Стиль: [[style-reality-show]] (`08-Templates\style-reality-show.md`) + `04-Projects\personal\facebook-diary-auto\_STYLE.md` + [[style-Mei-influence]] + золотой корпус ≤2023.

ШАГИ:
1. ВЫБОР темы: назвал Антон — её; иначе покажи 📝 из `posts.md`, возьми сильнейшую связку. `list` перед `new`.
2. СКАФФОЛД: `python episode_adapter.py new --slug <kebab> --title "<title>" --source "hub:<id>"` (+`--with-phase2` для VC.ru/Хабр/Reddit) → бандл с пустыми черновиками + meta.json.
3. НАПИСАНИЕ (модель по полю в плейсхолдере): teaser-ru/en, medium-fb (тело БЕЗ ссылки + блок «1-Й КОММЕНТАРИЙ»), longread-ru/en, devlog. Замени стабы, комментарии-подсказки оставь. Приватность жёстко (карв-аут — только WhatsApp co-founder).
4. ПРОВЕРКА (слой видимости): `python episode_adapter.py check --slug <slug>` — длины (тизер 240–370 = HARD-FAIL вне диапазона; medium/longread = WARN), наличие CTA, пустые. ТОЛЬКО FAIL=0 → шаг 5 (WARN на неполных лонгридах допустим до дописывания).
5. РЕВЬЮ (draft-first): `set-status --slug <slug> --status review`; в Telegram Saved (chat_id 226258979, account "work_acct_a", без parse_mode): «🎬 Эпизод „<title>“ — черновики по тирам готовы (check ✅). episodes\<slug>\. Сказать „публикуем“ — разложу». НИЧЕГО наружу.
6. ЭКСПОРТ В ПУБЛИКАЦИЮ — по явному «публикуем/+» Антона (Tier-2): `python episode_adapter.py export --slug <slug>` → `drafts\episode-<slug>.md` (формат `type: content-factory-draft` + регистры `## -> TG/X/FB`). Дальше СУЩЕСТВУЮЩИЙ путь: `content_approve.py --serve` → `content_publish.py` (→ Saved; реальные каналы = Phase 2b/Tier-2). GitHub/Reddit/VC.ru/Хабр — публикуются ВРУЧНУЮ (gh/нативно), не через content_publish. Второй публикатор НЕ плодим.

ОГРАНИЧЕНИЯ:
- Draft-first НАРУЖУ: каналы/X/GitHub не трогаем без явного «публикуем».
- МОДЕЛЬ: авторский голос = ТОЛЬКО Opus; dev-log = Sonnet+Opus; скаффолд/check/export = детерминированно, 0 токенов.
- Один пост = один эпизод. Windows cp1252: скрипт сам форсит UTF-8 stdout.
- Не выдумывай факты — пиши из реального пост-материала.
- Старые бандлы (4-файловые / интерим) читаются `list/show/check/export` через meta (обратная совместимость).
