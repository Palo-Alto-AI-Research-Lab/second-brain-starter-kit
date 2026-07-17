# Source adapters — per-source parsing specs

Each section documents one source type: its input format, parse script pattern, triage rules, provenance defaults, and special handling. The **universal pipeline** (parse → JSONL → triage → generate → validate → move → dedup → concept-map → MOC) is the same for every source; only Phase 1 (the parser) and provenance defaults differ.

---

## Facebook posts export (`посты.md` format)

**Source:** Facebook Data Export → HTML → converted to Markdown  
**File:** single `.md` file, e.g. `посты.md`  
**Provenance:** `origin: anton` · `authored_by: human` · tags: `[facebook-diary, anton-original]`  
**Target folder:** `01-Conversations/Facebook/posts/`

### Input format

```markdown
# Facebook posts export

---

## N. Month DD, YYYY HH:MM:SS am/pm

**Headline:** Anton Dziatkovskii shared a post.

**On Facebook:** [open in Facebook archive](https://www.facebook.com/dyi/l/...)

### Content

{post text, or `_[empty]_`, or URL, or [![](local/path.jpg)](local/path.jpg) + text}

---
```

### Triage classes

| Class | Condition | Action |
|---|---|---|
| `noise` | Content = `_[empty]_` | **Skip** — 1227 posts in the reference export |
| `link-only` | Content is a single bare URL (no surrounding text) | **Skip** — link archives without context |
| `photo-only` | Only `[![](...)` image markdown, caption <30 chars | **Skip** — local FB archive paths don't resolve |
| `text` | Any text content ≥30 chars after stripping photos | **Import** |
| `text+photo` | Text ≥30 chars + photo markdown | **Import** (strip photo markdown, keep text) |

Expected distribution (6475-post export):
- text+photo: ~2672 (41%)
- text-only: ~2250 (35%)  
- noise/link/photo-only: ~1553 (24%) → skipped
- **Net import: ~4922 posts**

### Special cases

**"5 Years Ago" memories** — Facebook injects reposts of old content as "memories":
```
[![](path.jpg)]Photos

Оригинальный текст поста...

5 Years Ago

Anton Dziatkovskii added a new photo.

Feb 23, 2021 11:06:48 am

Оригинальный текст поста...  ← same text, different date
```
Detection: block contains `\nN Years Ago\n` + duplicate of the original text.  
Rule: **keep oldest date, discard the memory wrapper** (dedup by content-hash).

**Photo stripping:** remove `[![](your_facebook_activity/posts/media/...)](...)` entirely — local Facebook archive paths are not accessible in Obsidian. If a meaningful caption follows on the next line, keep it.

**Facebook archive URLs:** The `[open in Facebook archive](facebook.com/dyi/l/?l=...)` links are session-specific and expire. Strip them or keep as plain text reference only.

### Parse script pattern (`parse_facebook.py`)

```python
import re, json, unicodedata
from pathlib import Path

content = open(INPUT_FILE, encoding='utf-8').read()
blocks = content.split('\n---\n')

PHOTO_RE = re.compile(r'\[!\[.*?\]\([^)]+\)\]\([^)]+\)[^\n]*\n?')
URL_RE = re.compile(r'^\[?https?://\S+\]?$', re.M)
MEMORIES_RE = re.compile(r'\n\d+ Years? Ago\n')

def parse_date(raw):  # "Mar 30, 2011 8:54:36 pm" → "2011-03-30"
    from datetime import datetime
    for fmt in ['%b %d, %Y %I:%M:%S %p', '%B %d, %Y %I:%M:%S %p']:
        try: return datetime.strptime(raw.strip(), fmt).strftime('%Y-%m-%d')
        except: pass
    return None

def slugify(text):
    text = text.lower()[:60]
    # transliterate Russian — dict form, because some letters map to multi-char
    # (ё→yo, ж→zh, ч→ch, ш→sh, щ→sch). The two-string str.maketrans form requires
    # both args to be equal length (one char → one char) and would raise ValueError.
    _CYR = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'  # 33 chars
    _LAT = ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r',
            's','t','u','f','h','c','ch','sh','sch','','y','','e','yu','ya']
    TRANSLIT = str.maketrans({c: l for c, l in zip(_CYR, _LAT)})
    text = text.translate(TRANSLIT)
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text).strip('-')

posts = []
for block in blocks:
    header = re.search(r'## \d+\. (.+?) \d+:\d+:\d+ [ap]m', block)
    if not header: continue
    date_str = parse_date(header.group(1) + ' ' + 
               re.search(r'\d+:\d+:\d+ [ap]m', block).group(0))
    content_m = re.search(r'### Content\n\n(.+?)(?=\n###|\Z)', block, re.DOTALL)
    if not content_m: continue
    text = content_m.group(1).strip()
    
    # Triage
    if text == '_[empty]_': continue
    stripped = PHOTO_RE.sub('', text).strip()
    stripped = re.sub(r'\[open in Facebook archive\]\([^)]+\)', '', stripped).strip()
    if not stripped or URL_RE.match(stripped): continue
    if len(stripped) < 30: continue
    # Skip memory duplicates (will dedup by content-hash anyway)
    
    posts.append({
        'date': date_str,
        'text': stripped,
        'slug': slugify(stripped),
        'word_count': len(stripped.split()),
        'has_photo': bool(PHOTO_RE.search(text))
    })
```

### Frontmatter template

```yaml
---
title: "{first 80 chars of text}"
type: facebook-post
source: facebook
origin: anton
authored_by: human
date: YYYY-MM-DD
year: YYYY
tags: [facebook-diary, anton-original]
msg_id: {original FB post number}
word_count: N
concept: "concept-... [internal]"      # filled in by LLM concept-mapping pass
---
```

### Filename pattern

`YYYY-MM-DD-{seq:04d}-{slug}.md` — date-prefixed, sequence within the day, latin-kebab slug from first 50 chars.

### MOC structure

`01-Conversations/Facebook/_Facebook-MOC.md`:
- Header: summary stats (total posts, date range, top concepts)
- Year-by-year table with post counts
- Dataview query: `FROM "01-Conversations/Facebook" WHERE tags contains "facebook-diary"`
- Concept map extracted post-import

### Concept mapping volume

4922 posts ÷ 25 per batch = ~197 batches. Run in parallel waves:
- Wave A (batches 1-60): 2017–2018 posts (peak period)
- Wave B (batches 61-120): 2019–2020
- Wave C (batches 121-197): 2011-2016 + 2023-2026

---

## Telegram HTML export

