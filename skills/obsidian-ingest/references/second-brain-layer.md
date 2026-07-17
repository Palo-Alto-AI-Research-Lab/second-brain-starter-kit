# Second-brain layer — distillation & retrieval (beyond ingest)

Ingest fills the vault; this layer makes it a *thinking partner*. Build/refresh after a big import, or when Anton asks to "make it a second brain". Scripts live in `$IMPORTS_ROOT\`.

The model: **Capture → Organize → Distill → Express**. Ingest = first two. This doc = last two.

## 1. Concept-synthesis notes — "Что я думаю о X"
Turn each concept from a definition into a living document of Anton's evolving thought.

**Pipeline (proven, ~62 concepts):**
1. `build_synth_packages.py` — one vault pass → `_synth/<slug>.json` per concept: year-sampled notes (≤10/yr), `#anton-original` prioritized, with `stem` for citations + counts + catalog.
2. Fan out parallel subagents (8 × ~8 concepts). Each reads `_synth_template.md` (the format spec + gold example) and writes a **body-only** markdown to `_synth_out/<slug>.md`. Depth calibrated by `anton_original_notes`: ≥15 → full evolution arc; 5–14 → thesis + key thoughts; <5 → thesis + "что изучал", **never fabricate an arc**.
3. `merge_synth.py` — grafts synthesis on top + preserves old note under `## Legacy`, strips hallucinated links to plain text. **Idempotency guard**: skips notes already containing `synthesis_built:` (running twice would nest Legacy — never do that).

**Note structure:** `> [!abstract] Тезис (year)` · `## Как менялся мой взгляд (year→year)` · `## Ключевые повороты и уроки` · `## Открытые вопросы` · `## Связанные концепты` · `---` `## Legacy`. Frontmatter gains `type: concept, authored_by: hybrid, origin: anton, synthesis_built, synthesis_sources`.

**Quality gates:** every `alias [internal]` must be a real package `stem`; every `concept-X [internal]` a real catalog slug. Agents self-validate; merge re-validates. Hallucination rate observed ~0.4% (auto-stripped).

## 2. Identity layer — who Anton is, distilled
Built ON TOP of the concept-syntheses (harvest their Тезис + повороты/уроки + evolution sections via `gather_beliefs.py`/`_timeline_material`). Five artifacts in `03-Insights/`, all cross-linked + on 00-HOME:
- `insight-worldview-throughlines.md` — ~12 cross-cutting **patterns of thought** (Хайп≠результат, Система>герой, …), each → concepts where it recurs + a `belief-*` note.
- `belief-*.md` (×12) — **atomic convictions**: quote · откуда · где проявляется (real cites) · **напряжение/нюанс** (every belief gets a counter-tension) · связанное.
- `insight-core-values.md` — **what he optimizes for** (8 values), each with the price he pays.
- `insight-contradictions.md` — **where belief ≠ behavior** (system>hero vs nano-manager; preaches anti-hype yet chases it). The most valuable self-knowledge note.
- `insight-decision-timeline.md` — the **trajectory** 2014→2026 (frontier→build→sobering→new frontier, repeating).
- `insight-prediction-ledger.md` — calibration: `mine_predictions.py` scans `#anton-original` for predictive markers + time horizon → curate falsifiable ones into a `Date|Prediction|Horizon|Status(✅/❌/🟡/⏳)|Note` table; assessments **provisional**. Pattern: strong on *direction*, over-optimistic on *timing/scale*.

Refresh after big imports: re-harvest beliefs material and update whichever notes' source counts grew.

