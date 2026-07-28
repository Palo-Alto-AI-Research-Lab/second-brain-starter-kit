# Per-source re-import reference

The canonical mechanics (roster, provenance, triage, layer structure) live in
`obsidian-ingest/references/source-adapters.md`. This file is the **re-import quick card**:
the idempotency gate that makes re-running safe, and the exact LLM curation to run on the
new items after the deterministic merge. The dispatcher (`scripts/reimport.py`) holds the
authoritative step list; keep the two in sync if you change either.

**Step 0 — archive the original (all sources, Rule 0).** Before any parsing, the dispatcher runs
`archive_original.py "<export>" --source <key>`, copying the raw export verbatim to
`$OBSIDIAN_ROOT/_originals\<key>\<date>__<name>\` with a sha256 manifest. Idempotent, integrity-checked,
**never deleted** — the upstream source of truth if derived notes are later changed or removed. Runs on
dry-run too (the export can vanish from Downloads first); `--no-archive` skips it (don't).

The export-path override is uniform: every patched parser reads `TG_EXPORT` (the export
**folder**); the dispatcher sets it from `--export`. `parse_faaa.py` is **not yet patched** —
patch it the same way before relying on `--apply` for FAAA.

---

## pokupki — «Покупки approve…» (result.json)

- **Deterministic:** `parse_pokupki.py` → `generate_pokupki.py` → `validate_pokupki_staging.py` → diff `staging_pokupki` vs vault → robocopy merge.
- **Idempotency:** ledgers `Sessions-YYYY-MM-DD.md` regenerate identically per day; post stems are collision-safe; re-running only adds new days/posts. Body-hash dedup vs `pokupki-archive.jsonl` already in the parser.
- **LLM curation for NEW posts:** run the concept-mapping pass (`map_concepts_pokupki.py` builds batches → LLM assigns `concept:` → `apply_concepts_pokupki.py`), then `build_rules_pokupki.py` for any new pinned purchase rules, then `build_moc_pokupki.py`. Dedup new rules' body-hash vs existing `reglament-pokupki-*`.
- **Dashboard:** after a merge, re-run `$IMPORTS_ROOT/build_pokupki_dashboard.py` to refresh `_Dashboards/Pokupki-Dashboard.html`.

## assistants-ops — «All Assistant's tasks 777…» (messages*.html)

- **Deterministic:** `parse_assistants_ops.py` rebuilds Layer-2 day-ledgers (idempotent by date; it skips a ledger already carrying "Регламенты этого дня") and emits a fresh `rule_candidates.json`.
- **LLM curation (the prize is the Bible):** curate the NEW `rule_candidates.json` rows in batches → `{is_rule, statement, theme, applies_to, origin, authored_by}` → `build_rules2.py` (merges, regenerates `_Operations-Bible-MOC.md`, **guarded so it won't clobber the fleshed `concept-bible-*` sub-concepts**). Dedup new statement-hashes vs existing `reglament-*`. Provenance: relay-footer `Перевела:/Делегировано:` = Anton's voice (`origin: anton`, poster→`transcribed_by`); Pavel only by her own name-marker; team SOP → `mixed`; conservative `#anton-original`.

## arhiv-golosa — content-team voice archive (messages*.html)

- **Fully deterministic (no LLM needed):** `parse_telegram.py` → `triage_telegram.py` → `generate_obsidian.py` → `dedup_posts.py` → `build_moc.py`.
- All of this chat is Anton's content (`origin: anton`); voice already transcribed → `authored_by: human`. Optionally refresh concept links for new posts, but it's not required for a clean re-import.

## faaa — «CALLS … FAAA follow up» CRM (result.json)

- **Deterministic:** `parse_faaa.py` rebuilds `faaa-archive.jsonl` + lead clusters. **Patch its SRC to read `TG_EXPORT` first** (it currently hard-codes the export path).
- **LLM curation (required — this source is synthesis-heavy):** the batched synthesis workflow over new/changed leads → `render_cards.py` → `build_ledgers.py` → `build_crm_moc.py`. **Union new calls into EXISTING leads by typed @handle + full name** (never regex `@\w+` — it scrapes email domains and over-merges); check `final_slugs.json` + vault `lead_id` frontmatter before creating a new card. Append new calls to existing cards; regenerate only touched ledger days.

---

## The voice gap (all chats)

Telegram exports omit `.ogg` voice notes, so most of Anton's spoken reasoning is still not in
text. If a re-export was made **with media**, that's the moment to Whisper-transcribe the new
`.ogg` and enrich ledgers/posts **by `msg_id`** (idempotent — no rework). A user-account Telegram
MCP that exposes `download_media(chat_id, message_id, file_path)` closes this gap directly; see
the connector guide (`_Dashboards/Telegram-MCP-Setup.md`).
