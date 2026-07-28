---
title: "Concept Creation Rules — vault skill"
aliases: [Concept-Creation-Rules, Concept-Rules, "How to create concepts"]
tags: [skill, rules, vault-hygiene, concepts, MOC]
date: 2026-05-30
type: skill
authored_by: claude-cowork
language: ru
value_score: 0.95
topic: 00-Meta
parent: "CLAUDE [internal]"
summary: "Канонические правила создания concept-нот в vault. Используется как inline-skill для Claude/Cursor/Cowork. Содержит шаблон, поля, naming, bridges, anti-patterns."
---

# 🧠 Concept Creation Rules — skill для AI-агентов

> **Назначение:** канонические правила создания concept-нот в `06-Concepts/` и bridge-нот в `09-Bridges/`. Любой AI-агент, работающий с vault'ом, обязан следовать этим правилам.

---

## 1. Когда создавать концепт

> ⭐ **STANDING RULE (origin: anton, 2026-06-12; усилено 2026-06-14):** создание недостающих концептов — **ОБЯЗАТЕЛЬНЫЙ шаг КАЖДОГО импорта**, не опциональный. Когда в волт добавляется новый блок информации/артефактов и в нём есть **повторяющаяся тема без своего концепта** (порог ниже) — агент ОБЯЗАН завести концепт (canonical или bridge) и связать с ним новые заметки. Единичные темы — не плодить. Дословно Антон: *«ВСЕГДА создавай НОВЫЕ КОНЦЕПТЫ если есть нужда при добавлении новых блоков информации/артефактов в волт»*. Это not-optional часть pipeline `obsidian-ingest` (фаза концепт-маппинга).
>
> 🔴 **SUPERSEDE (origin: anton, 2026-06-14) — НЕ спрашивать, СОЗДАВАТЬ:** отменяет прежнее «показывать Антону на подтверждение (batch)». Дословно Антон: *«каждый раз если ты считаешь (после анализа текущего массива концептов) что надо создать НОВЫЙ КОНЦЕПТ — СОЗДАВАЙ»*. Если агент после **анализа существующего массива концептов** (06-Concepts + aliases + 09-Bridges, чтобы не плодить дубль) считает, что нужен новый концепт по порогу §1 — **создаёт его сам, без запроса подтверждения**. Применяется НЕ только при импорте, а в любой работе с волтом. По-прежнему: проверь на дубль/bridge (§5), соблюди порог ≥3 и доменную привязку, перелинкуй новые заметки, отметь созданное в финальном отчёте Антону (постфактум, не для разрешения).

Создавай concept-ноту, **если выполнены все условия:**

- ✅ Термин упоминается **≥3 раз** в high-value файлах (vs ≥ 0.6)
- ✅ Это **существительное-сущность** (компания, продукт, концепция, методика, человек), а НЕ:
  - section header дистилла ("Контекст", "Источник", "Решение")
  - folder name ("Telegram", "Facebook", "Conversations")
  - generic adjective ("Подробный", "Детальный", "Глубокий")
  - meta-PKM term ("Permanent", "Атомарная", "Evergreen")
  - topic-tag ("Business-Finance", "Personal-Growth") — это уже в `topic:`
- ✅ Отсутствует в `06-Concepts/` (canonical) и в aliases других концептов
- ✅ Имеет **доменную привязку** (biohacking / crypto / ai / business / portugal / cars / family / etc)

Если термин — variant написания, transliteration или морф. форма существующего → **создавай bridge** (см. §5), не concept.

---

## 2. Frontmatter (canonical concept)

**Обязательные поля:**

