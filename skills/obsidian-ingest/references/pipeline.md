# Batch pipeline — checkpointed ingest of large exports

Reference for `obsidian-ingest` big-batch path. The bundled `scripts/` are the **reference implementations** used for the Telegram import; they are written for Telegram HTML but the shape generalizes. Adapt the parser to the source format; the later phases (triage, generate, dedup, provenance, MOC) are largely source-agnostic.

All intermediate artifacts go to `$IMPORTS_ROOT\` so any phase can re-run independently. Never delete these checkpoints mid-project. **Separately, the raw source original is archived once to `$OBSIDIAN_ROOT\_originals\` (Phase 0) and is permanent — never deleted, even after the project ends.**

## Phase map

| Phase | Script | Input → Output (checkpoint) |
|---|---|---|
| 0. Archive original | `archive_original.py` | raw source (file/folder) → `$OBSIDIAN_ROOT\_originals\<key>\<date>__<name>\` (verbatim copy + sha256 manifest; **permanent, never deleted**) |
| 0.5 Schema discovery | — | inspect the export; identify message types & fields |
| 1. Parse | `scripts/parse_telegram.py` | source files → `telegram-archive.jsonl` (`id, ts, sender, type, text, media_ref, reply_to, ...`) |
| 2. Triage + sessionize | `scripts/triage.py` | JSONL → `telegram-archive-classified.jsonl` (+ `triage_stats.json`); classes noise/link/fragment/post, 30-min session ids, month buckets |
| 3. Generate → staging | `scripts/generate.py` | classified JSONL → `staging/` mirroring vault tree (posts/, sessions/, person files) |
| 4. Validate | inline | wikilink integrity over staging + vault basenames; require **0 broken** |
| 5. Move | `cp -r` | `staging/...` → live vault |
| 6. Dedup | `scripts/dedup.py` | body content-hash; delete exact dups (keep 1), repoint session links; report near-dups (don't delete) |
| 7. Provenance | `scripts/backfill_provenance.py` | add `authored_by` to every post |
| 8. Cross-MOC | `scripts/build_moc.py` | data-driven `_<Source>-MOC.md`: summary, month index, participants, top items, extracted concepts |
| 9. Concept mapping | inline + script | map each transcript → one concept (rule 2); link to existing, create if needed |
| 10. Report | inline | counts, link check, tags added, dups resolved, flags |

## Phase notes

**Archive original (Phase 0 — Rule 0).** Before Phase 1, preserve the raw source verbatim: `python $IMPORTS_ROOT\archive_original.py "<source>" --source <key> --label "<note>"`. Copy-only (never moves/edits the source), idempotent (identical content is skipped by content digest), integrity-checked (sha256 per file). For pasted text with no file, write it to a `.txt` first, then archive that. Originals under `_originals\` are **permanent** and never deleted — this is the upstream source of truth, separate from the `_imports\` checkpoints (which are project-scoped) and from the vault git backup (which protects derived notes).

**Triage classes** (tune thresholds if a class swallows >80%): `noise` <10 chars, `link` URL-only, `fragment` 10–200 chars, `post` ≥200 chars. Drop whatever the user said to drop (e.g. audio placeholders, media) before generating.

**Sessionize**: new session when the gap between messages exceeds 30 min. For a spike month with hundreds of messages, bucket session files **by day** (`Sessions-YYYY-MM-DD.md`, with `## Сессия N` subsections inside) rather than one-file-per-session — raw 30-min splitting produces many near-empty micro-files.

**Generate granularity**: default to one file per substantive long item (Anton prefers maximum granularity). Session-ledger masters hold the full conversational flow; long posts get their own atomic file and are linked from the ledger via `полный текст [internal]`.

**Validate** (the gate before touching the vault):
```python
import re; from pathlib import Path
files={p.stem for p in Path('staging').rglob('*.md')} | {p.stem for p in Path(VAULT).rglob('*.md')}
# count every target [internal]; assert none missing. Account for escaped \| in tables.
```

**Dedup** keeps exactly one raw copy (rule 5). `scripts/dedup.py` runs detect-only by default; set `APPLY=1` to delete + repoint. Near-dups (same opening, different length) are *different content* — never auto-delete them.

**Concept mapping** (rule 2): assign each transcript ONE primary concept, write `concept: "concept-x [internal]"` into frontmatter + a backlink section in the concept file.

