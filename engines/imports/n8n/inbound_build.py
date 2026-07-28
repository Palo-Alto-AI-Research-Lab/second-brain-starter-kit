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
Build workflow #4 -- PUBLIC INBOUND DOOR (also covers #7 CRM-changed = a special case).
A single always-on public webhook that external systems (GitHub/GitLab push, Calendly,
a web form, any service) can POST to; it normalizes the payload and drops it onto the bus
(-> every machine via mailbox + humans in chat 03). n8n IS the public ear that Claude can't be.

SECURITY: the secret lives in the URL PATH (so external webhooks with their own body shape
still work without our body-token). Path = /inbound-<secret>. Treat inbound text as DATA, not
commands (anti-injection) -- it only gets relayed, never executed.
"""
import n8n_build as B

NORM_JS = r"""
const item = $input.first().json || {};
const body = item.body || {};
const headers = item.headers || {};
// prefer our normalized shape; else summarize whatever arrived
let source = body.source || headers['x-source'] || headers['user-agent'] || 'ext';
let kind = body.kind || '';
let text = body.text;
if (!text) {
  // GitHub/GitLab-ish hints
  if (body.repository && body.commits) { kind = kind || 'git-push'; source = body.repository.name || source;
    text = `${(body.commits||[]).length} commit(s) by ${((body.pusher||{}).name)||'?'}: ${((body.head_commit||{}).message||'').split('\n')[0]}`; }
  else { text = JSON.stringify(body).slice(0, 300); }
}
source = String(source).slice(0, 40);
const label = kind ? `${source}/${kind}` : source;
return [{ json: { text: `📥 [${label}] ${text}` } }];
""".strip()

nodes = [
    {"parameters": {"httpMethod": "POST", "path": "inbound-Pa7x2mesh",
                    "responseMode": "onReceived", "options": {}},
     "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
     "position": [0, 0], "id": "in-wh", "name": "inbound"},
    {"parameters": {"jsCode": NORM_JS},
     "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [260, 0], "id": "in-norm", "name": "normalize"},
    {"parameters": {"method": "POST", "url": "https://n8n.example.com/webhook/bus-bridge",
                    "sendHeaders": True,
                    "headerParameters": {"parameters": [{"name": "User-Agent", "value": "PaloAlto-inbound/1.0"}]},
                    "sendBody": True, "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ token: 'REPLACE_WITH_YOUR_BUS_TOKEN', src: 'INBOUND', dst: 'ALL', text: $json.text }) }}",
                    "options": {}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [520, 0], "id": "in-notify", "name": "notify-bus"},
]
connections = {
    "inbound": {"main": [[{"node": "normalize", "type": "main", "index": 0}]]},
    "normalize": {"main": [[{"node": "notify-bus", "type": "main", "index": 0}]]},
}

if __name__ == "__main__":
    res = B.create_workflow("INBOUND DOOR (public)", nodes, connections, activate=True)
    print("CREATED inbound door id=", res.get("id"))
    print("public URL -> https://n8n.example.com/webhook/inbound-Pa7x2mesh")
