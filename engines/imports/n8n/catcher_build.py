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
Build workflow #2 -- CENTRAL ERROR CATCHER.
An n8n Error-Trigger workflow: whenever ANY workflow that names this one as its
'Error Workflow' fails, this fires -> formats the failure -> POST to bus-bridge -> chat 03.
One pult where every silent n8n failure becomes visible.

After create, set settings.errorWorkflow=<catcherId> on the workflows we want watched.
"""
import n8n_build as B
import n8n_edit as E

BUILD_JS = r"""
const j = $input.first().json || {};
const wf = (j.workflow || {}).name || '?';
const ex = j.execution || {};
const node = ex.lastNodeExecuted || '?';
const msg = String(((ex.error || {}).message) || 'unknown').split('\n')[0].slice(0, 180);
const url = ex.url || '';
return [{ json: { text: `🔴 n8n FAIL: "${wf}" @ узел «${node}» — ${msg}${url ? ' | ' + url : ''}` } }];
""".strip()

nodes = [
    {"parameters": {}, "type": "n8n-nodes-base.errorTrigger", "typeVersion": 1,
     "position": [0, 0], "id": "ec-trigger", "name": "On Error"},
    {"parameters": {"jsCode": BUILD_JS}, "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [260, 0], "id": "ec-build", "name": "build msg"},
    {"parameters": {"method": "POST", "url": "https://n8n.example.com/webhook/bus-bridge",
                    "sendHeaders": True,
                    "headerParameters": {"parameters": [{"name": "User-Agent", "value": "PaloAlto-errcatch/1.0"}]},
                    "sendBody": True, "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ token: 'REPLACE_WITH_YOUR_BUS_TOKEN', src: 'N8N-ERR', dst: 'ALL', text: $json.text }) }}",
                    "options": {}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [520, 0], "id": "ec-notify", "name": "notify-bus"},
]
connections = {
    "On Error": {"main": [[{"node": "build msg", "type": "main", "index": 0}]]},
    "build msg": {"main": [[{"node": "notify-bus", "type": "main", "index": 0}]]},
}

if __name__ == "__main__":
    res = B.create_workflow("ERROR CATCHER (central)", nodes, connections, activate=True)
    cid = res["id"]
    print("CREATED catcher id=", cid, "active-attempted")
    # wire it as the error workflow on the rails we care about
    for wid, name in [("U96y7qLDLufGpbUf", "bus-bridge"), ("IdSRNxfOT9Mo7Qse", "watchdog")]:
        wf = E.get_workflow(wid)
        wf.setdefault("settings", {})["errorWorkflow"] = cid
        E.update_workflow(wid, wf, label="set-errorWorkflow")
        print(f"  wired errorWorkflow on {name} ({wid})")
