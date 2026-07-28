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
Second pass (0 tokens): from raw/all_workflows.json extract the high-value
human logic: sub-workflow call graph (resolved to names), agent system prompts,
tool node descriptions, webhook paths, schedule rules, telegram/credential refs.
Writes out/call_graph.json, out/deep_profiles.json, out/agent_prompts.md.
"""
import json, re
from collections import defaultdict

BASE = "E:/Obsidian/_imports/n8n"
wfs = json.load(open(f"{BASE}/raw/all_workflows.json", encoding="utf-8"))
by_id = {str(w["id"]): w for w in wfs}
name_of = {str(w["id"]): w["name"] for w in wfs}

def short(t): return (t or "").split(".")[-1]

def resolve_wf_id(v):
    if isinstance(v, dict):
        return v.get("value") or v.get("__rl_value") or v.get("cachedResultName")
    return v

# --- call graph -------------------------------------------------------------
edges = []  # (caller_id, callee_id_or_name, node_name)
for w in wfs:
    wid = str(w["id"])
    for n in (w.get("nodes") or []):
        st = short(n.get("type",""))
        if st in ("executeWorkflow","toolWorkflow"):
            p = n.get("parameters", {}) or {}
            tgt = resolve_wf_id(p.get("workflowId"))
            edges.append({"caller_id": wid, "caller": w["name"],
                          "callee_id": str(tgt) if tgt else None,
                          "callee_name": name_of.get(str(tgt), None),
                          "via_node": n.get("name"), "node_type": st})
json.dump(edges, open(f"{BASE}/out/call_graph.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)

# callers/callees counts
callees = defaultdict(set); callers = defaultdict(set)
for e in edges:
    if e["callee_id"]:
        callees[e["caller_id"]].add(e["callee_id"])
        callers[e["callee_id"]].add(e["caller_id"])

# --- deep profiles: prompts, webhooks, schedules ---------------------------
def get_text_params(n):
    """pull system messages / prompt text / descriptions from a node."""
    p = n.get("parameters", {}) or {}
    out = {}
    # agent system message
    opts = p.get("options", {}) or {}
    sm = opts.get("systemMessage") or p.get("systemMessage")
    if sm: out["systemMessage"] = sm
    txt = p.get("text")
    if isinstance(txt, str) and len(txt) > 40: out["text"] = txt
    pr = p.get("promptType")
    desc = p.get("description") or (p.get("toolDescription"))
    if desc: out["description"] = desc
    # message for telegram
    return out

CRON_DOW = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
def describe_schedule(p):
    rule = (p.get("rule") or {}).get("interval") or []
    out = []
    for iv in rule:
        f = iv.get("field")
        if f == "cronExpression":
            out.append("cron: "+iv.get("expression",""))
        elif f == "weeks":
            out.append(f"weekly day={iv.get('triggerAtDay')} {iv.get('triggerAtHour','?')}:{iv.get('triggerAtMinute',0):02d}")
        elif f == "days":
            out.append(f"daily {iv.get('triggerAtHour','?')}:{iv.get('triggerAtMinute',0):02d}")
        elif f == "hours":
            out.append(f"every {iv.get('hoursInterval',1)}h")
        elif f == "minutes":
            out.append(f"every {iv.get('minutesInterval',1)}min")
        else:
            out.append(json.dumps(iv, ensure_ascii=False))
    return out

deep = []
prompt_md = ["# n8n agent system prompts & tool descriptions (raw extract)\n"]
for w in wfs:
    wid = str(w["id"])
    nodes = w.get("nodes") or []
    webhooks, schedules, tg_chats, agents, tools, creds = [], [], [], [], [], set()
    for n in nodes:
        st = short(n.get("type",""))
        p = n.get("parameters", {}) or {}
        for cname, cval in (n.get("credentials") or {}).items():
            creds.add(cname + ":" + (cval.get("name","") if isinstance(cval,dict) else str(cval)))
        if st == "webhook":
            webhooks.append({"path": p.get("path"), "method": p.get("httpMethod","GET")})
        if st in ("scheduleTrigger","cron"):
            schedules += describe_schedule(p)
        if "telegram" in st.lower():
            cid = p.get("chatId")
            if cid: tg_chats.append(str(cid))
        if "agent" in st.lower() or st in ("chainLlm",):
            tp = get_text_params(n)
            if tp.get("systemMessage") or tp.get("text"):
                agents.append({"node": n.get("name"), **tp})
        if st in ("toolWorkflow","toolHttpRequest","httpRequestTool","mongoDbTool","airtableTool"):
            tools.append({"node": n.get("name"), "type": st,
                          "desc": (p.get("description") or p.get("toolDescription") or "")[:200]})
    deep.append({
        "id": wid, "name": w["name"], "active": w["active"],
        "webhooks": webhooks, "schedules": schedules,
        "telegram_chats": sorted(set(tg_chats)),
        "credentials": sorted(creds),
        "calls": sorted(name_of.get(c, c) for c in callees.get(wid, [])),
        "called_by": sorted(name_of.get(c, c) for c in callers.get(wid, [])),
        "agent_count": len(agents), "tool_count": len(tools),
        "tools": tools,
    })
    if agents:
        prompt_md.append(f"\n## {w['name']} {'(active)' if w['active'] else '(inactive)'}\n")
        for a in agents:
            sm = a.get("systemMessage") or a.get("text") or ""
            prompt_md.append(f"### node: {a['node']}\n```\n{sm[:3000]}\n```\n")

json.dump(deep, open(f"{BASE}/out/deep_profiles.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
open(f"{BASE}/out/agent_prompts.md","w",encoding="utf-8").write("\n".join(prompt_md))

# stats
print(f"edges (subworkflow calls): {len(edges)}")
print(f"workflows with agent prompts: {sum(1 for d in deep if d['agent_count'])}")
print(f"webhooks: {sum(len(d['webhooks']) for d in deep)}")
print(f"scheduled: {sum(1 for d in deep if d['schedules'])}")
print(f"telegram-bound: {sum(1 for d in deep if d['telegram_chats'])}")
# orphan tools (called_by empty but executeWorkflowTrigger) vs hubs
hubs = sorted(deep, key=lambda d: -len(d["calls"]))[:6]
print("Top hubs (call most):", [(d["name"], len(d["calls"])) for d in hubs])
import os
print("agent_prompts.md size:", os.path.getsize(f"{BASE}/out/agent_prompts.md"), "bytes")