```yaml
---
title: "Каноническое название"             # Главный label (EN или RU)
aliases:
  - "Главное название"
  - "alt-spelling"
  - "транслит"
  - "morphology variant"
tags: [concept, <domain-tag>, ...]          # `concept` обязательно
date: YYYY-MM-DD                            # Дата создания
type: concept                               # Всегда concept
language: ru | en | mixed
domain: biohacking | crypto | ai | business | cars | portugal | family | construction | media | travel
topic: <one of 15 topics from config.py>
value_score: 0.5-0.95                       # Reflects importance
status: active | stub | bridge
authored_by: <human-or-agent-id>
concepts: []                                # Связанные концепты (по wikilinks)
people: []                                  # Связанные люди (по wikilinks)
summary: "1-2 предложения — что это, почему важно для Anton."
---
```

**Опциональные поля:**

```yaml
parent: "MOC-Domain [internal]"          # Куда вписывается
predecessor: "Older-Concept [internal]"  # Если эволюция термина
status_review_after: YYYY-MM-DD   # Когда переоценить
related_projects: [proj-slug]     # Если связан с активными проектами
country: <slug>                   # Если концепт привязан к стране
region: <region>                  # Если концепт привязан к региону
```

## 2b. Country & Region поля (важно!)

С 2026-05-30 в vault введены `country:` и `region:` поля для geo-attribution:

- `topic:` остаётся по 15-теме pipeline (`11-Portugal` = home/expat life)
- `country:` детализирует конкретную страну (`switzerland`, `japan`, `usa`)
- `region:` группирует (`Europe`, `Asia`, `North-America`, `Oceania`, `Middle-East`, `Eurasia`, `Africa`, `South-America`)

**Когда создаёшь concept про страну** (например, `Lisbon`, `Portugal`, `Switzerland`):
- ОБЯЗАТЕЛЬНО ставь `country:` + `region:` в frontmatter
- Country MOCs (`90_MOCs/MOC-Country-{Name}.md`) автоматически подцепят концепт через Dataview

**Когда создаёшь bridge для country variant** (Лиссабоне → Lisbon):
- В bridge тоже ставь `country:` и `region:` от canonical

**Canonical country slugs:**
```
portugal, switzerland, japan, usa, australia, thailand, china, cambodia, myanmar,
russia, singapore, hong-kong, germany, south-korea, uk, france, poland, uae, spain,
canada, italy, philippines, sri-lanka, vietnam, estonia, austria, ukraine, turkey,
taiwan, belarus, indonesia, malaysia, norway, brazil, mexico, kazakhstan, georgia,
netherlands, kyrgyzstan, finland, mauritius, india, sweden, czech, belgium
```

**Region mapping:** см. `CLAUDE.md` или python `_country_region.json`.

---

## 3. Body — structure

```markdown
# {Title}

**Что это:** (1-2 предложения определения)

**Контекст для Anton:** (почему именно этот концепт важен в его жизни/работе)

## Хронология / История (если применимо)
- YYYY-MM-DD — событие 1
- YYYY-MM-DD — событие 2

## Reference points в архиве
- Конкретные посты/инсайты которые ссылаются на этот концепт

## Anton's playbook / стандарт (если есть)
- (опционально) — собственная методология / стандарт по этому концепту

## Связанные

- OtherConcept1 [internal]
- OtherConcept2 [internal]
- MOC-Domain [internal]

---

*Создан {who}, {date}. Status: {status}.*
```

**Длина body:**
- stub: 1-2 секции + Связанные (минимум для активации)
- active: 3-5 секций, в т.ч. собственный playbook
- mature: 5+ секций, evergreen content, можно использовать как reference

---

## 4. Naming conventions

### Slug (имя файла)

| Тип | Шаблон | Пример |
|---|---|---|
| Компания / продукт (EN/lat) | `PascalCase.md` или `lowercase.md` | `MicroMoney.md`, `n8n.md` |
| Аббревиатура | `UPPERCASE.md` | `ICO.md`, `CGM.md`, `LLM.md` |
| Person | `First-Last.md` | `Peter-Thiel.md` |
| Multi-word concept | `kebab-case-or-PascalCase.md` | `ARC-AGI.md`, `prompt-engineering.md` |
| Locations | EN canonical | `Lisbon.md`, `Silicon-Valley.md` |
| RU-канонический термин | строчные Марк. с дефисом | `биохакинг.md`, `аутофагия.md` |