## 3. "Спроси свой мозг" — retrieval
- `brain_ask.py` — **primary (best precision). v2 = CHUNKED + TAGGED.** e5-base dense retrieve top-60 → **dedup by path** (best chunk per file) → cross-encoder rerank (`mmarco-mMiniLMv2`, multilingual) **on the matched chunk** → top-12. **Source-type filters** trade recall↔precision: `--person` / `--conv` / `--leads` / `--concepts` / `--insights` / `--notes` (combine = union; default = all), plus `--anton` (#anton-original) and `--ask` (context bundle). Why v2: the old index stored 1 truncated-800-char vector per file → 56% was chat-starts, middles of long notes/chats invisible. Now every note is chunked → any moment of any conversation is findable (e.g. «Alina про Nansen-теги 2022»).
- `brain_embed_e5.py` — e5-base alone (`intfloat/multilingual-e5-base`, 768-dim, `query:`/`passage:` prefixes), faster fallback. `--reindex` rebuilds the e5 index (model ~1.1GB first run) — run this after big imports; both `brain_ask` and `brain_embed_e5` read it.
- `brain_embed.py` — MiniLM (384-dim) fallback — fastest.
- `brain_semantic.py` — LSA (TF-IDF → TruncatedSVD) fallback, numpy+sklearn only.
- `brain_search.py` — BM25 keyword fallback, pure stdlib.
- `brain_embed_update.py` — **PRIMARY reindex tool (use this routinely). v2 = CHUNKED + TAGGED + EDIT-AWARE (2026-06-07).** Splits each note into ~1500-char overlapping chunks (full coverage, no 800-char truncation), one vector per chunk, each carrying `source_type` (person/conversation/lead/concept/insight/note) + `tg_id`/`person`/`date`/`anton`/`chunk_idx`/`mtime`. Incremental keeps files whose `mtime` is unchanged, **re-chunks NEW *and EDITED* files** (fixes the old gap: edits used to stay stale until `--full`), drops deleted. Full rebuild ≈ 480k chunks / ~1.5 GB / ~2.8 h on an A3000 (then incremental = seconds). Still hardened: **single-instance lock** (`_brain_e5.lock` — refuses to start if a live instance runs, killing the zombie pile-up at the source), **device auto-pick** cuda/mps/cpu, **fp16 on CUDA** (halves VRAM → fits beside other GPU apps), **kills stale `brain_embed` GPU processes at start**, **checkpoints every 10k** (resumable). Flags: `--full` (rebuild), `--cpu` (force CPU), `--wait-gpu N` (wait up to N min for VRAM before CPU fallback).
- `brain_common.py` — shared helpers all `brain_*` scripts import: `Lock`, `pick_device(force_cpu, wait_gpu_min)`, `load_model(...fp16)`, `find_stale`/`kill_pids` (zombie cleanup), `pid_alive`. Edit GPU behavior here once → applies everywhere.

### ⚡ REINDEX PROTOCOL (do this, in order — learned the hard way)
1. **`python gpu_check.py`** first. It reports the GPU, whether torch can use it, AND any stuck `brain_embed_*` zombies. If "GPU PRESENT but torch is CPU-build" → install the CUDA wheel it prints (`cuXXX ≤ driver CUDA`, e.g. cu128) once. If it lists zombies → `python gpu_check.py --kill`.
2. **`python brain_embed_update.py`** (add `--wait-gpu 10` if the GPU is shared). It self-locks, self-cleans zombies, picks GPU+fp16, and incrementally catches up. **Never launch a 2nd copy** — the lock now refuses it, but don't fight it.
3. **GPU is machine-specific — ALWAYS detect, NEVER hardcode** (Anton runs me on different computers; once it was an RTX A3000 6 GB, but re-check every machine). VRAM, not utilization %, is the limit (e5 needs ~1.3 GB free).
4. **Zombie trap**: a GPU-OOM can leave python ALIVE holding ~1.4 GB VRAM. Verify death via `nvidia-smi --query-compute-apps=pid` (NOT wmic name-match — unreliable). The lock + auto-kill now prevent recurrence.
- The index is a static snapshot — search is blind to notes added since the last run. Re-run `brain_embed_update.py` after big imports; it's incremental + resumable.

## 4. CRM / social-capital layer (when the vault holds a contact graph)
Once Platinum-CRM leads + person notes are imported, activate the relationship engine. Person notes carry real fields: `relationship` (lead/peer-founder/investor/partner/…), `tier` (vc/fund/investor/founder/kol/…), `status` (new/negotiating/partner/stale/no-show), `dm_msg_count`, `last_contact`, `role_title`, `org`, `country`, domain tags. `crm_dashboards.py` computes 3 notes in `90_MOCs/` (recompute after imports):
- `_CRM-Warm-Stack.md` — contacts with history (`dm_msg_count`≥15) not contacted >90 days, ranked by relationship-weighted score × staleness.
- `_CRM-Investors.md` — `tier∈{vc,fund,investor}` sorted by deal stage.
- `_CRM-Intros.md` — per-domain matchmaking board (founders × investors) for warm intros.
`_CRM-MOC.md` is the hub (live dataview on real fields — NOT invented `warmth`/`message_count`). Date-diff/matchmaking must be computed in Python, not dataview.

## Coverage backfill (deterministic)
`fill_coverage.py` — for `02-Decisions`/`03-Insights` notes lacking `concept:`/`part_of:`, map by subfolder (Cars→concept-cars, Crypto-Web3→concept-blockchain, …) then `domain:`/`topic:` field. Skips meta/session-report notes and hand-built identity notes. Took those folders 44%/58% → 99%/98%.

## Maintenance loop (keep it alive)
After each new ingest: re-run `build_synth_packages.py` + merge only concepts whose source count grew; re-mine predictions; `brain_semantic.py --reindex`. Surface everything on `00-HOME` (dataview on `synthesis_built` + links to ledger + search usage).

## Gotchas (learned)
- **Link validation:** capture target with `re.findall(r'\[\[([^\]\|#]+)', t)` then `.rstrip('\\')` — this is how Obsidian resolves (basename before `|`/`#`) and correctly handles escaped-pipe `b [internal]` table links. A naive `\[\[(.+?)\]\]` + split mis-handles aliases and produces massive false-positive "broken" counts.
- **Merge once.** The graft treats current note body as Legacy; re-running nests it. Guard on `synthesis_built:`.
- **Windows/Cyrillic:** never `print()` Cyrillic (cp1252 crash) — write UTF-8 files and Read them.