**Source:** Telegram Desktop → Export → HTML (`messages.html`, possibly split)  
**Provenance:** `origin: anton` (all chats = Anton's content team) · `authored_by: human` for Anton's own messages, `hybrid` for summaries  
**Target folder:** `01-Conversations/Telegram/{chat-name}/posts/`, `sessions/`

### Input format

HTML file(s) with `<div class="message">` blocks. Fields: sender, date, text, reply-to, forwarded-from, media caption.

### Triage classes

| Class | Condition |
|---|---|
| `noise` | len(text) < 10 chars |
| `link` | URL-only message |
| `fragment` | 10–200 chars |
| `post` | ≥200 chars → individual file |

`fragment` + `link` messages → sessionized into `Sessions-YYYY-MM-DD.md` ledgers.  
`post` → individual file + entry in session ledger.

**Drop-vs-keep noise depends on chat shape.** In a *monologue/broadcast* chat (one author posting, e.g. the content channel) `noise`/empty is throwaway — drop it. In a *threaded approval/dialogue* chat (boss + team, see Покупки below) a one-word `noise` reply ("да", "нет", "одобряю", "ясно") **is the decision**, meaningless only without its parent — **sessionize it with reply context, never drop it.** Decide by reply density: >40 % of messages being replies ⇒ threaded chat ⇒ keep noise in the ledger.

**Prefer `result.json` over the HTML pages when both are present.** A Telegram Desktop export ships both `messages*.html` and a single `result.json`. The JSON has stable `from_id`s (the HTML only has display names, which collide and change), clean ISO `date`/`date_unixtime`, structured `text_entities` (links/mentions don't have to be re-scraped from `<a>` tags), explicit `media_type`/`mime_type`/`duration_seconds`, and `reply_to_message_id`/`forwarded_from`/pin actions as fields. Parsing one JSON is more reliable than 50 HTML files. Keep the HTML only as a fallback / for visual spot-checks.

**Feb-2025 spike rule:** a month with >500 messages → bucket sessions **by day** (Sessions-2025-02-01.md etc.) not one per 30-min block.

### Session ledger format

```yaml
---
type: session-ledger
source: telegram-archive
month: YYYY-MM
date: YYYY-MM-DD       # for day-bucketed files
session_count: N
tags: [telegram, session]
origin: anton
authored_by: hybrid
---
```

### Provenance note

Telegram content-team chat = all Anton (rule confirmed by Anton: "всё моё ANTON"). Even voice-note transcripts done by an assistant are `origin: anton`.

---

## Telegram — Assistants-Ops operational chat (MIXED, rules + Trello registry)

**Source:** Telegram HTML export of Anton's working chat with household assistants ("All Assistant's tasks 777…"). 73 pages, ~70.5k messages, 2022→2026. Differs fundamentally from the content-team chat: it is **mixed** (a boss + a rotating assistant team), and its prize is the **Библия of регламенты** (durable SOPs).
**Scripts:** `$IMPORTS_ROOT\parse_assistants_ops.py` (Layer 2 + rule candidates) → 8 curator subagents → `build_rules.py` (Layer 1). Checkpoints: `assistants-ops-sample.jsonl`, `rule_candidates.json`, `_rulebatch/curated_*.json`, `trello_rules.json`.

### Two-layer output (Anton's choice)
- **Layer 1 — Bible:** `03-Insights/Operations/` — one `reglament-<slug>.md` per full-text rule, `trello-cards/` (one note per formalized Trello rule-card), `_Operations-Bible-MOC.md` (grouped by theme, 🟢 anton / ⚪ team-SOP), `_Bible-Trello-Index.md` (MOC of the card notes).
- **Layer 2 — archive:** `01-Conversations/Telegram/Assistants-Ops/sessions/Sessions-YYYY-MM-DD.md` — every message, day-bucketed, role-labelled, reply-threaded; `_Assistants-Ops-MOC.md` (month index). Cheap/deterministic; no LLM.

### Provenance model (the hard part — this chat has many speakers)
- **`who()` roster:** Anton accounts (`Tony frm Palo Alto…`, `Anton Dziatkovskii 2023`, `Tony 📍Silicon Valley…`) → anton/principal. Anna (`Anna Dz`, `01 Anna … Dziatkovskaia`) → anna/principal. ~25 rotating assistants (Helena Kondricheva, Oksana, Ekaterina Lavrenyuk, Yuliya, Eva Anna, Olya Tkalich, Zubeyde, Inna, Margaret…) → mixed/assistant. Everyone else (channels, vendors, contractors) → external.
- **Bot-relay = voice principal.** A message with footer `Перевела: <Оксана/Лена/Катя/бот>` and/or `Делегировано:` is **Anton's dictated voice**, transcribed & posted by an assistant — often a `joined` (no-name) bubble, so a naive parser misattributes it to the previous sender. Override: any directive → `origin: anton` (poster/translator → `transcribed_by`/`posted_by`). Transcription ≠ authorship.
- **Anna only by her own name-marker** (`Anna Dz` account, `@annadziat`, `От Анны`, `Анна просит`) — NEVER the generic `задача Анны` (= a task in Anna's domain done by an assistant, not Anna authoring).
- **Rules → existing `[[concept-bible-platinum]]`** (the "Holy Bible Platinum / свод регламентов" concept, already in 06-Concepts) split into theme sub-concepts (`concept-bible-communications`, `-child-education`, `-procurement`, `-travel`, `-staff-hr`, `-access-security`, `-finance`, `-social-media`, `-household`), each `parent_concepts: [concept-bible-platinum]`. Don't mint a parallel umbrella — linking merges the working-chat rules with the canonical Bible instead of forming an island.
- **Conservative #anton-original.** LLM curator marks a rule `origin: anton` (#anton-original) only when it's clearly the boss's directive; team-authored operating SOPs → `origin: mixed`, `authored_by: hybrid`. When unsure, choose mixed — protecting Anton's authentic-voice corpus outranks completeness.

### Rule extraction = candidate-net + LLM curation (NOT regex alone)
Regex `Правил[оа]`-stream over-captures meta-chatter ("правило где??", "напиши правило", "Правила Библии жду") and the daily-report line-item "правило в библию — 15 мин". Export **candidates**, then batched subagents (~45/batch) decide `{is_rule, statement(cleaned), theme, applies_to, origin, authored_by, tags, confidence}`. Yield on the full chat: 356 candidates → **83 real full-text rules** (53 anton / 30 mixed), 273 dropped. Themes: communications-protocol, child-education, travel-logistics, procurement-vendors, staff-hr, access-security, finance-payments, social-media, household-general.

### Trello rule registry (don't drop the links!)
The formalized Bible lives on **Trello** (~696 cards referenced; 351 unique whose slug contains `правил`). Bodies are on Trello; the chat holds title+link. Decode the URL slug (`urllib.parse.unquote`, strip leading `NNN-`) → one `reglament-card` note each (title + link + theme + sub-concept), indexed by `_Bible-Trello-Index.md`. Task/purchase cards (the majority) are not rules — keep them in the ledgers only.

### Cross-dedup vs the Holy Bible channel corpus
A separate import (the "Holy Bible Регламенты Правила" private channel, ~2063 msgs → `concept-bible-platinum`) overlaps. After extracting working-chat rules, dedup their statements/titles against that corpus (content-hash + normalized-title) and flag overlaps in frontmatter (`duplicate_of:`) rather than deleting — the two sources corroborate each other.

### Media
Voice (≈thousands), photos, PDFs export as "Not included". Anton's voice is already bot-transcribed into the directive text, so text-only loses mainly photo-confirmations / menu PDFs / screenshots. Re-export with media only if those matter.

### Incremental re-import
Re-run `parse_assistants_ops.py` (it globs all `messages*.html`), dedup new rule candidates' statement-hash against existing `reglament-*` notes, generate only new ledgers/rules. Day-ledgers are idempotent by date; `build_rules.py` skips a ledger already carrying "Регламенты этого дня".

### Verifying coverage (`verify_file.py`)
To prove a source page was fully imported: parse it, and for every message with text assert its (whitespace-normalized) text is a substring of its day-ledger `Sessions-<date>.md` (check ±1 day for the UTC/local boundary). Media-only messages can't be matched by content — instead compare per-day counts (source media-only ≤ ledger "не выгружено" placeholders; ledger is ≥ because a day aggregates media across adjacent pages and captioned photos). Then check Layer-1: rule candidates whose `msg_id` is in the page made it into `reglament-*`, and any Trello card-ids are present.

> **Gotcha — strip blockquote markers before matching.** Ledgers quote every message line with a leading `> `. So a multi-line message renders as `> line1\n> line2`; after whitespace-collapse that's `> line1 > line2`, and the raw probe `line1 line2` is NOT a substring → false "missing". Run `re.sub(r"(?m)^[ \t]*>[ \t]?", "", ledger_text)` before normalizing. (First pass without this reported 167/688 "missing" that were all artifacts; with it, 688/688.)

---

## Telegram — Покупки / Purchases approval chat (MIXED, threaded, voice-heavy)

**Source:** Telegram `result.json` export of Anton's purchases-approval chat ("Покупки approve Assistant's tasks 777…"). ~48.4k messages, Aug 2023→2026, 28 senders. The **purchases sibling** of Assistants-Ops: same boss-plus-assistants ecosystem and roster, same bot-relay-of-voice pattern, but the prize is different — there is **no Bible of rules**; instead the value is **(a) Anton's buying-research notes** and **(b) a searchable, reply-threaded purchase archive**.
**Scripts:** `parse_pokupki.py` (result.json → `pokupki-archive.jsonl`) → `generate_pokupki.py` (staging: ledgers + posts) → validate → move → dedup → concept-map → `_Pokupki-MOC.md`. Checkpoints in `$IMPORTS_ROOT\`.

### Use result.json, key the roster on `from_id`
Parse the JSON, not the 49 HTML pages (see the generic-Telegram note above). `from_id` is 100 % stable here (0 ids carry >1 display name), so the roster is a `from_id → (origin, role)` dict, immune to name edits — build it from YOUR export (owner ids, assistant ids) instead of hardcoding names. Reuse the relay-footer override (`Перевела:/Делегировано:` ⇒ `origin: owner`, poster → `transcribed_by`). `text` may be a str **or** a list of entities — concatenate, rendering `text_link`→`text (href)` and `link`→the url so product links survive.

### The voice gap is the headline fact — account for it honestly
This chat is **voice-first**: of Anton's 19.5k messages, **11.8k are empty voice bubbles** and only **248 are typed ≥200-char posts**. Voice (9 418 `voice_message`, `audio/ogg`) and most photos/PDFs export as **media-not-included** (the media folders are ~0 MB). So most of Anton's actual reasoning is **not recoverable from this export**. Two consequences: (1) the recoverable Anton-voice is the **~4k relay messages** (assistant-transcribed) — treat those as the main `origin: anton` knowledge, not the 248 typed posts; (2) render every text-less media message as a compact **placeholder** in the ledger (`🎤 голосовое 16s [не транскрибировано]`, `🖼 фото`, `📄 PDF`) so threads stay intact and the gap is visible, and record `voice_not_transcribed: N` in the MOC. Offer (don't force) the follow-up: re-export *with media* → Whisper-transcribe the `.ogg` → enrich ledgers/posts **by message-id** (idempotent, no rework).

### Reply-threading is the spine — render parent context
51 % of messages are replies; a bare "нет"/"ясно"/"одобряю" is the actual decision and is meaningless alone. Build an `id → (sender, ≤80-char snippet)` map and render each reply as `↳ в ответ [Helena 13:24]: «…»`. Bare-`noise` approvals are **kept and sessionized** (NOT dropped — the generic Telegram pipeline drops noise; this chat must not).

### Two-layer output, purchases-flavoured
- **Layer 2 — archive (deterministic, no LLM):** `01-Conversations/Telegram/Pokupki/sessions/Sessions-YYYY-MM-DD.md` — every text message, day-bucketed, role-icon (🟢 Anton / 🔵 Anna / ⚪ assistant / ⚫ external), reply-threaded, media placeholders. `_Pokupki-MOC.md` = month index + stats + participants + concept index + voice-gap note.
- **Layer 1 — knowledge (the prize):** `Pokupki/posts/YYYY-MM-DD-slug.md` — one atomic note per substantive item: Anton typed posts + relay-recovered Anton-voice directives (`origin: anton`), plus genuine assistant **product/vendor research** (`origin: mixed`). **Exclude** pure **status-ledgers** (numbered lists of `отгружено/апрув/ищем/✅`) — those are operational logs, keep them in the day-ledger only. Detect a status-ledger by ≥3 numbered/bulleted lines AND status-word density; everything else ≥200 chars (or a relay directive ≥60 chars) is a knowledge candidate.

### Concepts — bridge to existing graph, don't island
Purchase **research** maps to existing domain concepts (`concept-construction-renovation`, `concept-cars`, `concept-parenting`, `concept-place-livability`, `concept-tech-tools`, `concept-product-recommendation`, `concept-personal-finance`); likely **new**: `concept-procurement-vendors`, `concept-garden-landscaping`, `concept-home-goods`. Purchase **rules** (the distinct pinned messages, e.g. "перед любой покупкой согласовывать цену — скрин, ссылка, цена, карта") bridge into the **existing Operations Bible** under `concept-bible-procurement` / `concept-bible-household` — this is what merges the import into the graph instead of forming an island.

### Pins = the standing purchase rules
`service` messages with `action: pin_message` carry `message_id`; collect the distinct pinned target ids (1 543 pin events, few distinct) → those messages are the chat's operating rules → Layer-1 bridge notes (above), not just ledger lines.

### Provenance defaults
`origin: anton` (Anton accts + relay directives, `#anton-original`) · `origin: mixed` (`authored_by: hybrid`, assistants) · Anna = `origin: mixed` + `#anna`, **never** `#anton-original` · channel/forwarded-external/"Personal Audio Summary" bot = `origin: external`.

### Incremental re-import
`parse_pokupki.py` reads `result.json` (one file). Dedup new text rows' body-hash against the existing `pokupki-archive.jsonl` and the live ledgers; regenerate only new day-ledgers (idempotent by date) and only new posts (collision-safe stems). Stamp `import_batch: <date>`. A future media-included re-export enriches by message-id rather than re-importing.

---

## ChatGPT JSON export (nexus / standard)

**Source:** ChatGPT data export (`conversations.json`) or nexus-ai-chat-importer plugin  
**Provenance:** `origin: mixed` (Anton's prompts + AI responses) · `authored_by: hybrid`  
**Target folder:** `01-Conversations/ChatGPT/{topic}/`

### Input format

JSON array of conversation objects. Each: `{id, title, create_time, messages:[{role, content}]}`.

### Integration approach (deterministic — no LLM needed)

1. **Map `topic` category → primary concept** via 15-entry hand map (see `integrate_chatgpt.py`).
2. **Convert `concepts:` free-text list** to `wikilinks [internal]` for entities that resolve.
3. **Bulk provenance**: add `authored_by: hybrid` + `origin: mixed`.
4. **Ghost-link strip**: run `unresolved [internal] → plain text` pass.

This handled 2539 notes in a single script run without LLM — use the deterministic path whenever frontmatter already has structured `topic` or `domain` fields.

---

## AI conversation — single Claude/ChatGPT transcript (epistemic-decay aware) ⭐

**Source:** ONE pasted/exported AI chat transcript (Claude or ChatGPT) handed over as "это мои мысли" — NOT the bulk `conversations.json` (that's the ChatGPT JSON adapter above). One conversation → one note.
**Provenance:** `origin: mixed` (Anton's prompts + AI answers — ASK if it's purely his) · `authored_by: hybrid`. **NOT `#anton-original`** unless he says the thinking is wholly his.
**Target folder:** `01-Conversations/AI/`
**Script:** `$IMPORTS_ROOT\ingest_ai_conversation.py` (deterministic scaffold + verbatim raw), then LLM-curate.

### Why this adapter exists
An AI dialogue is dense with Anton's live intent + decisions + their justification — flattening it to prose loses the structure. This adapter preserves the shape **Вопрос→интент→рассуждение→решение→триггер пересмотра** and stamps the epistemic-decay-layer [internal] fields so the note carries its own shelf-life.

### What the script does (deterministic)
1. Archive the raw transcript first (preserve-originals: `archive_original.py --source ai-conversations`).
2. Write a staged note to `staging/01-Conversations/AI/<date>-<slug>.md`: rich frontmatter (incl. `intent`, `valid_as_of`, `volatility`, `interpretation_confidence`, `revisit_if`) + the verbatim transcript in a fenced block (fence auto-sized so inner backticks can't break out) + a section skeleton with `<!-- LLM-fill -->` markers.
3. Cyrillic-safe: pass `--title` in latin (drives the slug); set the real RU title during curation (UTF-8 Write); never `print()` Cyrillic.

### LLM curation pass (then move to vault + reindex)
Fill: Интент (one line) · Распознавание (+ `interpretation_note` if it began as garbled voice → `interpretation_confidence: low|med`) · Рассуждение · Решение · Альтернативы (table) · Триггеры пересмотра (→ `revisit_if`) · Источники (with access date). Set `valid_as_of` to when the **load-bearing facts** were true — often EARLIER than the chat date (a Feb fact discussed in June is already volatile). Then move to `01-Conversations/AI/` and run `brain_embed_update.py` — the freshness flag then shows live in `brain_ask`.

### Frontmatter template
`vault-conventions.md` → "AI conversation" is the single source of truth for the template (don't duplicate it here).

---

## Nexus distilled corpus (02-Decisions / 03-Insights / 05-Resources)

**Source:** nexus-ai-chat-importer plugin distilling ChatGPT conversations  
**Provenance:** `origin: anton` (distilled from Anton's own conversations) · `authored_by: claude-cowork` (already set)  
**Target folders:** vault's 02-Decisions, 03-Insights, 05-Resources

Files already have: `type:`, `domain:`, `concepts:` list, `authored_by:`.  
Files lack: `origin:`, `concept:` wikilink.

### Integration approach

Script: `integrate_distilled.py`

```python
DOMAIN_CONCEPT = {
    'Portugal': 'concept-place-livability',
    'Construction': 'concept-construction-renovation',
    'Cars': 'concept-cars',
    'Business-Finance': 'concept-personal-finance',
    'Family-Kids': 'concept-parenting',
    'Biohacking': 'concept-biohacking-nutrition',
    'Medicine': 'concept-medicine-health',
    'AI-Tech': 'concept-ai-agents',
    'Translation': 'concept-language-learning',
    'Crypto-Web3': 'concept-blockchain',
    'Personal-Growth': 'concept-life-observations',
    'General-Tech': 'concept-tech-tools',
}
# 1. Add origin: anton
# 2. Set concept: "[[DOMAIN_CONCEPT[domain]]]"
# 3. Match concepts: list entries → existing concept files for secondaries
# 4. Strip ghost links in body
```

One script run → 906 files integrated (99% coverage achieved).

---

## External transcript splits (podcast / YouTube episodes)

**Source:** nexus-ai-chat-importer splitting large transcripts by token limit  
**Provenance:** `origin: external` · `authored_by: ai` (AI transcription)  
**Exception:** dialogue subfolders (dialogues_<account>_*) → `origin: mixed` · `authored_by: hybrid`  
**Target folder:** stays in `01-Conversations/{source-name}/`

Files have: `type: transcript-episode`, `parent: name [internal]`, no origin/concept.

### Integration approach

Script: `integrate_transcripts.py` — SUBFOLDER_MAP:

```python
# Key mappings (extend as new transcript sources appear)
{
    'Huberman*':           ('concept-biohacking-nutrition', 'external', 'ai'),
    'beloveshkin*':        ('concept-biomarkers',           'external', 'ai'),
    'vita dao':            ('concept-vitadao',              'external', 'ai'),
    'Lifespan Research*':  ('concept-longevity',            'external', 'ai'),
    'Randall Carlson*':    ('concept-alternative-history',  'external', 'ai'),
    'lobster*':            ('concept-dao',                  'external', 'ai'),
    'dialogues_*':         ('concept-life-observations',    'mixed',    'hybrid'),
}
# 60+ subfolders handled with heuristic fallbacks
```

### Author backfill — name the SPECIFIC author on every external transcript ⭐ (2026-06-09)

The adapters above set `origin: external` + `authored_by: ai` but historically left the **specific author/channel unnamed** (`author:` absent, `people: []`). Per provenance-attribute-real-author [internal] every external source MUST name its real creator. Token-optimal backfill (proven on **2,627 notes → 89 series**, ~0 extra LLM):

1. **Collapse to UNIQUE SERIES, not per-note** (`extract_series.py`): group all `origin: external` transcript notes by `parent:`/title → the ~80–150 distinct shows. Resolve the author ONCE per series, never per note (≈30× fewer tokens than an agent-per-file fan-out).
2. **Curated author map, 0 agents** (`stamp_authors.py`): prefix/exact rule-map (`Huberman*`→Andrew Huberman, `beloveshkin*`→Беловешкин, `lobster*`→LobsterDAO, Randall Carlson, Joe Rogan, Brien Foerster, Mauro Biglino, VitaDAO…) stamps `author:` from the short series list by knowledge. Unknown/risky → `author_status: needs-review` (**NEVER guess**).
3. **Resolve residual from CONTENT first, then 1 web-verify** (`stamp_authors2.py`): for needs-review series read ONE episode body — transcripts usually self-name ("смотрите мой канал", host name); web-verify only the few still-ambiguous English names. **Wrong-direction guard:** a folder like `my lunch Break` may be Anton's OWN — read & confirm before labelling external (it was an external YouTube show; `chat_-…` are multi-author group chats; `posts tg` = a multi-channel TG posts export).
4. **Fix the authorship axis**: on `transcript-episode`/`transcription`, `authored_by: ai → human` + add `transcribed_by: ai` (words are the blogger's; AI only transcribed). Parent/index notes keep their generator in `authored_by`.
5. Cyrillic-mangled titles (bad import) → `author: "External source (title corrupted)"` + `author_status: title-corrupted`. Multi-author group-chat exports → `author: "Telegram group chat (multi-author …)"`.

Scripts in `$IMPORTS_ROOT\`: `extract_series.py` → `stamp_authors.py` → `stamp_authors2.py` (dry-run by default, `APPLY=1`, idempotent). Run after every new transcript import.

---

## WhatsApp TXT export (template — not yet implemented)

**Source:** WhatsApp → Export Chat → Without Media → `.txt`  
**Provenance:** Depends on chat — ASK Anton  
**Target folder:** `01-Conversations/WhatsApp/{chat-name}/`

### Input format

```
MM/DD/YY, HH:MM – Sender Name: message text
MM/DD/YY, HH:MM – Sender Name: <Media omitted>
```

### Parse pattern

```python
LINE_RE = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2})\s*[–-]\s*([^:]+):\s*(.+)$')
# Filter: skip '<Media omitted>', system messages
# Sessionize: same 30-min gap rule as Telegram
# Dedup: same content-hash approach
```

### Triage notes
WhatsApp groups often have high noise ratio. Triage thresholds may need adjustment.

---

## Apple Notes / Bear / Notion export ⭐ (DONE 2026-06-12 — 649 notes)

**Source:** Apple Notes (iCloud) export from Anton's Mac. The Mac side ships a clean bundle: `notes_export.json` (self-contained — every note's full `markdown` + `apple_note_id` + `created`/`modified` + `attachments[]`), a `Notes/` folder (one `.md` each, first line = `# title`), an `attachments/` folder, plus `README_FOR_CLAUDE.md` + `_INDEX.md`. **Always read the README first — it documents the exact schema.**
**Provenance:** default `origin: anton` · `authored_by: human` — BUT a real fraction is pasted external content (articles, others' bios, lecture conspects, NOAH-team announcements) → those flip to `origin: external` + `author:`. Adjudicate per-note, don't blanket-stamp anton.
**Target folder:** `01-Conversations/Apple-Notes/` (`notes/`, `attachments/`, `_Apple-Notes-MOC.md`).

### The proven pipeline (scripts in `$IMPORTS_ROOT\apple-notes\`)
JSON-first, **0 tokens until triage**: `analyze.py` (stats + content-hash dups + secret-regex + vault collision + Latin date-slug) → `prep_batches.py` (26×25-note batches) → **triage workflow** (per-note category/origin/concept/value/persons/is_secret + concept-synthesis + adversarial verify) → `gen_staging.py` (frontmatter + attachments + MOC + junk-ledger; secrets → `_quarantine\` OUTSIDE vault) → `validate_staging.py` (0 broken links) → move → `validate_vault.py`. Result: 614 notes + 155 attachments + 4 new concepts; 22 secrets quarantined, 4 dups + 9 junk collapsed.

### ⚠️ GOTCHA 1 — exporter explodes STYLED text into heading fragments
Apple-Notes styling (bold/size) export-corrupts a run like `Мои экзиты` into `# М`\n`# ои`\n`# эк`\n`# зиты` — tiny `#` lines, sometimes losing the word-boundary space at split points. Hit **53/649** notes. Detect: ≥3 consecutive heading lines with ≥2 "fragment" qualities (len≤4 or lowercase-start). Repair = `extract_mangled.py` → LLM rewrite fleet (char-preserving) → `demangle_apply.py` (deterministic run-collapse fallback: join fragments, empty-`#`=para-break, prefix `# `). **Verifier is the safety net:** accept a repair ONLY if `canon(repaired)==canon(original)` where `canon = strip(whitespace + '#')` AND the wikilink set is unchanged — guarantees zero char loss.
### ⚠️ GOTCHA 2 — truncated `title:` is NOT ground-truth
Exported `title` is cut to ~80 chars with a trailing `…`. Do NOT substitute it for a reconstructed first line — you'll drop the chars past the cut (fails the char-check). Use clean `title` only when it doesn't end with `…` AND char-matches the collapsed fragments; else keep the fragments verbatim.
### ⚠️ GOTCHA 3 — secrets hide in personal notes
Apple Notes is where people stash passwords/passports/cards/seed-phrases. Regex flags are NOISY (`strong-token` ≈ mostly product names) — adjudicate by READING the full original. A verifier lens found **6 real secrets the regex missed** (seed-phrases, TeamViewer creds, full card+CVV) and cleared 34 false positives. Secrets NEVER enter the vault → `_quarantine\` only.

### Key difference vs chat exports
Notes are **already atomic** — no sessionizing. Focus on classification, concept mapping, cross-linking, and the 3 gotchas above.

---

## Voice notes (individual `.m4a` → Whisper transcription)

**Source:** voice memos transcribed by Whisper or assistant  
**Provenance:** `origin: anton` · `authored_by: human` (Whisper transcribed ≠ Whisper authored)  
**Target folder:** `01-Conversations/Voice/`

### Key rule

`transcribed_by: whisper` goes in frontmatter. `authored_by` stays `human` — the transcription tool is NOT the author. Anton spoke the words → Anton is the author.

### Whisper artifact handling

Common artifacts: `[МУЗЫКА]`, `[АПЛОДИСМЕНТЫ]`, `[Смех]`, repeated phrases from audio glitches, abrupt cuts. Strip markers to frontmatter (`has_artifacts: true`), flag in `transcription_quality:`.

---

## Telegram — FAAA CRM call-log (sales follow-ups → lead cards) ⭐

**Source:** Telegram JSON export (`result.json`; the HTML pages are the same data — JSON parses far cleaner) of Anton's sales follow-up channel **"CALLS … FAAA follow up MAIN (ТОЛЬКО итоги звонков)"**. ~27k messages, 2022→2026. NOT a knowledge chat — it's a **CRM dealflow log**: each substantive message is a structured call summary written by the sales team after a Zoom/Meet call with an external lead.
**Provenance:** `origin: mixed` (Anton's team ↔ external leads), `authored_by: hybrid` (team-drafted summaries + LLM synthesis). **NOT `#anton-original`** — operational records of other people's pitches, not Anton's own thinking.
**Scripts (the "updated import script", all in `$IMPORTS_ROOT\`):** `parse_faaa.py` → `cluster_faaa.py` → `build_faaa_batches.py` → **synthesis workflow** → `render_cards.py` → `build_ledgers.py` → `build_crm_moc.py` → `validate_faaa.py`. Checkpoints: `faaa-archive.jsonl`, `faaa-leads.json`, `faaa/batches/*`, `faaa/synth/*`, `faaa/{call2slug,final_slugs,leads_index}.json`.

### The FA (call-summary) schema
Tolerant Cyrillic regexes (spacing/colon optional, allow leading `N.`):
`Время` · `Группа в ТГ` · `Лички тех кто будет на звонке:` (lead @handles) · `Общение велось:` (which Anton acct) · `Тема:` · `Название звонка:` (`<Lead> and Platinum Dev Incubator`) · bullets (lead profile) · `Договорились:`/`Мы:`/`Они:`/`От нас:` · `Питчил(а/и):` (team). Status prefixes: `ЛИД НЕ ПРИШЁЛ`, `ПОПРОСИЛИ ПЕРЕБУКАТЬ`, `!!!`/`❗️`.

**⚠️ THE FORMAT CHANGES MID-CORPUS — detect BOTH.** From ~mid-2024 the team switched to an **English "Short follow-up"** template with NONE of the Russian markers above: first line = call name (`✨ Tony, VC & Ai incubator and <Lead>`), then `🙌 Thank you for the call!` / `Short follow-up👣:` / `Participants: @lead_handle, Platinum VC: ...` (lead handle here, not in `Лички`) / lead bullets / `about VC.Platinum.fund` (our pitch boilerplate — ignore as lead info) / `Promised 🤝` (= agreements). **A detector that only knows the Russian schema silently drops the entire 2024H2→2026 era as `longtext` — the most recent, most valuable leads.** Always sanity-check `call_summary` counts **by year** after parsing; a year reading 0 means a format you haven't handled. `is_eng_fa = "thank you for the call" in low or "short follow-up" in low or ("participants:" in low and ("promised" in low or "platinum.fund" in low))`; pull the lead handle from the `Participants:` line.

### Triage (of ~27k): `call_summary` (RU schema OR English Short-follow-up) ≈ **11.9k** · `media_only` (<10 ch, voice/photo not exported) ≈ 12k · `longtext`/`fragment` (chatter, process) ≈ 3k · `noise`/`service`. (Russian-only detection found just 9.6k and missed 2024H2→2026 entirely.)

### Two-layer output (Anton's choice — mirrors Assistants-Ops)
- **Layer 1 — lead cards:** `04-Projects/crypto/Platinum-CRM/leads/<year>/<slug>.md`, **one per unique lead**, `type: crm-lead`. Synthesis header (status/company/role/what_they_want/offered/agreements/outcome/2-4-sent summary/tags) **+ verbatim chronological call log (the single raw copy of call text)**. MOC `_Platinum-CRM-MOC.md` (status board / category / by-company / top-touched / dataview).
- **Layer 2 — archive:** `01-Conversations/Telegram/FAAA-Follow-ups/sessions/Sessions-YYYY-MM-DD.md` — every message day-bucketed; **call msgs = dated one-liner linking to the lead card (no text re-embed)**, chatter/process/media verbatim (their only copy). MOC `_FAAA-Follow-ups-MOC.md`. So every message's text exists exactly once.
- Graph hub: `concept-platinum-crm` — every card's `concept:` + both MOCs link it, so the import is a connected component, not an island.

### Lead identity resolution (THE hard part — dedup by @handle + name)
A lead recurs across many follow-ups; collapsing them is the whole point. Union-find:
- **Union by Telegram-TYPED `@mention` on the Лички line** (strong, exact). **Do NOT regex `@\w+` over text** — it scrapes email domains (`@gmail`,`@yahoo`) and fused 100s of unrelated leads into one fake card. Typed `mention` entities exclude emails.
- **Union by full (multi-token) normalized name** only. Single first-names ("Alex") are NOT name-merged (would fuse different people) — they join only via a shared handle.
- **Exclude non-identifying handles:** team/our-side (`@platinumvc*`,`@antondz*`,`@tonyssd`,`@manizha_business`,`@SmartContractArchitect`…) **and** frequent co-attendees (advisors who join many calls).
- **People migrate sides over time.** Azam Shaghaghi is a *lead* in 2022 (clusters by `@Azaam8`) but a *Platinum team member* by 2025 ("Platinum VC: Azam"). Add such transitioned principals (azam, manizha, malika) to `is_our_side()` so later-era call names attribute to the real external lead (taken from the `Participants:` handle), not to the now-teammate.
- Yield: ~11.9k call summaries → **~8.6k unique leads** (~1.8k multi-touch). Final import (2026-05-31): **8 638 lead cards** in `04-Projects/crypto/Platinum-CRM/leads/<year>/` (2022:2065·2023:4292·2024:1424·2025:822·2026:35), **1 230 day-ledgers**, 0 broken links over 40 485 wikilinks.

### Lead-name extraction — the call-name format DRIFTS over the years
Our-side label evolved: `Platinum Dev Incubator (Rust & Solidity)` → `B2B Platinum Department` → `Anton from Platinum` → `✨ Anton from Platinum VC` → `Tony, VC & Ai incubator` → `Tony + Malika`. So **split the call name on connectors** (`and`/`&`/`<>`/`x`/`et`/`+`/`between`/`with`) and **drop every chunk that is our-side** (`is_our_side()`: platinum/incubator/b2b/rust&solidity/`vc…ai`, or our principals Anton-Dziatkovskii/Tony/Malika — NOT a lead coincidentally named "Anton X"); the rest is the lead. Drop pure wrappers (`60 Minute Meeting`,`Intro Call`,`Discovery Call`) and generic non-names; null-out bad results so they fall back to handle/group instead of polluting clusters. Pitfall: alternation `(min|minute)` matches `min` inside `minute` → garbage shared name "ute meeting" name-merged 111 calls; order longest-first. Display name = best-scoring variant (penalize `@`, digits, wrapper words, length); the **LLM sets the authoritative name** — finalize slug at render and emit `call2slug` for the ledger pass so links stay valid.

### Batched LLM synthesis (Anton: "делать всё батчами")
`build_faaa_batches.py` packs leads + full chronological call text into ~215 batches (~45 calls each). A **workflow** fans out one **Sonnet** `general-purpose` agent per batch (cost/quality sweet spot at this volume): synthesizes each lead grounded ONLY in its calls (→ `{lead_id,name,company,role,country,category,status,what_they_do,what_they_want,what_we_offered,agreements,outcome,summary,tags,lang}`), **writes `faaa/synth/batch_NNNN.json`**, returns a status. Cached-skip (Read output first → "cached") = resumable. `render_cards.py` merges synth + deterministic fields (graceful fallback if a batch is missing). **Test ONE batch via the Agent tool before launching the full fan-out.**
**Incremental re-synth (don't re-pay for unchanged leads).** When you re-parse and re-cluster (e.g. after adding the English-format detector), back up the prior `faaa-leads.json`→`-prev.json` first; in `build_faaa_batches.py` reuse a prior synth obj for any lead whose **call-id SET is unchanged** (`frozenset(call_ids)` signature), write those to `synth2/reused.json`, and batch ONLY the new/changed leads. Real run: 8 638 leads = **6 100 reused + 2 538 re-synthesized** (88 batches) — ~70 % cost saved vs a full re-run.
**Background workflows can die (laptop sleep / host recycle).** A long idle gap killed the v2 run at 0/88 with the task vanished from the registry. Re-launch via `{scriptPath}` — cached-skip makes it idempotent. After launching, arm a tiny background liveness watcher (`until ls synth2/batch_* | wc -l ≥ 3`) so you catch a re-death early instead of assuming progress.

### Incremental re-import
Re-run `parse_faaa.py` (globs the new export), dedup new call rows by content-hash, cluster — union into EXISTING leads by handle/name (check `final_slugs.json` + vault `lead_id` frontmatter), append new calls to existing cards (+ new cards for new leads), regenerate touched ledger days. `import_batch:<date>` in frontmatter. Always dedup leads against existing cards first (Anton's standing rule).

### Pitfalls (learned the hard way)
- **Email-domain handles** (`@gmail`) from naive `@\w+` regex → catastrophic over-merge. Typed mentions only.
- **Multi-attendee Лички lines** (lead + advisor) → a recurring advisor handle fuses unrelated leads. Exclude high-freq co-attendee handles.
- **`min`/`minute` regex order** → garbage names that name-merge. Belt-and-suspenders: clusterer refuses to union by generic/ultra-frequent (`>15`) names.
- **Display ≠ truth:** deterministic display name is often a co-attendee or garbled chunk ("Roy"→Azam Shaghaghi); trust the LLM's grounded `name`.
- **Silent format drift = silent data loss.** The mid-2024 switch to the English template made the detector return 0 call summaries for 2025–26 — invisible unless you tally `call_summary` **by year**. Always print the per-year class histogram before declaring coverage; a 0 means an unhandled format, not an empty year.

---

## Telegram — Personal DMs (1:1 private chats → network of person-notes) ⭐

**Source:** a **pre-parsed Markdown** export of Anton's *private 1:1 Telegram DMs* (`account-<id>-<YEAR>.md`, one file per calendar year). Header per dialog `## Dialog: <Name> (@handle)` + `- Lead Telegram ID:` then messages `#### <ISO date+time> UTC · Account|Lead · <@handle>` with `> `-quoted bodies (some wrapped in ```text fences``, some carry `*Edited: …*`). NOT a group/broadcast stream — it is **452 separate two-party conversations with 346 distinct people** (ICO era: MicroMoney/AMM, Ledger Pay, early Platinum). Imported full span **2016–2026 = 570k msgs / 11,820 contacts** (two passes: 2016–2018, then 2019–2026 incrementally).
**Provenance:** `origin: mixed` (Anton + each contact). Conversation archive `authored_by: human` (pre-2023, real people typing). Person-notes `authored_by: hybrid` + `summarized_by: claude-cowork` (LLM-synthesised) — **NOT `#anton-original`** (mixed dialogue). Anton's own voice is preserved verbatim in the archive (🟢 lines) and surfaced as `notable_anton_reasoning` in person-notes.
**Scripts (all in `$IMPORTS_ROOT\`):** `parse_dm.py` → `fingerprint_vault.py` + `match_people.py` → `generate_dm_archive.py` (Layer 2) → `build_synth_batches.py` → **batched subagents** (Agent tool, `general-purpose`+`sonnet`, ~14 people/batch) → `aggregate_synth.py` (validate + authoritative clean slugs) → `generate_person_notes.py` (Layer 1 + concept/tag injection) → `build_dm_moc.py` → `validate_staging.py` → `move_to_vault.py` (**SELECTIVE**) → `inject_concept_backlinks.py`. Checkpoints: `dm-archive.jsonl`, `dm-index.json`, `dm-person-targets.json`, `dm-folderslug.json`/`dm-personslug.json`, `dm/synth_batches/*` + `dm/synth_out/*`, `dm-synth-all.json`, `dm-files-index.json`, `dm-concept-index.json`.

### The prize is the NETWORK (Anton's choice: "сеть в фокусе")
Unlike the Bible (Assistants-Ops) / purchase-ledger (Покупки) / lead-card (FAAA) chats, the value here is **(a) rich `person-*` notes = Anton's ICO-era network** and **(b) a searchable per-person archive**, with only **light concept tags** (no separate atomic knowledge-notes). Ask Anton three levers before generating: person-note threshold (default **≥20 msgs** → person note; archive built for ALL), extraction depth (network-focus vs full-extraction vs archive-only), privacy (import-all vs `#private` tag vs hand-pick).

### Two-layer output
- **Layer 2 — archive (deterministic):** `01-Conversations/Telegram/Personal-DMs/conversations/<slug>/<slug>-<year>[-MM].md` — verbatim, day-grouped (`## YYYY-MM` / `### date`), role-iconed (🟢 Anton / ⚪ contact). One file per person-year; **month-split when a person-year > ~1800 msgs**. `person:` frontmatter links the note (only when one exists).
- **Layer 1 — network (LLM):** `07-People/person-<slug>.md` — `who/org/role/location`, `## Что делали вместе`, `## Ключевые треды`, `## Переписка` (links every year/month file), `## Концепты`, `## См. также` (org-mates → person↔person edges). Concept **tags + `concept:`** injected into each conversation. `_Personal-DMs-MOC.md` = stats, top-contacts table, by-relationship groups, concept index, org rosters, minor-contacts (archive-only) list, by-year. Concept→person rosters appended back into the referenced `06-Concepts/*` files (rule 6).

### Identity & slugs (the fiddly part)
- **Telegram doubles Cyrillic+Latin name tokens** (`Сергей Sergey Походенко Pokhodenko Pohodrnko`). Deterministic slugify makes ugly slugs → **let the LLM return a cleaned `display_name`, then regenerate the authoritative slug from it** (collision-safe vs existing 07-People + each other) and regenerate the archive with that slug.
- **Dedup people vs existing 07-People FIRST** (standing rule): match by exact `@handle` or **full multi-token** normalised name only — never a bare first-name (would fuse different people, and `person-pavel` ≠ "Pavel Bogush"). First run: 0 collisions (the 48 existing notes are biohacking/celebrity, disjoint from the ICO contacts).
- **Anonymous contacts** (export name literally "Lead") → slug `lead-<tgid>`, `identified: false`, ⚠️ banner; the subagent often **recovers the real name from in-chat signatures** — let it.

### Concepts — bridge, don't island
The ICO era maps almost entirely onto **existing** concepts (`MicroMoney`, `ICO`, `токеномика`, `concept-blockchain`, `-smart-contracts`, `-crypto-project-building`, `-startup-fundraising`, `-investor-taxonomy`, `-crypto-influencer-marketing`, `KYC-AML`, `Binance/Coinbase/Liquid/OKX/QDAO/Wintermute`, …). Tell subagents to PREFER existing + propose `NEW:` only when nothing fits. First run: **0 NEW proposals**; one recurring theme (`exchange-listing`, 15 votes) promoted to a single new stub `concept-crypto-exchange-listing` via an alias map.

### Pitfalls (learned the hard way)
- **Staging is SHARED across imports.** `staging/06-Concepts`, `07-People`, `01-Conversations` hold leftovers from prior imports → **never `cp -r staging/`**. `move_to_vault.py` copies an **explicit file list** (the Personal-DMs tree + exactly my 223 person-slugs + my 1 new concept), refuses to clobber, and dry-runs first.
- **Subagents miscount and occasionally drop 1–2 records** (their "done N" is unreliable). Always **assert output pids == input pids per batch** and re-synthesise the missing as a patch batch (`batch_0017`).
- **`concept_index` stores person-slugs, not pids** — keep a `slug→pid` map for backlinks.
- **Inject conversation tags only on a FRESH archive** (the generator wipes `ROOT`); the regex tag-merge is not idempotent if run twice over the same files.
- **Windows/Cyrillic:** never `print()` Cyrillic (cp1252) — write UTF-8 files, keep stdout ASCII.

### Incremental re-import (new years) — PROVEN at 2016→2026 scale
Done once already: 2016–2018 first (346 people / 116k msgs), then 2019–2026 folded in → **full span 570,603 msgs · 11,820 contacts · 1,348 person-notes · 9,350 archive files · 0 broken links**. The per-era split matters: 2019–2021 hold the heavy threads; 2023–2026 are outreach-heavy (2025 alone ≈6,300 contacts averaging ~5 msgs). Anton picks the thresholds each time — last run **notes ≥20, archive ≥5** (`<5` = index-only, no file). Steps:
1. `parse_dm.py` **globs ALL** `account-<id>-*.md` (keys people by stable `tg_id`); regenerate `dm-archive.jsonl` + `dm-index.json`.
2. `fingerprint_vault.py` (now sees prior DM notes) → `plan_incremental.py`: builds `tg_id→existing-slug` from vault frontmatter so continuing contacts **reuse their note/folder slug** (no dupes); emits `dm-synth-needed.json` = NEW notes + existing notes that **grew ≥20 msgs since their last year**; the rest **reuse the prior `dm-synth-all.json`** (cheap).
3. `build_synth_batches.py` (→ `synth_batches2/`, fresh dir so it doesn't collide with the first run) → batched subagents (~16/batch; ~81 batches at this scale, run in waves) → `aggregate_inc.py` validates pids/batch, merges reuse+new, assigns **stable slugs** (existing reuse; new clean; archive-only deterministic).
4. `generate_dm_archive.py` (skips `<ARCH_THR`) → `generate_person_notes.py` → `build_dm_moc.py` (splits the long 5–19-msg roster into `_Personal-DMs-Minor-Contacts.md`).
5. `validate_dm.py` (scoped to MY files — staging is shared!) must be 0 broken → `move_inc.py` (overwrites only my prior import; **prunes orphaned conversation files** whose slug shifted in the larger collision pool or who fell below `ARCH_THR`) → `inject_concept_backlinks.py`. `import_batch: <date>` stamps everything. (The `telegram-reimport` skill doesn't know this chat — use this adapter.)

### Verifying coverage
Parser row-count == Σ conversation `msg_count`. For a page: every message text is a substring of its `<slug>-<period>.md` after stripping the leading `> ` blockquote markers (same gotcha as Assistants-Ops). Person-note count == people with `total ≥ threshold`.

---

## Platinum CRM entity CSV (the entity-DB sibling of FAAA) ⭐

**Source:** `crm_entities_export.csv` — a full dump of Anton's Telegram-native Platinum CRM **entity database** (~123 538 rows, ~255 MB). NOT a chat export — it's the structured contact DB: per-entity `telegram_id`, qualification `tags`/`tags_str` (319 distinct: INVESTOR/VC, Project/Founder, KOL, B2B, "Not investor"…), operator `assigned`, `bio`, `username`, `created_at`/`last_activity_date`, and **embedded DM history in the `chats` column (≈65 % of file = JSON arrays of `last_messages`)**. 102.6k users · 20.9k groups; ~90k live; `telegram_id` is a clean unique key. ~11 schema columns export empty (temperature, lang, messages_count, last_message_date…) — engagement metrics lossy; ask Anton to re-export with them if needed.
**Provenance:** `origin: mixed` · `authored_by: hybrid` · **never `#anton-original`** (operational records of other people's pitches + private chat).
**Relationship to FAAA:** this CSV and the FAAA call-log are **two projections of the same CRM** → unify into ONE layer keyed by `telegram_id`/`@handle`. FAAA = "what happened on calls"; CSV = "who they are, how qualified, DM history". Run FAAA FIRST (builds `04-Projects/crypto/Platinum-CRM/leads/`); this adapter enriches those cards + adds DM-only leads.

### Pipeline (proven 2026-06; end-state 14 108 cards, 0 broken links)
1. **Split** (Python, `csv.field_size_limit(1<<30)`, UTF-8-sig) → `$USERPROFILE\!CLAUDE-HP17 May26\crm_export\`: `contacts.csv` (all cols minus `chats`), `chats.jsonl` (DM thread/entity), `leads_clean.csv`, `operators.csv`, `enrichment.jsonl` (handle-keyed: tier/tags/operators/bio/dm_msgs/dm_two_way), `new_leads.json` (investor/founder w/ two-way DM, no call).
2. **Enrich existing FAAA cards** — append a `## CRM-данные` body section + `crm_tier`/`crm_telegram_id`/`dm_msgs`/`crm_operators` frontmatter, via **4 ordered join passes, each guarded "match only if EXACTLY ONE candidate"**: (a) `@handle` (frontmatter `handles:`); (b) `telegram_id`; (c) **unique normalized full-name** (≥2 tokens; ambiguous skipped → `crm_match: name`); (d) **non-team `@handle` from the call-log BODY** (`recover_body_handle.py`; EXCLUDE team/co-attendee handles by ≥12-card cross-frequency + seeds `@platinumvc*`/`@antondz*`/`@tonyssd`/`@azam*` → `crm_match: body-handle`). Ceiling ≈ **77.5 %** (the rest simply aren't in the CSV). Idempotent: skip if `## CRM-данные` present; add a frontmatter key only `if "key:" not in fm`.
3. **DM-only leads** (`new_leads.json`) → `build_dm_batches.py` (join `chats.jsonl`, ≤30 msgs/lead, ~45/batch) → **background `Workflow` "platinum-dm-synth"** (1 Sonnet agent/batch reads its batch file, writes `faaa/dm_synth/batch_NNNN.json`, cache-skips existing → **resumable**; bg run stalls on machine-sleep → re-launch `Workflow({scriptPath, resumeFromRunId})`) → `render_dm_cards.py` (`source: telegram-dm`, slug-dedup vs FAAA `leads/`, id `dm-<tid>`, embeds ≤8-msg verbatim thread).
4. **Metadata backfill** — `crm_tier` from `category` then from frontmatter `tags` (→100 %); keep `origin: mixed`.
5. **07-People promotion** (`render_people_full.py`) — Anton's rule: every lead with **≥1 call (incl. no-show) OR ≥20 DM msgs** → a `person-*` note with `org` (=company), role, tier, status, `contact_type: work-lead|personal-friend` (personal = "Personal contact"/"IRL" tag), `lead_card`. New → create; existing Personal-DM note → **append** a "## Platinum CRM" block (never clobber). `_People-MOC` gets a Dataview section.
6. **Analytics** → `_Dashboards\Platinum-CRM-Dashboard.html` (`build_crm_dashboard.py`), `_Platinum-CRM-Tag-Taxonomy.md` (`build_tag_taxonomy.py` + `merge_tags.py` for real dupes), `_Platinum-CRM-Hotlist.md` (`build_hotlist.py`, warm-but-quiet deals).
7. **MOC + hub** `_Platinum-CRM-MOC.md` + `concept-platinum-crm` (link `concept-blockchain`). Then `brain_embed_update.py` (incremental reindex).

### Gotchas (learned the hard way 2026-06)
- **ONE run at a time.** Two concurrent runs (shared session-id) re-rendered `leads/` repeatedly (6 778→…→14 108) + made a duplicate DM set in a parallel `leads-dm/`. A re-render **wipes body `## CRM-данные`** (regenerated from synth) → re-run pass 2 after any FAAA re-render. People→card links ride on `leads/` slugs → re-verify after a rebuild.
- **`fv()` can't parse a YAML list** — `handles: ["@x"]` read by a scalar regex grabs `[` (put `telegram: "["` on 3 790 notes once); parse the first list element explicitly.
- **Team/co-attendee handle contamination**: the call log names BOTH the lead and the Platinum operator (operator handles) + recurring advisors — exclude before ANY handle match or you glue the team's record onto a lead.
- **Don't fuzzy-match single-token / no-handle names** — false positive = wrong qualification on a card; stop at the unique-exact ceiling.
- Windows/Cyrillic: never `print()` Cyrillic (cp1252) → write UTF-8 files; `find -delete` on a vault folder can hang (indexer) → PowerShell `Move-Item` the folder out instead.

### Incremental re-import (fresh CSV export)
Re-split → re-run the 4 enrich passes (idempotent) → `build_dm_batches.py` for `new_leads` not already carded → resume `platinum-dm-synth` (cache-skips) → `render_dm_cards.py` → backfill tier → `render_people_full.py` (new only) → rebuild dashboard/taxonomy/hotlist/MOC → `brain_embed_update.py`. **A bigger re-export that finally includes the ~2.5k called-but-not-entity leads is the only way past the 77.5 % ceiling.** Stamp `import_batch: <date>`.

---

## Quick decision table: which adapter to use?

| Input | Adapter | Script |
|---|---|---|
| **CRM entity DB dump** `crm_entities_export.csv` (tags/handles/`chats` col) | **Platinum CRM entity CSV** | split + 4 enrich passes + `platinum-dm-synth` workflow |
| Single `.md` with `## N. Month DD, YYYY` posts | Facebook | `parse_facebook.py` |
| Telegram **CRM/sales call-log** (итоги звонков, leads) | FAAA CRM | `parse_faaa.py` (+ synthesis workflow) |
| Telegram **private 1:1 DMs** (`account-<id>-<year>.md`, many people) | Personal DMs | `parse_dm.py` (+ person-synth subagents) |
| Telegram export **with `result.json`** | (prefer JSON; pick the chat-specific adapter below) | `parse_pokupki.py` (model) |
| `messages.html` Telegram export (no JSON) | Telegram HTML | `parse_telegram.py` |
| Telegram boss+assistants **purchases** chat | Покупки / Purchases | `parse_pokupki.py` |
| Telegram boss+assistants **ops/rules** chat | Assistants-Ops | `parse_assistants_ops.py` |
| `conversations.json` ChatGPT export | ChatGPT JSON | `integrate_chatgpt.py` |
| AI chat **single transcript** (Claude/ChatGPT, "это мои мысли") | AI conversation | `ingest_ai_conversation.py` |
| Vault 02-Decisions/03-Insights/05-Resources without concept: | Nexus distilled | `integrate_distilled.py` |
| `type: transcript-episode` files without origin: | Transcript splits | `integrate_transcripts.py` |
| WhatsApp `.txt` export | WhatsApp TXT | (template) |
| Folder of individual `.txt` / `.md` notes | Apple Notes | inline or batch |
| Voice `.m4a` (already transcribed) | Voice notes | inline |
| Personal **Google Drive mirror** (`source: gdrive-personal-mirror`) | GDrive Personal | classify origin by SUBFOLDER — see below |

---

## GDrive Personal mirror (`source: gdrive-personal-mirror` / `gdrive-personal-cloud`)

**Input:** Anton's whole personal Google Drive, mirrored to `05-Resources/GDrive-Personal/`
(docx/gdoc/gsheet → markdown). Big archive subtrees were moved to `_originals/gdrive-personal-archive/`.

**⚠️ The provenance trap (caught + fixed 2026-06-13 — memory `gdrive-personal-mirror-provenance-bug`):**
the first importer stamped **`origin: anton-archive` on EVERY file** regardless of real authorship —
including Ray Bradbury stories, candidate CVs, employee NDAs. This **violates the standing rule
`provenance-attribute-real-author`** ("source NOT Anton's → name the real author, never hang it on him").
The principle existed; the **per-source machine spec did not** → the bug. This adapter is that spec.

**Provenance = classify by SUBFOLDER + filename, NEVER blanket-stamp `anton`.** Apply in priority order
(first match wins). This is exactly what `$IMPORTS_ROOT\gdrive-provenance\fix_gdrive_provenance.py`
(pass B) + `split_grey_zone_C.py` (pass C) encode — reuse them, don't re-derive:

| Signal (in source_path or filename) | origin | author |
|---|---|---|
| Ray Bradbury / `/Stories/(YYYY)` | `external` | `Ray Bradbury` |
| NDA / agreement / termination / trial period / passport / services agreement | `external` | `corporate` |
| `/Recruitment/`, `!Fired`, `Личные дела сотрудников` | `external` | `needs-review` |
| `writer_copywriter` / portfolio / work_samples | `external` | `needs-review` |
| "файл от <X>" / "от Дениса" | `external` | `needs-review` |
| PLATINUM FRAMEWORK, pitch docs (AAA/Palo Alto/Canton/L3 Swarm), "мысли по…", "резюме звонка", his name + CV | `anton` | — |
| visas / taxes / bank / KYC / invoices / rental / mortgage / purchase agreements | `personal-docs` | — |
| other projects' tokenomics (eesee/Dechat/Sidus/GotBit…) not Anton's | `external` | `needs-review` |
| genuinely ambiguous | `gdrive-personal-mixed` | — |

**Hard guards (both learned 2026-06-13):**
1. **Don't match "Anton" in the full disk path** — the vault root is `Anton-Knowledge\`, so check
   `source_path`, not the absolute path, when deciding "is this Anton's own".
2. **Don't classify candidate CVs by the word `cv`/`резюме` in a filename** — "резюме звонка" = a CALL
   SUMMARY (Anton's own), and the "SELF PRESENTING REZUMEs" folder holds his self-pitch material.
   Match by FOLDER (recruitment/fired/personnel), not the word.

Never touch our own `map-*` / "Карта папки" navigation files. Stamp `provenance_fixed:` / `provenance_split_c:` for traceability.
