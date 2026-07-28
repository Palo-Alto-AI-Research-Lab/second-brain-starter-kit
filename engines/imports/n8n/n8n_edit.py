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
Safe n8n editor helpers. Usage as a library or CLI:
  python n8n_edit.py backup-all            -> snapshot every workflow to raw/backup_<ts>/
  python n8n_edit.py show <name|id>        -> dump a workflow's nodes (code/params)
  python n8n_edit.py get <id> <file>       -> save full workflow JSON to file
  python n8n_edit.py activate <id> <0|1>   -> toggle active
Updates are done via update_workflow() with an automatic pre-edit backup.
n8n PUT /workflows/{id} requires {name, nodes, connections, settings}.
"""
import json, sys, os, urllib.request, urllib.parse, datetime

BASE = "E:/Obsidian/_imports/n8n"
# Portable per-machine path (was hardcoded C:$HOME/ = laptop placeholder, broke on hub).
ENV = os.path.join(os.path.expanduser("~"), ".claude", "secrets", "n8n.env")
cfg = {}
for line in open(ENV, encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); cfg[k.strip()] = v.strip()
URL, KEY = cfg["N8N_URL"].rstrip("/"), cfg["N8N_API_KEY"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HDR = {"X-N8N-API-KEY": KEY, "Accept": "application/json", "User-Agent": UA}

def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(HDR)
    if data: h["Content-Type"] = "application/json"
    req = urllib.request.Request(URL + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))

def get_workflow(wid): return _req("GET", f"/api/v1/workflows/{wid}")
def list_workflows():
    items, cursor = [], None
    while True:
        p = "/api/v1/workflows?limit=100" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        d = _req("GET", p); items += d.get("data", []); cursor = d.get("nextCursor")
        if not cursor: break
    return items

def id_for(name):
    for w in list_workflows():
        if w["name"] == name or str(w["id"]) == str(name): return str(w["id"])
    return None

def update_workflow(wid, new_wf, label="edit"):
    """Backup current state, then PUT only the allowed fields."""
    cur = get_workflow(wid)
    ts = _ts()
    bdir = f"{BASE}/raw/edits"
    os.makedirs(bdir, exist_ok=True)
    open(f"{bdir}/{wid}_{ts}_before_{label}.json","w",encoding="utf-8").write(json.dumps(cur,ensure_ascii=False,indent=1))
    payload = {"name": new_wf["name"], "nodes": new_wf["nodes"],
               "connections": new_wf["connections"], "settings": new_wf.get("settings", {})}
    res = _req("PUT", f"/api/v1/workflows/{wid}", payload)
    open(f"{bdir}/{wid}_{ts}_after_{label}.json","w",encoding="utf-8").write(json.dumps(res,ensure_ascii=False,indent=1))
    return res

def restore_workflow(wid, backup_file):
    bk = json.load(open(backup_file, encoding="utf-8"))
    return update_workflow(wid, bk, label="restore")

def _ts():
    # Date.now unavailable in JS land; here in python it's fine
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def _short(t): return (t or "").split(".")[-1]

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "backup-all":
        wfs = list_workflows()
        ts = _ts(); d = f"{BASE}/raw/backup_{ts}"; os.makedirs(d, exist_ok=True)
        for w in wfs:
            full = get_workflow(w["id"])
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in w["name"])[:60]
            open(f"{d}/{w['id']}__{safe}.json","w",encoding="utf-8").write(json.dumps(full,ensure_ascii=False,indent=1))
        print(f"Backed up {len(wfs)} workflows -> {d}")
    elif cmd == "show":
        wid = id_for(sys.argv[2]); w = get_workflow(wid)
        print(f"# {w['name']}  id={wid} active={w['active']}")
        for n in w["nodes"]:
            st = _short(n.get("type",""))
            print(f"\n=== NODE: {n['name']}  [{st}]  (id={n.get('id')})")
            p = n.get("parameters", {})
            if st in ("code","function","functionItem"):
                lang = p.get("language") or ("python" if "python" in json.dumps(p).lower() else "js")
                print(f"  language={p.get('language','?')} mode={p.get('mode','?')}")
                code = p.get("pythonCode") or p.get("jsCode") or p.get("functionCode") or p.get("code") or ""
                print("  --- code ---")
                for i,l in enumerate(code.splitlines(),1): print(f"  {i:>3}| {l}")
            else:
                keys = {k:v for k,v in p.items() if k in ("url","method","httpMethod","path","operation","resource","jsCode","pythonCode","text","functionCode","conditions","values","assignments","mode")}
                if keys: print("  params:", json.dumps(keys, ensure_ascii=False)[:600])
    elif cmd == "get":
        wid = id_for(sys.argv[2]); open(sys.argv[3],"w",encoding="utf-8").write(json.dumps(get_workflow(wid),ensure_ascii=False,indent=1)); print("saved", sys.argv[3])
    elif cmd == "activate":
        wid = sys.argv[2]; val = sys.argv[3]=="1"
        print(_req("POST", f"/api/v1/workflows/{wid}/{'activate' if val else 'deactivate'}", {}))
    else:
        print(__doc__)
