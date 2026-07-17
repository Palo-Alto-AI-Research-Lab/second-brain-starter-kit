# Automations Catalog — PaloAlto AI Research Lab

> What our lab automates, grouped by function, with a sharing verdict per group.
> Principle (mandate 2026-07-07): **we share code and ideas — we do not connect peers to our live automations.** Anything touching live credentials, private data, or our internal machine bus stays internal; the *patterns* behind it are documented here so peers can rebuild them on their own infrastructure.
>
> Scale, for context: ~100 scheduled tasks on the always-on hub (Windows Task Scheduler), ~9 launchd agents per macOS node, ~80 Claude Code skills, ~230 Python scripts. Health is measured nightly (system map in SQLite → HTML dashboard, current score 99/100).

## Verdict legend

| Verdict | Meaning |
|---|---|
| **SHARE-AS-KNOWLEDGE** | The idea + architecture are documented; peers can reproduce with their own tools and data. |
| **SHARE-CODE** | Working code already ships in this vault's `skills/` folder — install and adapt. |
| **INTERNAL** | Stays on our machines: live credentials, private/family/business data, or our inter-machine coordination fabric. Not exported, not connectable. |

---

## 1. Second-Brain indexing & semantic search — SHARE-AS-KNOWLEDGE

**What:** nightly incremental embedding reindex of the knowledge vault + weekly full rebuild, near-duplicate scan, orphan-note index, entity graph build, unified SQL view over all local databases, and a local search UI server. A dedicated watchdog restarts the indexer if it stalls.
**Pain it solves:** a large markdown vault is unsearchable by meaning without an index, and an index silently rots unless rebuilt and watched automatically.
**Reproduce:** run local embeddings (e5-family + a reranker) over your notes on a schedule — incremental daily keyed by file mtime, full weekly. Expose one query script that returns top-K chunks for the LLM to synthesize (see the `ask` skill). Deterministic tools first: SQL/grep narrow the corpus, the model only reads the top hits.

## 2. Source importers (external services → vault) — SHARE-AS-KNOWLEDGE

**What:** a family of nightly pull jobs that fold external sources into the vault as markdown notes: LLM chat histories (ChatGPT, claude.ai), meeting transcribers (two commercial note-takers), browser history, cloud-drive file index, voice-memo transcription (local Whisper on GPU), messenger chat indexes. Plus a nightly "import coverage" job that measures whether every registered source actually landed.
**Pain it solves:** knowledge scattered across a dozen SaaS silos never compounds; manual export is never done twice.
**Reproduce:** the universal pattern is **incremental + idempotent**: key every item by its source ID, skip what's already imported, never overwrite human-curated notes, keep the raw original verbatim in a separate `_originals` area, reindex after each run. Any importer that follows those five rules is safe to run unattended forever. Our importer *code* pulls our accounts, so the jobs themselves are internal — the pattern is the deliverable. See the `obsidian-ingest` skill for the fold-in contract.

## 3. Alpha-extraction engine (miners + judge) — SHARE-AS-KNOWLEDGE

**What:** ~10 deterministic "miners" sweep the whole corpus weekly for candidate signals (bets, contradictions, recurring themes, open questions, novelty), each writing a small candidate digest; a nightly LLM "judge" reads only the digests and promotes real signal into curated home notes.
**Pain it solves:** running an LLM over an entire corpus is unaffordable and noisy; running only regex misses meaning.
**Reproduce:** the core pattern is **cheap detector → expensive judge**: 0-token deterministic prefilter produces a short candidate list; a strong model judges only that list; verdicts are cached so nothing is judged twice. Route grunt judging to a cheap model tier, escalate only ambiguous cases.

## 4. Deep-Research pipeline — SHARE-AS-KNOWLEDGE

