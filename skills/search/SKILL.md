---
name: search
description: Keyword/full-text search INSIDE all of Anton's conversations at once — Telegram, Facebook, ChatGPT, Claude, Apple-Notes, transcripts (~99k notes) — via the local BM25/FTS5 catalog `search_catalog.db`. 0 tokens, 0 GPU, 0 MCP, instant, with snippets + chat-title hits from dialogs.db. Trigger on "/search <words>", "найди в чатах <слова>", "поищи по перепискам", "search my chats", "где я писал про <X> в чатах", "в каком чате обсуждали <X>". This is the LEXICAL (exact-words) lane of the unified search layer (decision-unified-search-layer). DISTINCT from /ask (semantic MEANING over curated vault), /find (exact PERSON names over names.db), and brain_ask. Use /ask when the question is conceptual; use /search when looking for specific words/phrases that appear in chat text. Visual UI at http://127.0.0.1:8771 (search_server.py).
---

OBJECTIVE: Find specific words/phrases inside Anton's entire conversation corpus (~99k notes in `01-Conversations/**`) instantly and token-free, returning ranked snippets + which chats match by title. The lexical (BM25) lane of the unified search layer; the semantic (sqlite-vec + RRF) lane is added per the decision memo.

CONTEXT:
- Engine: `$IMPORTS_ROOT/search/search_catalog.db` (SQLite FTS5 over title+body of every conversation .md). Rebuilt by `build_catalog_fts.py` (derived, rebuildable artifact; ~3 min over 99k files).
- CLI: `python $IMPORTS_ROOT/search/search.py [--k N] [--chats] <query>` (UTF-8 output, real Cyrillic).
- Visual UI: `python $IMPORTS_ROOT/search/search_server.py` -> http://127.0.0.1:8771 (stdlib, no deps; autostart task keeps it alive).
- Title index reused: `..\dialogs\dialogs.db` (chat lookup by name).
- Canon: vault `02-Decisions\decision-unified-search-layer.md`; memory `unified-search-layer`. Token law: exact/SQL before BM25, BM25 before embeddings, retrieval before LLM.

STEPS:
1. Take Anton's query words. If he wants the visual interface, point him to http://127.0.0.1:8771 (start `search_server.py` if down).
2. Run: `python $IMPORTS_ROOT/search/search.py --k 15 --chats <query>` (add `--chats` when he's hunting for WHICH chat, not just content).
3. Read the ranked hits (lower bm25 score = more relevant) + snippets. Summarize the top matches for Anton with their file links and the chat/source they came from; offer to open or dig deeper.
4. If results look stale or a chat was recently imported, note that the catalog may need a rebuild (`build_catalog_fts.py`) — the weekly task handles this, or run it on demand.

CONSTRAINTS:
- Read-only over the catalog. Never write to the vault from this skill.
- Keep it token-cheap: this is deterministic search; do NOT pipe the whole corpus into an LLM. Only synthesize over the small returned hit set if asked.
- If the query is conceptual/"what do I think about X", prefer `/ask` (semantic) instead; if it's a person's name, prefer `/find`.

OUTPUT: A short ranked list of the best matches (title · source · date · snippet · file link) + any chat-title hits, then offer next step. End replies to Anton with a 🧒 Простыми словами recap.

RELATION (do not duplicate):
- /ask = semantic meaning (RAG e5+reranker) over curated vault. /find = exact person names (names.db). /search = exact words across ALL conversations (this).
- Vector/RRF/reranker lane + refresh routine: see memory `unified-search-layer` + decision note.
