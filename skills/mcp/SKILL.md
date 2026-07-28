---
name: mcp
description: Health-check Anton's connected MCP servers and discover/suggest new ones — the safe pre-flight before any integration work, plus a connector scout. Trigger on "/mcp", "/mcp health", "/mcp discover <need>", "проверь mcp", "какие mcp живы", "найди mcp для <X>", "подключить mcp", "health-check connectors", "what mcp servers do I have". READ-ONLY by default. Canon = memory [[mcp-health-check]]; standing rule: verify MCP health BEFORE starting integration work.
---

# /mcp — connector health-check & discovery

> 🧒 When reporting to Anton end with a child-simple "Простыми словами" recap. (memory `eli5-always`)

Two jobs: (1) **health** — is each MCP server alive & authorized? (2) **discover** — is there an MCP for a need Anton has? Full rules + the Telegram landmine = memory [[mcp-health-check]].

## health (READ-ONLY, safe order)
1. **In-session tool check FIRST (zero-risk)** — if a server's tools are present in the session, call ONE cheap read tool to confirm auth + liveness:
   - Telegram → `mcp__telegram__get_me` (expect Tony / @work_acct_a).
   - WhatsApp → `mcp__whatsapp__get_my_profile`. n8n → `mcp__n8n__n8n_health_check`. Google Drive/Calendar → a list call. MongoDB → `list-databases`.
   This uses the ALREADY-RUNNING server — no second client.
2. **Only if a server's tools are ABSENT** → it didn't load. Diagnose registration (`$USERPROFILE/.claude.json` mcpServers) + processes, then reconnect.
3. **⚠️ TELEGRAM LANDMINE:** do NOT run `claude mcp list` or spawn a Telethon client as a casual check — a 2nd client on the same StringSession triggers **AUTH_KEY_DUPLICATED** and logs the account out. Prefer in-session `get_me`. Use `claude mcp list` only when the server clearly isn't loaded.
4. **Zombie/leak watch (Windows):** stdio MCPs launched via `uv run`/`npx` can orphan → prefer the direct interpreter as `command`; the "Telegram MCP Janitor" task (every 15 min) kills true orphans (no live `claude.exe` ancestor). Don't guess a hung process — verify with facts (alive? progress mtime? elapsed?).

## discover
Use the registry tools: `mcp__mcp-registry__suggest_connectors` (for a stated need), `mcp__mcp-registry__search_mcp_registry`, `mcp__mcp-registry__list_connectors` (what's already available). Rank by: does it solve a REAL recurring need? subscription/local (free) over paid ([[prefer-included-limits-before-paid-api]])? does a stdio server risk Windows orphaning? Propose, don't auto-install — wiring a new server = Anton's call.

## Safety
- Health = read-only, run anytime (this is the standing pre-flight before Telegram/integration work).
- Reconnecting, editing `.claude.json`, installing a new server = pause + confirm.

## Output
Per-server 🟢/🔴 (alive + authed) + any down one with its fix command; for discover, a short ranked shortlist. Then 🧒 recap. Setup detail: [[telegram-mcp-connector]], [[whatsapp-mcp-integration]], [[n8n-stack]].
