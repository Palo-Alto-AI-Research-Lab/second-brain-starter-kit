# Vault conventions — $OBSIDIAN_VAULT

Reference for `obsidian-ingest`. Load when classifying notes, naming files, or writing frontmatter.

## Folder layout (PARA-inspired)

| Folder | Holds | Notes |
|---|---|---|
| `01-Conversations/` | raw inputs | `ChatGPT/` (bulk exports), `Voice/` (whisper transcripts), `Telegram/<chat>/` (chat imports: `posts/`, `sessions/`, `_*-MOC.md`), `Facebook/posts/` (Facebook export), `<Transcript-Name>/` (podcast/YouTube splits). Date-prefixed flat notes also live here. |
| `02-Decisions/` | decisions | sparsely used |
| `03-Insights/` | `insight-*` notes | non-obvious learnings, schemes, rules-of-thumb |
| `04-Projects/` | active work | domain subfolders: biohacking, crypto, history, personal, philosophy, science, tech |
| `05-Resources/` | external reference | articles, videos, books |
| `06-Concepts/` | `concept-*` notes | flat, definitional |
| `07-People/` | `person-*` notes | flat |
| `08-Templates/` | templates | |

Imports/checkpoints live **outside** the vault proper in `$IMPORTS_ROOT/` (JSONL, scripts, `staging/`).

## Naming

- Concepts: `concept-<slug>.md` (e.g. `concept-aging`, `concept-hardware-dex`)
- People: `person-<slug>.md` (e.g. `person-vitalik-buterin`). **Anton's standing rule: when you encounter a NEW identifiable person, create the note — but always dedup first.** Check the existing `07-People/` set AND merge obvious variants (`person-huberman` ⇄ `person-andrew-huberman`, first-name ⇄ full-name) into one canonical note with the rest as `aliases:`, never a second file. Truly ambiguous bare first names with no context still get flagged in the source note's `unresolved_flags` rather than spawned as empty stubs.
- Insights: `insight-<slug>.md`
- Posts/transcripts (batch): `YYYY-MM-DD-<translit-slug>.md`
- MOCs: `_<Source>-MOC.md` (underscore sorts to top)
- Slugs: **filenames are ALWAYS Latin, NEVER Cyrillic** (a filename = a wikilink target, set 2026-06-08 by Anton). Transliterate Cyrillic → latin kebab (`finansirovanie-...`), or better a short *English* slug that conveys the meaning (`financing-mercedes-vito`); strip any leftover non-ASCII — never leave Cyrillic in a name. Keep `title:` in the original language and the Cyrillic original/variants in `aliases:` (this is also the **safe-rename net**: rename → Latin, add old name to `aliases:`, 0 broken links). NOTE CONTENT stays in its own language — transliterate NAMES, never translate the text. New import scripts: reuse the existing translit+strip slug, never hand-roll a non-transliterating one. Canonical rule + the `vault_doctor` `filenames-cyrillic` tripwire live in memory [[vault-conventions]].

## Classification decision tree

- One person as the subject, with context → `07-People`
- Definition of a term/idea → `06-Concepts`
- A non-obvious learning/scheme/rule → `03-Insights`
- Active work with a goal → `04-Projects/<domain>`
- External material for reference → `05-Resources`
- Raw conversation/dump → `01-Conversations/<source>`
- Fits nothing cleanly → keep in the source note and flag it; don't force-fit

## Canonical tags (reuse before inventing)

Tags are kebab-case; Russian kebab is fine (`налоги`, `двойня`, `гликемия`). High-frequency canon includes:

`portugal · longevity · defi · налоги · prompt-engineering · ai-agents · tokenomics · дизайн · двойня · chatgpt · due-diligence · web3 · гликемия · cgm · biohacking · добавки · виза · venture-capital · mitochondria · crm · crypto-security · blockchain-security · wallet · hardware · dex · decentralized-exchange · ico · fraud-analysis · crypto-payments · stablecoins · llm · n8n · hrv`

Crypto sub-tags are richly developed (`crypto-controversies`, `crypto-og`, `crypto-forensics`, `cex-dex`, `perp-dex`, etc.) — grep the vault for existing tags before adding a synonym. Per Anton's rule, **add new tags freely** when none fit — just don't create synonyms of existing ones.

## Frontmatter templates

**Concept:**
```yaml
---
title: <original language>
aliases: [<translations / variants>]
type: concept
authored_by: human
created: YYYY-MM-DD
source_post: "[[<source-slug>]]"
tags: [<domain>, <canonical subtags>]
---
```

**Insight:** same shape, `type: insight`, plus `domain:` and `applicability:`.

**Conversation / source note:**
```yaml
---
title: "<title>"
type: conversation            # or conversation-overlay if it links to raw elsewhere
source: voice-transcription   # or telegram-archive, chatgpt-export, ...
transcribed_by: whisper
summarized_by: GPT-5.5        # if applicable
authored_by: human            # human|ai|hybrid (who WROTE it)
origin: anton                 # anton|mixed|external (whose IDEAS — ASK, never guess)
date_recorded: YYYY-MM        # estimate from content cues if unknown
date_added: YYYY-MM-DD
language: ru
participants: [...]
tags: [...]
value_score: 0.0-1.0
mentioned_entities: { people: [...], projects: [...] }
unresolved_flags: [...]
related_concepts: [...]
related_insights: [...]
---
```

**Batch post/transcript (Telegram):**
```yaml
---
title: "<first line, ≤80 chars>"
type: telegram-post
source: telegram-archive
chat: "<chat name>"
author: "<sender>"
authored_by: human|ai|hybrid
origin: anton|mixed|external
date: <ISO ts>
msg_id: <id>
session: <n>
month: YYYY-MM
is_transcript: true|false
concept: "[[concept-<slug>]]"
tags: [telegram, telegram-post, anton-original, ...]
---
```

