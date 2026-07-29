---
name: x-post
description: Publish a VETTED post/tweet to Anton's X (Twitter) account @Tony_Stef_ through his real logged-in Chrome (Claude-in-Chrome MCP, live tab — low-ban-risk path), rate-guarded and draft-first. Trigger on "/x-post", "запости в X", "твитни", "опубликуй в твиттер", "выложи в X", "post to X", "tweet this". Text = Anton's authorial voice (Opus), EN teaser per /episode canon (≤280 chars for a single post). Publishing = OUTBOUND + PUBLIC (Tier-2) → show final draft, wait for explicit "+". Guard = social_guard.py (x ≤6/day + anti-dup). Sibling of /fb-post (same Chrome pattern) and /tg-post. Handle truth = vault 00-System\Channels-Registry.md; ALWAYS verify the logged-in handle in the live tab before posting.
---

# /x-post — пост в X с аккаунта Антона (Chrome, draft-first)

**Зачем.** EN-тизеры (/episode) до сих пор оседали черновиками — не было постера в X. Тот же безопасный паттерн, что /fb-post: живая залогиненная вкладка, никакого headless.

## 0. Предохранитель (обязательно)
```bash
python "$USERPROFILE/.claude/scripts/_shared/social_guard.py" check x --text "<финальный текст>"
```
`BLOCKED` (exit 3) → СТОП, доложи (лимит 6/день или дубль). Не обходи.

## 1. Текст (голос Антона, Opus)
Бери готовый черновик (episode teaser EN / intention-lane) или пиши на Opus. Один твит ≤280 символов — посчитай ДО браузера; длиннее → тред (каждый твит ≤280, нить через reply) или предложи Антону сократить.

## 2. Tier-2 gate (draft-first)
Покажи финальный текст (+ разбивку треда, если тред) → жди явного `+`. Без «+» ничего не публикуется.

## 3. Браузер (Claude-in-Chrome, живая вкладка)
> Браузерная работа — локально на этой машине; окно вперёд не тащить.
> ⛔ IP-гейт (anton 16.07): постинг в X/соцсети с бан-риском — ТОЛЬКО с хаба `HUB-1` (постоянный IP). На другой машине НЕ постить — задачу текстом на хаб. Канон: `reglament-ip-sensitive-deystviya-tolko-s-haba`.
1. `list_connected_browsers` → нет расширения → блок, скажи Антону (не падать в Playwright).
2. Вкладка `x.com`. **Сверь залогиненный handle** (аватар/меню профиля) = **@Tony_Stef_** из реестра. Другой аккаунт → СТОП, спроси. Не залогинен → блок (логин/2FA не трогаем в X — checkpoint-риск).
3. Композер: `find` «post composer / What's happening». Введи текст (`form_input`). **Кнопку Post не жми** до выполненного гейта §2.
4. После `+` — Post. Тред: после первого твита кнопка «+» в композере / reply на свой твит.
5. Скриншот опубликованного + URL твита (клик по timestamp → адресная строка) = доказательство.

## 4. Зафиксируй (ПОСЛЕ успешной публикации)
```bash
python "$USERPROFILE/.claude/scripts/_shared/social_guard.py" record x --text "<текст>"
```
Доклад: ссылка + скрин + «сегодня x N/6».

## Стоп-краны
- Любой checkpoint/captcha/«unusual activity» X → немедленно СТОП, доложи, ноль ретраев.
- Не публиковать идентичный текст повторно; не постить чужими аккаунтами.
- Ссылки в тексте — только живые и наши (link-safety).

## Связанное
`/fb-post` (образец паттерна) · `/tg-post` · `/episode` (тиры: teaser EN → X) · гейт `scripts\_shared\social_guard.py` · реестр `00-System\Channels-Registry.md`.
