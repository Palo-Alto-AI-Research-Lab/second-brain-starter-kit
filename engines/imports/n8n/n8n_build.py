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
"""
n8n_build.py -- create NEW workflows over the REST public API (dead-MCP workaround).
Reuses n8n_edit's _req + WAF-bypass UA + secrets. The n8n MCP wrapper was just a thin
layer over this same REST API, so when the MCP drops we build straight over HTTP.

Library:
  create_workflow(name, nodes, connections, settings=None, activate=False) -> dict
  activate(wid, on=True)
  post_webhook(path, payload)  -- fire a production webhook for /tt testing
CLI:
  python n8n_build.py list
  python n8n_build.py post <webhook-path> '<json>'   -- test-fire a webhook
"""
import json, sys, urllib.request
import n8n_edit as E  # reuse _req, URL, KEY, HDR, list_workflows, get_workflow


def create_workflow(name, nodes, connections, settings=None, activate=False):
    payload = {"name": name, "nodes": nodes, "connections": connections,
               "settings": settings or {"executionOrder": "v1"}}
    res = E._req("POST", "/api/v1/workflows", payload)
    wid = res.get("id")
    # snapshot to git-tracked infra dir so n8n is never a black box
    import os
    d = f"{E.BASE}/raw/created"
    os.makedirs(d, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
    open(f"{d}/{wid}__{safe}.json", "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=1))
    if activate and wid:
        set_active(wid, True)
    return res


def set_active(wid, on=True):
    return E._req("POST", f"/api/v1/workflows/{wid}/{'activate' if on else 'deactivate'}", {})


def post_webhook(path, payload, base=None, test=False):
    """Fire a webhook (production by default) with the WAF-bypass UA. For /tt."""
    url = (base or E.URL).rstrip("/") + ("/webhook-test/" if test else "/webhook/") + path.lstrip("/")
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json", "User-Agent": E.UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(body)
        except Exception:
            return r.status, body


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        for w in E.list_workflows():
            print(f"{w['id']}  active={str(w['active']):5}  {w['name']}")
    elif cmd == "post":
        st, out = post_webhook(sys.argv[2], json.loads(sys.argv[3]))
        print("HTTP", st)
        print(json.dumps(out, ensure_ascii=False, indent=1) if isinstance(out, (dict, list)) else out)
    elif cmd == "activate":
        print(set_active(sys.argv[2], sys.argv[3] != "0"))
    else:
        print(__doc__)
