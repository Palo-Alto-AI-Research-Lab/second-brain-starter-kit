---
title: "Weekly Review — <% tp.date.now('YYYY-[W]ww') %>"
aliases: []
tags: [weekly-review, periodic, MOC]
date: <% tp.date.now('YYYY-MM-DD') %>
type: template
authored_by: anton
language: ru
value_score: 0.7
topic: 00-Meta
summary: "Weekly review за <% tp.date.now('YYYY-[W]ww') %>: что было, что узнал, что распределить."
---

# 📅 Week <% tp.date.now('YYYY-[W]ww') %> — <% tp.date.now('YYYY-MM-DD') %>

> Цель weekly: достать инсайты из последних 7 дней, переместить высокоценные в Insights/Decisions, закрыть open loops, спланировать следующую неделю.

## 1. 📥 Inbox-проверка

- [ ] `Inbox-Processing/` пуст? (Dataview ниже)
- [ ] Все ChatGPT/Granola за неделю обогащены? (запустить incremental batch если нужно)

```dataview
LIST FROM "Inbox-Processing"
```

## 2. 📝 Daily-notes за неделю

```dataview
LIST
FROM "00-Daily"
WHERE file.cday >= date(today) - dur(7 days)
SORT file.cday DESC
```

**Что сделал за неделю** (1-2 пункта на день, что важного):
- Пн:
- Вт:
- Ср:
- Чт:
- Пт:
- Сб:
- Вс:

## 3. 💎 Новые high-value (vs ≥ 0.7) за эту неделю

```dataview
TABLE WITHOUT ID
  file.link AS "Заметка",
  value_score AS "VS",
  topic AS "Топик",
  summary AS "Идея"
FROM "01-Conversations"
WHERE file.cday >= date(today) - dur(7 days)
  AND value_score >= 0.7 AND !archive
SORT value_score DESC
```

**Что из этого distill в PARA?** (отмечайте distilled_to при перемещении)
- 

## 4. 🔄 Decisions на пересмотр на этой неделе

```dataview
LIST
FROM "02-Decisions"
WHERE review_after AND date(review_after) <= date(today) + dur(7 days)
SORT review_after ASC
```

**Решения по review** (всё ещё актуально / нужно поменять):
- 

## 5. 🧠 Что прочитал — кандидаты на permanent-notes

Литература, статьи, подкасты, видео которые меня тронули за неделю:

```dataview
LIST
FROM "06-Concepts" OR "05-Resources"
WHERE file.cday >= date(today) - dur(7 days)
SORT file.cday DESC
```

**Permanent-кандидаты** (атомарные мысли которые войдут в 03-Insights):
- 

## 6. 🎯 Open loops / unfinished

- [ ] (что осталось висеть)

## 7. 📈 Biomarkers / wellbeing (если веду)

- HRV avg:
- Sleep avg:
- RHR avg:
- Energy 1-10:
- Notable: 

## 8. 👥 People — кому позвонить / написать на след неделе

(networking-список из MOC-People)
- [ ] 
- [ ] 

## 9. 🎬 Next week — приоритеты (max 3)

1. 
2. 
3. 

## 10. 📤 Output на след неделе

- [ ] Newsletter draft / FB-пост / контент на след неделю
- [ ] Update Dashboard, если новые домены появились

---

## 🔗 См. также

- 2026-monthly-review-XX [internal] (текущий месяц)
- Dashboard-Biohacking-Longevity [internal]
- Dashboard-Crypto-Web3 [internal]
- Dashboard-Business-Finance [internal]

---

*Шаблон Templater. Используется через Periodic Notes plugin.*
