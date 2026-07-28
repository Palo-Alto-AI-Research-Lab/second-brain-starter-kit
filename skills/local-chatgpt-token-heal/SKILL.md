---
name: local-chatgpt-token-heal
description: Refresh the ChatGPT bearer token when the nightly sync dies with exit=7 (token expired). Root-cause fix — the bearer lives ~5-9 days but the NextAuth SESSION cookie lives ~3 months and re-mints a fresh bearer deterministically (0 LLM, 0 browser). Trigger on "/chatgpt-token-heal", "почини chatgpt токен", "chatgpt exit 7", "обнови bearer chatgpt", "chatgpt token dead", "heal chatgpt token", or when nightly_sync/incremental_pull reports AUTH FAILED / exit 7. Fleet-local skill (hub HUB-1 — where the nightly runs + a logged-in chatgpt.com Chrome lives). Engine = $IMPORTS_ROOT/chatgpt/token_heal.py. Pairs with /chatgpt-sync + memory [[chatgpt-export-pipeline]].
---

OBJECTIVE: Get the ChatGPT nightly sync back to `exit=0` by refreshing the dead bearer token — the correct, root-cause way (session cookie → fresh bearer), falling back to Chrome only when the cookie itself has died.

## The root cause (why this skill exists)
The `secrets\bearer.txt` accessToken expires every **~5-9 days** — that is OpenAI's design, there is no refresh-token for it. BUT the login **session cookie** (`__Secure-next-auth.session-token`, stored in `secrets\session_token.txt`) lives **~3 months** and `chatgpt.com/api/auth/session` mints a **fresh bearer from it on every call**. So the fix is deterministic: cookie → new bearer, no browser, no LLM. The cookie also silently rotates (NextAuth rolling sessions) and `token_heal.py` captures the rotated one, so routine use keeps the cookie fresh indefinitely.

⚠️ GRABLI: a bare `curl -H "User-Agent: Mozilla/5.0"` to `/backend-api/...` returns **403 for BOTH dead AND live tokens** — Cloudflare bot-blocks the curl UA before the auth layer. That curl is a USELESS token test. The authoritative check is `token_heal.py --verify-only` (urllib + full browser headers, reaches the real auth layer → 200/401).

## LAYERS (do them in order, stop at the first that reaches exit=0)

### L1 — deterministic re-mint (default; no browser, no LLM)
```
python "%IMPORTS_ROOT%\chatgpt\token_heal.py"     # PowerShell: use %IMPORTS%\chatgpt\token_heal.py
```
- exit **0** → fresh bearer written + VERIFIED (HTTP 200), cookie rotated if server rotated it. DONE — go to "Finish".
- exit **5** → session cookie dead/absent → do **L2**.
- exit **6** → transient network/Cloudflare → wait a few min, retry L1 once; still 6 → note it and stop (not a token problem).

Note: nightly_sync.py already calls L1 automatically on pull exit 7 and retries the pull. So most of the time you never run this by hand — this skill is for when L1 itself returns 5 (cookie dead) and a human-in-the-loop Chrome step is needed, or when Anton runs `/chatgpt-token-heal` directly.

### L2 — Chrome re-harvest of the session cookie (only when L1 exits 5)
Needs a Chrome logged into chatgpt.com on account **owner.work@example.com** + the Claude-in-Chrome MCP (load via ToolSearch if deferred). Do it ON THE HUB.
1. `list_connected_browsers` → confirm a local Chrome. `navigate` a tab to `https://chatgpt.com/api/auth/session`.
2. `get_page_text` on that tab → JSON. (On the hub this reads the token directly; the old Blob-download dance is NOT needed here.)
3. From that JSON take BOTH fields and write them to secrets (single line, no trailing newline, back up the old first):
   - `accessToken` → `secrets\bearer.txt`
   - `sessionToken` → `secrets\session_token.txt`  ← **this is the long-lived cookie; saving it is what makes future heals deterministic**
4. Navigate the tab away from the session page (hygiene) so the token isn't left on screen.
5. Re-run L1 (`token_heal.py`) to VERIFY + capture any rotation → expect exit 0.

If the page shows an empty `{}` or a login screen → Chrome is logged out → **L3**.

### L3 — human (only if Chrome is logged out of chatgpt.com)
Escalate to Anton via the approval rail (D-type "needs his hands"): ask him to log into chatgpt.com in Chrome on the hub (account a2), then re-run this skill. This is the ONLY genuine human blocker.

## Finish (after any layer reaches a fresh bearer)
```
cmd /c "%IMPORTS%\chatgpt\nightly_sync.cmd"
```
then tail `%IMPORTS%\chatgpt\_nightly_sync-HUB-1.log` → confirm `exit=0`. Report: which layer healed it, session-cookie expiry date, +N new chats. NEVER print the token/cookie value.

## Files
- Engine: `%IMPORTS%\chatgpt\token_heal.py` (L1 + `--verify-only`)
- Secrets: `secrets\bearer.txt` (short-lived, ~5-9d) · `secrets\session_token.txt` (long-lived cookie, ~3mo) · `_token_heal_last.json` (heal stamp)
- Auto-heal loop: `nightly_sync.py` calls L1 on pull exit 7, retries pull, and bus-TASKs the hub (L2) if L1 exits 5.
- Canon: memory [[chatgpt-export-pipeline]], [[credential-store]]; sibling skill `/chatgpt-sync`.