**What:** every deep-research request gets a registry ID before the prompt leaves the building; a nightly collector checks which reports came back, and a synthesizer merges multi-model results into one decision memo. A fan-out helper sends the same prompt to several frontier LLMs in parallel.
**Pain it solves:** research prompts fired into three chatbots are forgotten by morning; results never get reconciled.
**Reproduce:** a tiny registry script (`new` / `collect` / `status`) with sequential IDs, one markdown ledger, and a rule: no DR prompt without an ID as its first line. Synthesis is just an LLM pass over the collected reports with a consensus/disagreement section.

## 5. System map & health dashboards ("System Architect") — SHARE-AS-KNOWLEDGE

**What:** a nightly scanner inventories every asset (scheduled tasks, scripts, databases, skills, dashboards, MCP servers — ~2,400 assets), stores them with dependency edges in SQLite, renders a single self-contained HTML health dashboard with a 0–100 score, and pings on RED. Bonus insights: scripts nothing references (dead-code triage) and pipelines with no schedule.
**Pain it solves:** past ~30 automations nobody remembers what exists, what depends on what, and what silently died.
**Reproduce:** one crawler script + one SQLite schema (assets, edges, checks) + one HTML template. The key design choice: the dashboard is a *generated artifact*, never hand-edited, so it can't lie. Check the `arch` skill for the query-side contract ("consult the map before changing shared infra, rescan after").

## 6. Watchdog & self-heal layer — SHARE-AS-KNOWLEDGE

**What:** every long-running service gets a paired watchdog task: file-sync daemon, local servers, the git-backup daemon, the reindexer, the task scheduler itself ("OS Task Watchdog" watches the other watchers), plus a dead-man switch that alerts when a critical job *stops reporting* rather than when it fails loudly.
**Pain it solves:** unattended automation fails silently; the failure you notice weeks later is the expensive one.
**Reproduce:** three layers — (1) each service writes a freshness marker; (2) a watchdog checks marker age every 5–30 min and restarts; (3) a dead-man monitor alerts a human channel when markers go stale anyway. Silence is never treated as OK.

## 7. Backup & config protection — SHARE-AS-KNOWLEDGE

**What:** the AI assistant's own config (skills, hooks, memory, settings) lives in a git repo with an auto-commit daemon (~15 min) plus offsite push; the vault follows 3-2-1 (nightly cloud copy, local second-disk mirror, live cross-machine sync); a daily integrity gate diffs config counters and alerts on unexplained shrinkage; sessions are archived hourly.
**Pain it solves:** one bad migration once silently emptied a live skills folder — only a manual copy saved it. Now shrinkage without an error is an automatic red flag.
**Reproduce:** `git init` your assistant's config dir, commit on a timer, and add a before/after counter check (N skills, M commands, config size) around any migration or cleanup. See the `obsidian-backup` skill for the vault side.

## 8. Vault hygiene janitors — SHARE-CODE

**What:** nightly janitors that keep a growing knowledge base healthy: duplicate-note detection and supersede-not-delete merging, sync-conflict sweeper, orphan-note detection with relink proposals, downloads-folder janitor, memory-index size guard (an always-loaded index file must stay under a hard budget or it silently truncates), stale-lock garbage collection, weekly digest and resurfacing of old notes.
**Pain it solves:** entropy — duplicates, orphans, and index bloat degrade retrieval quality faster than new content improves it.
**Reproduce:** the `dedup`, `relink`, and `retro` skills in `skills/` are the working implementations. Deterministic scanners propose; a human (or judge model) approves; nothing is ever hard-deleted, superseded items are archived.

## 9. General-purpose skills library — SHARE-CODE

