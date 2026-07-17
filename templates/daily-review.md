---
title: "Daily Review — <% tp.date.now("YYYY-MM-DD") %>"
aliases: []
tags: [daily, review]
date: <% tp.date.now("YYYY-MM-DD") %>
type: template
mood: <% tp.file.cursor(1) %>
energy: <% tp.file.cursor(2) %>
sleep_hours: <% tp.file.cursor(3) %>
hrv:
rhr:
weight:
training: <% tp.file.cursor(4) %>
fasting_hours:
supplements_taken: []
biomarkers_today: []
value_score: 0.5
language: ru
summary: <% tp.file.cursor(5) %>
---

# Daily — <% tp.date.now("dddd, DD MMMM YYYY") %>

## 1. Самочувствие (1–10)
| Метрика | Значение | Норма | Δ |
|---|---:|---:|---:|
| Sleep duration | <% tp.file.cursor(3) %> ч | 7.5 | |
| HRV (RMSSD) |  ms |  | |
| RHR |  bpm |  | |
| Energy 0–10 | <% tp.file.cursor(2) %> | | |
| Mood 0–10 | <% tp.file.cursor(1) %> | | |
| Focus 0–10 |  | | |

## 2. Что было ценного вчера/сегодня (3 пункта)
- 
- 
- 

## 3. Что прочитал → permanent-note кандидаты
- [[]] — 
- [[]] — 

## 4. Решения (→ 02-Decisions)
- 

## 5. Идеи / инсайты (→ 03-Insights)
- 

## 6. Прогресс по активным проектам
- [[]] — 
- [[]] — 

## 7. Биомаркеры / эксперименты
- 

## 8. Open loops / завтра
- [ ] 
- [ ] 
- [ ] 

## 9. Wins
- 

## 10. Lessons
- 

---

Связано: <% tp.date.yesterday("YYYY-MM-DD") %> · <% tp.date.tomorrow("YYYY-MM-DD") %>
