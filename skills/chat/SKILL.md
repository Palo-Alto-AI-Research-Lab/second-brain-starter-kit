---
name: chat
description: >
  Find a Telegram CHAT/group/channel by name instantly — returns its telegram_id +
  t.me link from the local chats.db index (0 tokens, no live crawl). Trigger on
  "/chat <query>", "найди чат <X>", "id чата <X>", "дай ссылку на чат <X>", "в каком
  чате <...>", "find the <X> chat". Also answers "есть ли общие группы с <человеком/
  компанией>" (common_groups). This is the CHAT lane — distinct from /find (people via
  names.db) and /search (words inside chat messages) and /ask (semantic vault). When a
  chat isn't in the index, fall back to the live MCP search_dialogs / get_common_chats.
---

# /chat — instant Telegram chat lookup

Anton's pain: "найди чат X" used to mean 20–60 min crawling the live dialog list.
The chat's `telegram_id` + link already live in `chats.db` (built from the CRM
`tg_entities` dump — the same extraction the CRM's mtproto-api does). Look it up,
get the id, then operate the chat directly via the Telegram MCP.

## Rule (always)
When you need to act on "some chat by name", FIRST query the local index — never
crawl the live dialog list blind. Memory: [[telegram-chat-index]].

## Lookup — `find_chat.py`
```
cd $IMPORTS_ROOT/dialogs
PYTHONUTF8=1 python find_chat.py <query words>      # chats first, then people
PYTHONUTF8=1 python find_chat.py <query> --all      # include user DMs
PYTHONUTF8=1 python find_chat.py <query> --limit 80
```
Prints `[TYPE] telegram_id  name  t.me-link (+members)`. Matching reuses
`..\namesearch\name_norm.py` so wrong-layout (`dbrnjh`) / translit / typos still hit.
⚠️ ALWAYS `PYTHONUTF8=1` (else cp1252 crash). The `???` in console = ASCII echo only;
the DB stores proper UTF-8 — read it programmatically when you need the real title.

## "Common groups with a person / company" — `common_groups.py`
```
PYTHONUTF8=1 python common_groups.py @handle [--account corp_acct]
PYTHONUTF8=1 python common_groups.py "Firstname Lastname"
PYTHONUTF8=1 python common_groups.py <telegram_id>
```
Lists groups where one of OUR accounts sits alongside that person (ours/theirs +
which account + link). COVERAGE: rosters are full for small/curated groups, partial
for big public ones → for an authoritative per-person answer use the live MCP
`get_common_chats(user, account)`.

## Visual (Anton works by eye)
`_Dashboards\Telegram-Groups.html` — all chats, filter by account / ours-vs-theirs /
topic / value, search, per-group sub-classification.

## Freshness
`chats.db` backbone = CRM dump (refreshed by the `telegram-chat-index-refresh`
routine that appends live `list_chats` from Anton's accounts via `refresh_chats.py`).
If a brand-new chat is missing, run that refresh or fall back to live `search_dialogs`.

## Build / rebuild (rarely)
`build_chats_db.py` → index · `build_group_graph.py` → accounts/members/ours-theirs ·
`build_group_digest.py` + Sonnet classifier → `group_class` · `build_groups_dashboard.py`.
All under `$IMPORTS_ROOT/dialogs/`. See memory [[telegram-chat-index]].
