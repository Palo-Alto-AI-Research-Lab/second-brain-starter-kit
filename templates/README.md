---
title: "08-Templates — каталог шаблонов"
aliases: []
tags: [meta, templates]
date: 2026-05-28
type: template
---

# 08-Templates

Шаблоны для [Templater](https://github.com/SilentVoid13/Templater). Чтобы они подхватились — в Templater Settings указать `Template folder location: Owner-Knowledge/08-Templates`.

## Каталог

| Шаблон | Когда применять | Куда сохранять |
|---|---|---|
| `literature-note.md` | Прочитал статью/книгу/подкаст — фиксируем источник + конспект | `05-Resources/Literature/` или `01-Conversations/_transcripts/` |
| `concept-note.md` | Атомарная permanent-note по Луманну: одна идея на файл, evergreen | `06-Concepts/` |
| `project-note.md` | Активный проект с целью, DoD, roadmap | `04-Projects/` |
| `daily-review.md` | Ежедневный review с биомаркерами + извлечением | `00-Daily/` (создать через Periodic Notes plugin) |

## Принципы шаблонов

1. **YAML frontmatter совместим с pipeline**: поля `title`, `aliases`, `tags`, `date`, `type`, `value_score`, `language`, `summary`, `concepts`, `people` — это те же поля, что заполняет `scripts/05-apply-results.py`. Не перезаписываются.
2. **`aliases: []`** — заполнять минимум RU + EN-вариантом термина. Это разрешает русско-английские wikilinks.
3. **`status: stub`** для концептов — Dataview-запросом легко вытащить недозаполненные заметки.
4. **Cursor-якоря** (`<% tp.file.cursor(N) %>`) — Templater после вставки прыгает по полям Tab-ом.

## Сопутствующие папки

Если ещё не существуют — создать:
- `00-Daily/` — для daily-review (Periodic Notes plugin делает автоматически)
- `05-Resources/Literature/` — хаб литературных заметок
- `90_MOCs/` — Maps of Content (топ-уровень навигации)
- `02-Decisions/` — решения (структура ADR-light)

## Dataview-запросы для самопроверки vault-а

````dataview
TABLE WITHOUT ID
  file.link AS "Концепт",
  status,
  length(file.outlinks) AS "→ links",
  length(file.inlinks) AS "← links"
FROM "06-Concepts"
WHERE status = "stub"
SORT length(file.inlinks) DESC
LIMIT 50
````

````dataview
LIST
FROM "04-Projects"
WHERE status = "active"
SORT date_start DESC
````

````dataview
TABLE WITHOUT ID
  file.link AS "Lit-note",
  authored_by,
  year,
  value_score
FROM "05-Resources/Literature"
WHERE read_status = "unread"
SORT value_score DESC
````
