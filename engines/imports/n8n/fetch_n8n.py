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
Deterministic n8n audit fetcher. 0 LLM tokens.
Pulls full JSON of every workflow + recent executions, parses structure into a
compact per-workflow profile (trigger, node types, external services, sub-workflow
calls, schedule, last-exec status). Writes raw JSON to raw/ and a structured
audit_profiles.json + audit_summary.md to out/.
"""
import json, os, sys, urllib.request, urllib.error, re
from collections import Counter, defaultdict

BASE = "E:/Obsidian/_imports/n8n"
ENV = "C:$HOME/.claude/secrets/n8n.env"

def load_env():
    cfg = {}
    with open(ENV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

CFG = load_env()
URL = CFG["N8N_URL"].rstrip("/")
KEY = CFG["N8N_API_KEY"]

def api(path):
    req = urllib.request.Request(URL + path, headers={
        "X-N8N-API-KEY": KEY,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_all_workflows():
    items, cursor = [], None
    while True:
        path = "/api/v1/workflows?limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        data = api(path)
        items.extend(data.get("data", []))
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return items

def fetch_executions():
    """Recent executions to determine health per workflow."""
    by_wf = defaultdict(lambda: {"success": 0, "error": 0, "waiting": 0, "last": None, "last_status": None})
    cursor, pages = None, 0
    while pages < 20:  # cap
        path = "/api/v1/executions?limit=100&includeData=false"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        try:
            data = api(path)
        except Exception as e:
            print("exec fetch stop:", e); break
        for ex in data.get("data", []):
            wid = str(ex.get("workflowId"))
            st = ex.get("status") or ("error" if ex.get("finished") is False else "success")
            rec = by_wf[wid]
            if st == "error" or st == "crashed" or st == "failed":
                rec["error"] += 1
            elif st == "waiting" or st == "running":
                rec["waiting"] += 1
            else:
                rec["success"] += 1
            started = ex.get("startedAt") or ex.get("createdAt")
            if started and (rec["last"] is None or started > rec["last"]):
                rec["last"] = started
                rec["last_status"] = st
        cursor = data.get("nextCursor")
        pages += 1
        if not cursor:
            break
    return by_wf

# --- node classification ----------------------------------------------------
TRIGGER_HINT = re.compile(r"(trigger|webhook|cron|schedule|formTrigger|chatTrigger|errorTrigger|manualTrigger|telegramTrigger|emailReadImap|executeWorkflowTrigger|n8nTrigger|mcpTrigger)", re.I)

def short_type(t):
    # n8n-nodes-base.telegram -> telegram ; @n8n/n8n-nodes-langchain.agent -> agent
    t = t or ""
    t = t.split(".")[-1]
    return t

def classify(wf):
    nodes = wf.get("nodes", []) or []
    types = [n.get("type", "") for n in nodes]
    short = [short_type(t) for t in types]
    triggers = [short_type(t) for t in types if TRIGGER_HINT.search(t or "")]
    type_count = Counter(short)

    # external services / integrations (strip langchain + base utility nodes)
    UTILITY = {"set","if","switch","merge","function","functionItem","code","noOp",
               "stickyNote","splitInBatches","itemLists","aggregate","filter","wait",
               "respondToWebhook","executeWorkflow","stopAndError","dateTime","html",
               "extractFromFile","convertToFile","editImage","limit","removeDuplicates",
               "splitOut","summarize","sort","renameKeys","compareDatasets","markdown"}
    services = sorted(set(s for s in short if s.lower() not in UTILITY
                          and not s.lower().endswith("trigger")
                          and s not in ("manualTrigger","webhook","cron","scheduleTrigger")))
    # sub-workflow calls
    subcalls = []
    for n in nodes:
        if short_type(n.get("type","")) in ("executeWorkflow","toolWorkflow"):
            params = n.get("parameters", {}) or {}
            wid = params.get("workflowId")
            if isinstance(wid, dict):
                wid = wid.get("value") or wid.get("cachedResultName")
            subcalls.append({"node": n.get("name"), "target": wid})
    # schedule details
    schedules = []
    for n in nodes:
        st = short_type(n.get("type",""))
        if st in ("scheduleTrigger","cron"):
            schedules.append(n.get("parameters", {}))
    # AI: models + tools
    ai_models = [short_type(t) for t in types if "lmChat" in t or "lmOpenAi" in t or "Anthropic" in t or "ollama" in t.lower()]
    has_agent = any("agent" in s.lower() for s in short)
    return {
        "node_count": len(nodes),
        "triggers": triggers or (["manual?"] if not triggers else triggers),
        "services": services,
        "subworkflow_calls": subcalls,
        "schedules": schedules,
        "ai_models": ai_models,
        "has_agent": has_agent,
        "top_nodes": type_count.most_common(8),
    }

def main():
    print("Fetching workflows...")
    wfs = fetch_all_workflows()
    print(f"  got {len(wfs)} workflows")
    # save raw
    with open(f"{BASE}/raw/all_workflows.json", "w", encoding="utf-8") as f:
        json.dump(wfs, f, ensure_ascii=False, indent=1)

    print("Fetching executions...")
    try:
        execs = fetch_executions()
    except Exception as e:
        print("exec err:", e); execs = {}
    print(f"  health for {len(execs)} workflows")

    profiles = []
    for wf in wfs:
        c = classify(wf)
        wid = str(wf.get("id"))
        h = execs.get(wid, {})
        profiles.append({
            "id": wid,
            "name": wf.get("name"),
            "active": wf.get("active"),
            "updatedAt": wf.get("updatedAt"),
            "createdAt": wf.get("createdAt"),
            "tags": [t.get("name") for t in (wf.get("tags") or [])],
            **c,
            "health": {
                "success": h.get("success",0), "error": h.get("error",0),
                "waiting": h.get("waiting",0),
                "last": h.get("last"), "last_status": h.get("last_status"),
            },
        })
    profiles.sort(key=lambda p: (not p["active"], p["name"].lower()))
    with open(f"{BASE}/out/audit_profiles.json", "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=1)

    # quick summary md
    active = sum(1 for p in profiles if p["active"])
    total_nodes = sum(p["node_count"] for p in profiles)
    svc_counter = Counter()
    for p in profiles:
        svc_counter.update(p["services"])
    lines = []
    lines.append(f"# n8n audit (deterministic) — {len(profiles)} workflows\n")
    lines.append(f"- Active: {active} / Inactive: {len(profiles)-active}")
    lines.append(f"- Total nodes across all: {total_nodes}")
    lines.append(f"- Top services/integrations: " + ", ".join(f"{k}({v})" for k,v in svc_counter.most_common(25)))
    lines.append("")
    lines.append("| # | Workflow | Act | Nodes | Trigger | Err | Services |")
    lines.append("|---|---|---|---|---|---|---|")
    for i,p in enumerate(profiles,1):
        trg = ",".join(p["triggers"][:3])
        svc = ",".join(p["services"][:6])
        err = p["health"]["error"]
        lines.append(f"| {i} | {p['name']} | {'✅' if p['active'] else '💤'} | {p['node_count']} | {trg} | {err or ''} | {svc} |")
    with open(f"{BASE}/out/audit_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(profiles)} profiles. Active={active}. Total nodes={total_nodes}.")
    print("Sub-workflow links:", sum(len(p["subworkflow_calls"]) for p in profiles))

if __name__ == "__main__":
    import urllib.parse
    main()