- **Don't use keyword matching for this.** It fails on Russian/cross-language text and over-fires on generic words (e.g. a seed like "америк" captured 25 unrelated notes). Keyword matching is fine for a rough first pass only.
- **Use LLM classification via batched subagents.** Build a catalog of existing concepts (slug + title + one-line def), split transcripts into batches of ~24, give each subagent the catalog + its batch, have it return `{slug, concept, confidence}` per transcript — preferring existing concepts, proposing `NEW:concept-<slug>` only when nothing fits.
- **MANDATORY consolidation (reduce) pass.** Independent subagents cannot coordinate vocabulary, so they WILL proliferate near-duplicate new concepts (e.g. one run produced `concept-startup-fundraising`, `-founder-equity`, `-token-vesting`, `-cofounder-dynamics`, `-startup-finances` for one theme; `simulation-hypothesis` vs `simulation-theory` vs `philosophy-of-existence`). After aggregating, manually map the raw proposed slugs → a small canonical set (a 75→26 reduction is typical), merging synonyms and folding singletons into the nearest bucket or an existing concept. Only then create stub concept files and write the labels. Skipping this step violates rule 2 (no duplicate concepts).
- **Do concept AND tags in the same subagent pass** — it's nearly free. Have each batch return `{slug, concept, tags:[3-5], confidence}`. Merge those tags into the note's frontmatter `tags:` list (dedup; reuse canonical tags, add new freely per rule 4). This satisfies "tag every note" without a second pass.
- Mark auto-created concepts `status: stub`, then **flesh them out**: a follow-up subagent reads each stub's backlinked notes and writes a real `## Определение` + `## Ключевые тезисы` (grounded, no invention), flipping `status: defined`. Route pure-noise transcripts to `concept: null` + `transcription_quality: noise`.
- Finally add a concept index to the Cross-MOC (each concept + note count).

**Concept interlinking (перелинковка — rule 6).** Atomic notes alone aren't a knowledge graph; the concepts must link to *each other*. After concepts exist, give ONE subagent the full concept catalog (`slug :: title`) and have it return a relatedness map `{concept: [3-5 neighbour concepts]}` (topic-adjacency clusters: crypto, biohacking/longevity, startup/fundraising, philosophy/simulation, alt-history, AI/agents…). Then a script appends a `## Связанные концепты` section to each concept linking its neighbours (filter to slugs that exist). Combined with note→concept (`concept:` field) and concept→note (backlink sections), this closes the graph in all directions.

**Incremental re-imports.** Anton re-exports the same chat periodically (a fuller snapshot a day later). **Archive the new export first** (Phase 0 / Rule 0 — each re-export is its own original, kept verbatim and never deleted). Then, to add only what's new: parse the new export → **dedup every text row against the already-imported archive by body content-hash** (and against itself) → keep only unique rows → import those with collision-safe filenames (check existing post stems, suffix on clash), `import_batch: <date>` in frontmatter, and a single per-increment session ledger (`Sessions-<month>-import<date>.md`). Report the duplicate count so Anton sees the overlap. Then run concept+tag mapping on just the new posts.

**Name alt-spellings for people/leads (Bible rule, 2026-06-13).** Every imported **lead / person / contact** note must get an "alternative spellings" field so the name is findable in any form (Vlad/Viktor/виктор/typo/wrong-layout). Mechanics: append to the standard `aliases:` (Obsidian's native search + quick-switch index it), generated deterministically (0 tokens) by `$IMPORTS_ROOT\namesearch\alt_spellings.py` → `alt_spellings(name)`: cross-script (Cyrillic↔Latin) + common translit forks; **do NOT** force Cyrillic onto non-Slavic Latin names (no "Джохн" for John), and do NOT put keyboard-layout garble/phonetic keys in the visible field (that's the search layer `find_name.py`, not the card). Backfill across all existing 35 772 cards already done via `backfill_aliases.py` (idempotent — re-run after a big import). After import, rebuild the name index (`name_index.py --vault`). Canonical rule: vault `reglament-pri-importe-lyubogo-lida-cheloveka-zapolnyat-alt-napisaniya`; tool memory `smart-name-search`.

## Avoiding islands — connect new data to the existing vault

A batch import can form a disconnected island in the graph even when internally well-linked. This happens when the new notes and the old notes **don't share link targets**. Real case: 1156 new Telegram posts all linked to `concept-* [internal]` files, while ~2500 old ChatGPT notes linked to inline ghost terms like `[[CGM]]`, `BDNF [internal]`, `RWA [internal]`, `C(H+A)RM [internal]` that had **no backing note** (8998 links, only 46 resolving). Obsidian clusters the old notes around those phantom nodes, but since the new world's targets (`concept-*`) and the old world's targets (acronyms) never overlap, you get two separate blobs.

**Diagnose first:** extract every `target [internal]` in the old data, count how many resolve to a real file, and tally the top unresolved targets. If the old data leans on a different vocabulary (free-text frontmatter `concepts:` lists, inline acronym links) than the new data, that's the disconnect.

