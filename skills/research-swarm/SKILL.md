---
name: research-swarm
description: >-
  Research swarm — turn ANY hypothesis (however wild/fringe) into an ARGUMENT MAP, never a verdict.
  Fans out 5 independent lenses — Consensus, Skeptic, Frontier, Historian, Experimental-Design — over
  the idea, then synthesizes for/against + evidence quality + confidence tier (established/emerging/
  speculative/fringe) + the cheapest decisive experiment. Trigger on "/research-swarm <hypothesis>",
  "рой агентов", "запусти рой по <X>", "построй карту аргументов по <X>", "разбери гипотезу <X>",
  "за и против <X>", "steelman both sides of <X>", "argument map for <X>". RECALL-first (brain_ask),
  outputs a vault note + a visual HTML argument-map dashboard. Embodies the epistemic-neutrality
  protocol (consensus ≠ truth; investigate, don't judge) and pairs with Alpha Protocol (R+DR).
  Built 2026-06-14.
---

# /research-swarm — карта аргументов по любой гипотезе (рой исследовательских агентов)

> 🧒 **When reporting to Anton:** end with a child-simple «Простыми словами» recap.
> ⚖️ **Doctrine:** this skill IS the operational arm of `protocol-epistemic-neutrality-fringe-research`. NEVER judge or mock the hypothesis. Consensus ≠ truth. Build a map of arguments + confidence — **расследование, а не приговор**. Bounded by `operating-agreement` safety invariants (no illegal/harm/bypass/fraud).

## When to use
Anton hands a hypothesis — frontier science (antigravity, perpetual motion, anomalous materials, radical longevity, models of consciousness/time), an unusual business model (DAO/network states, no-employee AI co, token labor markets), or a controversial/stigmatized vertical (adult, gaming, gambling). Goal: a balanced, grounded **argument map**, not a yes/no.

## The 5 lenses (run as a parallel swarm)
1. **Consensus** — steelman the current mainstream/established view. What does well-replicated science / the market actually hold, and why.
2. **Skeptic** — strongest arguments AGAINST. Where the idea breaks, hidden assumptions, falsification points, known failure modes.
3. **Frontier** — strongest arguments FOR. Steelman the believer: what would have to be true, adjacent emerging evidence, why it's not obviously impossible.
4. **Historian** — precedents and base rates. Ideas once dismissed then vindicated (and once hyped then debunked); the historical analog for THIS idea.
5. **Experimental-Design** — what measurement/experiment would confirm or refute, the **cheapest decisive test**, what data to gather first.

Each lens does light, targeted web grounding (WebSearch/WebFetch) — claims should be evidenced, not just model priors — but stays token-aware. The synthesis NEVER returns a verdict; it returns a confidence tier + open questions.

## Control node — Verifier-Calibrator (added 2026-06-15, via Alpha R+DR)
After synthesis, one **Verifier-Calibrator** node runs (the swarm's *acceptance function*, not another opinion). It (1) audits the strongest for/against claims — supported / partial / unsupported, (2) re-derives the confidence tier from **evidence** (support density + cross-lens agreement), not vibe, lowering tiers that rest on unsupported or single-lens claims, and (3) may **abstain**: the new tier `insufficient` is a first-class honest answer when evidence is too thin to place the idea on the established→fringe axis. The calibrated tier + claim audit + flags surface in the note and dashboard. This is the DR-recommended **control plane** over the 5-lens **content plane** (gaps: no verifier / qualitative-not-calibrated tiers / no abstain lane). Decision: vault `02-Decisions\decision-research-swarm-v2-upgrade`.

## How to run

**Step 0 — parse** the hypothesis from Anton's message (everything after the trigger). If it's a vague one-liner, ask ONE clarifying question first (scope/domain), else proceed.

**Step 1 — RECALL first** (token law — cheap before LLM/web). Pull what Anton already thinks on the topic:
```
python "$IMPORTS_ROOT/brain_ask.py" "<hypothesis>" --k 8
```
Keep the synthesized recall as `recall_context` (Anton's prior notes/leanings on the topic — feeds every lens so the swarm builds on his own thinking, not from zero).

**Step 2 — run the swarm** via the Workflow tool (this skill IS your explicit opt-in to orchestrate):
```
Workflow({ scriptPath: "C:\\Users\\_\\.claude\\skills\\research-swarm\\workflow.js",
           args: { hypothesis: "<hypothesis>", recall_context: "<from step 1>" } })
```
The script fans out the 5 lenses (parallel barrier — synthesis needs all), a synthesis agent merges them, then the **Verifier-Calibrator** audits the strongest claims and calibrates the tier (or abstains → `insufficient`). Returns the structured **argument map** object with a `calibration` block.

**Step 3 — persist (backup first).** `python "$IMPORTS_ROOT/vault_backup.py"` then:
- Write the map as a vault note in `03-Insights\Research-Swarm\<YYYY-MM-DD>-<slug>.md` (frontmatter `type: insight`, `origin: anton`, `tags: [research-swarm, argument-map]`; body = for/against tables, confidence tier, historical analogs, open questions, the decisive experiment). Link it to `[[protocol-epistemic-neutrality-fringe-research]]` + `[[insight-glavnaya-tsel-tsifrovoj-dvojnik]]` and any concept the topic touches (no-orphan: ≥1 inbound).
- Dump the map object to `<skill>\last_map.json` and build the visual:
```
python "$USERPROFILE/.claude/skills/research-swarm/build_argmap_dashboard.py" <map.json> <out.html>
```
Dashboard → `$OBSIDIAN_VAULT/_Dashboards/Research-Swarm/<slug>.html`. Offer to open it (Anton works by eye).

**Step 4 — reindex** so the new note is searchable: `python "$IMPORTS_ROOT/brain_embed_update.py"`.

**Step 5 — report** to Anton: the confidence tier, the 2-3 strongest for/against, the cheapest decisive experiment, link to the dashboard — and the ELI5 recap. NEVER editorialize a verdict; present the map.

## Scaling (AK-47)
Default = 5 lenses, single pass. For a big/important hypothesis Anton can say "глубже" → add a second round per lens or 3-vote adversarial verification of the strongest claims (loop-until-dry). Don't over-build by default.

## Relation
Operational arm of vault `protocol-epistemic-neutrality-fringe-research` · memory [[epistemic-neutrality]]. Pairs with `/alfa-search-recall-deepresearch` (R+DR — recall→gap→deep-research→synthesis; the swarm is the multi-lens synthesis engine). Distinct from `/ask` (single recall) and `/deep-research` (web fan-out, single perspective). Serves [[main-goals]] goal #1 — the twin reasons like Anton-the-researcher.
