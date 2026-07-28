#!/usr/bin/env python
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
"""x_post.py - post a single tweet to X (Twitter) via API v2, OAuth 1.0a user context.

WHY: /fb-watch writes EN teasers; once Anton supplies X API creds this posts them.
     X browser-posting = instant ban -> API is the only safe path (DR #39, verified
     2026-06-30: X is pay-per-use, $0.20/post-with-link, ~$6/mo at 1 teaser/day).

DORMANT UNTIL CREDS EXIST. Reads OAuth1 creds from an env file `x_api.env`:
    X_API_KEY=...            (consumer / app key)
    X_API_SECRET=...         (consumer / app secret)
    X_ACCESS_TOKEN=...       (user access token)
    X_ACCESS_TOKEN_SECRET=...(user access token secret)
All four come from developer.x.com -> your app -> Keys and tokens. The access
token/secret must be generated with READ AND WRITE permission (else posting 403s).

Searched (first match wins): $CLAUDE_SECRETS, ~/.claude/secrets,
    %WORKDIR%\\secrets, %WORKDIR%\\secrets

USAGE:
    python x_post.py check                 # validate creds (cheap GET /2$HOME)
    python x_post.py post "tweet text"     # post; prints tweet id + url
    python x_post.py post "text" --dry-run # validate length only, no API call
    python x_post.py config                # show which creds file/dir would be used

Exit: 0 ok | 2 bad args | 3 creds missing | 4 too long/empty | 5 API error
"""
import os, sys, json

try:  # Windows console is often cp1251 -> emoji in teasers would crash print(); force UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

MAX_LEN = 280
SECRET_DIRS = [
    os.environ.get("CLAUDE_SECRETS"),
    os.path.join(os.path.expanduser("~"), ".claude", "secrets"),
    r"%WORKDIR%\secrets",
    r"%WORKDIR%\secrets",
]
ENV_NAME = "x_api.env"
REQUIRED = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]


def _find_env():
    for d in SECRET_DIRS:
        if not d:
            continue
        p = os.path.join(d, ENV_NAME)
        if os.path.isfile(p):
            return p
    return None


def _load_env(path):
    creds = {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            creds[k.strip()] = v.strip().strip('"').strip("'")
    return creds


def _creds():
    p = _find_env()
    if not p:
        print("CREDS MISSING: put %s in one of: %s" % (
            ENV_NAME, ", ".join(d for d in SECRET_DIRS if d)), file=sys.stderr)
        print("  keys needed: " + ", ".join(REQUIRED), file=sys.stderr)
        return None, None
    creds = _load_env(p)
    missing = [k for k in REQUIRED if not creds.get(k)]
    if missing:
        print("CREDS INCOMPLETE in %s: missing %s" % (p, ", ".join(missing)), file=sys.stderr)
        return None, p
    return creds, p


def _session(creds):
    from requests_oauthlib import OAuth1Session
    return OAuth1Session(
        creds["X_API_KEY"], client_secret=creds["X_API_SECRET"],
        resource_owner_key=creds["X_ACCESS_TOKEN"],
        resource_owner_secret=creds["X_ACCESS_TOKEN_SECRET"])


def cmd_config():
    p = _find_env()
    print("env file: %s" % (p or "(none found yet)"))
    print("search order:")
    for d in SECRET_DIRS:
        if d:
            print("  - %s%s" % (d, "  <-- HERE" if p and os.path.dirname(p) == d else ""))
    return 0


def cmd_check():
    creds, p = _creds()
    if not creds:
        return 3
    try:
        r = _session(creds).get("https://api.x.com/2$HOME", timeout=30)
    except Exception as e:
        print("API ERROR: %s" % e, file=sys.stderr)
        return 5
    if r.status_code == 200:
        u = r.json().get("data", {})
        print("AUTH OK creds=%s user=@%s id=%s" % (p, u.get("username"), u.get("id")))
        return 0
    print("AUTH FAILED http=%s body=%s" % (r.status_code, r.text[:300]), file=sys.stderr)
    return 5


def cmd_post(text, dry):
    if not text or not text.strip():
        print("REFUSE: empty tweet", file=sys.stderr)
        return 4
    n = len(text)
    if n > MAX_LEN:
        print("REFUSE: %d chars > %d limit" % (n, MAX_LEN), file=sys.stderr)
        return 4
    if dry:
        print("DRY-RUN OK len=%d/%d text=%r" % (n, MAX_LEN, text))
        return 0
    creds, _ = _creds()
    if not creds:
        return 3
    try:
        r = _session(creds).post("https://api.x.com/2/tweets",
                                 json={"text": text}, timeout=30)
    except Exception as e:
        print("API ERROR: %s" % e, file=sys.stderr)
        return 5
    if r.status_code in (200, 201):
        tid = r.json().get("data", {}).get("id")
        print("POSTED id=%s url=https://x.com/i/web/status/%s" % (tid, tid))
        return 0
    print("POST FAILED http=%s body=%s" % (r.status_code, r.text[:400]), file=sys.stderr)
    return 5


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    cmd = a[0]
    if cmd == "config":
        return cmd_config()
    if cmd == "check":
        return cmd_check()
    if cmd == "post":
        if len(a) < 2:
            print("usage: x_post.py post \"<text>\" [--dry-run]", file=sys.stderr)
            return 2
        return cmd_post(a[1], "--dry-run" in a[2:])
    print("unknown command: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