### Title vs Aliases

- `title:` — каноническое имя что будет в bracket suggestions
- `aliases:` — ВСЁ остальное:
  - другая раскладка (EN+RU)
  - транслит
  - morphology forms (Лиссабон/Лиссабоне/Лиссабона)
  - точные battered wikilinks которые встречаются в архиве

**Правило:** alias должен быть **точной строкой**, как написано где-то в архиве. Не нормализуй — добавляй все варианты.

---

## 5. Bridge-нот rules

**Когда создавать bridge** (вместо concept):

- Термин — это morphology variant существующего (Лиссабоне → Lisbon)
- Термин — это transliteration существующего (Силиконовой Долины → Silicon-Valley)
- Термин — это abbreviation существующего (ARC → ARC-AGI)

**Шаблон bridge:**

```yaml
---
title: "{term}"
aliases: ["{term}"]
tags: [bridge, redirect]
date: YYYY-MM-DD
type: bridge
language: ru
topic: 00-Meta
value_score: 0.3
status: bridge
authored_by: <who>
canonical: "{Canonical-Slug}"
summary: "Bridge: {term} -> {Canonical} [internal]"
---

# {term}

→ {Canonical} [internal]

*Bridge-нота.*
```

Хранятся в `09-Bridges/`, не в `06-Concepts/`.

---

## 6. Anti-patterns — НЕ создавай

- ❌ Section headers моих distill-нот ("Контекст", "Связанные", "Источник", "Альтернативы", "Триггеры")
- ❌ Folder names ("Telegram", "Facebook", "Conversations", "Arhiv-Golosa")
- ❌ Topic tags ("Business-Finance" — это `topic:`, не концепт)
- ❌ Generic adjectives ("Подробный", "Глубокий", "Детальный", "Систематический")
- ❌ Meta-PKM terms ("Permanent", "Atomic", "Evergreen", "Луман", "auto-distilled")
- ❌ Trivial nouns без специфики ("Personal", "Research", "Application", "Discussion")
- ❌ Дубли (если уже есть → расширяй существующий или делай bridge)

---

## 7. Workflow для AI-агента

При получении задачи "создай концепты":

1. **Прочитай существующие** `06-Concepts/*.md` — собери набор canonical названий + aliases
2. **Фильтруй кандидатов** через §1 (когда создавать)
3. **Распиши Tier-ы:**
   - Tier 1 — canonical (новый домен/гэп)
   - Tier 2 — bridge (variant существующего)
   - Tier 3 — skip (шум)
4. **Покажи user-у** список с domain guess для каждого, **спроси подтверждение** для batch >10 файлов
5. **Создавай** batch:
   - Tier 1 → `06-Concepts/{slug}.md` с full body
   - Tier 2 → `09-Bridges/{slug}.md` с redirect-стрелкой
6. **Update CLAUDE.md** stats (concepts count)
7. **(Опционально)** запусти auto-link заново — новые концепты подцепятся к существующим файлам

---

## 8. Frontmatter validation

После создания **обязательно проверь:**

```bash
python3 -c "
import yaml; from pathlib import Path
for f in Path('Owner-Knowledge/06-Concepts').glob('*.md'):
    try:
        c = f.read_text(encoding='utf-8')
        fm_text = c.split('---')[1]
        fm = yaml.safe_load(fm_text)
        assert 'title' in fm, f.name
        assert 'aliases' in fm, f.name
        assert 'tags' in fm, f.name
        assert 'summary' in fm, f.name
        assert 'topic' in fm, f.name
    except Exception as e: print(f.name, e)
"
```

---

## 9. Auto-link integration

После создания концептов **запусти TF-IDF auto-link** ещё раз:
- Все файлы где упоминается canonical или alias → получают concept в `concepts[]`
- Это активирует backlinks в графе Obsidian
- Команда (упрощённая):
  ```python
  # См. P7-Sprint в session 2026-05-30
  # term_to_concept dict собирается из 06-Concepts/ + aliases
  # regex word-boundary применяется к 01-Conversations/
  ```

