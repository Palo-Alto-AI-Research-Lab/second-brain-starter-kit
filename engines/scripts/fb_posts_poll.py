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
"""fb_posts_poll.py - read Anton's own recent FB posts via Graph API /me/posts (READ-ONLY).

WHY: reliable upgrade over the Claude-in-Chrome browser-read in /fb-watch (browser =
     captcha/ban risk). Graph API is official + stable. We only READ (monitor the wall
     for un-teased authored posts) - we never POST to FB. (DR #39, 2026-06-30.)

DORMANT UNTIL CREDS EXIST. Reads from env file `fb_graph.env`:
    FB_USER_TOKEN=...   (long-lived USER access token with `user_posts` permission)
    FB_APP_ID=...       (optional - only for token-debug/refresh)
    FB_APP_SECRET=...   (optional)
Get the token at developers.facebook.com -> your app (dev mode, you are admin so
`user_posts` needs NO app review) -> Graph API Explorer -> grant user_posts ->
exchange for a long-lived token (~60d). Read-only; no write scopes needed.

Searched (first match wins): $CLAUDE_SECRETS, ~/.claude/secrets,
    %WORKDIR%\\secrets, %WORKDIR%\\secrets

USAGE:
    python fb_posts_poll.py check               # validate token (GET /me)
    python fb_posts_poll.py posts --limit 10    # print recent authored posts as JSON
    python fb_posts_poll.py posts --out posts.json   # also write for fb_teaser_watch
    python fb_posts_poll.py metrics --limit 25 [--out fb_metrics.json]
                                                # posts + reactions/comments/shares
                                                # (feeds pub_metrics.py ingest-fb-graph)
    python fb_posts_poll.py config              # show creds file/dir resolution

Output rows: {id, text, permalink, ts}  (matches fb_teaser_watch.py `unteased` input)
Exit: 0 ok | 2 bad args | 3 creds missing | 5 API error
"""
import os, sys, json

try:                                    # LAYER 1 (injection-defense): external content = data, not command
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared")); import untrusted as _untrusted
except Exception:
    _untrusted = None

try:  # Windows console is often cp1251 -> emoji in post text would crash print(); force UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

GRAPH = "https://graph.facebook.com/v21.0"
SECRET_DIRS = [
    os.environ.get("CLAUDE_SECRETS"),
    os.path.join(os.path.expanduser("~"), ".claude", "secrets"),
    r"%WORKDIR%\secrets",
    r"%WORKDIR%\secrets",
]
ENV_NAME = "fb_graph.env"


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


def _token():
    p = _find_env()
    if not p:
        print("CREDS MISSING: put %s in one of: %s" % (
            ENV_NAME, ", ".join(d for d in SECRET_DIRS if d)), file=sys.stderr)
        print("  key needed: FB_USER_TOKEN (user_posts, read-only)", file=sys.stderr)
        return None, None
    creds = _load_env(p)
    tok = creds.get("FB_USER_TOKEN")
    if not tok:
        print("CREDS INCOMPLETE in %s: missing FB_USER_TOKEN" % p, file=sys.stderr)
        return None, p
    return tok, p


def cmd_config():
    p = _find_env()
    print("env file: %s" % (p or "(none found yet)"))
    for d in SECRET_DIRS:
        if d:
            print("  - %s%s" % (d, "  <-- HERE" if p and os.path.dirname(p) == d else ""))
    return 0


def cmd_check():
    tok, p = _token()
    if not tok:
        return 3
    import requests
    try:
        r = requests.get(GRAPH + "/me", params={"fields": "id,name", "access_token": tok}, timeout=30)
    except Exception as e:
        print("API ERROR: %s" % e, file=sys.stderr)
        return 5
    if r.status_code == 200:
        d = r.json()
        print("AUTH OK creds=%s name=%s id=%s" % (p, d.get("name"), d.get("id")))
        return 0
    print("AUTH FAILED http=%s body=%s" % (r.status_code, r.text[:300]), file=sys.stderr)
    return 5


