---
name: telegram-reimport
description: >-
  One-command incremental RE-IMPORT of a Telegram chat that already lives in Anton's
  Obsidian vault (Покупки/purchases, Assistants-Ops/household-rules, Arhiv-Golosa/content-team,
  FAAA/CRM-calls). Use this whenever Anton exports a FRESH/updated copy of an already-imported
  Telegram chat and wants only the new messages folded in — "переимпортируй покупки",
  "обнови телеграм импорт", "re-import the assistants chat", "I re-exported the покупки chat,
  pull the new messages", "refresh the vault from the new export". It detects which chat the
  export is, re-runs that source's deterministic pipeline pointed at the new export, regenerates
  only new day-ledgers + new posts (idempotent), validates links, and hands off the LLM curation
  (concept-mapping, rule-extraction) for the new items. For a FIRST-TIME import of a brand-new
  source, use the obsidian-ingest skill instead — this skill is specifically for re-running an
  import that already exists.
---

# Telegram re-import (incremental)

> 🧒 **When reporting to Anton:** always end with a child-simple "Простыми словами" recap in his language (plain words, no jargon) — his standing request. See memory `eli5-always` / global `CLAUDE.md`.

This skill turns "I re-exported chat X" into one orchestrated run that adds only the **new** messages to the vault, without re-doing the whole import. It is the maintenance counterpart to `obsidian-ingest` (which does first-time imports). The heavy per-source mechanics — roster, provenance, triage, layer structure — already live in `obsidian-ingest/references/source-adapters.md`; **this skill is the dispatch + orchestration layer over the real scripts in `$IMPORTS_ROOT/`.** Don't duplicate adapter logic here; read that file when you need the why.

## The four known sources

| Source key | Chat | Vault home | Parser |
|---|---|---|---|
| `pokupki` | «Покупки approve Assistant's tasks 777…» | `01-Conversations/Telegram/Pokupki/` | `parse_pokupki.py` (result.json) |
| `assistants-ops` | «All Assistant's tasks 777…» (household rules → Bible) | `01-Conversations/Telegram/Assistants-Ops/` + `03-Insights/Operations/` | `parse_assistants_ops.py` (messages*.html) |
| `arhiv-golosa` | content-team voice archive | `01-Conversations/Telegram/Arhiv-Golosa/` | `parse_telegram.py` (messages*.html) |
| `faaa` | «CALLS … FAAA follow up» (CRM) | `04-Projects/crypto/Platinum-CRM/` | `parse_faaa.py` (result.json) |

## How to run it

The dispatcher is `scripts/reimport.py`. It is **safe by default**: it never mutates the vault, only inspects — the one write it performs is **Step 0, archiving the original** (which is itself a safety op).

```
# 0) ALWAYS FIRST (automatic, Rule 0): the dispatcher copies the raw export VERBATIM to
#    $OBSIDIAN_ROOT/_originals/<source>\<date>__<name>\ (idempotent, sha256 integrity-checked, NEVER deleted)
#    BEFORE it parses anything — even on a dry run, because the export can vanish from Downloads before
#    you reach --apply. It aborts the run if the archive fails. Pass --no-archive to skip (don't).

# 1) DRY RUN — detect the chat, ARCHIVE THE ORIGINAL, print the plan + current vault counts, verify the parser is override-ready
python scripts/reimport.py --export "$USERPROFILE/Downloads/Telegram Desktop\<NewExportFolder>"

# 2) BUILD TO STAGING — re-parse the new export + regenerate into $IMPORTS_ROOT/<staging> (vault untouched),
#    then diff staging vs vault to show exactly how many NEW ledgers/posts would be added, and print the merge command
python scripts/reimport.py --export "...<NewExportFolder>" --apply

# 3) MERGE — only after you (or Anton) eyeball the staging diff, run the robocopy line the tool prints
```