---

## 10. Examples — реальные созданные концепты (2026-05-30)

| Slug | Domain | Topic | VS | Aliases count |
|---|---|---|---:|---:|
| MicroMoney | business | 02-Crypto | 0.9 | 4 |
| Platinum-Engineering | business | 02-Crypto | 0.85 | 3 |
| NOAH | crypto | 02-Crypto | 0.85 | 3 |
| LinkedIn | business | 14-Business | 0.85 | 4 |
| n8n | ai | 01-AI | 0.85 | 1 |
| CGM | biohacking | 03-Biohacking | 0.85 | 3 |
| ICO | crypto | 02-Crypto | 0.85 | 5 |
| Portugal | portugal | 11-Portugal | 0.85 | 4 |

И 7 bridges (Лиссабоне, Лиссабона, Силиконовой, Кремниевой, Германии, Испании, CHAT).

---

## 11. Интеграция в граф — «Перелинковка важного» (origin: anton, 2026-06-14)

> ⭐ **STANDING RULE.** Создать заметку — это ещё НЕ сделать её частью Второго Мозга. Важная новая идея, которая просто *лежит* заметкой и ни с чем не связана — это **остров**, не узел графа. **Любой важный новый узел ОБЯЗАН быть интегрирован в граф знаний — связи в ОБЕ стороны.** Это касается ВСЕХ акторов (Антон + ассистенты + AI-агенты), не только импорта.

**Что считать «важным» (запускать интеграцию):** новый концепт · ментальная модель · фреймворк · теория · новый термин · проект · философия · исследовательский кластер · личный принцип · система организации знаний. Порог — как в §1 (≥3 повтора, существительное-сущность, доменная привязка). Рутинные заметки покрываются пассивным orphan-check, а не этим.

**Главный принцип — связность, не «симметрия ради симметрии»** (уточнено по deep-research 2026-06-14):
- не «новая заметка → старые», а **новая ↔ весь волт**;
- **forward-ссылка в Obsidian УЖЕ создаёт обратную (backlink) автоматически** → НЕ лепить явные обратные inline-ссылки везде ради симметрии (это overlinking и раздувание хабов);
- **явную обратную ссылку** в старую заметку добавлять ТОЛЬКО когда она полезна сама по себе: цель = концепт-хаб/MOC · асимметричная важная связь (`depends_on`/`defined_by`/`extends`) · без неё цель теряет контекст · источник даёт цели новый пример/контраргумент/метод;
- **что реально важно для «старые→новое» — вписать новый узел в нужный MOC/хаб** (≤2 MOC; новый MOC — только в deep-режиме); завести недостающие концепты (по §1, без запроса);
- **типизировать связи** закрытым словарём (`defines/defined_by/extends/depends_on/contrasts/example_of/evidence_for/method_for/same_cluster/moc_member/see_also`) — короткий глосс после ссылки: `- Цель [internal] — method_for: <почему>`.

**Гард-рейлы (анти-overlinking, идемпотентность):** ≤5–7 новых ссылок на обычную evergreen-заметку за прогон (MOC — исключение), ≤3 на секцию; `append_once` + dedupe-key `source::target::relation` (повторный прогон = no-op, без дублей); evidence обязателен для P0/P1, иначе defer; preflight на битые цели до записи. Мультиязычность RU/EN покрыта e5-эмбеддингами.

**Как искать связи — НЕ «сканируй весь волт» (утопия на 150k+ заметок), а дёшево достать кандидатов** (закон токенов: SQL/grep/RAG → потом LLM):
- **RAG** (`brain_ask.py`, e5+reranker) — семантические соседи, в т.ч. скрытые связи 2-3 порядка (причинность, аналогия, общий механизм, противоположный взгляд);
- **namesearch** (`find_name.py`) — точные имена/сущности (0 токенов);
- **grep** — буквальные упоминания;
- сверить `06-Concepts/` + aliases + `09-Bridges/`, чтобы не плодить дубль (§5).
LLM судит/линкует ТОЛЬКО топ-K кандидатов, а не весь корпус.

