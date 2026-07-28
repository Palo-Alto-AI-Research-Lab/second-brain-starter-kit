# Engine passports

One entry per published engine: what it does, what goes in and out, who calls it, and - where it has been written - what breaks and how to fix it.

**What / input / output / config / called by** are read straight from the source, so they stay true as the source changes.
**What breaks / how to tell / how to fix** is judgement and is written by hand. 61 of 246 engines have it so far; the rest say so plainly instead of guessing.

Engines are ordered by how many published documents cite them, so the ones you are most likely to reach for are at the top.

---

## `imports/vault_backup.py`

**What it does.** vault_backup.py — RUN BEFORE ANY VAULT-MODIFYING OPERATION.

**Input.** command line: `--force`, `--porcelain`, `--short`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `VAULT_CANON_OK`, `VAULT_MASSDEL_OK`

**Needs installed.** `brain_common`, `git_author`, `vault_precommit_guard`

**Called by.** `skills/alpha-judge/SKILL.md`, `skills/arch/SKILL.md`, `skills/claudeai-sync/SKILL.md`, `skills/coach/SKILL.md`, `skills/crm-sync/SKILL.md`, `skills/dedup/SKILL.md` and 16 more

**What breaks.** The backup target is unreachable or full - an external drive that was not plugged in, or a synced folder that is mid-conflict.

**How to tell.** The run prints a copied-file count. A count of 0, or a count far below the last run's, means it backed up nothing and said nothing was wrong.

**How to fix.** Check the destination exists and is writable, then re-run. If the count is still 0, the source path is wrong - print it and compare against your vault root. Never delete the old backup to 'make room' before the new one verifies.

---

## `imports/brain_embed_update.py`

**What it does.** brain_embed_update.py v2 — CHUNKED + TAGGED + edit-aware e5 index.

**Input.** command line: `--cpu`, `--force`, `--full`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`

**Needs installed.** `brain_common`, `numpy`, `torch`

**Called by.** `skills/ask/SKILL.md`, `skills/brain/SKILL.md`, `skills/chatgpt-sync/SKILL.md`, `skills/claudeai-sync/SKILL.md`, `skills/crm-sync/SKILL.md`, `skills/dr-fanout/SKILL.md` and 15 more

**What breaks.** No GPU, no sentence-transformers, or a model download that never finished. It also stalls on a vault so large the batch does not fit in memory.

**How to tell.** It reports how many notes were embedded. If that number is 0 while notes have changed, the index is now stale and every /ask answer is silently out of date.

**How to fix.** Run it with a smaller batch size first. If the model cannot load, delete the half-downloaded model cache and let it fetch again. Re-run until the embedded count matches the changed-note count.

---

## `imports/brain_ask.py`

**What it does.** brain_ask.py v2 — chunked + tagged retrieval.

**Input.** command line: `--ab`, `--anton`, `--ask`, `--beliefs`, `--concept`, `--concepts`, `--conv`, `--conversations`, `--decisions`, `--graph`, `--insights`, `--lead`, `--leads`, `--notes`, `--person`, `--protocols`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `AB_SOURCE`, `BRAIN_AB_JSON`, `BRAIN_ANSWER_OUT`, `BRAIN_EMB_BACKEND`, `OPENAI_EMB_MODEL`, `OPENAI_SECRET_FILE`

**Needs installed.** `brain_common`, `brain_entity`, `numpy`, `sentence_transformers`

**Called by.** `BOOTSTRAP-CLAUDE.md`, `skills/alfa-search-recall-deepresearch/SKILL.md`, `skills/ask/SKILL.md`, `skills/bible/SKILL.md`, `skills/coach/SKILL.md`, `skills/cofounder/SKILL.md` and 12 more

**What breaks.** The embedding index is missing or older than the notes, so it retrieves confidently from a vault that no longer exists in that shape.

**How to tell.** Answers cite notes you have since deleted or renamed, or it finds nothing for a topic you know you wrote about last week.

**How to fix.** Re-run brain_embed_update.py, then ask again. If it still misses, the note is outside the indexed folder set - check the include list at the top of the file.

---

## `imports/archive_original.py`

**What it does.** archive_original.py — RUN AT THE START OF ANY IMPORT (Rule 0 / Phase 0).

**Input.** command line: `--dry-run`, `--label`, `--lock`, `--source`, `source`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-backup/SKILL.md`, `skills/obsidian-ingest/SKILL.md`, `skills/obsidian-ingest/references/pipeline.md`, `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** The originals folder is missing or read-only, so the raw source is dropped while the derived note is still created - the lossy half survives.

**How to tell.** The note exists but its provenance link points at a file that is not there.

**How to fix.** Create the originals folder, then re-run the import from the raw source. If the raw source is gone, say so in the note rather than leaving a broken link.

---

## `imports/namesearch/find_name.py`

**What it does.** find_name.py — умный поиск имени по names.db.

**Input.** command line: `--all`, `--html`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `name_norm`

**Called by.** `skills/fa/SKILL.md`, `skills/find/SKILL.md`, `skills/obsidian-ingest/references/pipeline.md`, `skills/portret/SKILL.md`, `skills/relink/SKILL.md`, `templates/concept-creation-rules.md`

**What breaks.** The name database has not been rebuilt since contacts changed, so a real person returns no match.

**How to tell.** A name you are certain exists returns nothing, while other names still work.

**How to fix.** Rebuild the name database, then search again. If one specific spelling still misses, add it as an alias rather than loosening the matcher for everyone.

---

## `scripts/bus_send.py`

**What it does.** bus_send.py -- the ONE entry point for every machine->machine message.

**Input.** command line: `--sign`, `--to`, `-t`, `words`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `COMPUTERNAME`, `MACHINE_BUS_DIR`, `MACHINE_KEY`

**Needs installed.** `ack_watchdog`, `bus_ping`, `fleet_hmac`, `tg_bot_send`

**Called by.** `skills/dr-fanout/SKILL.md`, `skills/reboot/SKILL.md`, `skills/skill-forge/SKILL.md`, `skills/tt/SKILL.md`, `skills/wow/SKILL.md`

**What breaks.** One of the two rails is down. It is designed to send on both, so a single dead rail degrades quietly instead of failing.

**How to tell.** The output names each rail and its result. Two 'ok' lines is healthy; one ok and one error still counts as delivered and still needs fixing.

**How to fix.** Fix the failing rail on its own terms - network for the chat rail, sync for the folder rail. Do not disable the broken one to silence the error; the second rail is the whole point.

---

## `imports/content-factory/canon_render.py`

**What it does.** canon_render.py — рендер публичных ЖУРНАЛОВ-РЕЕСТРОВ канона (show-canon) в репо the-journey.

**Input.** command line: `--announce-season`, `--today`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `leak_scan`

**Called by.** `skills/episode/SKILL.md`, `skills/journey/SKILL.md`, `skills/reality-show/SKILL.md`, `skills/retro/SKILL.md`, `skills/wow/SKILL.md`

**What breaks.** It renders registries into a repo. If the repo checkout is stale or dirty, the render lands on top of unrelated local edits.

**How to tell.** The rendered output contains changes you did not make this run.

**How to fix.** Start from a clean checkout, then render. Do not commit a render you cannot explain line by line.

---

## `scripts/approval.py`

**What it does.** !/usr/bin/env python3

**Input.** command line: `--cat`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_seen`, `machine_bus`

**Called by.** `skills/03/SKILL.md`, `skills/fa/SKILL.md`, `skills/fb-watch/SKILL.md`, `skills/tg-slot/SKILL.md`

**What breaks.** The chat id is wrong or the bot was removed from the group, so questions are posted into nowhere and the answer never comes.

**How to tell.** `approval.py due` lists questions still waiting. A question that has been waiting far longer than the others was probably never delivered at all.

**How to fix.** Send one test question and confirm it appears in the chat by eye. If it does not, the bot's group membership is the first thing to check, the chat id the second. Do not raise the timeout to hide it.

---

## `imports/build_rules2.py`

