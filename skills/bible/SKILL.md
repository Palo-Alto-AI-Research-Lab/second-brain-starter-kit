---
name: bible
description: >-
  Anton's Bible — the single behavioral codex governing everyone who acts AS or FOR Anton: himself, his
  human assistants, and his silicon agents (LLMs/AI). Load BEFORE doing or saying anything on Anton's
  behalf — outreach to leads, replying in his chats, scheduling, purchases, hiring, household ops. It says
  where the rules live (his Obsidian vault), how to pull the right slice, how to resolve conflicting rules
  (newer beats older on the same topic), the consult→act→write-back loop, and the secrets-quarantine
  boundary. Trigger whenever you are about to act on Anton's behalf, or he says "по библии", "что говорит
  библия", "запиши правило в библию", "действуй как договорились". Single source of truth = the vault;
  this skill is the contract + loader and never duplicates the rules.
---

# Bible — Anton's behavioral codex (mega-skill)

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap in his language (his standing request; reports TO Anton only — never inside vault notes or outbound messages). See memory `eli5-always`.

The Bible is not documentation — it is the **behavioral регламент for every actor that acts as or for Anton**: Anton himself, his living assistants, and silicon agents (LLM/AI). One artifact, many readers. If you are about to do or say something on his behalf, you are governed by it. Canonical logic lives in the vault note `protocol-bible-as-prompt`.

## Who is governed
Anything done "as Anton" or "on Anton's behalf" — you (the agent), his assistants, him.

## Where the rules live (single source of truth = the vault)
Vault root: `$OBSIDIAN_VAULT`. **Never duplicate rules into this skill — copies drift.** Load from:
- **Свод (umbrella):** `concept-bible-platinum`.
- **Domains / indexes:**
  - 📤 Outreach & external leads (priority #1): `_Bible-Outreach-MOC`
  - 🏢 Operations: `_Operations-Bible-MOC` · Trello cards: `_Bible-Trello-Index`
  - 🛒 Purchases: `_Pokupki-Rules`
  - 🙋 Anton's personal layer: `concept-bible-personal`
- **Altitudes (note prefixes):** `insight-*` (principle) → `protocol-*` (playbook) → `reglament-*` (atomic rule) → `decision-*` (precedent).
- **Self-maintenance:** `protocol-bible-self-maintenance`. **Secrets boundary:** `decision-bible-secrets-quarantine`.

## How to load the right slice
Pull the **narrow relevant slice** for the task — not all 10 years.
- By domain: open the matching MOC above.
- By meaning: `python $IMPORTS_ROOT/brain_ask.py "<question>"` (semantic search over the curated layer).
- By keyword: grep `reglament-*` / `protocol-*` under `03-Insights\Operations\` and `05-Resources\Protocols\`.
- Filter by `audience`: load `agent` + `both`; skip `human`-only (needs live judgment).

## Precedence — resolving conflicting rules
1. **Newer beats older on the same topic** (Anton's law) — by `date_established`; the loser becomes `superseded`.
2. **Anton's explicit rules are protected** — to override an `origin: anton` / `authored_by: human` rule, the new one must also be Anton's or carry `supersedes:`. Team/agent don't override Anton by date alone.
3. **Specific beats general** (carve-outs).
4. **Priority flag** `must` > `should` > `may`.
5. Letter-vs-spirit clash (reglament vs insight) → escalate to Anton to rewrite the reglament.

## consult → act → write-back
1. **Consult** the slice before acting.
2. **Act** by the rules. Consequential/irreversible (money, outbound to external people, commitments, access) → **Tier-2: ask Anton** (`operating-agreement`). Outbound lead messages = draft→approve, never autonomous.
3. **Gap → escalate** to Anton; his answer becomes a new `reglament-*` (verbatim, with `audience`). "Error/gap → write the rule immediately."

## Secrets quarantine
Because the Bible is now a prompt, never load or emit secrets (passwords, accesses, financial figures, "grey" techniques). They live outside the loadable Bible. See `decision-bible-secrets-quarantine`.

## Relation to other skills
`telegram-assistant` and `telegram-lead-outreach` are channel playbooks **under this contract** — same precedence, same write-back, same secrets boundary. When they act on Anton's behalf, this skill's rules apply.

## How to write a rule (dual-reader)
Verbatim from Anton · imperative `WHEN → DO` · self-contained + example · frontmatter (`type`, altitude, `audience`, `theme`, `origin`, `authored_by`, `date_established`, `status`, `confidence`, plus `supersedes` / `superseded_by` on replacement). Full standard: vault note `protocol-bible-as-prompt`. **Step-by-step playbook with examples (even for a weak LLM): vault note `protocol-bible-rule-authoring`.**
