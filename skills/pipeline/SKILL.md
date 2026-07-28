---
name: pipeline
description: >-
  Work Anton's lead pipeline — CRM/outreach triage: who needs action TODAY (replied→send Calendly;
  Calendly sent 24h+ but not booked→booking nudge; awaiting-reply→check for new inbound; going cold→
  follow-up; booked→close out), ranked and ready to send (Anton edits after if off). Trigger on "/pipeline",
  "разбери пайплайн", "кого пинговать", "что по лидам", "work my leads", "кто завис в воронке",
  "follow-up due". Reads live state in tg_followups.json + the Platinum CRM; executes via
  telegram-lead-outreach (send-direct per 2026-06-16 — Anton edits after; still NO mass auto-blast). This is TRIAGE (what to work); telegram-lead-outreach is EXECUTION.
---

# /pipeline — work the leads (today's actions)

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap. NEVER inside lead messages.
> 📖 Operates under the `bible` skill — outreach codex `_Bible-Outreach-MOC`. Outbound = **send-direct (Anton 2026-06-16 — he edits the sent message after)**; NO mass auto-blast (pace + personalize per lead). Money / commitments / credentials → escalate.

## 🖥️ Визуальный дашборд первым (Антон работает глазами)
`python "$IMPORTS_ROOT/build_pipeline_dashboard.py"` → открой `$OBSIDIAN_VAULT/_Dashboards/Pipeline-Dashboard.html`: канбан по стадиям (🔥 ответили → ⏰ напомнить → ⏳ бронь → 👀 ждём → ✅ готово) + готовые черновики (клик = копировать). Только просмотр, ничего не шлёт. Текстовый разбор ниже — для самих действий (send-direct, Антон правит постфактум).

## Step 1 — Load live pipeline state (deterministic, ~free)
Read `$IMPORTS_ROOT/tg_followups.json` (the watcher's live state). Each `pending[]` lead: `lead`, `chat_id`, `username`, `pitch_sent`, `calendly_sent`, `replied`, `booked`, `booking_confirmed`, + a `check` instruction. Plus `calendly_sent_at` (for the 24h nudge) and `booking_nudge_rule`.
Deeper history per lead: `04-Projects\crypto\Platinum-CRM\_Platinum-CRM-MOC.md` + its lead cards, or `/ask --leads "<name>"`.

## Step 2 — Classify each lead → TODAY's action (priority order)
1. 🔥 **Replied, Calendly not sent** (`replied` set, `calendly_sent:false`) → draft `calendly_text` to that chat. Warm NOW = top priority.
2. ⏰ **Calendly sent ≥24h, not booked** (`calendly_sent:true`, no `booking_confirmed`, `calendly_sent_at` >24h ago) → draft `booking_nudge_text` (leads forget to book — standing rule).
3. 👀 **Awaiting reply** (`pitch_sent:true`, no `replied`) → run the lead's `check`: read recent messages of `chat_id` (Telegram MCP; see `telegram-howto`) for a NEW inbound (sender ≠ Tony) after our pitch. If replied → it becomes case 1.
4. ❄️ **Going cold** (pitched long ago, no reply, no nudge) → propose ONE soft follow-up, or mark to drop.
5. ✅ **Booked/confirmed** → close out; suggest removing from `pending`. Never re-pitch.

## Step 3 — Output the worklist, then act on Anton's go
- Show a ranked table: **lead · state · proposed action · exact draft text**.
- Send each directly (Anton edits the sent message if something's off); NO mass auto-blast — pace + personalize per lead.
- After sending, **UPDATE `tg_followups.json`** (`calendly_sent`, `booking_confirmed`, `booking_nudge_sent`…) so state stays true.
- Refresh the lead's CRM card (telegram-lead-outreach capture step).
- End with 🧒 recap.

## Guardrails
- Voice = Anton's words **verbatim** (his rule); concise, без воды.
- Money / commitments / credentials → escalate, never autonomous.
- If `tg_followups.json` is empty/stale → say so; offer to rebuild from recent Telegram via telegram-lead-outreach ("find + capture").