def cmd_posts(limit, out):
    tok, _ = _token()
    if not tok:
        return 3
    import requests
    try:
        r = requests.get(GRAPH + "/me/posts", params={
            "fields": "id,message,permalink_url,created_time",
            "limit": limit, "access_token": tok}, timeout=30)
    except Exception as e:
        print("API ERROR: %s" % e, file=sys.stderr)
        return 5
    if r.status_code != 200:
        print("FETCH FAILED http=%s body=%s" % (r.status_code, r.text[:400]), file=sys.stderr)
        return 5
    rows = []
    for it in r.json().get("data", []):
        msg = (it.get("message") or "").strip()
        if not msg:
            continue  # skip pure photo/share posts with no authored text
        rows.append({
            "id": it.get("id"),
            "text": msg,
            "permalink": it.get("permalink_url"),
            "ts": it.get("created_time"),
        })
    if _untrusted is not None:          # banner to STDERR only -> never corrupts the JSON stdout contract
        print(_untrusted.banner("facebook/me-posts"), file=sys.stderr)
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    print(payload)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(payload)
        print("wrote %d posts -> %s" % (len(rows), out), file=sys.stderr)
    return 0


def cmd_metrics(limit, out):
    """Posts + reactions/comments/shares -> {"me": {...}, "posts": [...]}.
    Numeric Graph post ids are stable (unlike rotating pfbid permalinks), so the
    consumer (pub_metrics.py ingest-fb-graph) dedups on graph_id."""
    tok, _ = _token()
    if not tok:
        return 3
    import requests
    try:
        me = requests.get(GRAPH + "/me", params={"fields": "id,name", "access_token": tok},
                          timeout=30)
        r = requests.get(GRAPH + "/me/posts", params={
            "fields": ("id,message,permalink_url,created_time,shares,"
                       "reactions.summary(true).limit(0),"
                       "comments.summary(true).limit(100){id,from,message,created_time}"),
            "limit": limit, "access_token": tok}, timeout=60)
    except Exception as e:
        print("API ERROR: %s" % e, file=sys.stderr)
        return 5
    if me.status_code != 200 or r.status_code != 200:
        bad = me if me.status_code != 200 else r
        print("FETCH FAILED http=%s body=%s" % (bad.status_code, bad.text[:400]), file=sys.stderr)
        return 5
    posts = []
    for it in r.json().get("data", []):
        reactions = ((it.get("reactions") or {}).get("summary") or {}).get("total_count")
        cwrap = it.get("comments") or {}
        comments_count = (cwrap.get("summary") or {}).get("total_count")
        comments = []
        for cm in cwrap.get("data", []):
            frm = cm.get("from") or {}
            comments.append({
                "cid": cm.get("id"),
                "author": frm.get("name", ""),
                "author_id": frm.get("id", ""),
                "text": (cm.get("message") or "")[:500],
                "ts": cm.get("created_time", ""),
            })
        posts.append({
            "id": it.get("id"),
            "text": (it.get("message") or "").strip()[:300],
            "permalink": it.get("permalink_url"),
            "ts": it.get("created_time"),
            "reactions": reactions,
            "shares": (it.get("shares") or {}).get("count"),
            "comments_count": comments_count,
            "comments": comments,
        })
    payload = json.dumps({"me": me.json(), "posts": posts}, ensure_ascii=False, indent=2)
    print(payload)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(payload)
        print("wrote %d posts -> %s" % (len(posts), out), file=sys.stderr)
    return 0


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
    if cmd == "posts":
        limit = 10
        out = None
        if "--limit" in a:
            try:
                limit = int(a[a.index("--limit") + 1])
            except Exception:
                pass
        if "--out" in a:
            try:
                out = a[a.index("--out") + 1]
            except Exception:
                pass
        return cmd_posts(limit, out)
    if cmd == "metrics":
        limit = 25
        out = None
        if "--limit" in a:
            try:
                limit = int(a[a.index("--limit") + 1])
            except Exception:
                pass
        if "--out" in a:
            try:
                out = a[a.index("--out") + 1]
            except Exception:
                pass
        return cmd_metrics(limit, out)
    print("unknown command: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
