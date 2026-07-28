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
Build workflow #1 -- WATCHDOG (dead-man's-switch / сторож тишины).
ONE workflow, two triggers sharing $getWorkflowStaticData('global'):
  (a) Webhook POST /watchdog-hb {source, every_min[, _backdate_min][, action:'check']}
      -> records per-source last-seen in static data.
  (b) Schedule every 5 min -> checks staleness -> overdue & not-yet-alerted
      -> POST to the bus-bridge webhook (email + TG group 03).
Alert path REUSES the existing bus-bridge (single notification path, DRY, not-brain).
"""
import json
import n8n_build as B

HANDLE_JS = r"""
const store = $getWorkflowStaticData('global');
store.hb = store.hb || {};
const now = Date.now();
const item = $input.first().json;
const body = item.body || item || {};
const isCheck = body.action === 'check' || !body.source;

if (!isCheck) {
  const src = String(body.source);
  const every = Number(body.every_min || 15);
  let last = now;
  if (body._backdate_min) last = now - Number(body._backdate_min) * 60000;
  store.hb[src] = { last, every_min: every, alerted: false };
  return [{ json: { type: 'hb', ok: true, source: src, every_min: every } }];
}

const out = [];
for (const src of Object.keys(store.hb)) {
  const rec = store.hb[src];
  const graceMs = (rec.every_min || 15) * 2 * 60000;
  const overdueMin = Math.round((now - rec.last) / 60000);
  if (now - rec.last > graceMs && !rec.alerted) {
    rec.alerted = true;
    out.push({ json: { type: 'alert', source: src,
      text: `🔴 WATCHDOG: '${src}' молчит ${overdueMin}мин (ждали пинг каждые ${rec.every_min}мин)` } });
  }
}
if (out.length === 0) return [{ json: { type: 'ok', checked: Object.keys(store.hb).length } }];
return out;
""".strip()

nodes = [
    {"parameters": {"httpMethod": "POST", "path": "watchdog-hb",
                    "responseMode": "lastNode", "options": {}},
     "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
     "position": [0, -120], "id": "wd-hb-in", "name": "hb-in"},

    {"parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
     "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
     "position": [0, 120], "id": "wd-sched", "name": "every-5min"},

    {"parameters": {"jsCode": HANDLE_JS},
     "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [260, 0], "id": "wd-handle", "name": "handle"},

    {"parameters": {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
                                   "combinator": "and",
                                   "conditions": [{"id": "c1", "leftValue": "={{ $json.type }}",
                                                   "rightValue": "alert",
                                                   "operator": {"type": "string", "operation": "equals"}}]}},
     "type": "n8n-nodes-base.if", "typeVersion": 2,
     "position": [520, 0], "id": "wd-if", "name": "is-alert"},

    {"parameters": {"method": "POST", "url": "https://n8n.example.com/webhook/bus-bridge",
                    "sendHeaders": True,
                    "headerParameters": {"parameters": [
                        {"name": "User-Agent", "value": "PaloAlto-watchdog/1.0"}]},
                    "sendBody": True, "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ token: 'REPLACE_WITH_YOUR_BUS_TOKEN', src: 'WATCHDOG', dst: 'ALL', text: $json.text }) }}",
                    "options": {}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [780, -80], "id": "wd-notify", "name": "notify-bus"},
]

connections = {
    "hb-in": {"main": [[{"node": "handle", "type": "main", "index": 0}]]},
    "every-5min": {"main": [[{"node": "handle", "type": "main", "index": 0}]]},
    "handle": {"main": [[{"node": "is-alert", "type": "main", "index": 0}]]},
    "is-alert": {"main": [[{"node": "notify-bus", "type": "main", "index": 0}], []]},
}

if __name__ == "__main__":
    res = B.create_workflow("WATCHDOG (dead-mans-switch)", nodes, connections, activate=False)
    print("CREATED id=", res.get("id"), "name=", res.get("name"))
    print("activate ->", B.set_active(res["id"], True))