Why three phases and not one button: the parse/generate steps write to `staging`/JSONL and **never** mutate the vault, so they're safe to automate. The final merge into the live vault is the one irreversible step, and Anton's standing preference is to review non-trivial writes before they land. Phase 2 gives him the exact new-file counts to approve; phase 3 is the copy. If he says "just do it", you can run the printed merge command yourself right after showing the counts.

`--source <key>` forces the source when auto-detection can't read a `result.json` (e.g. an HTML-only export). `auto` is the default.

## What the dispatcher does per source (deterministic core)

**Step 0 precedes every source** — `archive_original.py` copies the raw export verbatim to `$OBSIDIAN_ROOT/_originals/<source>\<date>__<name>\` (idempotent, integrity-checked, never deleted) before any parsing. Then:

`pokupki` → `parse_pokupki.py` → `generate_pokupki.py` → `validate_pokupki_staging.py` → diff `staging_pokupki` vs vault.
`arhiv-golosa` → `parse_telegram.py` → `triage_telegram.py` → `generate_obsidian.py` → `dedup_posts.py` → `build_moc.py` (fully deterministic, no LLM needed).
`assistants-ops` → `parse_assistants_ops.py` (rebuilds day-ledgers idempotent by date + emits fresh `rule_candidates.json`).
`faaa` → `parse_faaa.py` (rebuilds the call archive + lead clusters).

All parsers honor the `TG_EXPORT` env var (the dispatcher sets it to `--export`). Ledgers are **idempotent by date**; posts/cards are collision-safe by stem; rules/leads dedup by body-hash / identity. So re-running only ever adds genuinely new content. See `references/sources.md` for the per-source step list, idempotency gate, and LLM hand-off.

## The honest boundary: deterministic vs LLM

The dispatcher automates the **deterministic** 90% (parse → regenerate → validate → diff). It does **not** run the LLM curation, because that needs judgment per new item:
- **`pokupki`**: new posts need concept-mapping (`map_concepts_pokupki.py` + concept batches) and new pinned rules need extraction (`build_rules_pokupki.py`). New status-ledgers stay ledger-only.
- **`assistants-ops`**: new `rule_candidates.json` rows need the curator pass (is-this-a-rule? theme? provenance?) before `build_rules2.py`. Bible sub-concepts must not be clobbered (`build_rules2.py` is guarded).
- **`faaa`**: new leads need the batched synthesis workflow before `render_cards.py` → `build_ledgers.py` → `build_crm_moc.py`, unioning into existing leads by @handle/name.

After phase 3, **report how many new items need curation and offer to run that pass** following `obsidian-ingest` (Anton's rule: always dedup against existing first; protect `#anton-original`). Don't silently skip it — a re-import isn't "done" until the new items are concept-linked, or the gap is flagged.

## Provenance & the voice gap (carry over, don't re-derive)

Provenance defaults are fixed per source in `source-adapters.md` — relay-footer `Перевела:/Делегировано:` = Anton's voice (`origin: anton`, poster→`transcribed_by`); Pavel only by her own name-marker; team SOPs → `mixed`. The **voice gap persists**: Telegram exports omit `.ogg` voice notes, so most of Anton's reasoning still isn't recoverable from text. If this export was made **with media**, that's the moment to Whisper-transcribe and enrich by `msg_id` (idempotent) — flag it. (A Telegram MCP that downloads voice by msg_id would close this — see the connector guide.)

## Windows / Cyrillic gotchas (same as obsidian-ingest)

- Python `print()` of Cyrillic crashes on cp1252 stdout → write UTF-8 files, keep stdout ASCII. Run with `$env:PYTHONUTF8=1`.
- Never `rm -rf` inside `%VAULT_ROOT%\` (Obsidian/indexer hold handles → "Device or resource busy"). The dispatcher merges with `robocopy` (no delete), never mirror.
- Transliterate Cyrillic filenames → latin kebab, date-prefix `YYYY-MM-DD-slug`.

## Finish

End every re-import with the standard report (rule 8 of obsidian-ingest): new ledgers, new posts/cards, new rules/leads, links validated (0 broken), and the curation hand-off list. The vault should get *more* connected, not just bigger.