**Bridge via shared hubs (low-effort, high-leverage):** the high-frequency ghost terms ARE concepts. Create a real note for each top unresolved term (filename = the exact link text so `[[CGM]]` resolves) that links to the matching `concept-*` the new data also uses. Now: `old note → [[CGM]] → CGM.md → concept-biohacking-nutrition [internal] ← new post`. A subagent maps terms→concepts; a script creates the bridge notes (put them in a dedicated folder like `09-Bridges/`; skip terms with Windows-forbidden filename chars `<>:"/\|?*` and path-style false-positives containing `/`). ~100 bridge notes covering the top shared terms is enough to merge the clusters — verify by counting concepts linked by BOTH a bridge and a new note.

This is far less invasive than editing thousands of old notes, and it resolves dead ghost links as a bonus. Prefer it over rewriting old frontmatter.

**Graph hygiene — bridge the hubs, unlink the long tail.** After bridging high-frequency ghost terms, a long tail of one-off `free-text [internal]` links remains (singletons that cluster nothing but show as thousands of empty graph nodes). Don't create notes for these. Instead **unlink them**: strip ` [internal]` → plain text for every wikilink whose target doesn't resolve (keep the alias display text; keep `#headings`). One pass took a vault from ~50% to 99% link resolution. Watch for malformed pseudo-links in raw content (e.g. ChatGPT shopping-card JSON `"turn0product1","…" [internal]`, coordinates) — real wikilinks never contain `"`, so a `"`-containing-`... [internal]` rule unwraps those safely. Net effect: every remaining edge points to a real note, so the graph view shows structure instead of noise.

**Integrating a pre-tagged corpus cheaply (no per-note LLM).** If the old notes already carry structured frontmatter (e.g. ChatGPT exports with `topic`, `concepts:`, `people:`, `value_score`), don't re-classify them with subagents — mine the metadata deterministically: (1) map the handful of `topic` categories → one primary concept each (a ~15-entry hand map, creating umbrella concepts where none exist) and write `concept: ... [internal]` — this guarantees every note joins the concept layer; (2) convert the free-text `concepts:` list into body `wikilinks [internal]` (high-frequency ones resolve to the bridge notes / concepts you already have); (3) bulk-add provenance. This integrated 2539 notes in one script run. Provenance note: ChatGPT conversations are `authored_by: hybrid` + `origin: mixed` (his prompts + AI answers) — NOT `anton-original`, since they contain heavy AI-generated text; that distinction is the whole point of the provenance system.

## Integrating distilled corpus (nexus-ai-chat-importer pattern)

When a plugin or agent bulk-imports a pre-distilled corpus (e.g. `02-Decisions`, `03-Insights`, `05-Resources` created by nexus-ai-chat-importer), the files already carry rich frontmatter (`type`, `domain`, `concepts:` list, `authored_by:`) but lack the vault's graph fields (`concept:` wikilink, `origin:`). Integration is deterministic and fast:

1. **Map `domain:` → primary concept** using a hand-made domain→concept dict (~15 entries). Covers all files in one pass without LLM.
2. **Add `origin: anton`** to all distilled notes (they are distillations of Anton's own conversations, even if `authored_by: claude-cowork`).
3. **Match `concepts:` list entries to existing concept files** for secondaries — normalize to slug form, check if `concept-{slug}` exists, add matched ones to `## Смежные концепты`.
4. **Strip ghost links** in body: run the same `unresolved [internal] → plain text` pass on the new folders. Typical yield: ~5 broken links per file.

**Transcript-episode subfolders** (external content split into 30-50 parts): map by subfolder name → (concept, origin, authored_by). Key rules:
- Podcasts/lectures/YouTube transcripts: `origin: external`, `authored_by: ai`
- Anton's own dialogues with others: `origin: mixed`, `authored_by: hybrid`
- `type: transcript-parent` index files are also updated (1 per series)

**Total new files** for a typical vault growth of ~4000 files: ≈4500 can be integrated in 4 script runs (~10 minutes total), achieving 93%+ concept coverage and 98%+ origin coverage.

**Scripts reference** (`E:/Obsidian/_imports/`):
- `integrate_distilled.py` — handles 02-Decisions / 03-Insights / 05-Resources with domain→concept map
- `integrate_transcripts.py` — handles known external-content subfolders (explicit name map)
- `integrate_transcripts2.py` — extended heuristic map for 60+ subfolders
- `integrate_remainder.py` — cleans up collection folders (`type: transcript-parent`) and sessions
- `strip_ghosts_new.py` — ghost-link strip for new corpus folders

## Reusable invariants when adapting the parser

Whatever the source (WhatsApp txt, Slack json, ChatGPT json, etc.), normalize to the same JSONL row shape in Phase 1. Then phases 2–10 work unchanged. That is the whole point of the JSONL checkpoint: it decouples the messy source-specific parsing from the clean, source-agnostic Obsidian generation.
