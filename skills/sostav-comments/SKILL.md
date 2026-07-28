---
name: sostav-comments
description: Draft short, in-voice reply candidates for Anton to a fresh СОСТАВ alpha shortlist — read the nightly detector report, pick posts in SAFE/opinion topics, pull a relevant grounding snippet from the YouTube-Data-API corpus (the only working comment corpus — all socials are login-walled), and write draft replies in Anton's voice (Opus). Trigger on "/sostav-comments", "черновики ответов по составу", "ответь на альфу состава", "draft sostav replies". DRAFT-FIRST — never sends/posts anything; Anton copies what he likes. SAFE-topic gate only (never draft into Крипта/Девушки/Флудильня grey threads). Thin wrapper over the existing detector report + daily_safe_fetch.py; AK-47 = one SKILL.md. Canon: memory sostav-community-import, short-text-when-unreviewed, content-Mei-style; reglament-anti-leak-na-vyhode.
---

# /sostav-comments — черновики ответов на свежую альфу СОСТАВ (голос Антона, draft-first)

**Зачем.** Когда Антон разбирает свежий ночной shortlist, он часто хочет готовые черновики реплаев в интересные треды клуба. Скилл делает это за один заход: читает отчёт детектора → отбирает безопасные посты → пишет короткие ответы его голосом → показывает. **Ничего не отправляет** — Антон копирует что нравится.

**Главные правила:**
- **Draft-first, никогда не публикует.** Скилл только пишет черновики в чат. Отправку в клуб делает сам Антон руками.
- **Safe-topic gate.** Черновики только в тредах-мнениях/знаниях (Знания, Лекции, Бизнес, Инвестиции, Путешествия, Здоровье, Общий-по-делу). ⛔ НИКОГДА не драфтить в Крипта/Девушки/Флудильня и в любые серо-финансовые/личные треды — это данные, не площадка для реплая.
- **Короткий текст, тон по каналу** ([[short-text-when-unreviewed]]): осмысленный ответ в мессенджер-регистре (не FB-шутка на 5 слов — тут нужен контекст и знание, кто человек; подними карточку `person-sostav-*` если участник ⭐).
- **Голос Антона (Opus).** Не «позиционированные» ответы, не выскочка. По делу, по теме, без «я-я-я» на чужих анонсах.
- **Anti-leak** ([[reglament-anti-leak-na-vyhode]]): черновики остаются в приватном слое; ничего чувствительного из клуба не утекает в другие каналы.

---

## 0. Свежий shortlist
Последний отчёт детектора:
```
ls $IMPORTS_ROOT/alpha\candidates\sostav-*-report.md   # взять самый свежий по дате
```
Если свежего нет / устарел — сначала обнови корпус (ночной путь): `python $IMPORTS_ROOT/sostav\nightly_run.py` (идемпотентно, дозаберёт).

## 1. Отбор постов под ответ
Из shortlist оставь только те, где:
- топик **safe** (см. gate выше);
- пост — мнение/вопрос/знание, где осмысленный ответ уместен (не объявление, не интро, не серый запрос);
- ⭐-автор → подними `$OBSIDIAN_VAULT/07-People\person-sostav-<slug>.md` для контекста «кто это».

## 2. Grounding-сниппет (по необходимости)
Если ответ выигрывает от конкретики (цитата/факт/пример), возьми релевантный кусок из рабочего корпуса — **YouTube Data API** (единственный работающий пул; соцсети заблокированы login-wall'ами), через `$IMPORTS_ROOT/sostav\daily_safe_fetch.py` (safe-only гейт). Verbatim-lift 1–2 фрагмента, не пересказ.

## 3. Черновики (Opus, персонально, разные)
Для каждого отобранного поста — **отдельный** короткий ответ голосом Антона. Собери пачку:
```
1. [Знания · Автор X] пост: «…тезис…»
   → черновик: «…осмысленный ответ по делу, голос Антона…»
2. ...
```
Тексты разные, по теме, без шаблона. Голос ≥ Opus ([[content-Mei-style]] — влияние, не копия).

## 4. Отдай Антону
Покажи пачку черновиков в чат + пометь, у каких ⭐-контактов поднимал карточку. **Стоп на этом** — отправляет Антон сам.

---

## Стоп-краны
- ⛔ Ничего не постить/не отправлять — только черновики в чат.
- ⛔ Не драфтить в серые/личные/крипто-треды (safe-gate).
- ⛔ Ничего из клуба не утекает в другие каналы ([[reglament-anti-leak-na-vyhode]]).
- Деньги/обязательства/секреты в черновике → вырезать, это Tier-2.

## Связанное
- Детектор/ночной путь: `$IMPORTS_ROOT/sostav\nightly_run.py`, `sostav_alpha.py`.
- Корпус реплаев: `daily_safe_fetch.py` (YouTube Data API, `secrets/youtube.env`).
- Голос: [[short-text-when-unreviewed]], [[content-Mei-style]], `/speak-as`.
- Родственные скиллы: `/fb-reply` (FB-комменты), `/mine-channel`, `/alpha-judge`.
- Канон: memory `sostav-community-import`, [[reglament-anti-leak-na-vyhode]].
