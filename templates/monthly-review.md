---
title: "Monthly Review — <% tp.date.now('YYYY-MM') %>"
aliases: []
tags: [monthly-review, periodic, MOC]
date: <% tp.date.now('YYYY-MM-DD') %>
type: template
authored_by: anton
language: ru
value_score: 0.8
topic: 00-Meta
summary: "Monthly review за <% tp.date.now('YYYY-MM') %>: вектора, прогресс по проектам, decisions retrospective, output."
---

# 🌙 Month <% tp.date.now('YYYY-MM') %>

> Цель monthly: посмотреть на месяц с высоты — что сдвинулось, что застряло, куда направляться. Output: month-end newsletter / personal report.

## 1. 🎯 Главные сдвиги этого месяца (3-5 vectors)

1. 
2. 
3. 

## 2. 🚀 Проекты — прогресс

```dataview
TABLE WITHOUT ID
  file.link AS "Проект",
  status AS "Статус",
  priority AS "Приоритет",
  summary AS "Сейчас"
FROM "04-Projects"
WHERE status != "completed" AND status != "archived"
SORT priority DESC
```

**Что закрыли / что застряло:**
- ✅ Закрыли:
- 🟡 В работе:
- 🔴 Заблокировано:

## 3. 💎 Top-20 inсайтов месяца (vs ≥ 0.8)

```dataview
TABLE WITHOUT ID
  file.link AS "Insight",
  topic AS "Топик",
  summary AS "Идея"
FROM "03-Insights"
WHERE file.cday >= date(today) - dur(31 days) AND value_score >= 0.8
SORT value_score DESC
LIMIT 20
```

**Самое важное (выбрать 3):**
1. 
2. 
3. 

## 4. ⚖️ Top-20 decisions месяца

```dataview
TABLE WITHOUT ID
  file.link AS "Decision",
  topic AS "Домен",
  value_score AS "VS"
FROM "02-Decisions"
WHERE file.cday >= date(today) - dur(31 days)
SORT value_score DESC
LIMIT 20
```

**Какие decisions требуют review через 3 мес?** (поставить `review_after`)
- 

## 5. 🔄 Decisions на пересмотр в этом месяце

```dataview
TABLE WITHOUT ID
  file.link AS "Decision",
  review_after AS "Review After",
  summary AS "Контекст"
FROM "02-Decisions"
WHERE review_after AND date(review_after) <= date(today) + dur(31 days)
SORT review_after ASC
```

**Retrospective:**
- Что подтвердилось:
- Что переоценил:
- Что отменил:

## 6. 📊 Метрики месяца

| Метрика | Значение |
|---|---|
| Новых файлов в 01-Conversations | (запустить count script) |
| Новых Insights | |
| Новых Decisions | |
| Новых Concepts | |
| HRV avg | |
| Sleep avg | |
| Revenue / fundraise (если применимо) | |
| Книг прочитано | |

## 7. 🧬 Health/biohacking summary

- Эксперименты:
- Что работает:
- Что отменил:
- Биомаркеры: 

## 8. 👥 Network — кого встретил / в кого инвестировал внимание

- VIP people met:
- Reactivated connections:
- New people who matter:

## 9. 📤 Output этого месяца

- Posts/newsletter:
- Talks/podcasts:
- Investments:
- Public commitments:

## 10. 🎬 Next month — vectors (3-5)

1. 
2. 
3. 

## 11. 💭 Personal note

(одно-два предложения вольным языком — что я чувствую про этот месяц)

---

## 🔗 См. также

- Dashboard-Biohacking-Longevity [internal]
- Dashboard-Crypto-Web3 [internal]
- [[Dashboard-AI-Tech]]
- Dashboard-Business-Finance [internal]
- Dashboard-Family-Kids [internal]
- Dashboard-Portugal [internal]
- 2026-quarterly-review-Qx [internal] (если есть)

---

*Шаблон Templater. Используется через Periodic Notes plugin.*
