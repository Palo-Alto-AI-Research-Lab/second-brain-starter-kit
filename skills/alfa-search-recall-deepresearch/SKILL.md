---
name: alfa-search-recall-deepresearch
description: >-
  Anton's mandatory decision protocol ("Alpha Protocol") for any new STRATEGIC work — never jump to
  implementation on local recall alone. Run RECALL (own Second Brain) → GAP analysis → emit a DEEP RESEARCH
  PROMPT for Anton to run in an EXTERNAL deep-research tool (Claude Code does NOT do the deep DR itself) →
  SYNTHESIS + Decision Memo when he brings results back. Trigger on "/alfa-search-recall-deepresearch",
  "alpha protocol", "alfa", "альфа", "R+DR", "RDR", "РДР", "R + DR", "recall + deep research", "recall + dr", or whenever
  starting a strategic decision. Anton's shorthand for Deep Research: "DR" = "ДР" = "Резеч" = "Deep Research"
  are synonyms — bare DR/ДР/Резеч = the Deep-Research step (emit the DR prompt), R+DR = the full protocol
  (context disambiguates; "ДР" can also mean birthday — ask if unclear). (new product/feature/AI-functionality/tokenomics/GTM/market/business-module/
  investment-hypothesis/architecture). This is "Recall + Deep Research":
  recall is necessary but NOT sufficient for strategic work. Pairs with /ask (recall) and extends the
  RECALL-before-activity rule. Canon: vault protocol-alpha-protocol-recall-plus-deep-research; always-on lift
  in CLAUDE.md § "Alpha Protocol".
---

# 🅰️ Alpha Protocol — Recall + Deep Research before deciding

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap (his standing request; reports TO Anton only).

**Binding rule (must):** For ANY new strategic function, product, business model, tokenomics, AI-functionality, GTM, market, investment hypothesis, or architecture decision — it is **FORBIDDEN to go to implementation on recall alone**. Do `Recall → Gap → Deep Research → Synthesis → Decision Memo` first. Recall is necessary but NOT sufficient for strategic work. Canon: vault note `protocol-alpha-protocol-recall-plus-deep-research`.

## When this fires
- Anton writes the trigger: **`R+DR`** (= **`RDR`** = **`РДР`** — `+`/space & case don't matter), **`alpha protocol`**, **`альфа`** (or `/alpha`).
- OR you are about to start a **Level-2** task (below) — invoke this protocol proactively, don't wait for the trigger.

## Levels (size the response to the task)
- **L0 — Quick** (answer a question, fix a bug, tiny tweak): plain recall is enough. No DR.
- **L1 — Recall** (new module / hypothesis / feature / market): recall memory + internal docs + past research + form hypotheses. **Do NOT decide immediately.** Usually no external DR unless it turns strategic.
- **L2 — Recall + DR** (strategic — see binding rule): run the full flow below.

## ★ Proactive multi-agent reflex (EVERY task, not just strategic) — set 2026-06-25
The user FORGETS whether they need agents — so YOU remember and propose, reflexively, after RECALL on **any** task. Canon: vault `reglament-proaktivno-predlagay-agentov` + memory `multi-agent-offer-reflex`; tool-choice canon = `decision-adopt-agent-teams-scoped`.

1. **Cheap-first:** did SQL/grep/RAG already answer it? → done, no agents.
2. **Type = Decision · Comparison · Analysis · Research-synthesis** where several INDEPENDENT lenses materially improve the answer (inclusion test: *will one lens's finding redirect another before both finish?*)? NO (import/fix/ops/mechanical/trivial) → single agent, stay silent about agents. YES → multi-agent fits → fork:
   - **AUTO-RUN (announce, don't ask):** read-only · no vault write · no outbound · ~2 Sonnet agents · not huge → spawn advocate↔skeptic (or champion-X↔champion-Y, or N orthogonal lenses) then synthesize. First line: `🤝 Запускаю 2 Sonnet-агентов (read-only)…`.
   - **OFFER + ASK (`+`):** vault-write/outbound · ≥3 agents or long/expensive · strategic-irreversible (→ full R+DR L2 below) · [REDACTED-SECRET-PATH] One line: `🤝 Агенты: советую (…); собрать? (+)`.
3. Teammates on **Sonnet**; don't auto-keep an Opus lead; never ask for "consensus" — preserve dissent. Mechanism = Agent-tool subagents (cheap, ~80% of the value) or native Agent Teams when enabled.

This is **L1.5** — broader than the L2 strategic flow: it fires on everyday comparisons/analysis, not only big decisions. The advocate/skeptic/frontier panel below is the same machinery.

## The flow (what YOU, Claude Code, do)

**Step 1 — RECALL.** Pull EVERYTHING we already have on the topic (per the RECALL-before-activity rule):
- memory: `MEMORY.md` + grep the memory dir
- vault meaning: `python "$IMPORTS_ROOT\brain_ask.py" "<topic>"` (or `/ask`)
- vault exact: grep concepts/insights/protocols/people/leads
- SQLite facts where relevant (Platinum CRM, browser_history, etc.)
Report concisely: what we know · what we already researched · prior conclusions · prior mistakes.

**Step 2 — GAP ANALYSIS.** State plainly: what we do NOT know, which questions stay open. This sharpens the DR prompt so the external tool digs where we're blind, not where we're already strong.

**Step 3 — DEEP RESEARCH PROMPT (hand-off).** ⭐ FIRST allocate the DR number (anton 2026-07-03): `python $IMPORTS_ROOT\dr_registry.py new "<тема>" --tool <chatgpt|gemini|grok|cowork>` → prints `DRYY-MM-DD-МАШИНА-NN` (machine code auto-detected — per-machine sequences, no sync collisions) and registers it in `_DR-Registry.md`. Put the ID as the FIRST line of the emitted prompt (`# DR26-07-03-ZB-01 — <тема>`) so the external chat inherits it as its title and exports match the registry. Counter unsure → `--gap` (+10). When the report comes back: `dr_registry.py update <ID> --status collected --file "<путь>"`. Canon: Bible `reglament-numeratsiya-dr-i-reestr`. You do NOT run the deep research yourself. **Hybrid mode:** you MAY do a light in-session web pass (WebSearch/WebFetch) to sharpen the prompt and catch the obvious — but the deep, exhaustive DR is done by Anton in an EXTERNAL tool (ChatGPT/Gemini/Perplexity Deep Research). Emit the prompt for him to copy:
- Read the canonical template: `$OBSIDIAN_VAULT\08-Templates\deep-research-prompt-template.md` and emit it **filling `{topic}`**, prepending a `CONTEXT:` block with the recall findings + open questions from Step 2 (so the external DR doesn't redo what we know).
- Present it as one clean, clearly-marked copy-paste block. Tell Anton: "вставь во внешний Deep Research, принеси результат назад — я сделаю Synthesis."

**Step 4 — SYNTHESIS + DECISION MEMO** (after Anton returns the DR results). Merge memory + DR into a **Decision Memo**:
`проблема · текущие знания · результаты DR · варианты решения · риски · рекомендации`.
Only AFTER the Decision Memo do we start implementation.

## Notes
- If a `/schedule`-style recurring research cadence emerges for a topic, evaluate per `evaluate-recurring-into-routine`.
- The DR prompt template is the single source — if it changes, edit the vault template file, not a copy.
- This skill is SEARCH+STRUCTURE; the deep-research harness skill (`deep-research`) is the in-session web variant Anton can opt into, but his default flow is the external hand-off above.
