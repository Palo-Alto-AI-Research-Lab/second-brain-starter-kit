---
name: agenda
description: Anton's day at a glance, on demand — today's calendar + what needs HIM personally (leads due, real humans awaiting a reply, deadlines) pulled from Calendar + Telegram, ranked. The manual twin of the scheduled "Tg calendar agenda" task. Trigger on "/agenda", "что у меня сегодня", "повестка дня", "план на день", "что на сегодня", "what's on today", "my agenda", "какие встречи сегодня". READ-ONLY summary — it never sends or commits anything. Pairs with /pipeline (leads) and /coach (accountability).
---

# /agenda — today at a glance

> 🧒 When reporting to Anton end with a child-simple "Простыми словами" recap. (memory `eli5-always`)

A fast, read-only "what does my day look like" — the manual counterpart of the scheduled `Tg calendar agenda` task (same intent, fired by hand). It assembles, it does NOT act (sending/booking lives in /pipeline + /intro).

## Assemble (read-only)
1. **Calendar** — `mcp__a63ab772-..._list_events` for today across Anton's calendars (`list_calendars` first if unsure). If that tool id is stale (connector reconnected), load it via ToolSearch query "calendar list events" like the `tg-calendar-agenda` twin does. His reminders live in **`owner.calendar@example.com`**, times in **Europe/Lisbon** (he lives there mostly — [[remind-anton-via-calendar]]). List meetings/reminders with times.
2. **Needs HIM personally** — the rare things only Anton can clear: leads due today (read `$IMPORTS_ROOT/tg_followups.json` + Platinum CRM, or call /pipeline's triage logic), a real human awaiting his reply, a money/legal deadline. He doesn't read email → surface only the email items that need HIM ([[anton-doesnt-read-email]]); no digest walls.
3. **Today's one commitment** — if /coach logged an evening "tomorrow's one commitment" in `04-Coach/`, echo it.

## Rank & present
Top of the list = time-bound + needs-Anton (a meeting in 2h, a lead going cold). Then fixed calendar blocks. Then nice-to-have. Keep it tight — this is a glance, not a report. Offer the obvious next action ("работать лиды → /pipeline", "встреча без повестки → /intro").

## Safety
Read-only. Never send a message, book, or commit from here — hand off to /pipeline, /intro, or ask.

## Output
A short ranked agenda (≤~8 lines): ⏰ time-bound first, then context. Then 🧒 recap. Visual option: the Life-OS / Coach dashboards already render the day by eye ([[prefer-visual-dashboards]]).
