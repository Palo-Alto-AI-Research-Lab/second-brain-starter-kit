#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# PUBLISHED SAMPLE - the paths and identifiers below are placeholders, not live
# values. This file runs a real system on the author's machines. Before it runs
# on yours, replace:
#   %VAULT%        your Obsidian vault root
#   %IMPORTS%      wherever you keep these engines' data
#   %USERPROFILE%  your home directory
#   %WORKDIR%      your working folder
# Chat ids, handles, phone numbers and e-mail addresses were swapped for fakes of
# the same shape, so the code still reads and parses - but it talks to nothing
# until you point it at your own accounts.
# Passport (what it does / what breaks / how to fix): see engines/README.md.
# ---------------------------------------------------------------------------
r"""token_heal.py -- deterministic ChatGPT bearer self-heal (0 LLM, 0 browser).

ROOT-CAUSE FIX 2026-07-16: the bearer accessToken dies every ~5-9 days, but the
NextAuth SESSION cookie (__Secure-next-auth.session-token) lives ~3 months and
chatgpt.com/api/auth/session mints a FRESH accessToken from it on every call.
So we keep the session cookie in secrets\session_token.txt and re-mint the
bearer deterministically whenever the pull hits 401/403 -- no Chrome, no LLM.

Also captures the ROTATED session cookie from Set-Cookie (NextAuth rolling
sessions), so regular use keeps the cookie itself fresh indefinitely.

Layers of self-heal (who calls whom):
  L1 (this script, deterministic) -- called by nightly_sync.py on pull exit 7.
  L2 (Chrome, needs a live claude session) -- skill local-chatgpt-token-heal:
     navigate chatgpt.com/api/auth/session -> get_page_text -> save BOTH
     accessToken -> bearer.txt AND sessionToken -> session_token.txt.
  L3 (human) -- only if Chrome is logged out of chatgpt.com.

Exit codes:
  0 = fresh bearer written AND verified against backend-api (HTTP 200)
  5 = session cookie missing/dead -> needs L2 (Chrome re-harvest)
  6 = network/Cloudflare trouble (transient; retry later)

USAGE: python token_heal.py [--verify-only]
       --verify-only = just test the CURRENT bearer against backend-api
                       (exit 0 alive / 5 dead), touch nothing.

NOTE: curl with a bare User-Agent gets CF-blocked (403) on chatgpt.com even
with a live token -- urllib with full browser-ish headers (below) passes.
That is why this script, not curl, is the authoritative token check.
"""
import os, sys, json, time, uuid, datetime, ssl, urllib.request, urllib.error
import certifi

_CTX = ssl.create_default_context(cafile=certifi.where())

ROOT = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.join(ROOT, "secrets")
BEARER_F = os.path.join(SECRETS, "bearer.txt")
SESSION_F = os.path.join(SECRETS, "session_token.txt")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
COOKIE_NAME = "__Secure-next-auth.session-token"


def log(msg):
    print("[token_heal] %s" % msg, flush=True)


def base_headers():
    return {
        "User-Agent": UA, "Accept": "application/json",
        "oai-language": "en-US", "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com", "OAI-Device-Id": str(uuid.uuid4()),
    }


def verify_bearer(bearer):
    """True if the bearer is alive against the real list endpoint."""
    req = urllib.request.Request(
        "https://chatgpt.com/backend-api/conversations?offset=0&limit=1&order=updated",
        headers={**base_headers(), "Authorization": "Bearer " + bearer})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False
        raise


def read_secret(path):
    if not os.path.exists(path):
        return None
    v = open(path, encoding="utf-8").read().strip()
    return v or None


def backup_and_write(path, value):
    if os.path.exists(path):
        prev = path.rsplit(".", 1)[0] + ".prev.txt"
        try:
            os.replace(prev, prev + ".2") if os.path.exists(prev) else None
        except OSError:
            pass
        with open(prev, "w", encoding="utf-8", newline="") as f:
            f.write(open(path, encoding="utf-8").read())
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(value)


def extract_rotated_cookie(resp):
    """NextAuth rolling sessions: pick a rotated session cookie out of
    Set-Cookie (handles the chunked .0/.1 variant too)."""
    setcookies = resp.headers.get_all("Set-Cookie") or []
    chunks = {}
    whole = None
    for sc in setcookies:
        kv = sc.split(";", 1)[0].strip()
        if "=" not in kv:
            continue
        name, val = kv.split("=", 1)
        if name == COOKIE_NAME and val:
            whole = val
        elif name.startswith(COOKIE_NAME + ".") and val:
            try:
                chunks[int(name.rsplit(".", 1)[1])] = val
            except ValueError:
                pass
    if whole:
        return whole
    if chunks:
        return "".join(chunks[i] for i in sorted(chunks))
    return None


def mint_from_session(session_cookie):
    """GET /api/auth/session with the session cookie -> (accessToken, rotated_cookie|None)."""
    req = urllib.request.Request(
        "https://chatgpt.com/api/auth/session",
        headers={**base_headers(), "Cookie": "%s=%s" % (COOKIE_NAME, session_cookie)})
    last = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                body = r.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    log("non-JSON response from /api/auth/session (CF challenge?) len=%d" % len(body))
                    sys.exit(6)
                tok = data.get("accessToken")
                if not tok:
                    # empty {} = session cookie dead/logged-out
                    log("no accessToken in session response (cookie dead?) keys=%s" % sorted(data.keys()))
                    sys.exit(5)
                exp = data.get("expires", "?")
                log("minted fresh accessToken (session expires %s)" % exp)
                return tok, extract_rotated_cookie(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                log("auth/session HTTP %d -> session cookie dead, needs Chrome re-harvest" % e.code)
                sys.exit(5)
            last = "HTTP %d" % e.code
            time.sleep(3 + i * 2)
        except Exception as e:  # noqa: BLE001 - network layer, keep robust
            last = str(e)
            time.sleep(3 + i * 2)
    log("network trouble talking to /api/auth/session (%s)" % last)
    sys.exit(6)


def main():
    if "--verify-only" in sys.argv:
        bearer = read_secret(BEARER_F)
        ok = bool(bearer) and verify_bearer(bearer)
        log("verify-only: bearer %s" % ("ALIVE" if ok else "DEAD/absent"))
        sys.exit(0 if ok else 5)

    session_cookie = read_secret(SESSION_F)
    if not session_cookie:
        log("secrets\\session_token.txt missing/empty -> needs ONE Chrome harvest "
            "(chatgpt.com/api/auth/session -> save sessionToken field)")
        sys.exit(5)

    tok, rotated = mint_from_session(session_cookie)

    if not verify_bearer(tok):
        log("freshly-minted bearer FAILED backend-api verify -- treating session as dead")
        sys.exit(5)
    log("fresh bearer VERIFIED against backend-api (HTTP 200)")

    backup_and_write(BEARER_F, tok)
    log("bearer.txt updated (old kept as bearer.prev.txt)")

    if rotated and rotated != session_cookie:
        backup_and_write(SESSION_F, rotated)
        log("session cookie ROTATED by server -> session_token.txt updated")

    stamp = os.path.join(SECRETS, "_token_heal_last.json")
    with open(stamp, "w", encoding="utf-8") as f:
        json.dump({"healed_at": datetime.datetime.now().isoformat(timespec="seconds"),
                   "rotated_cookie": bool(rotated and rotated != session_cookie)}, f)
    sys.exit(0)


if __name__ == "__main__":
    main()