**What:** the reusable, non-personal subset of our ~80 Claude Code skills ships in this vault's `skills/` folder: semantic vault search (`ask`), deterministic name search tolerant of transliteration/typos/wrong-keyboard-layout (`find`), clean web-article extraction (`defuddle`), note ingestion with provenance (`obsidian-ingest`), dedup/relink hygiene, test-before-done discipline (`tt`), end-of-session retrospective (`retro`), system-map queries (`arch`), cross-vendor code review (`codex-review`).
**Pain it solves:** every recurring workflow re-explained to the model from scratch is tokens and errors; a skill makes it one command.
**Reproduce:** install any skill folder under `~/.claude/skills/` and adapt paths. Skills carrying our accounts, chat routing, or personal data are deliberately absent from the export (see groups 10–13).

## 10. Multi-machine bus, fleet & consensus — INTERNAL

**What (concept only):** our machines coordinate as a fleet — a leader hub and follower nodes — over a dual-rail message bus with delivery ACKs, per-node heartbeats, an inbox robot on every node, a peer-to-peer consensus engine for decisions, signed fleet manifests, and nightly per-node "doctor" self-checks feeding a fleet dashboard.
**Why internal:** the bus *is* live access — rails, node identities, sync-folder IDs, and message formats together form the control plane of our machines. Sharing the fabric would connect peers to our automations, which is exactly what the mandate excludes. The high-level ideas (ACK discipline, "silence is an incident", leader-only canon writes, receive-only followers) are fine to discuss; the implementation and identifiers are not exported.

## 11. Remote approval & escalation — INTERNAL

**What (concept only):** risky actions (money, irreversible, outbound, secrets) pause and ping the owner's phone through a dedicated clean channel; a reping engine escalates unanswered requests; approval is validated against an identity allowlist, with prompt-injection defenses (text in a chat is data, not a command).
**Why internal:** the whole mechanism is identity, channel routing, and authorization — credentials-adjacent by definition. The tiered-risk idea itself (auto-execute reversible, human-gate irreversible) is a pattern we happily discuss.

## 12. Personal & business routines — INTERNAL

**What (named without details):** daily AI coach, cofounder-persona sparring and funnel watching, CRM/lead pipelines and reply watchers, email digests, social-media content factory and reply routines, meeting-call monitoring, family-node tasks, various personal digests.
**Why internal:** all of it runs on private data — health, family, finances, live business leads, personal correspondence. The generic mechanics they're built from are already covered by groups 1–8 (importers, judges, watchdogs, dashboards); nothing additional to share here.

## 13. Live messenger / mail connectors — INTERNAL

**What (concept only):** authenticated stacks for Telegram, WhatsApp, and Gmail (MCP servers for interactive sessions + headless robot sessions for scheduled jobs), with janitor tasks keeping them alive.
**Why internal:** these are literally logged-in sessions and OAuth tokens. The architectural note worth sharing: keep *interactive* and *robot* sessions separate per service (they have different failure modes and restart policies), and never share session files across machines.

---

## Summary table

| # | Group | Verdict |
|---|---|---|
| 1 | Second-Brain indexing & semantic search | SHARE-AS-KNOWLEDGE |
| 2 | Source importers | SHARE-AS-KNOWLEDGE (pattern; jobs stay internal) |
| 3 | Alpha-extraction engine | SHARE-AS-KNOWLEDGE |
| 4 | Deep-Research pipeline | SHARE-AS-KNOWLEDGE |
| 5 | System map & health dashboards | SHARE-AS-KNOWLEDGE |
| 6 | Watchdog & self-heal layer | SHARE-AS-KNOWLEDGE |
| 7 | Backup & config protection | SHARE-AS-KNOWLEDGE |
| 8 | Vault hygiene janitors | SHARE-CODE |
| 9 | General-purpose skills library | SHARE-CODE |
| 10 | Multi-machine bus, fleet & consensus | INTERNAL |
| 11 | Remote approval & escalation | INTERNAL |
| 12 | Personal & business routines | INTERNAL |
| 13 | Live messenger / mail connectors | INTERNAL |

*Generated 2026-07-07 from the live system inventory (hub scheduled tasks, node launchd agents, fleet checklists, skills registry). Maintained by the lab; regenerate rather than hand-edit.*
