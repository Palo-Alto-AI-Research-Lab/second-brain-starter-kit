---
name: fb-post
description: Publish a VETTED post to Anton's personal Facebook wall through his real logged-in Chrome (Claude-in-Chrome MCP = the low-ban-risk "act in the live tab" path), rate-limit-guarded and draft-first. Trigger on "/fb-post", "запости в фб", "опубликуй пост в facebook", "выложи на стену", "publish to facebook", "post this to my wall". The TEXT is written in Anton's author voice (Opus) -- reuse content-factory / fb-diary / episode drafts, never invent a fresh voice. Publishing is OUTBOUND + PUBLIC (Tier-2): show the final draft and get Anton's explicit "+" (or let him click Post) before anything goes live. Every post is gated by fb_guard.py (<=8/day). Phase-1 sibling of /fb-reply; the engine guard is ~/.claude/scripts/fb_guard.py. Canon: Decision Memo 2026-06-28 (FB skill set), memory facebook-diary-auto + content-factory + chrome-autonomy-self-drive.
---

# /fb-post — опубликовать пост на стену Антона (безопасно, draft-first)

**Зачем.** Контент-фабрика и FB-дневник уже ПИШУТ посты голосом Антона, но черновик до сих пор оседает в Saved/волте. Не хватало только «кнопки публикации». Этот скилл закрывает её — и делает это самым безопасным способом (действуем в живой залогиненной вкладке Chrome, а не headless-ботом), с жёстким счётчиком объёма.

**Главные правила (из Deep-Research #32):**
- Публикация = **OUTBOUND + PUBLIC = Tier-2** → финальный текст показываю Антону и жду явного `+` (или он сам жмёт «Опубликовать»). Никогда не публикую молча.
- **Голос Антона = Opus.** Текст беру из готового черновика (`content-factory`, `facebook-diary`, `episode`) или пишу на Opus. Не выдумываю новый голос, не даю Sonnet писать авторское.
- **Объём низкий:** `fb_guard` режет на ≤8 постов/день. Не дублировать один и тот же текст (спам-флаг).

---

## 0. Предохранитель ПЕРЕД браузером (обязательно)
```bash
python "$USERPROFILE/.claude/scripts/fb_guard.py" check post
```
- `OK post (...)` → можно продолжать.
- `BLOCKED post: ...` (exit 3) → СТОП. Скажи Антону, что дневной лимит постов исчерпан, предложи запланировать на завтра. Не обходи.

## 1. Текст (голос Антона, Opus)
1. Если Антон дал готовый черновик — бери его. Если просит «оформи из X» — собери на Opus в его голосе (см. `fb-diary-voice`: вплетённо, с самоиронией, ~4000 знаков для дневникового; короче для анонса).
2. Покажи Антону **финальный текст** и спроси `+`. Это Tier-2 gate — без явного «да» дальше не идём.

## 2. Браузер (Claude-in-Chrome, живая вкладка)
> Браузерная работа — строго ЛОКАЛЬНО на этой машине (Антон за хабом). Не тащить окно Claude вперёд.
> ⛔ IP-гейт (anton 16.07): постинг/комментинг FB — ТОЛЬКО с хаба `HUB-1` (постоянный IP). Ты на другой машине? НЕ постить отсюда — задачу текстом на хаб (шина/03). Канон: `reglament-ip-sensitive-deystviya-tolko-s-haba`.

1. Проверь, что Chrome-MCP подключён: `mcp__Claude_in_Chrome__list_connected_browsers`. Если нет — попроси Антона открыть Chrome с расширением (не падай в Playwright).
2. Открой/выбери вкладку `facebook.com` (он уже залогинен — НЕ трогаем логин/пароль). Если не залогинен — это блок, скажи Антону.
3. Найди композер: `mcp__Claude_in_Chrome__find` запросом «What's on your mind / Что у вас нового — create post box». Кликни, чтобы открыть окно создания поста.
4. Введи текст в поле композера (`form_input` по ref из `find`). **НЕ нажимай «Опубликовать»** сам, пока не выполнен Tier-2 gate из §1.
5. После явного `+` Антона — нажми кнопку «Опубликовать»/«Post» (или попроси Антона нажать, если он рядом и хочет сам). ⚠️ Диалог двухшаговый: compose → «Next» → Post settings → «Post». Сделай скриншот результата (`computer` screenshot), чтобы Антон ВИДЕЛ, что пост ушёл.
6. **Футер 1-м комментарием** (правило §7.7, тело поста без ссылок): открой опубликованный пост → поле «Comment» → блоки B+C+E из `_imports\content-factory\_STYLE-footer.md` (только живые ссылки). ⚠️ Enter отправляет коммент — переносы строк только Shift+Enter.
7. **Селф-лайк** (правило Антона 05.07: «первый лайк всегда тяжело ставить»): поставь Like на свой пост сразу после футер-коммента. Штатный шаг, отдельно не спрашивать.
8. Грабли композера: первый клик может попасть в Stories (лента сдвигается при ленивой подгрузке) — после навигации подожди ~2с, скриншот, потом клик по свежим координатам.

## 3. Зафиксируй в счётчике (ПОСЛЕ успешной публикации)
```bash
python "$USERPROFILE/.claude/scripts/fb_guard.py" record post
```

## 4. Доложи
Одной строкой: что опубликовано + ссылка/скрин + «сегодня постов N/8».

---

## Стоп-краны (account safety)
- Любое предупреждение FB (checkpoint, «вы делаете это слишком часто», запрос подтверждения личности) → **немедленно СТОП**, доложи Антону, НЕ ретрай-спам (ретраи и есть путь в бан).
- Не публиковать идентичный текст повторно.
- Не трогать логин/пароль/2FA — если не залогинен, это блок для Антона.

## Связанное
- `/fb-reply` — ответы на комментарии (Фаза 1, тот же guard).
- Движок-счётчик: `~/.claude/scripts/fb_guard.py` (общий на post/reply/dm).
- Тексты: `content-factory`, `facebook-diary`, `episode`, голос — `fb-diary-voice`.
- Канон: Decision Memo 2026-06-28 (набор FB-скиллов), `chrome-autonomy-self-drive`, `browser-work-on-peers-not-hub`.
