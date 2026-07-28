---
name: alpha-judge
description: >-
  The LLM-JUDGE stage of Anton's alpha-extraction engine — the reusable "expensive judge"
  half of the "cheap detector → expensive judge" pattern, shared by ALL 10 miners. Given a
  miner's deterministic candidates (0-token prefilter), it keeps only the REAL signal (Anton's
  own X of the right type) and drops noise, then proposes additions to that miner's pre-existing
  curated HOME note. Trigger on "/alpha-judge", "/alpha-judge <miner>", "суди кандидатов",
  "отсуди <майнер>", "прогони судью", "judge the candidates", "просуди майнер". Miners: bets,
  contradictions (stance, bridge, recurring, novelty, identity, openq as they ship; leadsignal+orphan RETIRED 2026-07-16 per etalon).
  Model: Opus in-session by default (Anton's 2026-06-14 session override — switch to Sonnet on his
  command when Opus near limit); nightly unattended = Sonnet (free bucket). Token-cheap: reads ONLY
  the small candidate digest + the home note, NEVER the corpus. Canon: decision-alpha-extraction-engine-variant-a;
  memory alpha-extraction-engine.
---

# 🅰️⚖️ /alpha-judge — the reusable LLM-judge for every alpha miner

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap (his standing request; reports TO Anton only).

The alpha-extraction engine = **cheap deterministic detector (0 tokens) → LLM judge → weekly ≤10 + yes/no calibration**, repeated for each of the 10 miners. The DETECTORS are per-miner scripts in `$IMPORTS_ROOT/alpha/`. The JUDGE is the SAME logic every time — so it lives HERE, once, and is reused. Canon: `02-Decisions\decision-alpha-extraction-engine-variant-a`; memory [[alpha-extraction-engine]].