**Процедура (ранжируй P0 критич. / P1 важн. / P2 полезн. / P3 опц.):**
1. извлечь сущности из новой заметки;
2. достать кандидатов (RAG + namesearch + grep);
3. ранжировать P0–P3;
4. **превью двустороннего плана** (новое→старые · старые→новое · какие MOC · каких заметок не хватает) как ДО→ПОСЛЕ на реальных заметках → **ОК Антона**;
5. **бэкап волта** (`vault_backup.py`) ПЕРЕД записью;
6. проставить ссылки в обе стороны, обновить MOC, создать недостающие концепты;
7. `validate_links.py` (0 битых) + orphan-check + реиндекс (`brain_embed_update.py`) → **Integration Memo**.

**Глубокая перелинковка (раз в месяц / по команде):** работать по уже посчитанному списку островов (`_imports\orphan-scan\` + `Vault-Orphans.html`), прогоняя верхние кластеры через ту же процедуру; дубли → отдать на dedup. Loop-until-dry.

**Безопасность:** двусторонняя = правка СТАРЫХ заметок → бэкап перед, превью до, никогда без ОК; никогда не удалять / не трогать по маске `concept-*`/`person-*`; вставлять ссылки в блок `## Связанные`, не калечить соседние строки списка.

**Дома правила (не дублировать — каждый уровень ссылается вниз):** канон = этот §11; машинный подъём = `CLAUDE.md` § «перелинковка важного» + память `relink-mechanism`; исполняемое = skill `relink` (`/relink`, `/relink --deep`). Зеркало no-orphan-notes-rule [internal] (пассивно «≥1 входящая») — этот §11 активен («максимизируй связность важного узла»).

---

## 12. Онтология контента — ТИП · СЛОЙ · ЭТАП · ПРОВЕНАНС (origin: anton, 2026-06-27)

> ⭐ **STANDING.** Достройка решения decision-essence-evidence-ontology-2026-06-25 [internal] + регламента [[reglament-znat-vs-dokazat-essence-evidence]]. Цель: у КАЖДОЙ информационной ячейки видно — **что это, к чему относится, чьё, какого года, из чего получено, с чем связано**. Поля **АДДИТИВНЫ** (старые заметки не ломаются), метка = оверрайд, **БЕЗ дефолт-запрета**.

### 12.1. Контролируемый словарь `type:` (~15 значений вместо стихийных 109)

Каждый тип живёт на одной из полок (ЭССЕНЦИЯ = в умный поиск · ЭВИДЕНЦИЯ = в архив/grep):

| Полка / память | Канон `type:` | Что это |
|---|---|---|
| **ЭССЕНЦИЯ · semantic** | `concept` · `insight` · `belief` · `decision` · `person` (модель) | «что я думаю / решил» — атомарно, в RAG-«Ум» |
| **ЭССЕНЦИЯ · procedural** | `reglament` · `protocol` | правила/инструкции (Библия, standing) |
| **ЭССЕНЦИЯ · episodic** | `retro` · `session-distillate` | дистиллят сессий/звонков (отдельная полка) |
| **СТРУКТУРА** | `moc` · `bridge` · `template` | навигация/мосты/шаблоны |
| **НОВОЕ** | `experiment` | гипотеза / A-B / эксперимент / находка-альфа (§12.4) |
| **ЭВИДЕНЦИЯ · факты** | `company` · `crm-lead` · `contact` · `vc-fund` · `vc-investor` · `vc-project` | структурные факты → дублируются в `leads.db` |
| **ЭВИДЕНЦИЯ · сырьё** | `transcript` · `dm-conversation` · `telegram-post` · `facebook-post` · `session-ledger` · `ai-conversation` · `diary` · `apple-note` · `log` | первичный след, никогда не удаляется |

**Свод синонимов при бэкфилле (Этап 3):** `"person"`(в кавычках)→`person` · `reglament-card`→`reglament` · `transcript-episode`→`transcript` · `claude-session`→`ai-conversation` · `external-channel-post`/`telegram-day-ledger`→ближайший сырьевой. Новый тип вне словаря — только с явным обоснованием в отчёте.

### 12.2. Три новых поля (минимальная схема, АК-47)

```yaml
layer:  essence | evidence            # ТОЛЬКО оверрайд; дефолт берётся по папке (см. ниже)
stage:  raw | distilled | merged      # сырец / дистиллят / СКЛЕЕННЫЙ дистиллят (много сессий→одно)
evidence_refs:                        # откуда выжата суть (провенанс к сырцу/span)
  - "источник-1 [internal]"
  - "источник-2 [internal]"
```

- **`layer`** — дефолт по папке: `06/03/02/00/09/04-Coach/08`, `05-Resources/Protocols`, `90_MOCs`, `07-People`(модель) → essence; `01-Conversations` сырьё / `_session-md` / ledgers / DM-архивы / импорты → evidence; сессии → episodic. Поле пишем ТОЛЬКО для исключения.
- **`stage`** — этап обработки: `raw` (сырец), `distilled` (выжимка одной сессии: ретро/инсайт/решение), `merged` (СКЛЕЕННЫЙ дистиллят = синтез-концепт «Что я думаю о X» из многих сессий).
- **`evidence_refs`** — обязателен на `distilled`/`merged` essence: без ссылки на след essence-нота уходит в карантин (нельзя «спуститься к доказательству»). Зеркало уже существующих `concepts:`/`people:`/`source_post:`.

### 12.3. Три закона связи (из регламента)
1. Каждая ЭССЕНЦИЯ ссылается на свой СЛЕД (`evidence_refs`).
2. Беречь **ПОЧЕМУ и тупики** — суть = «вывод + рассуждение», не голый заголовок.
3. `status: active | superseded` — свежее бьёт старое.

### 12.4. Новый тип `experiment` (дом для гипотез / A-B / альфы)

Раньше дома НЕ было (0 заметок). Мини-схема:

```yaml
type: experiment
layer: essence
stage: distilled
status: hypothesis | running | done | superseded   # жизненный цикл
origin: anton
hypothesis: "одно предложение — что проверяем"
method: "A/B | замер | майнер | прогон"
result: "вывод (заполняется по завершении)"
evidence_refs: ["сырой-лог-или-база [internal]"]
theme: <тема>
```

Цепочка связей эксперимента (перелинковать по §11): `research/decision → hypothesis(experiment) → A-B/прогон → result → дом-инсайт`. Намайненная альфа: пока сырой кандидат — `layer: evidence` в `_imports`; после judge+апрув повышается до `experiment`/`insight` с `evidence_refs` на свою базу-ledger и линком в дом (`insight-prediction-ledger` и т.п.).

### 12.5. Что НЕ требуется (АК-47)
Поля `theme/topic/domain · project/related_projects · authored_by+origin · date/created · status · value_score · confidence` — **уже в каноне (§2), просто заполняй постоянно**. Новых сущностей не плодим; «тип контента / тема / проект / автор / год / источник / статус / уровень обработки / связь с RAG / релевантность / достоверность» из задачи Антона = маппинг: `type`+`layer` · `theme/topic` · `project` · `authored_by`+`origin` · `date` · `source`+`evidence_refs` · `status` · `stage` · `layer:essence` (=в RAG) · `value_score` · `confidence`.

---

## 🔗 См. также

- CLAUDE [internal] — главные правила vault
- [[concept-note]] — Templater-шаблон для ручного создания
- _concept-candidates-20260530 [internal] — TF-IDF mined candidates
- 06-Concepts/README [internal] (если есть)
- `scripts/utils.py` — `safe_move`, `read_markdown`, `write_markdown`

---

*Создано Claude Cowork, 2026-05-30. Update этот документ при изменении правил.*
