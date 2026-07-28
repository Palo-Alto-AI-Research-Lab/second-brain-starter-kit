---
name: dedup
description: >-
  Find and merge DUPLICATE / near-duplicate notes anywhere in Anton's vault (rules, concepts, people,
  leads) using a deterministic scanner + the proven supersede-NOT-delete merge policy. Trigger on
  "/dedup", "почисти дубли", "склей дубли", "найди повторы", "убери дубликаты", "dedupe <folder>".
  Codified 2026-06-08 from the Bible dedup (4 batches, 14 rules merged). Deterministic-first; review before merge; nothing is ever deleted.
---

# /dedup — find & merge duplicates (supersede, never delete)

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap.

## 🖥️ Визуальный дашборд первым (Антон работает глазами)
`python "$IMPORTS_ROOT/build_dedup_dashboard.py"` (сам гоняет скан) → открой `$OBSIDIAN_VAULT/_Dashboards/Dedup-Dashboard.html`: кандидаты-кластеры по темам, цвет = похожесть (🔴 ≥0.7 почти точно дубль), в каждом — какое оставить (новее) / какое superseded. ТОЛЬКО показ; склейка — вручную ниже (supersede, не delete). Комплементарные не трогаем.

## Step 1 — Scan (deterministic; AK-47, ~free; token law)
`python "$IMPORTS_ROOT/dedup_scan.py"` → scans ACTIVE notes by theme, difflib similarity → candidate clusters in `$IMPORTS_ROOT/dedup_report.txt`. For a DIFFERENT folder, copy the script and change its `OPS` path. Start at similarity ≥0.5 (high-confidence), then ≥0.4 for the next tier — **loop-until-dry** (stop when remaining clusters are complementary/noise).

## Step 2 — Judge each cluster (NOT every look-alike is a dup)
- **Identical** → keep the original (lowest msg_id), mark the echo superseded.
- **Same topic, different nuance, non-conflicting** → keep the NEWER; graft the older's unique nuances into it.
- **Conflict** → NEWER wins (Anton's law: свежее бьёт старое по теме). BUT an explicit `origin: anton` rule is overridden only by Anton or an explicit `supersedes`.
- **Complementary** (different facets/recipients) → **LEAVE**. Merging loses nuance (e.g. "notify Anton" vs "notify teacher" vs "notify nanny" = 3 rules, not 1).
- **Money / sensitive / ambiguous** → do NOT merge; **FLAG for Anton**.

## Step 3 — Apply the merge (truth layer)
- Canonical note: add `audience`, `supersedes: "[[loser]]"`, graft nuances into the body.
- Loser note: `status: active` → `superseded`; add `superseded_by: "[[canonical]]"`; add body marker `> ⊘ Объединено в [[canonical]] — <reason>`. **NEVER delete** (git-reversible; nothing lost).
- Record in the sidecar `$IMPORTS_ROOT/superseded_rules.json` (`"<msg_id>": {"by": "<canonical_fn>"}`) so the decision survives a pipeline rebuild.

## Step 4 — Fix the index/MOC view
- If a generator builds the list (e.g. `build_rules2.py`, superseded-aware) AND its inputs exist → re-run → deploy just the MOC file.
- Else hand-fix the index: drop the superseded lines + update the count.
- ⚠️ **GRABLI:** deleting MULTIPLE adjacent list-lines via batched `\n`-anchored Edits JOINS neighbor lines. To remove several lines, use a SCRIPT that filters by slug (like `fix_pokupki_moc.py`), or `git checkout <good-commit> -- <file>` then re-script. NEVER batch-Edit list deletions.

## Step 5 — Backup + verify + report
`vault_backup.py` before edits; after, grep-count `^status: superseded` to verify the number; commit. Report ДО→ПОСЛЕ on real notes + 🧒 recap. Flag anything left for Anton (e.g. money conflicts).