## Model policy (per [[model-routing-sonnet-grunt]] + Anton's 2026-06-14 session override)
- **In-session, now:** judge on **Opus** (Anton steers; he'll say when to switch to Sonnet as Opus nears its limit).
- **Nightly unattended:** **Sonnet** (idle free bucket) via `judge_nightly.cmd` (headless `claude -p --model sonnet`). LIVE + verified 2026-06-15 — Windows task "Alpha Judge Nightly" Mon 05:00, chained after the 04:15 scan. **Now judges ALL 10 miners** (was bets-only; expanded 2026-06-15) — one headless session reads THIS spec, loops the registry, applies the dedup-vs-home gate, writes each `<miner>-judged-latest.md`. **Vault writes are forbidden in nightly mode** (judge-only; home-note additions wait for Anton's in-session approval). (Auth is in the Windows keychain; check with `claude auth status`, re-login via `claude auth login`. Keep `.cmd` pure-ASCII.)
- The judge is grunt-classification → Sonnet is the natural default once the session-override lifts.

## Miner registry (detector → home → verdict scheme)
| miner key | candidates file (in `_imports\alpha\candidates\`) | ledger db | curated HOME note (feeds, never duplicates) | verdict scheme |
|---|---|---|---|---|
| `bets` | `bets-report-latest.md` | `bets_ledger.db` (table `bets`) | `insight-prediction-ledger` | ✅ сбылось · ❌ не сбылось · 🔁 ещё открыто · 🗑 не ставка |
| `contradictions` | `contra-report-latest.md` | `contra_ledger.db` (`pairs`+`claims`) | `insight-contradictions` | ✅ реальное противоречие · 🟡 эволюция мнения · 🗑 шум |
| `stance` | `stance-report-latest.md` | `stance_ledger.db` (`shifts`+`pairs`) | `insight-contradictions` (§«готов менять мнение») | ✅ реальный сдвиг взгляда (раньше А→теперь Б) · 🟡 уточнение, не сдвиг · 🗑 шум |
| `bridge` | `bridge-report-latest.md` | `bridge_ledger.db` | `insight-worldview-throughlines` | ✅ неочевидный ценный мост между доменами · 🟡 ожидаемая связь · 🗑 случайное со-упоминание |
| `recurring` | `recurring-report-latest.md` | `recurring_ledger.db` | `insight-worldview-throughlines` | ✅ настоящая повторяющаяся убеждённость · 🟡 операц. повтор · 🗑 со-частотность служебных слов |
| ~~`leadsignal`~~ ⛔ RETIRED 2026-07-16 | `leadsignal-report-latest.md` | `leadsignal_ledger.db` | точность 42.9% на эталоне Антона (111🟡/27🔴, 2026-07-05) — лиды живут в `/pipeline`, не в ленте инсайтов. Скрипт на диске, из weekly/judge/harvest выключен | — |
| `novelty` | `novelty-report-latest.md` | `novelty_ledger.db` | `insight-novelty-ideas` (СОЗДАТЬ при первом ✅) | ✅ действительно новая идея · 🟡 вариация известного · 🗑 редкие слова без идеи |
| `identity` | `identity-report-latest.md` | `identity_ledger.db` | `_Self-Bible-MOC` (+ `concept-*` «что я думаю») | ✅ настоящее само-определение (ценность/принцип) · 🟡 ситуативное · 🗑 не про идентичность |
| `openq` | `openq-report-latest.md` | `openq_ledger.db` | `insight-open-questions` ✅ (создан 2026-06-15, 25 вопросов; +226 Detector-A ждут) | ✅ реальный открытый вопрос Антона · 🟡 риторический · 🗑 чужой/служебный |
| ~~`orphan`~~ ⛔ RETIRED 2026-07-16 | `orphan-insight-report-latest.md` | `orphan_insight_ledger.db` | точность 37.5% на эталоне Антона — промахи = рабочие протоколы команды из `05-Resources` (evidence-слой, несвязанность там норма). Сироты-инсайты ловит `/relink --deep`. Скрипт на диске, из weekly/judge/harvest выключен | — |

## Flow (what YOU do)
1. **Pick the miner** from the arg (default `bets` if none; if unclear, ask). Read its candidates file (or query its db for the top unjudged candidates — cap ~25; never the whole corpus).
2. **RECALL the HOME note** (e.g. `insight-prediction-ledger` / `insight-contradictions`) so you DON'T re-propose what's already catalogued. Token-cheap: read only that one note + the candidate digest.
3. **JUDGE each candidate** against the miner's core question — *"is this ANTON'S OWN <X-of-the-right-type>, not noise / not someone else's / not a restatement?"* Classify per the verdict scheme + a ONE-line reason. The detector optimises RECALL; the judge supplies PRECISION.
   - **🛡 DEDUP-VS-HOME GATE (mandatory — added 2026-06-15):** before you KEEP a candidate, check it against the HOME note you recalled in step 2. If the candidate merely **restates** something already catalogued there (same belief / value / bet / question / shift / bridge — even if worded differently), DROP it with verdict **🗑 уже в доме (restatement)**. Only candidates that add something the home note does NOT already contain survive. This is a semantic check (you, the judge, do it — NOT a blind word-overlap filter, which would false-drop real nuance). *Why:* on 2026-06-15 the `identity` (11 raw keeps → 0 truly new after dedup) and `stance` miners re-proposed items already in `_Self-Bible-MOC` / `insight-contradictions`; this gate makes that dedup a required step, not a manual afterthought.
4. **Write the clean signal** → `_imports\alpha\candidates\<miner>-judged-latest.md` (utf-8, `\n`): only the ✅/🟡 keepers, each with quote(s), source `[[wikilink]]`, date if known, verdict, reason. If zero signal, say so plainly (that's a valid, honest result — don't invent).
5. **Propose HOME additions** (the keepers not already in the home note): show Anton **ДО→ПОСЛЕ** ([[show-before-after]]); on his OK → `vault_backup.py` first ([[vault-backup-rule]]) → append to the home note (draft status, he edits) → recalc if the home has an engine (bets → `ledger_calibration.py`). **Never auto-write a curated vault note.**

## Guardrails
- **Token-economy ([[vault-data-architecture]]):** judge reads ONLY the candidate digest + the one home note. NEVER load the corpus. The detector already did the 0-token narrowing.
- **Honesty over yield:** "0 real" is a legitimate verdict (contradictions hit it 2026-06-14 — Anton is consistent + already has the curated map). Don't manufacture signal to look productive.
- **No new ledgers:** every miner FEEDS a pre-existing curated home (bets→prediction-ledger, contradiction→insight-contradictions). Surface NEW candidates; don't duplicate the home.
- **Vault writes** = backup → preview → approve → reindex. Concurrent-git aware: if the vault `index.lock` is held by live git, defer the write and say so.

## Not this skill
Building/refining a DETECTOR script = direct work in `_imports\alpha\` (not here). Running the deterministic scan = the miner's own `.py` / weekly task. This skill is ONLY the judge + home-feed stage.