**What it does.** Build Layer-1 v2 into staging: - 9 theme sub-concepts (children of concept-bible-platinum) - 83 reglament-*.md re-pointed to their theme sub-concept (+ related_holybible flag) - individual Trello rule-card notes in trello-cards/ (replacing ...

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/dedup/SKILL.md`, `skills/obsidian-ingest/SKILL.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** It writes into staging on the assumption the source rules parsed cleanly.

**How to tell.** Sub-concept count does not match the number of themes in the source.

**How to fix.** Check the source rules file first. Staging is disposable - regenerate it.

---

## `scripts/machine_bus.py`

**What it does.** !/usr/bin/env python3

**Input.** command line: `cmd`, `rest`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `MACHINE_BUS_DIR`

**Needs installed.** `ack_watchdog`, `fleet_hmac`, `fleet_sign`, `inbox_debt`, `injection_detector`, `untrusted`

**Called by.** `skills/bus/SKILL.md`, `skills/handoff/SKILL.md`, `skills/inbox/SKILL.md`, `skills/notpeople-wave/SKILL.md`

**What breaks.** The shared folder is not syncing, so messages are written locally and never arrive. This looks identical to 'nobody sent anything'.

**How to tell.** Check the sync client, not the inbox. A silent peer and a stopped sync produce the same empty inbox, and only one of them is normal.

**How to fix.** Restart the sync client and confirm the folder's timestamp moves on the other machine. Messages already written are not lost - they deliver once sync resumes. Do not re-send; the receiver de-duplicates on message id.

---

## `scripts/cc-review/secondop.py`

**What it does.** secondop.py -- Codex SECOND OPINION at 3 touchpoints, for EVERY substantive task (Phase 1.5).

**Input.** command line: `--context`, `--days`, `--engine`, `--no-post`, `--note`, `--post`, `--reason`, `--reviewer`, `--ritual`, `--role`, `--stale-min`, `--standby`, `--task`, `--timeout`, `--verdict`, `cmd`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_ping`

**Called by.** `skills/codex-mirror/SKILL.md`, `skills/gemini/SKILL.md`, `skills/secondop/SKILL.md`, `skills/tt/SKILL.md`

**What breaks.** The external reviewer is unreachable or rate-limited, so the second opinion never arrives.

**How to tell.** A verdict comes back with no reviewer content in it - an empty second opinion is not agreement.

**How to fix.** Check the reviewer's quota window before retrying; retrying inside a rate limit just extends it. Record the skip explicitly rather than treating it as a pass.

---

## `imports/build_crm_moc.py`

**What it does.** FAAA Phase 7 — CRM status-board MOC + concept hub note.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** The status board is built from card frontmatter. A card with malformed frontmatter drops off the board without error.

**How to tell.** A lead you know exists is absent from the board.

**How to fix.** Open that lead's card and check its frontmatter parses. Fix the card, rebuild the board.

---

## `imports/build_ledgers.py`

**What it does.** FAAA Phase 6 — day-bucketed raw archive ledgers + archive MOC.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Day bucketing depends on a timezone. Run it under a different timezone and messages land in the wrong day.

**How to tell.** Day boundaries look shifted by a few hours against the source chat.

**How to fix.** Set the timezone explicitly rather than relying on the machine's local one, then rebuild the ledgers - they are derived and safe to regenerate.

---

## `imports/claude_sessions/continue_session.py`

**What it does.** continue_session.py - "continue an old conversation as a NEW session" (Anton 2026-06-23).

**Input.** command line: `--last`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `export_md`, `session_archive`

**Called by.** `skills/1/SKILL.md`, `skills/chat-search/SKILL.md`, `skills/resume-last/SKILL.md`

**What breaks.** It starts a new session from an old conversation. If the old conversation cannot be found it starts an empty one instead of failing.

**How to tell.** The new session has no prior context in it.

**How to fix.** Confirm the source conversation id resolves before relying on the continuation.

---

## `imports/content-factory/episode_adapter.py`

**What it does.** episode_adapter.py - deterministic scaffolder for a content "episode" (content-factory v2, S5 tier adapters).

**Input.** command line: `--from-seed`, `--slug`, `--source`, `--status`, `--title`, `--when`, `--with-phase2`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/episode/SKILL.md`, `skills/intention/SKILL.md`, `skills/wow/SKILL.md`

**What breaks.** It scaffolds drafts per tier. A missing tier template yields a draft that is structurally wrong rather than absent.

**How to tell.** One tier's draft is much shorter or oddly shaped compared with the others.

**How to fix.** Compare against the tier's template and fix the template. Everything it writes is a draft - nothing here publishes anything.

---

## `imports/generate_pokupki.py`

**What it does.** Phase 3 generate: pokupki-archive.jsonl -> staging tree.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** It writes into a staging tree. If the previous phase produced an empty archive, this one cheerfully generates an empty tree.

**How to tell.** The staging folder exists but holds few or no notes.

**How to fix.** Go back one phase and check the archive line count before regenerating. Staging is disposable - delete it and re-run rather than patching it.

---

## `imports/gpu_check.py`

**What it does.** gpu_check.py — machine-agnostic accelerator probe.

**Input.** command line: `--kill`

**Output.** prints to the console; writes nothing

**Needs installed.** `brain_common`, `torch`

**Called by.** `skills/brain/SKILL.md`, `skills/obsidian-ingest/SKILL.md`, `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks.** Drivers or the accelerator library are missing, so it reports no GPU on a machine that has one.

**How to tell.** It says CPU-only on hardware you know has an accelerator.

**How to fix.** Check the driver and the library separately - either one missing produces the same message. Do not proceed with heavy embedding work until it reports the accelerator, or the job will take hours instead of minutes.

---

## `imports/parse_assistants_ops.py`

**What it does.** Assistants-Ops Telegram import -- TEST SAMPLE build (messages71-73).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Same as the other chat parsers: a changed export shape, or a message author whose handle is not in the roster, so their messages are dropped unattributed.

**How to tell.** Message counts per author look wrong - one person contributes suspiciously few.

**How to fix.** Add the missing handle to the roster at the top of the file and re-run. The parser is safe to re-run; it rebuilds its output from scratch.

---

## `imports/parse_faaa.py`

**What it does.** FAAA Follow-ups adapter — Phase 1 parser.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** A follow-up line that does not match the expected pattern is skipped in silence, so real follow-ups vanish between phases.

**How to tell.** The parsed count is lower than the number of follow-up lines you can see in the source by eye.

**How to fix.** Run it on a small slice first and read the output next to the input. Widen the pattern for the missed form; re-run the whole phase afterwards.

---

## `imports/parse_pokupki.py`

**What it does.** Phase 1 parse: Pokupki (purchases) Telegram result.json -> pokupki-archive.jsonl Roster keyed on stable from_id.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** The chat export is missing, or it is a different export shape than the parser expects, so it matches nothing.

**How to tell.** The archive file it produces has zero lines, or far fewer than the export has messages. Compare the two counts every run; do not trust 'finished'.

**How to fix.** Open the export and confirm it is the JSON form the parser reads, not the HTML one. If the shape changed, fix the parser - do not hand-edit the archive, or the next run overwrites your edit.

---

## `imports/render_cards.py`

**What it does.** FAAA Phase 5 — render one CRM lead card per lead into staging.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** It writes one card per lead. A lead missing its key field is skipped.

**How to tell.** Card count is lower than lead count.

**How to fix.** Find the leads with the missing field and fill it upstream in the CRM, not in the rendered card - cards are regenerated and your edit would be lost.

---

## `imports/retro_inventory.py`

**What it does.** Read-only deterministic inventory of recently built/changed REUSABLE artifacts.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fleet/SKILL.md`, `skills/retro/SKILL.md`, `skills/tt/SKILL.md`

**What breaks.** It looks at recently-changed files. A clock skew or a bad time window makes it report nothing was built.

**How to tell.** An empty inventory after a session you know produced files.

**How to fix.** Widen the time window and re-run. It is read-only, so re-running costs nothing.

---

## `scripts/rule_home_guard.py`

**What it does.** rule_home_guard.py -- счётчик покрытия правила в always-loaded слое.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/canon-revision/SKILL.md`, `skills/intake/SKILL.md`, `skills/retro/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/alpha/alpha_harvest.py`

**What it does.** alpha_harvest.py — fold the 10 miners' heterogeneous judge reports into ONE uniform table the review screen can read.

**Input.** command line: `--quiet`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/alpha-review/SKILL.md`, `skills/community-alpha/SKILL.md`

**What breaks.** It folds several judge reports into one table. A missing report is skipped, so the table looks complete while one miner is absent.

**How to tell.** The table has fewer source miners than you ran.

**How to fix.** Compare the miner list against the reports present, and re-run the missing miner rather than accepting the short table.

---

## `imports/arch/arch_status.py`

**What it does.** arch_status.py -- System Architect, on-demand status reader (for the /arch skill).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/1/SKILL.md`, `skills/arch/SKILL.md`

**What breaks.** It reads a map database built by a separate scan. If the scan has not run, it reports yesterday's system as today's.

**How to tell.** Components you added or removed today are missing or still listed.

**How to fix.** Re-run the scan, then read the status again. Check the scan's own timestamp rather than assuming it ran.

---

## `imports/dialogs/build_chats_db.py`

**What it does.** build_chats_db.py -- local index of ALL Telegram chats/entities -> chats.db.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chat/SKILL.md`, `skills/telegram-howto/SKILL.md`

**What breaks.** It needs a live Telegram session to enumerate chats. Without one it builds an empty or partial index.

**How to tell.** Chat count in the database is far below the chats you actually have.

**How to fix.** Re-authenticate, then rebuild. A partial index is worse than none, because lookups against it return confident misses.

---

## `imports/n8n/build_dashboard.py`

**What it does.** Build a self-contained HTML dashboard from the n8n audit profiles.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/n8n/SKILL.md`, `skills/relink/SKILL.md`

**What breaks.** It renders a self-contained HTML from an analysis step. If the analysis is stale the dashboard is confidently out of date.

**How to tell.** The dashboard shows a date older than the data you just imported.

**How to fix.** Re-run the analysis, then re-render. The dashboard carries its own build date - read it before trusting the numbers.

---

## `imports/orphan-scan/build_dashboard.py`

**What it does.** Build a self-contained HTML dashboard from orphan-scan outputs.

**Input.** command line: `--force`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `derived_writers`

**Called by.** `skills/n8n/SKILL.md`, `skills/relink/SKILL.md`

**What breaks.** It renders a self-contained HTML from an analysis step. If the analysis is stale the dashboard is confidently out of date.

**How to tell.** The dashboard shows a date older than the data you just imported.

**How to fix.** Re-run the analysis, then re-render. The dashboard carries its own build date - read it before trusting the numbers.

---

## `imports/build_rules_pokupki.py`

**What it does.** Build reglament-pokupki-*.md from curated purchase rules; link to the existing Operations Bible concepts; write a Pokupki-rules index.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** It links generated rules into an existing Bible note. If that note moved or was renamed, the links dangle.

**How to tell.** The generated rules exist but their links resolve nowhere.

**How to fix.** Point the link target at the note's current name and regenerate.

---

## `scripts/bus_ping.py`

**What it does.** bus_ping.py -- one-shot Telegram ping to Anton's Saved Messages.

**Input.** command line: `--check`, `--drain`, `--post`, `text`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`, `tg_bot_send`

**Called by.** `skills/five-hard/SKILL.md`, `skills/wisdom-distill/SKILL.md`

**What breaks.** A wrong chat id sends successfully into a chat nobody reads.

**How to tell.** The send reports success but nothing appears where you expected it.

**How to fix.** Verify the destination id against the chat itself before assuming the sender is broken. Success means 'Telegram accepted it', not 'the right people saw it'.

---

## `imports/granola/call_distill.py`

**What it does.** Stage 1 distillation: verbatim Granola transcript -> structured JSON via Sonnet.

**Input.** command line: `--dry`, `--limit`, `--model`, `--only`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fireflies-sync/SKILL.md`, `skills/granola-sync/SKILL.md`

**What breaks.** It sends a transcript to a model for structuring. A truncated transcript distills into confident but partial notes.

**How to tell.** The structured output stops mid-topic, or covers only the first part of a call.

**How to fix.** Check the transcript length against the call length before distilling. Re-run on the full transcript; do not stitch two partial distillations together.

---

## `scripts/cc-review/cc_review.py`

**What it does.** cc_review.py - "Claude checks Codex" review pair (thin broker).

**Input.** command line: `--diff`, `--model`, `--out`, `--range`, `--repo`, `--task`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/codex-review/SKILL.md`, `skills/gemini/SKILL.md`

**What breaks.** It brokers one side of a review pair. If the other side never answers, it waits or returns empty.

**How to tell.** A review with no findings AND no reviewer text - distinct from a genuine 'no issues found'.

**How to fix.** Confirm the other side is running. Treat an empty review as not-done, never as approval.

---

## `scripts/claude_md_guard.py`

**What it does.** ---------------------------------------------------------------------------

**Input.** command line: `--hard-kb`, `--notify`, `--soft-kb`

**Output.** prints to the console; writes nothing

**Needs installed.** `bus_ping`

**Called by.** `skills/canon-revision/SKILL.md`, `skills/intake/SKILL.md`

**What breaks.** It checks a rules file against size thresholds. Thresholds drift out of sync with the documented ones and it starts enforcing a number nobody agreed.

**How to tell.** It fails on a size the written rule says is fine, or passes one the rule says is not.

**How to fix.** Make the code match the written rule, not the other way round - the rule is the source of truth and the code is the mirror.

---

## `imports/coach_run.py`

**What it does.** coach_run.py — deterministic engine for Anton's daily coach (skill `coach`).

**Input.** command line: `--context`, `--dashboard`, `--set-tone`, `--status`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/coach/SKILL.md`, `skills/coach/references/playbook.md`

**What breaks.** It is deterministic over vault content. Missing input notes give a confident but empty output.

**How to tell.** The generated output has sections with no content under them.

**How to fix.** Check the input notes exist where it expects them; fix the source, regenerate.

---

## `scripts/cc-review/codex_review.py`

**What it does.** codex_review.py - "Codex checks Claude" review pair (thin broker, REVERSE of cc_review.py).

**Input.** command line: `--diff`, `--model`, `--out`, `--range`, `--repo`, `--task`, `--timeout`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `verdict_parse`

**Called by.** `skills/codex-review/SKILL.md`, `skills/gemini/SKILL.md`

**What breaks.** The mirror image of cc_review.py, with the same failure: a silent partner.

**How to tell.** Same signal - empty output that is not an explicit 'no issues'.

**How to fix.** Same fix. Do not let an unanswered review count towards a green verdict.

---

## `scripts/consensus.py`

**What it does.** consensus.py -- autonomous machine<->machine CONSENSUS engine (Phase 1).

**Input.** command line: `--all`, `--days`, `--details`, `--help`, `--id`, `--json`, `--reversible`, `--tier`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_ping`, `fleet_sign`, `telethon`

**Called by.** `skills/03/SKILL.md`, `skills/retro/SKILL.md`

**What breaks.** A peer stops answering mid-negotiation, leaving a proposal open forever.

**How to tell.** A proposal sits in the same state across several checks with no new rounds.

**How to fix.** Check the peer is alive on the bus first. If it is genuinely gone, close the proposal explicitly - an abandoned open proposal blocks the next one.

---

## `imports/dedup_posts.py`

**What it does.** Systematic exact-duplicate detection across Telegram post files.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Exact-duplicate detection only catches byte-identical posts. Near-duplicates with one edited character survive.

**How to tell.** You still see obvious repeats after a clean run.

**How to fix.** Those are near-duplicates, not a bug in this tool - use the near-duplicate pass instead. Do not loosen exact matching; it is what makes this one safe to trust.

---

## `imports/dr_collect.py`

**What it does.** dr_collect.py — ночной СБОРЩИК + СТОРОЖ Deep Research отчётов (0 токенов, stdlib).

**Input.** command line: `--post-alerts`, `--stale-hours`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `dr_registry`

**Called by.** `skills/alfa-search-recall-deepresearch/SKILL.md`, `skills/dr-fanout/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/dr_registry.py`

**What it does.** dr_registry.py v3.1 — реестр Deep Research Антона (0 токенов, stdlib only).

**Input.** command line: `--file`, `--gap`, `--note`, `--status`, `--today`, `--tool`, `id`, `topic`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `CLAUDE_VAULT_ROOT`

**Needs installed.** `fleet_nodes`

**Called by.** `skills/alfa-search-recall-deepresearch/SKILL.md`, `skills/dr-fanout/SKILL.md`

**What breaks.** Entries are closed with an explicit status and reason. Without one they sit in an intermediate state forever, which looks like ongoing work.

**How to tell.** A large backlog of entries in the same middle state with no recent movement.

**How to fix.** Close each one as applied or parked with a written reason. Do not bulk-close them - the reason is the point of the record.

---

## `scripts/fb_guard.py`

**What it does.** !/usr/bin/env python3

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fb-post/SKILL.md`, `skills/fb-reply/SKILL.md`

**What breaks.** Same shape as social_guard.py: a lost counter reads as an unused quota.

**How to tell.** It allows more posts in a day than the cap it advertises.

**How to fix.** Check the counter file exists and is being written. Never bypass the guard to get one more post out - that is precisely the post that triggers a ban.

---

## `scripts/fb_posts_poll.py`

**What it does.** fb_posts_poll.py - read Anton's own recent FB posts via Graph API /me/posts (READ-ONLY).

**Input.** command line: `--limit`, `--out`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `requests`, `untrusted`

**Called by.** `skills/fb-reply/SKILL.md`, `skills/fb-watch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/find_chat.py`

**What it does.** find_chat.py -- instant local Telegram chat lookup over chats.db (0 tokens, 0 MCP).

**Input.** command line: `--all`, `--limit`, `--users`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `name_norm`

**Called by.** `skills/chat/SKILL.md`, `skills/telegram-howto/SKILL.md`

**What breaks.** It reads the local index only, so it is exactly as stale as the last refresh.

**How to tell.** A chat you joined recently is not found.

**How to fix.** Refresh the index, then look again. Do not add the chat to the index by hand.

---

## `imports/fireflies/fireflies_pull.py`

**What it does.** Fireflies.ai -> vault pull (official GraphQL API, key from secrets\fireflies.env).

**Input.** command line: `--dry`, `--limit`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fa/SKILL.md`, `skills/fireflies-sync/SKILL.md`

**What breaks.** It needs an API key from a local secrets file that is deliberately not in this repo.

**How to tell.** It fails immediately with a missing-key or unauthorized error.

**How to fix.** Create the secrets file with your own key. Never commit it - the path is in the source precisely so the value does not have to be.

---

## `scripts/_shared/firefox_cookies.py`

**What it does.** firefox_cookies.py -- Флотовый хелпер: извлечение session-куки из Firefox.

**Input.** command line: `--count`, `--domain`, `--export`, `--profile`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `APPDATA`

**Called by.** `skills/dr-fanout/SKILL.md`, `skills/notebooklm/SKILL.md`

**What breaks.** It reads cookies from a browser profile. A locked profile - the browser is open - or a moved profile yields nothing.

**How to tell.** It returns no cookies while you are demonstrably logged in.

**How to fix.** Close the browser and re-run. If it still finds nothing, the profile path is wrong. Treat extracted cookies as credentials: they belong nowhere near a repo.

---

## `scripts/cc-review/gemini_review.py`

**What it does.** gemini_review.py -- "Gemini проверяет Claude": ТРЕТЬЯ внешняя пара глаз, родной брат codex_review.py (OpenAI) и grok_review.py (xAI).

**Input.** command line: `--context`, `--diff`, `--engine`, `--model`, `--no-log`, `--out`, `--range`, `--repo`, `--ritual`, `--task`, `--timeout`, `mode`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `verdict_parse`

**Called by.** `skills/gemini/SKILL.md`, `skills/tt/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/generate_obsidian.py`

**What it does.** Phase 3 generator: classified JSONL -> Obsidian markdown into STAGING.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Same shape: it turns classified records into notes, so a classification step that produced nothing yields a staging tree with nothing in it.

**How to tell.** Note count in staging does not match record count in the classified file.

**How to fix.** Check the classified input first. Regenerate staging from scratch; never edit staging by hand, because it is rebuilt on every run.

---

## `imports/ingest_ai_conversation.py`

**What it does.** ingest_ai_conversation.py — wrap a single AI chat transcript (Claude/ChatGPT) into a STAGED vault note that (a) preserves the raw transcript verbatim and (b) scaffolds the epistemic-decay schema (intent / valid_as_of / volatility / interpre...

**Input.** command line: `--authored-by`, `--date`, `--in`, `--origin`, `--out-dir`, `--source`, `--title`, `--volatility`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`, `skills/obsidian-ingest/references/vault-conventions.md`

**What breaks.** It wraps one transcript into staging. A transcript in an unexpected export format produces a note with no body.

**How to tell.** The staged note exists but is nearly empty.

**How to fix.** Check which export format you have and use the matching adapter. Delete the empty staged note; do not fill it in by hand.

---

## `imports/integrate_distilled.py`

**What it does.** Integrate 02-Decisions, 03-Insights, 05-Resources into the knowledge graph.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/pipeline.md`, `skills/obsidian-ingest/references/source-adapters.md`

**What breaks.** Graph integration edits existing notes. Interrupted halfway, it leaves some notes linked and others not.

**How to tell.** Newly integrated notes have inbound links; the rest of the batch has none.

**How to fix.** Back up the vault, then re-run - it is written to be re-runnable. If it is not safe to re-run on your data, stop and check that before running it twice.

---

## `imports/integrate_transcripts.py`

**What it does.** Integrate new transcript-episode subfolders under 01-Conversations.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/pipeline.md`, `skills/obsidian-ingest/references/source-adapters.md`

**What breaks.** It keys episodes by folder name. Rename a folder and the same episode integrates twice under two identities.

**How to tell.** Duplicate episode notes differing only in title.

**How to fix.** Settle the folder name before integrating. Merge the duplicates by hand and keep the name stable afterwards.

---

## `imports/leak_scan.py`

**What it does.** leak_scan.py — deterministic pre-publication leak scanner (ONE gate for every public rail).

**Input.** command line: `--diff`, `--profile`, `--self-test`, `--stdin`

**Output.** prints to the console; writes nothing

**Called by.** `skills/journey/SKILL.md`, `skills/release-slice/SKILL.md`

**What breaks.** Its pattern list ages. New handles, hosts and ids appear and it keeps reporting clean against last month's definition of private.

**How to tell.** It reports zero hits on a file you know mentions someone by name.

**How to fix.** Add the missing value to its pattern list and re-run. Treat a zero-hit result on new material as untested, not as proof.

---

## `imports/map_concepts_pokupki.py`

**What it does.** Concept + tag routing for Pokupki knowledge notes (weighted bilingual keyword map; product-domain beats process-domain).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Routing is a keyword map. Vocabulary drifts, and notes stop matching any concept, so they land unrouted.

**How to tell.** A growing pile of notes with no concept tag.

**How to fix.** Read the unrouted notes and add the words they actually use to the map. Do not add a catch-all fallback - unrouted-and-visible beats wrongly-routed.

---

## `imports/alpha/mine_channel.py`

**What it does.** mine_channel.py — GENERIC one-command miner for ANY Telegram channel/chat.

**Input.** command line: `--channel`, `--detect-only`, `--limit`, `--since`, `--slug`, `--top`, `--until`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`

**Called by.** `skills/mine-channel/SKILL.md`, `skills/watch-channel/SKILL.md`

**What breaks.** Mining a channel you are not a member of returns nothing, which reads identically to 'the channel is quiet'.

**How to tell.** Zero messages from a channel you know is active.

**How to fix.** Confirm membership first, then re-run with a small limit to check the pipe works before pulling the full history.

---

## `imports/namesearch/name_index.py`

**What it does.** name_index.py — строит names.db: отпечаток имени -> карточка.

**Input.** command line: `--vault`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `name_norm`

**Called by.** `skills/find/SKILL.md`, `skills/obsidian-ingest/references/pipeline.md`

**What breaks.** It builds the fingerprint database the name lookup depends on. Built from a partial contact list, it produces confident misses.

**How to tell.** Lookups fail for people you know are in your contacts.

**How to fix.** Rebuild from the full contact source. A partial index is worse than an absent one, because a miss reads as 'this person does not exist'.

---

## `imports/chatgpt/nightly_sync.py`

**What it does.** nightly_sync.py - ORCHESTRATES the nightly ChatGPT -> vault pull, reusing the existing single-source scripts (no logic duplication).

**Input.** command line: `--zip`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chatgpt-sync/SKILL.md`, `skills/local-chatgpt-token-heal/SKILL.md`

**What breaks.** It orchestrates a pull that depends on a live browser session; the session expires silently overnight.

**How to tell.** The nightly run completes with zero new items several nights running.

**How to fix.** Re-authenticate and run once by hand to confirm items arrive, before trusting the schedule again. Zero new items is only normal if you were genuinely idle.

---

## `scripts/onair.py`

**What it does.** onair.py -- ON AIR board: advisory work-declaration layer for the fleet (v1).

**Input.** command line: `--agent-kind`, `--also`, `--branch`, `--contact`, `--expected-end`, `--force`, `--hook`, `--journal`, `--mode`, `--person`, `--session`, `--summary`, `--title`, `--ttl-hours`, `--zone`, `id`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/canon-revision/SKILL.md`, `skills/retro/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/persona_build.py`

**What it does.** persona_build.py -- собирает ПЕРСОНАЛЬНЫЙ комплект (CLAUDE.md + MEMORY.md) для нового человека и/или нового узла из трёх источников, вместо того чтобы раздавать всем личный 87-килобайтный CLAUDE.md Антона.

**Input.** command line: `--allow-leaks`, `--check`, `--list`, `--node`, `--out`, `--person`, `--print`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `HANDOVER.md`, `skills/follower-onboard/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/refresh_chats.py`

**What it does.** refresh_chats.py -- keep chats.db fresh from a DEDICATED read session.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`

**Called by.** `skills/chat/SKILL.md`, `skills/telegram-howto/SKILL.md`

**What breaks.** It runs on a dedicated read session. If that session is also used elsewhere at the same time, Telegram may drop one of them.

**How to tell.** Refreshes start failing intermittently rather than consistently.

**How to fix.** Give it its own session and do not share it with an interactive client.

---

## `scripts/_shared/secondop_client.py`

**What it does.** secondop_client.py -- peer-side client for the Codex second-opinion broker (Phase 1.5).

**Input.** command line: `--context`, `--force-broker`, `--ritual`, `--task`, `--wait`, `point`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/secondop/SKILL.md`, `skills/tt/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/_shared/social_guard.py`

**What it does.** social_guard.py — единый rate-guard публикаций в соцсети (TG / X / FB).

**Input.** command line: `--text`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/tg-post/SKILL.md`, `skills/x-post/SKILL.md`

**What breaks.** Rate limits are counted from a local record. Delete or lose that record and the guard thinks today's quota is untouched.

**How to tell.** It permits a post you know is over the daily limit.

**How to fix.** Restore the record rather than raising the limit. The limit exists to protect the account from a ban, and the guard cannot see posts made without it.

---

## `imports/sostav/sostav_alpha.py`

**What it does.** sostav_alpha.py — COMMUNITY-alpha detector over the СОСТАВ club (sostav.db).

**Input.** command line: `--since`, `--tag`, `--top`, `--until`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/community-alpha/SKILL.md`, `skills/sostav-comments/SKILL.md`

**What breaks.** Detection runs over a local database that must be refreshed first.

**How to tell.** No new signal across a period the community was clearly active in.

**How to fix.** Refresh the database, then re-run the detector.

---

## `scripts/tg_bus_send.py`

**What it does.** tg_bus_send.py -- post a message to the clan Telegram bus WITHOUT the Telegram MCP.

**Input.** command line: `--file`, `--raw`, `--to`, `text`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`

**Called by.** `skills/intention/SKILL.md`, `skills/tg-check/SKILL.md`

**What breaks.** It posts without the Telegram MCP, so it needs its own session. An expired session fails at send time, not at import time.

**How to tell.** Sends stop working while everything else about the bus looks healthy.

**How to fix.** Refresh the session credentials it reads, then send one test message and confirm it lands by eye.

---

## `imports/chatgpt/token_heal.py`

**What it does.** token_heal.py -- deterministic ChatGPT bearer self-heal (0 LLM, 0 browser).

**Input.** command line: `--verify-only`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `certifi`

**Called by.** `skills/chatgpt-sync/SKILL.md`, `skills/local-chatgpt-token-heal/SKILL.md`

**What breaks.** It refreshes a bearer token deterministically. If the source of the token changed shape, it heals nothing and reports success.

**How to tell.** Downstream calls keep failing with an auth error after a 'successful' heal.

**How to fix.** Print the token's shape - not its value - and compare against what the API expects. Fix the extraction, not the retry count.

---

## `imports/triage_telegram.py`

**What it does.** Phase 2: triage + sessionize.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Sessionizing depends on message timestamps. An export with missing or out-of-order timestamps produces one giant session or thousands of tiny ones.

**How to tell.** Session count is wildly implausible - one session for a year of chat, or one session per message.

**How to fix.** Inspect the timestamps in the source export. Fix the parse of the timestamp field rather than the session-gap threshold, which is rarely the real cause.

---

## `imports/turnstate/turnstate_show.py`

**What it does.** Viewer for the per-turn semantic-state ledger (Phase 1 of always-on memory).

**Input.** command line: `--dream`, `--n`, `--session`, `--stats`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/1/SKILL.md`, `skills/retro/SKILL.md`

**What breaks.** It only shows what the ledger recorded. If the recorder was not running, the viewer shows a blank stretch that looks like idle time.

**How to tell.** A gap in the timeline covering a period you know was busy.

**How to fix.** Check the recorder, not the viewer. The viewer is read-only and cannot lose data on its own.

---

## `imports/validate_links.py`

**What it does.** Vault link integrity check + RATCHET gate.

**Input.** command line: `--full`, `--gate`, `--json`, `--write-baseline`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/relink/SKILL.md`, `templates/concept-creation-rules.md`

**What breaks.** It ratchets: the allowed number of broken links may only go down. A large legitimate import can trip it.

**How to tell.** It fails with a count just above the stored ratchet value.

**How to fix.** Fix the new broken links. Only raise the ratchet deliberately, and say why in the same change - raising it silently is how link rot restarts.

---

## `imports/validate_pokupki_staging.py`

**What it does.** Phase 4 gate: every [[wikilink]] in staging must resolve to a staging or vault file.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/telegram-reimport/SKILL.md`, `skills/telegram-reimport/references/sources.md`

**What breaks.** Nothing much - it is a gate. Its risk is being skipped because it is slow or noisy.

**How to tell.** It lists wikilinks that resolve nowhere. Any non-empty list means the staging tree would import broken links into the real vault.

**How to fix.** Fix the link target or the link text, then re-run until the list is empty. Never import staging while this gate is failing.

---

## `imports/watchers/watch_run.py`

**What it does.** watch_run.py - the /watch-channel nightly runner (ONE task, many channels).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `mine_channel`, `telethon`

**Called by.** `skills/last30days/SKILL.md`, `skills/watch-channel/SKILL.md`

**What breaks.** One channel failing can abort the run for all the others.

**How to tell.** Channels later in the list have no fresh data while earlier ones do.

**How to fix.** Run the failing channel alone to see its real error. The runner should carry on past one bad channel; if it does not, that is the bug to fix.

---

## `imports/_paths.py`

**What it does.** _paths.py -- ONE place _imports ENGINE scripts resolve machine-specific roots.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/tt/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/aggregate_inc.py`

**What it does.** Incremental aggregate: validate synth_out2, merge reused prior synth, assign STABLE slugs (existing contacts reuse their vault slug by tg_id; new get clean slugs).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/aggregate_synth.py`

**What it does.** Phase 4b: validate + aggregate synth outputs; build authoritative clean slugs.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/alpha/alpha_review_server.py`

**What it does.** alpha_review_server.py — the ONE screen where Anton says "это золото / это мимо".

**Input.** command line: `--no-harvest`, `--port`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `alpha_harvest`, `alpha_security_lens`

**Called by.** `skills/alpha-review/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/alpha/alpha_security_lens.py`

**What it does.** alpha_security_lens.py -- the SECOND lens over alpha candidates: the QUARANTINE PRISM (Lite).

**Input.** command line: `--selftest`

**Output.** prints to the console; writes nothing

**Needs installed.** `quarantine_lib`

**Called by.** `skills/quarantine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/alpha/alpha_tune.py`

**What it does.** alpha_tune.py — the active-learning closer of the alpha-extraction loop.

**Input.** command line: `--min`, `--miner`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/alpha-review/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/namesearch/alt_spellings.py`

**What it does.** alt_spellings.py — ЧИТАЕМЫЕ альтернативные написания имени для поля в карточке.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Needs installed.** `name_norm`

**Called by.** `skills/obsidian-ingest/references/pipeline.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/analyze.py`

**What it does.** Deterministic pre-analysis of the Apple Notes export (0 LLM tokens).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apply_concepts_pokupki.py`

**What it does.** Apply merged concept map (strong deterministic + LLM) to Pokupki post notes: write concept wikilink + domain tag.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/references/sources.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/claude-ai/apply_curation.py`

**What it does.** apply_curation.py -- apply the artifact->concept curation proposals (from the claudeai-artifact-curation Workflow result JSON) into the artifact notes, deterministically.

**Input.** command line: `--dry`, `--result`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/claudeai-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/apply_group_labels.py`

**What it does.** ---------------------------------------------------------------------------

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/ask_server.py`

**What it does.** ask_server.py — /ask as a live visual search of the Second Brain.

**Input.** command line: `--gpu`, `--port`

**Output.** prints to the console; writes nothing

**Needs installed.** `brain_ask`, `brain_common`, `numpy`, `sentence_transformers`

**Called by.** `skills/ask/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/namesearch/backfill_aliases.py`

**What it does.** backfill_aliases.py — вписывает альтернативные написания в aliases: всех лид/человеко-карточек.

**Input.** command line: `--apply`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `alt_spellings`

**Called by.** `skills/obsidian-ingest/references/pipeline.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/backup_healthcheck.py`

**What it does.** backup_healthcheck.py - weekly DETERMINISTIC check that the Obsidian offsite backup is still alive (see backup_to_drive.py + Windows task 'Obsidian Backup to Drive').

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `backup_to_drive`

**Called by.** `skills/obsidian-backup/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/backup_to_drive.py`

**What it does.** backup_to_drive.py — 3-2-1 backup of the Obsidian vault + originals.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-backup/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_common.py`

**What it does.** brain_common.py — shared helpers for the brain_* embedding/search scripts.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `CUDA_VISIBLE_DEVICES`, `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`

**Needs installed.** `sentence_transformers`, `torch`

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_embed.py`

**What it does.** brain_embed.py — TRUE neural-semantic search over the vault.

**Input.** command line: `--anton`, `--ask`, `--reindex`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `numpy`, `sentence_transformers`

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_embed_e5.py`

**What it does.** brain_embed_e5.py — neural search with intfloat/multilingual-e5-base (sharper for Russian).

**Input.** command line: `--anton`, `--ask`, `--reindex`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `brain_common`, `numpy`

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_health.py`

**What it does.** brain_health.py — one-glance health of Anton's "second brain" so failures aren't SILENT.

**Input.** command line: `--quiet`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `BRAIN_EMB_BACKEND`

**Needs installed.** `brain_ask`

**Called by.** `skills/brain/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_search.py`

**What it does.** brain_search.py — "Спроси свой второй мозг".

**Input.** command line: `--anton`, `--ask`, `--reindex`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_semantic.py`

**What it does.** brain_semantic.py — semantic search over the vault via LSA (TF-IDF + TruncatedSVD).

**Input.** command line: `--anton`, `--ask`, `--reindex`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `numpy`, `sklearn`

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/brain_sessions_index.py`

**What it does.** brain_sessions_index.py — "Книга чатов" (episodic-namespace index, Этап 2).

**Input.** command line: `--cpu`, `--full`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `brain_common`, `numpy`, `torch`

**Called by.** `skills/chat-search/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/build_arch_map.py`

**What it does.** build_arch_map.py -- System Architect: VISUAL architecture map (interactive HTML).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/arch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/search/build_catalog_fts.py`

**What it does.** First brick of the unified search layer: BM25/FTS5 catalog over CHAT content.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/search/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/chatgpt/build_chatgpt_moc.py`

**What it does.** build_chatgpt_moc.py — regenerate _ChatGPT-MOC.md from the enriched notes, primary view BY TOPIC (harvested), secondary index BY MONTH.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chatgpt-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_combined_moc.py`

**What it does.** Rebuild _Platinum-CRM-MOC over the COMBINED vault leads (FAAA calls + DM leads).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/faaa-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_crm_dashboard.py`

**What it does.** Platinum CRM funnel dashboard -> _Dashboards/Platinum-CRM-Dashboard.html (self-contained, Chart.js CDN).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/build_dash_export.py`

**What it does.** Build WhatsApp dashboard HTML from SQLite + export valuable named chats for summarization.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/sostav/build_db.py`

**What it does.** Sostav community → SQLite (corpus + people SQL).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_dedup_dashboard.py`

**What it does.** build_dedup_dashboard.py — /dedup review screen (visual).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/dedup/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_dm_moc.py`

**What it does.** Phase 8a: build _Personal-DMs-MOC.md in staging.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_faaa_batches.py`

**What it does.** FAAA Phase 3 — assemble per-lead call bundles and pack into LLM batches.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_fleet_dashboard.py`

**What it does.** build_fleet_dashboard.py — /fleet as a visual snapshot.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fleet/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/build_group_digest.py`

**What it does.** build_group_digest.py -- compact per-group material for LLM sub-classification.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chat/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/build_group_graph.py`

**What it does.** build_group_graph.py -- the group-graph layer on top of chats.db.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chat/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/build_groups_dashboard.py`

**What it does.** build_groups_dashboard.py -- self-contained visual dashboard over chats.db.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chat/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/build_groups_note.py`

**What it does.** Generate the WhatsApp Groups vault note from the DB (labeled active groups).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gitbook/live/build_live.py`

**What it does.** Собирает markdown-заметки волта из выгруженных страниц GitBook (публичная вики лаборатории).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/gitbook-import/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_moc_pokupki.py`

**What it does.** Build _Pokupki-MOC.md: stats, participants, concept index, month/day index, voice-gap note, graph bridges.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/references/sources.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_pipeline_dashboard.py`

**What it does.** build_pipeline_dashboard.py — /pipeline as a visual kanban.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/pipeline/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_pokupki_dashboard.py`

**What it does.** Build a self-contained HTML spending/activity dashboard from the Pokupki import.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/telegram-reimport/references/sources.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_rules.py`

**What it does.** Build Layer-1 (the Bible) from curated rules + Trello rule-cards into staging.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_synth_batches.py`

**What it does.** Phase 4a: condense each >=20-msg person's DM into a compact transcript and pack into synth batches for subagent person-note synthesis.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_synth_packages.py`

**What it does.** Step 3a: one vault pass -> per-concept synthesis material packages.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/build_system_docs.py`

**What it does.** build_system_docs.py -- System Architect, Phase 2 (status + docs-as-code) Reads system.db (from sys_scan.py) and emits: 1) %VAULT%\_Dashboards\System-Health.html (visual status) 2) %VAULT%\00-System\_System-MOC.md (architecture map) 3) %VAU...

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/arch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/build_tag_taxonomy.py`

**What it does.** Organize the 319 Platinum-CRM tags into a taxonomy note + flag merge candidates.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/canon_intake.py`

**What it does.** canon_intake.py — ПРИЁМКА бит-кандидатов из beats-inbox в канон (механика разбора).

**Input.** command line: `--arcs`, `--why`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `show_canon_sync`

**Called by.** `skills/reality-show/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/canon_write_gate.py`

**What it does.** canon_write_gate.py -- GATE before writing CANON (CLAUDE.md / Bible reglament-*/protocol-* / operating-agreement / standing MEMORY.md).

**Input.** command line: `--dry`, `--selftest`, `target`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `CLAUDE_BUS_NOADVANCE`, `CLAUDE_OPERATOR`

**Called by.** `skills/canon-revision/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/catcher_build.py`

**What it does.** Build workflow #2 -- CENTRAL ERROR CATCHER.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Needs installed.** `n8n_build`, `n8n_edit`

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/chat_search.py`

**What it does.** chat_search.py — search INSIDE old chats ("Книга чатов" / episodic index).

**Input.** command line: `--machine`, `--top`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `CHAT_SEARCH_OUT`

**Needs installed.** `brain_common`, `numpy`, `sentence_transformers`

**Called by.** `skills/chat-search/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/chatgpt/chatgpt_export_to_vault.py`

**What it does.** chatgpt_export_to_vault.py — turn the OFFICIAL ChatGPT data export ZIP (conversations-NNN.json split format) into well-linked Obsidian notes following Anton's vault conventions, mirroring claudeai_export_to_vault.py.

**Input.** command line: `--out`, `--zip`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chatgpt-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/clan_alive.py`

**What it does.** clan_alive.py -- THE deterministic answer to "is clan node X alive?" (0 LLM, read-only).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/03/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/claude_md_compress.py`

**What it does.** CLAUDE.md compression harness (deterministic, loss-proof).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/intake/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/claude-ai/claudeai_export_to_vault.py`

**What it does.** claudeai_export_to_vault.py -- convert a claude.ai account export bundle (produced by the browser dump: schema 'claude-ai-export/v1') into well-linked, atomic Obsidian notes following Anton's vault conventions.

**Input.** command line: `--in`, `--out`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/claudeai-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/claude-ai/claudeai_sync.py`

**What it does.** claudeai_sync.py -- idempotent one-command sync of a claude.ai export into the live vault.

**Input.** command line: `--commit`, `--in`, `--reindex`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/claudeai-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/cluster_faaa.py`

**What it does.** FAAA Phase 2 — lead identity resolution (deterministic dedup).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/cc-review/codex_bridge.py`

**What it does.** codex_bridge.py -- Phase 1 of the Claude<->Codex two-vendor consensus chat.

**Input.** command line: `--context`, `--fresh`, `--model`, `--role`, `--task`, `--timeout`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `PATH`

**Needs installed.** `fleet_hmac`

**Called by.** `skills/secondop/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/codex_mirror.py`

**What it does.** codex_mirror.py -- one command to keep Codex's canon mirror (~/.codex/AGENTS.md) fresh.

**Input.** command line: `--dry-run`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/codex-mirror/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/cc-review/codex_pair.py`

**What it does.** codex_pair.py - FULL-AUTO heterogeneous pair: Codex implements, Claude reviews.

**Input.** command line: `--model`, `--out`, `--repo-wsl`, `--task`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/codex-review/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/cofounder/cofounder_watch.py`

**What it does.** cofounder_watch.py — Phase 0 of the real-time / ambient cofounder (decision-realtime-cofounder-2026-07-02).

**Input.** command line: `--reset`, `--stdout`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/cofounder-watch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dialogs/common_groups.py`

**What it does.** common_groups.py -- "do we share any groups with this person/company?" Deterministic join over chats.db (chat_members x chat_accounts).

**Input.** command line: `--account`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `name_norm`

**Called by.** `skills/chat/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/call-bot/config.py`

**What it does.** config.py — single source of the canon values for the BB Platinum booking module.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `templates/concept-creation-rules.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/content_approve.py`

**What it does.** content_approve.py - Phase-1 approval GATE for Anton's content factory.

**Input.** command line: `--port`, `--serve`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/episode/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/content_miner.py`

**What it does.** content_miner.py - the "content lane" of the content-factory.

**Input.** command line: `--all`, `--angle`, `--cap`, `--day`, `--days`, `--lang-hint`, `--limit`, `--note`, `--operator`, `--sid`, `--src`, `--tier`, `--title`, `--visibility`, `--when`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `fb_diary_collect`, `vault_sessions`

**Called by.** `skills/content-mine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/content_publish.py`

**What it does.** content_publish.py -- Phase-2a AK-47 publisher for APPROVED content.

**Input.** command line: `--dry-run`, `--force`, `--register`, `--target`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/episode/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/crm_dashboards.py`

**What it does.** A: generate 3 computed CRM dashboards from person notes (9718).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/sostav/daily_safe_fetch.py`

**What it does.** Daily fetch of recent messages from the SAFE Sostav topic-groups, for the comment-suggestion routine (read summaries -> pick safe thread -> Reddit/Threads answer -> propose to Anton, draft-first, never publish).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Configuration.** Reads these environment variables: `TELEGRAM_API_HASH`, `TELEGRAM_API_ID`, `TELEGRAM_SESSION_STRING_PERSONAL_ACCT`

**Needs installed.** `dotenv`, `telethon`

**Called by.** `skills/sostav-comments/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/declined-scan/declined_scan.py`

**What it does.** declined_scan.py - nightly safety-net for the declined-decisions registry.

**Input.** command line: `--accept-count`, `--revisit`, `--to`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/declined/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/dedup_scan.py`

**What it does.** Read-only: surface near-duplicate ACTIVE full-text reglament rules within each theme.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/dedup/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/_shared/delegate.py`

**What it does.** delegate.py -- 0-token engine for the "04 TASKS" human-delegation lane (Anton 2026-07-14).

**Input.** command line: `--all`, `--by`, `--for`, `--from`, `--note`, `--seed`, `--seed-file`, `--title`, `--to`, `id`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/task/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/demangle_apply.py`

**What it does.** Apply demangle to vault notes whose styled text the Mac exporter exploded into heading fragments.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/deploy_apply.py`

**What it does.** ---------------------------------------------------------------------------

**Input.** command line: `--confirm`, `--force`, `id`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `deploy_lib`

**Called by.** `skills/quarantine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/enrich_n8n.py`

**What it does.** Second pass (0 tokens): from raw/all_workflows.json extract the high-value human logic: sub-workflow call graph (resolved to names), agent system prompts, tool node descriptions, webhook paths, schedule rules, telegram/credential refs.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/namesearch/expand_query.py`

**What it does.** expand_query.py — расширяет ЛЮБОЕ важное слово во все написания.

**Input.** command line: `--grep`, `--line`

**Output.** prints to the console; writes nothing

**Needs installed.** `name_norm`

**Called by.** `skills/find/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/extract_active_groups.py`

**What it does.** ---------------------------------------------------------------------------

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/extract_mangled.py`

**What it does.** Extract notes with exploded-heading mangling (Mac exporter artifact) into per-note files for LLM repair.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/extract_series.py`

**What it does.** Token-optimal step 1: collapse the ~2700 external transcript notes into the UNIQUE set of shows/series (by `parent:`/title), so the author can be resolved once per series, not once per note.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/fb_diary_collect.py`

**What it does.** fb_diary_collect.py - gather one day of Claude Code (openclaw) conversation text into a single UTF-8 file for the daily Facebook-diary generator.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `vault_sessions`

**Called by.** `skills/wow/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/fb_teaser_watch.py`

**What it does.** fb_teaser_watch.py -- deterministic detector + ledger for the "FB-first -> teaser backfill" lane.

**Input.** command line: `--id`, `--in`, `--max-age-hours`, `--no-auto-skip`, `--permalink`, `--rail`, `--text`, `--ts`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fb-watch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/fetch_n8n.py`

**What it does.** Deterministic n8n audit fetcher.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/fill_coverage.py`

**What it does.** C: fill concept: coverage for 02-Decisions & 03-Insights notes lacking concept AND part_of.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/fingerprint_vault.py`

**What it does.** Phase 2: fingerprint existing vault people + concepts for dedup/reuse.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/_shared/firefox_login.py`

**What it does.** firefox_login.py -- Флотовый launcher выделенного Firefox-профиля автоматизации (Playwright persistent context).

**Input.** command line: `--export-state`, `--headless`, `--profile`, `--url`, `--wait`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `playwright`

**Called by.** `skills/notebooklm/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/five_hard_pick.py`

**What it does.** Pick 5 candidate notes for /five-hard.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/five-hard/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gdrive-provenance/fix_gdrive_provenance.py`

**What it does.** Fix the gdrive-personal-mirror provenance bug (see memory gdrive-personal-mirror-provenance-bug).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/fix_pokupki_moc.py`

**What it does.** Deterministically drop superseded reglament lines from _Pokupki-Rules MOC + fix count.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/dedup/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/fleet_migration_dashboard.py`

**What it does.** Fleet migration dashboard — LIVE counts hub scheduled tasks (enabled/disabled), ANCHOR1 crons, and the routine-health rollup, into one auto-refreshing HTML.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fireflies-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gather_beliefs.py`

**What it does.** Harvest distilled beliefs from the 62 concept-synthesis notes: Тезис + Ключевые повороты/уроки + Открытые вопросы.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gemini/gemini_lib.py`

**What it does.** gemini_lib.py — Google Gemini Apps activity -> SQLite + Obsidian notes.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/takeout-pull/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/gen_staging.py`

**What it does.** Generate staging notes for the Apple Notes import.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/generate_dm_archive.py`

**What it does.** Phase 3: generate per-person conversation archive (Layer 2) into staging.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/generate_person_notes.py`

**What it does.** Phase 5: generate person notes (Layer 1) into staging/07-People, inject concept+tags into conversation frontmatter, emit concept index.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/granola/granola_pull.py`

**What it does.** Granola -> vault pull (official public API, key from secrets\granola.env).

**Input.** command line: `--dry`, `--limit`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/granola-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/cc-review/grok_review.py`

**What it does.** grok_review.py - "Grok checks Claude" review lane (THIRD vendor, sibling of codex_review.py).

**Input.** command line: `--diff`, `--effort`, `--out`, `--range`, `--repo`, `--task`, `--timeout`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `verdict_parse`

**Called by.** `skills/gemini/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/hub_boot_report.py`

**What it does.** hub_boot_report.py -- after a reboot the hub CHECKS ITSELF and REPORTS, so Anton never has to remote-in "to switch the robots back on" (Anton 2026-07-14, away-mode).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_ping`

**Called by.** `skills/reboot/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/inbound_build.py`

**What it does.** Build workflow #4 -- PUBLIC INBOUND DOOR (also covers #7 CRM-changed = a special case).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Needs installed.** `n8n_build`

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/chatgpt/incremental_pull.py`

**What it does.** incremental_pull.py — pull ONLY recently-updated ChatGPT conversations via backend-api and emit a ZIP in the official-export shape so the existing chatgpt_export_to_vault.py can fold them in (idempotent by conversation_id).

**Input.** command line: `--projects-only`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/chatgpt-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/ingest_faaa_live.py`

**What it does.** FAAA LIVE incremental ingest — process new messages pulled from the Telegram chat via MCP (faaa/faaa-new-msgs.json, MCP shape) into the existing CRM.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/faaa-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/ingest_live.py`

**What it does.** Bridge: convert a live MCP pull (live_pull.json) into the raw_train/ + manifest format that build_db.py expects.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/inject_concept_backlinks.py`

**What it does.** Phase 8b: append concept->person backlink rosters to referenced concept files (vault).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/integrate_chatgpt.py`

**What it does.** Integrate 2539 ChatGPT notes into the concept layer cheaply, using their existing frontmatter (no per-note LLM).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `yaml`

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/integrate_remainder.py`

**What it does.** Final pass: handle transcript-parent files in collection folders and Telegram sessions missing concept:.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/pipeline.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/integrate_transcripts2.py`

**What it does.** Second-pass integration for remaining transcript-episode subfolders.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/pipeline.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/intention/intention_mine.py`

**What it does.** intention_mine.py - the "intention lane" of the content-factory.

**Input.** command line: `--channel`, `--day`, `--id`, `--limit`, `--no-phase2`, `--note`, `--pending`, `--status`, `--who`, `day`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `fb_diary_collect`, `vault_sessions`

**Called by.** `skills/intention/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/issue_match.py`

**What it does.** issue_match.py -- ЗАМЕР очереди чужого репо + поиск ЖИВОЙ двери (issue) ДО пуша PR.

**Input.** command line: `--all`, `--artifact`, `--init`, `--json`, `--live-days`, `--no-draft`, `repo`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/issue-match/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/watchers/last30days.py`

**What it does.** last30days.py — deterministic "what's NEW in the last N days on topic X" trend-watch.

**Input.** command line: `--days`, `--json`, `--refresh`, `--top`, `--topic`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `mine_channel`

**Called by.** `skills/last30days/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/ledger_calibration.py`

**What it does.** Compute calibration scoring for insight-prediction-ledger.md.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/alpha-judge/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/link_apply.py`

**What it does.** Rail 1+2 APPLY (idempotent, DATA-DRIVEN): weave WhatsApp person notes into the graph.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/link_people.py`

**What it does.** Rail 1 (PEOPLE): deterministic match of WhatsApp DM contacts to the broader vault.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/lint_agents_mirror.py`

**What it does.** lint_agents_mirror.py -- deterministic gate for the "Codex canon mirror went STALE" class.

**Input.** command line: `--agents-md`, `--claude-md`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/codex-mirror/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/lint_approval_routing.py`

**What it does.** lint_approval_routing.py -- deterministic gate for the "ask Anton" routing class.

**Input.** command line: `--arch`, `--rebaseline`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/fb-watch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/match_people.py`

**What it does.** Phase 2b: resolve each DM person -> person-note target (dedup vs existing 07-People).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/memory_guard.py`

**What it does.** Memory Index Guard — keep MEMORY.md from ever bloating past the always-loaded window.

**Input.** command line: `--notify`, `--quiet`, `--soft`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/tt/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/health/merge_health_raw.py`

**What it does.** Merge freshly-pulled messages (raw\_new\<slug>.json) into raw\<slug>.json.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/health-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/merge_synth.py`

**What it does.** Step 3c: merge agent synthesis bodies into 06-Concepts notes.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/mine_predictions.py`

**What it does.** Mine Anton's OWN notes for forward-looking statements (prediction candidates).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/second-brain-layer.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/move_inc.py`

**What it does.** Phase 14: incremental move of Personal-DMs from staging -> vault.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/move_to_vault.py`

**What it does.** Phase 7: selectively move ONLY the Personal-DMs import from staging into the vault.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/n8n_build.py`

**What it does.** n8n_build.py -- create NEW workflows over the REST public API (dead-MCP workaround).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `n8n_edit`

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/n8n_edit.py`

**What it does.** Safe n8n editor helpers.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/namesearch/name_norm.py`

**What it does.** name_norm.py — общий «мозг» умного поиска имён/слов для волта Антона.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/chat/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/names_fix.py`

**What it does.** Phase 1: ask WhatsApp to refresh contact/LID names, then re-snapshot chat list.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/nightly_pull.py`

**What it does.** WhatsApp NIGHTLY pull (variant A, live bridge) -- ONE client session, headless-safe.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/sostav/nightly_run.py`

**What it does.** nightly_run.py — the СОСТАВ nightly watcher (ALL 13 topics, sensitive included).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Needs installed.** `nightly_fetch`, `sostav_alpha`

**Called by.** `skills/sostav-comments/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/orphan-scan/orphan_scan.py`

**What it does.** Vault-wide orphan scanner.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `orphan_scope`

**Called by.** `skills/relink/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/parse_dm.py`

**What it does.** Phase 1 parser: Anton's personal Telegram DM markdown exports -> dm-archive.jsonl + dm-index.json One JSONL row per message.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/parse_facebook.py`

**What it does.** Phase 1: Parse Facebook posts export (посты.md) → JSONL checkpoint.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/plan_incremental.py`

**What it does.** Incremental planning: resolve person-note targets with slug stability by tg_id, decide synth-needed (new + grown) vs reuse-prior-synth.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/pr_watch.py`

**What it does.** pr_watch.py -- ночной сторож GitHub-PR (0 LLM, детерминированный).

**Input.** command line: `--dry-run`, `--paginate`, `--slurp`

**Output.** writes files (see the paths near the top of the source)

**Configuration.** Reads these environment variables: `GH_TOKEN`

**Called by.** `skills/issue-match/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/prep_batches.py`

**What it does.** Split the 649 notes into triage batch files for workflow agents.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/registry/pub_comments_report.py`

**What it does.** pub_comments_report.py - утренний дайджест неотвеченных комментов -> чат 03.

**Input.** command line: `--post`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/comments/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/registry/pub_metrics.py`

**What it does.** pub_metrics.py - единый реестр ОПУБЛИКОВАННОГО контента + метрики + комменты.

**Input.** command line: `--author`, `--author-id`, `--cid`, `--date`, `--in`, `--n`, `--org`, `--ours`, `--replied`, `--story`, `--text`, `--url`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/comments/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/registry/pub_registry.py`

**What it does.** pub_registry.py — ЕДИНЫЙ РЕЕСТР ИСХОДЯЩИХ ПУБЛИКАЦИЙ (content-factory).

**Input.** command line: `--needs-plus`, `--platform`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `voice_triage`

**Called by.** `skills/content-mine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/publish_canon.py`

**What it does.** ---------------------------------------------------------------------------

**Input.** command line: `--check`, `--dry`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_ping`, `deploy_lib`, `fleet_hmac`

**Called by.** `skills/canon-revision/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/quarantine.py`

**What it does.** quarantine.py -- CLI + dashboard for the incoming-package quarantine (layer 4).

**Input.** command line: `cmd`, `note`, `pkg_id`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `deploy_lib`, `quarantine_lib`

**Called by.** `skills/quarantine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/quarantine_lib.py`

**What it does.** quarantine_lib.py -- the PROVENANCE/SECURITY gate over incoming fleet packages.

**Input.** command line: `--selftest`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `deploy_lib`, `fleet_hmac`, `injection_detector`

**Called by.** `skills/quarantine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/quarantine_watch.py`

**What it does.** quarantine_watch.py -- watchdog: a NEW held package -> ping Anton at 02 POLICE.

**Input.** command line: `--dry`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `deploy_lib`, `quarantine`, `quarantine_lib`, `tg_bot_send`

**Called by.** `skills/quarantine/SKILL.md`

**What breaks.** It watches a folder for untrusted arrivals. If the folder path is wrong it watches an empty directory forever and reports all-clear.

**How to tell.** It never reports anything, ever, including when you deliberately drop a test file in.

**How to fix.** Drop a test file in and confirm it is noticed. A watcher that has never fired is untested, not proven quiet.

---

## `imports/recover_body_handle.py`

**What it does.** Recover ## CRM-данные via NON-team @handle found in the call-log body (exact, unambiguous).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/alpha/recurring_scan.py`

**What it does.** recurring_scan.py - RECURRING-PATTERN miner (alpha engine miner #5).

**Input.** command line: `--all`, `--today`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `alpha_roots`

**Called by.** `skills/wisdom-distill/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/render_dm_cards.py`

**What it does.** Render Platinum CRM DM-leads (no-call) into cards.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/render_live.py`

**What it does.** Render the live-ingested fresh FAAA leads into the vault: lead cards + person overlays + day-ledger entries + archive append (advance watermark).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/faaa-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/render_people_full.py`

**What it does.** Promote ALL Platinum-CRM leads with >=1 call (incl no-show) OR >=20 DM msgs to 07-People.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/sync_check/resolve_conflicts.py`

**What it does.** !/usr/bin/env python3

**Input.** command line: `--apply`, `--quarantine`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/sync-check/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/health/run_health_pipeline.py`

**What it does.** One-shot runner: parse -> generate -> moc -> dashboard -> validate.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/health-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/search/search.py`

**What it does.** search.py — unified chat search CLI (first brick: BM25/FTS5 lane).

**Input.** command line: `--chats`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/search/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/search/search_server.py`

**What it does.** search_server.py — visual local search UI over the chat-content catalog.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/search/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/season_state.py`

**What it does.** season_state.py — season-bible контент-фабрики v2 (S3 reality-show континьюити-слой).

**Input.** command line: `--arc`, `--cliff`, `--episode`, `--id`, `--json`, `--name`, `--text`, `--title`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/reality-show/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/show_canon_check.py`

**What it does.** show_canon_check.py — недельный медосмотр сериала по ЖИВОМУ канону show-canon.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/reality-show/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/show_canon_sync.py`

**What it does.** show_canon_sync.py — ПИСАТЕЛЬ ТАБЛО канона (пара к read-only сторожу show_canon_check.py).

**Input.** command line: `--apply`, `--force`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/reality-show/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gitbook/live/slugs.py`

**What it does.** Карта «заголовок главы GitBook -> её slug и URL».

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/gitbook-import/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/gdrive-provenance/split_grey_zone_C.py`

**What it does.** Schema C — split the grey zone (origin: gdrive-personal-mixed) into: - anton : Anton's OWN authorship (his CV, PLATINUM FRAMEWORK, his pitch docs, his call-notes) - personal-docs : documents ABOUT/belonging to Anton but authored by a counte...

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/split_rule.py`

**What it does.** split_rule.py - ТЕНЕВОЙ замер правила разрыва «чиню здесь vs выношу в отдельную сессию».

**Input.** command line: `--attempts`, `--context-pct`, `--days`, `--decision`, `--files`, `--minutes`, `--note`, `--repro-min`, `--shared`, `--what`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/tt/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/stamp_authors.py`

**What it does.** Token-optimal step 3: stamp author: on external transcript notes via a curated series->author map (built from the 89-unique-series list, 0 LLM calls).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/stamp_authors2.py`

**What it does.** Step 3b: resolve the 524 author_status: needs-review notes using authors identified from their OWN content + web-verify (Anton confirmed all external, 2026-06-09).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/strip_ghosts_new.py`

**What it does.** Strip unresolved wikilinks from 02-Decisions, 03-Insights, 05-Resources bodies.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/pipeline.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/sync_monitor.py`

**What it does.** !/usr/bin/env python3

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/raise-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/sys_check.py`

**What it does.** sys_check.py -- System Architect, Phase 4 (tiered integrity tests + restore drill) Reads system.db, runs a cadence-tagged battery of checks, writes results back to system.db (table `check_result`) and a RED flag file if anything critical/da...

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/arch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/sys_coverage.py`

**What it does.** sys_coverage.py -- System Architect: COVERAGE AUDIT.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `backup_to_drive`, `vault_sessions`

**Called by.** `skills/arch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/arch/sys_scan.py`

**What it does.** sys_scan.py -- System Architect, Phase 1 (catalog) + Phase 3 (graph edges) Deterministic, 0 tokens, READ-ONLY discovery of every meaningful asset in Anton's Personal Knowledge Platform -> system.db (SQLite).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/arch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/tailnet_guard.py`

**What it does.** tailnet_guard.py -- nightly check: EVERY fleet peer must be in the tailnet.

**Input.** command line: `--json`, `--test`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/follower-onboard/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/youtube/takeout_pull.py`

**What it does.** takeout_pull.py - the ACTOR that closes the "dropped Takeout handoff" class.

**Input.** command line: `--days`, `--json`, `--label`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `gmail_common`

**Called by.** `skills/takeout-pull/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/tasks/tasks_index.py`

**What it does.** tasks_index.py -- индексатор журнала задач v2 (декрет Антона 2026-07-04, DR26-07-04-HUB-05).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `yaml`

**Called by.** `skills/retro/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/tg_bus.py`

**What it does.** !/usr/bin/env python3

**Input.** command line: `--dedup`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `bus_seen`, `machine_bus`

**Called by.** `skills/bus/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/tg_bus_read.py`

**What it does.** tg_bus_read.py -- surface NEW Telegram-bus messages addressed to THIS machine.

**Input.** command line: `--all`, `--check`, `--dir`, `--files`, `--peek`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`, `untrusted`

**Called by.** `skills/tg-check/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/tg_channels_check.py`

**What it does.** tg_channels_check.py -- per-machine self-test of BOTH Telegram channels.

**Input.** command line: `--check`, `--json`, `--notify`, `--to`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/tg-check/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/registry/tg_comments_collect.py`

**What it does.** tg_comments_collect.py - комменты к нашим TG-постам -> pubmetrics.db (таблица comments).

**Input.** command line: `--dry-run`, `--platform`, `--sleep`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`

**Called by.** `skills/comments/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/tg_group_slots.py`

**What it does.** tg_group_slots.py -- инвентарь и РАНЖИРОВАНИЕ Telegram-групп по релевантности (0 LLM токенов).

**Input.** command line: `--account`, `--confirm`, `--no-probe`, `--plan`, `--top`, `mode`

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `telethon`

**Called by.** `skills/tg-slot/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/whatsapp/train_pull.py`

**What it does.** WhatsApp TRAINING pull (variant A, live bridge).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/whatsapp-sync/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/tg_voice/transcribe_pokupki_voice.py`

**What it does.** Transcribe the downloaded «Покупки» voice .ogg -> pokupki_voice_transcripts.jsonl (keyed by msg_id).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Needs installed.** `whisper_best`

**Called by.** `skills/telegram-howto/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/validate_dm.py`

**What it does.** Validate wikilinks in MY Personal-DMs staging files only (not other imports' staging leftovers), resolving against vault stems + all staging stems.

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/validate_faaa.py`

**What it does.** FAAA Phase 8 — wikilink integrity over staging (vs staging+vault basenames).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/validate_staging.py`

**What it does.** Phase 6: wikilink integrity over staging (resolving against staging + vault basenames).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/apple-notes/validate_vault.py`

**What it does.** Post-move validation in the LIVE vault: every [[wikilink]] in the Apple-Notes import resolves against the full vault.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/verify_file.py`

**What it does.** Verify that EVERY message in one source HTML page is present in the vault.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/obsidian-ingest/references/source-adapters.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/content-factory/voice_triage.py`

**What it does.** voice_triage.py - deterministic state + queue helper for the voice-triage lane AND the unified post-material store (content-factory v2, S4).

**Input.** command line: `--allow-private`, `--bucket`, `--day`, `--days`, `--hub`, `--id`, `--json`, `--lang-hint`, `--note`, `--platform`, `--reason`, `--saved`, `--slug`, `--source-kind`, `--src`, `--status`, `--title`, `--url`, `--via`, `--visibility`, `--when`, `--write`

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/content-mine/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/n8n/watchdog_build.py`

**What it does.** Build workflow #1 -- WATCHDOG (dead-man's-switch / сторож тишины).

**Input.** no command-line arguments - run it as-is

**Output.** prints to the console; writes nothing

**Needs installed.** `n8n_build`

**Called by.** `skills/n8n/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/wisdom_week_gather.py`

**What it does.** Gather Anton's OWN writing from the last N days (default 7) for /wisdom-distill.

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/wisdom-distill/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `scripts/x_post.py`

**What it does.** x_post.py - post a single tweet to X (Twitter) via API v2, OAuth 1.0a user context.

**Input.** command line: `--dry-run`

**Output.** prints to the console; writes nothing

**Needs installed.** `requests_oauthlib`

**Called by.** `skills/fb-watch/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

## `imports/youtube/yt_lib.py`

**What it does.** yt_lib.py — YouTube history normalizer + SQLite store (stdlib only, AK-47).

**Input.** no command-line arguments - run it as-is

**Output.** writes files (see the paths near the top of the source)

**Called by.** `skills/takeout-pull/SKILL.md`

**What breaks / how to tell / how to fix.** Not yet written. Read the source before relying on this engine - do not assume it is safe to re-run.

---