**Facebook post:**
```yaml
---
title: "<first 80 chars of text>"
type: facebook-post
source: facebook
origin: anton
authored_by: human
date: YYYY-MM-DD
year: YYYY
msg_id: <original FB post number>
word_count: N
concept: "[[concept-<slug>]]"
tags: [facebook-diary, anton-original]
---
```

**External transcript episode:**
```yaml
---
title: "<Series Name> — Part N"
type: transcript-episode
parent: "[[<Series Name>]]"
episode: N
origin: external
authored_by: ai
concept: "[[concept-<slug>]]"
tags: [transcript, episode]
---
```

**Decision (`02-Decisions/`) — time-aware (first real template for this folder):**
```yaml
---
title: "<the decision>"
type: decision
authored_by: human
origin: anton
date: YYYY-MM-DD
valid_as_of: YYYY-MM-DD
volatility: durable|slow|volatile
intent: "<what was being decided/solved, one line>"
status: active|superseded|expired
revisit_if: "<trip-wire condition that should reopen this — a condition, not just a date>"
expires_when: "<optional hard date/event after which it is presumed stale>"
alternatives_considered: [...]
tags: [decision]
related_concepts: []
---
```
Body: `## Контекст · ## Альтернативы (вариант / когда брать / минусы) · ## Выбор и почему · ## Триггеры пересмотра`.

**AI conversation (`01-Conversations/AI/`) — Claude/ChatGPT transcript:**
```yaml
---
title: "<topic>"
type: ai-conversation
source: claude-conversation   # or chatgpt
authored_by: hybrid
origin: mixed                 # Anton's prompts + AI answers — ASK if it is purely his
date_recorded: YYYY-MM-DD
valid_as_of: YYYY-MM-DD
volatility: volatile          # tech how-tos decay fast; durable for timeless content
intent: "<what was being solved>"
interpretation_confidence: high   # low + interpretation_note if it began as garbled voice
tags: [ai-conversation]
revisit_if: ""
---
```
Generated by `ingest_ai_conversation.py` (scaffold + verbatim raw), then LLM-curated. See `source-adapters.md` → "AI conversation".

## Provenance — two axes

**Axis 1 — `authored_by` (who *wrote* the text):**
- Voice transcript (e.g. sender "Personal Audio Summary", not a GPT summary) → `human`
- Anton's own messages → `human`
- Body starts with "Краткое содержание" / "Обсуждали" / "Summary" → `ai`
- Assistant/team member posts (translations, drafts) → `hybrid`
- Anything written before 2023 → `human`

**Axis 2 — `origin` (whose *ideas* they are): ALWAYS ASK Anton, never infer.**
- `origin: anton` — his own thinking (voice notes of him thinking, his own writing) → also tag `#anton-original`
- `origin: mixed` — conversations where Anton and others both speak
- `origin: external` — articles, others' notes, someone else's monologue, reference material

**Transcription ≠ authorship.** If the words/ideas are Anton's, the note is `authored_by: human` + `origin: anton` even when an assistant or tool did the voice→text. Put the transcriber in `transcribed_by`, never in `authored_by`/`origin`. A named assistant only makes a note `hybrid`/`mixed` when *they* drafted, translated, or wrote original content — not when they merely transcribed Anton's voice.

The point: Anton must be able to filter his corpus down to **only his own thoughts** (`#anton-original`), uncontaminated by AI text or other people's ideas. This is his top priority, so ownership is established by asking at ingest (Step zero in SKILL.md), not guessed from content.

## Epistemic decay & confidence (time-aware fields)

The vault is an archive (durable by design) — but operational facts decay. These fields let a note say *how much to still trust it now.* See memory `epistemic-decay-layer`. Apply on NEW notes; existing notes default to unset = treated as unknown (no false-stale).

- **`valid_as_of: YYYY-MM-DD`** — when the fact was last known true. Defaults to `date_added`. For an import, use the content's real date, not the import date.
- **`volatility: durable|slow|volatile`**
  - `durable` — timeless: math, history, Anton's values/identity, settled decisions. Never stale.
  - `slow` — shifts over years: a person's role/employer, a vendor, a price band, visa/tax policy. Stale after ~720d.
  - `volatile` — shifts in weeks/months: software features, API/tool behaviour, "research preview" status, quotes, availability. Stale after ~90d.
- **`intent:`** — one line: *what was being decided/solved.* The highest-value extract, ESPECIALLY for garbled voice/ASR — mangled words, but the goal stays usable. Always capture it for voice notes (addresses the Покупки voice-gap).
- **`interpretation_confidence: high|med|low`** (+ **`interpretation_note:`**) — ONLY on notes derived from a noisy source (bad ASR, garbled voice, lossy OCR). Flags how sure we are of *our reading* of the raw (which preserve-originals keeps verbatim). Clean text → omit (= high).
- **`revisit_if:` / `expires_when:`** — on decisions: the condition (or hard date) that should reopen the call. The decision-side twin of `volatility`.

**Consumer:** `brain_ask.py` reads `valid_as_of`/`volatility` per hit, prints age + a `⚠ STALE` flag (volatile >90d, slow >720d), so a stale fact announces itself at recall — re-verify before acting on it.

## Date cue

Voice-note/export timestamps often mark **save/transcription date, not recording date**. Reconstruct the real window from content (political events, tech context, named products) and record both (`date_recorded` vs `date_added`).
