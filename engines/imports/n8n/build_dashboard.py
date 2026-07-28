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
"""Build a self-contained HTML dashboard from the n8n audit profiles. 0 tokens, no CDN."""
import json, html

BASE = "E:/Obsidian/_imports/n8n"
OUT = "E:/Obsidian/Owner-Knowledge/_Dashboards/n8n-Automation-Audit.html"
prof = json.load(open(f"{BASE}/out/audit_profiles.json", encoding="utf-8"))
deep = {d["id"]: d for d in json.load(open(f"{BASE}/out/deep_profiles.json", encoding="utf-8"))}
estat = json.load(open(f"{BASE}/out/exec_stats.json", encoding="utf-8"))
ex_by_id = {r["id"]: r for r in estat["workflows"]}
why = json.load(open(f"{BASE}/out/why_broken.json", encoding="utf-8"))
WINDOW = "5–15 июня 2026 (~10 дней, лимит логов n8n 10k)"

CLUSTERS = {
 "CHARM CRM": {"CHARM CRM Main Agent","CHARM CRM Inner Agent","Charm CRM tool","aaaZeroInbound","aaaZeroInbound DEV",
  "add_remove_tag_tool","approve_lead_tool","approve_request_superviser_tool","ask_superviser_tool","autotag_lead_charm_tool",
  "calls_tool","count_leads_with_tags_tool","create_call_tool","create_newsletter_tool","create_tag_tool","edit_call_tool",
  "edit_newsletter_tool","find_lead_in_crm_tool","get_accounts_tool","get_automatic_actions_listing_info_tool","get_crm description",
  "get_employees_tool","get_leads_individual_info_tool","get_leads_listing_info_tool","get_newsletter_messages_tool",
  "get_newsletter_sent_messages_tool","get_newsletter_tool","get_newsletters_listing_info_tool","get_tags_tool","newsletters_tool",
  "reject_lead_tool","send_message_in_crm_tool","send_message_to_lead_tool","send_msg_to_lead_tool","send_msg_to_lead_tool DEV",
  "Tag lead tool","Unassign lead","update_lead_info_tool","upsert_chat_template_tool"},
 "Content/Summary": {"BD in Web3 Summary","Canton Network Summary","Lobster DAO Summary","Telegram Chats Summary",
  "Channel list reading and summary","LobsterDAO Translation","Lobster Daily Translation","Everyday group posting",
  "Events Posting","Multi Posting Telegram"},
 "Audio/Media": {"Personal Audio Summary","Audio to text flow","Audio to text flow 11labs","audio to text","Youtube to text",
  "AI vocabulary","Calories counter","Number verification"},
 "AI Agents": {"Eliza Agent Core","Eliza AI Agent TG bot","aaapad chat agent","aaapad longevity agent","Pavel Agent core",
  "Gitbook Pavel support bot","MTProto Telegram","Tasks assistant","Talk back bot v2","Talk back bot","HH Agent",
  "Codex Agent Chat","Tagging test"},
 "Dev/RAG/Legacy": {"Codex cron","Edit PR in Codex","Github PR webhook","Gitbook update","PG RAG","Create task in airtable",
  "Get tasks airtable","Update task in airtable","Export tasks to text","add employees to crm","Check if calls in crm",
  "crm export to google","crm linkedin search and export","Export dialogues","Get Card Balance","mongo test","My workflow",
  "test python node"},
}
def cluster_of(n):
    for c, s in CLUSTERS.items():
        if n in s: return c
    return "Other"

active = sum(1 for p in prof if p["active"])
total_nodes = sum(p["node_count"] for p in prof)
total_runs = estat["total_executions"]
err_wfs = [r for r in estat["workflows"] if r["error"]]
webhook_ct = sum(len(deep.get(p["id"],{}).get("webhooks",[])) for p in prof)
sched_ct = sum(1 for p in prof if deep.get(p["id"],{}).get("schedules"))

TOOLISH = ("executeWorkflowTrigger" in "")  # placeholder
rows = []
for p in sorted(prof, key=lambda x:(cluster_of(x["name"]), not x["active"], x["name"].lower())):
    d = deep.get(p["id"], {})
    cl = cluster_of(p["name"])
    ex = ex_by_id.get(p["id"])
    runs = ex["runs"] if ex else 0
    err = ex["error"] if ex else 0
    last = (ex["last"][:10] if ex and ex["last"] else None)
    err_rate = ex["err_rate"] if ex else 0
    is_tool = "executeWorkflowTrigger" in p["triggers"]
    # classification
    if err and err_rate >= 50:
        status, scls = f"🔴 {runs}з / {err} err ({err_rate}%)", "err"
    elif err:
        status, scls = f"🟠 {runs}з / {err} err ({err_rate}%)", "flaky"
    elif not p["active"]:
        status, scls = "💤 спящий", "off"
    elif runs > 0:
        status, scls = f"✅ {runs}з · last {last}", "ok"
    elif is_tool:
        status, scls = "🔧 инструмент (не логир.)", "tool"
    else:
        status, scls = "⚠️ активен, 0 запусков", "warn"
    trg = ", ".join(p["triggers"][:3])
    sched = "; ".join(d.get("schedules",[]))[:60]
    svc = ", ".join(p["services"][:7])
    calls = len(d.get("calls",[])); called = len(d.get("called_by",[]))
    wh = len(d.get("webhooks",[]))
    flags = []
    if wh: flags.append(f"🌐{wh}wh")
    if d.get("telegram_chats"): flags.append("📌tg-id")
    rows.append({
      "cluster":cl,"name":p["name"],"active":p["active"],"status":status,"scls":scls,
      "nodes":p["node_count"],"trg":trg,"sched":sched,"svc":svc,
      "calls":calls,"called":called,"flags":" ".join(flags),"err":err,"runs":runs,"last":last,
    })

# usage ranking (real runs) + broken panel
top_use = sorted([r for r in rows if r["runs"]>0], key=lambda r:-r["runs"])[:12]
maxruns = max((r["runs"] for r in top_use), default=1)
broken = [(nm, info) for nm, info in why.items()]
broken.sort(key=lambda x:-x[1].get("error_count",0))

def esc(s): return html.escape(str(s))
clusters_order = ["CHARM CRM","Content/Summary","Audio/Media","AI Agents","Dev/RAG/Legacy","Other"]
cl_counts = {c: sum(1 for r in rows if r["cluster"]==c) for c in clusters_order}

import math
def ubar(n):
    if not n: return ""
    w = max(2, round(math.log10(n+1)/math.log10(maxruns+1)*100))
    return f'<div class=ub><span style="width:{w}%"></span></div><span class=un>{n}</span>'

tr_html = []
for r in rows:
    tr_html.append(f"""<tr data-cluster="{esc(r['cluster'])}" data-status="{r['scls']}">
<td><span class="cl cl-{esc(r['cluster'].split('/')[0])}">{esc(r['cluster'])}</span></td>
<td class="nm">{esc(r['name'])}</td>
<td class="st {r['scls']}">{esc(r['status'])}</td>
<td class="usg">{ubar(r['runs'])}</td>
<td class="num">{r['nodes']}</td>
<td>{esc(r['trg'])}{('<br><span class=sub>'+esc(r['sched'])+'</span>') if r['sched'] else ''}</td>
<td class="sub">{esc(r['svc'])}</td>
<td class="num">{('→'+str(r['calls'])+' ') if r['calls'] else ''}{('←'+str(r['called'])) if r['called'] else ''}</td>
<td class="fl">{r['flags']}</td></tr>""")

# usage panel rows
use_html = "".join(
    f'<div class=urow><span class=uname>{esc(r["name"])}</span>'
    f'<div class=ub><span style="width:{max(3,round(r["runs"]/maxruns*100))}%;background:{"#f85149" if r["err"] else "#3fb950"}"></span></div>'
    f'<span class=ucnt>{r["runs"]}{(" · "+str(r["err"])+"err") if r["err"] else ""}</span></div>'
    for r in top_use)
# broken panel rows
diag = {
 "Events Posting": "Python-нода: <code>name '_input' is not defined</code> — баг в коде. <b>100% падений</b>, каждый запуск (10/10).",
 "Gitbook Pavel support bot": "Postgres-память <code>Pavel Chat Memory1</code> валится (11% запусков). Агент жив, ломается слой памяти.",
 "Channel list reading and summary": "LLM <code>Text Classifier: Service unavailable</code> 503 — транзиентно. → включить авто-retry.",
 "Personal Audio Summary": "<code>OpenAI: connection aborted</code> 2 из 1435 (0.1%) — кратковременный сбой OpenAI, не баг.",
 "Eliza AI Agent TG bot": "<code>Send voice transcription: Bad request</code> 1 раз — редкая ошибка параметров Telegram.",
 "Audio to text flow": "<code>Send voice transcription: Bad request</code> 1 раз — редко.",
 "BD in Web3 Summary": "<code>reading 'messages' undefined</code> 1 раз — пустой источник (edge-case).",
 "Talk back bot v2": "<code>Telegram1: Bad request</code> 1 раз — редкая ошибка параметров.",
}
broken_html = "".join(
    f'<li><b>{esc(nm)}</b> <span class="badge {"bad" if info.get("error_count",0)>=5 else "warn"}">{info.get("error_count")}×</span> — {diag.get(nm,"см. лог")}</li>'
    for nm, info in broken)

html_doc = f"""<!DOCTYPE html><html lang=ru><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>n8n Automation Audit</title><style>
:root{{--bg:#0e1116;--card:#171c24;--bd:#262d38;--tx:#e6edf3;--mut:#8b949e;--acc:#58a6ff;
--ok:#3fb950;--warn:#d29922;--err:#f85149;--off:#6e7681;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);font-size:12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin:20px 0}}
.kpi{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px}}
.kpi .v{{font-size:26px;font-weight:700}}.kpi .l{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
.kpi.err .v{{color:var(--err)}}.kpi.ok .v{{color:var(--ok)}}
.bar{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}
.bar button{{background:var(--card);border:1px solid var(--bd);color:var(--tx);padding:6px 12px;border-radius:20px;cursor:pointer;font-size:12px}}
.bar button.on{{background:var(--acc);color:#04101f;border-color:var(--acc);font-weight:600}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--bd);border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--bd);vertical-align:top}}
th{{color:var(--mut);font-size:11px;text-transform:uppercase;position:sticky;top:0;background:#10151c;cursor:pointer}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}td.nm{{font-weight:600}}
td.sub,.sub{{color:var(--mut);font-size:12px}}
.st.ok{{color:var(--ok)}}.st.warn{{color:var(--warn)}}.st.err{{color:var(--err)}}.st.off{{color:var(--off)}}
.st.flaky{{color:#e3852a}}.st.tool{{color:#6ca0c4}}
.cl{{font-size:10px;padding:2px 7px;border-radius:20px;background:#21262d;white-space:nowrap}}
.cl-CHARM{{background:#1f2d3d;color:#79c0ff}}.cl-Content{{background:#2d2438;color:#d2a8ff}}
.cl-Audio{{background:#1f3329;color:#7ee787}}.cl-AI{{background:#3d2e1f;color:#ffa657}}.cl-Dev{{background:#33272a;color:#ff7b72}}
.fl{{font-size:11px;color:var(--warn)}}
td.usg{{width:120px}}.ub{{display:inline-block;width:80px;height:7px;background:#21262d;border-radius:4px;overflow:hidden;vertical-align:middle}}
.ub span{{display:block;height:100%;background:var(--acc)}}.un{{font-size:11px;color:var(--mut);margin-left:6px;font-variant-numeric:tabular-nums}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}}@media(max-width:760px){{.panels{{grid-template-columns:1fr}}}}
.panel{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 18px}}.panel h3{{margin:0 0 10px;font-size:14px}}
.urow{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px}}.uname{{flex:0 0 200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.urow .ub{{flex:1;width:auto}}.ucnt{{flex:0 0 70px;text-align:right;color:var(--mut);font-variant-numeric:tabular-nums}}
.note{{background:var(--card);border:1px solid var(--bd);border-left:3px solid var(--err);border-radius:8px;padding:14px 18px;margin:16px 0}}
.note h3{{margin:0 0 8px;font-size:14px}}.note ul{{margin:6px 0;padding-left:20px}}.note li{{margin:4px 0;font-size:13px}}
.badge{{font-size:10px;padding:1px 6px;border-radius:10px}}.badge.bad{{background:#3d1d1d;color:#ff7b72}}.badge.warn{{background:#3a3216;color:#e3b341}}
code{{background:#0c1117;padding:1px 5px;border-radius:4px;font-size:12px;color:#ffa657}}
</style></head><body><div class=wrap>
<h1>n8n Automation Stack — операционный аудит</h1>
<div class=sub>https://n8n.example.com · v2.14.2 · окно логов {WINDOW} · агентный движок за Platinum CRM</div>
<div class=kpis>
<div class=kpi><div class=v>{len(prof)}</div><div class=l>Workflows</div></div>
<div class="kpi ok"><div class=v>{active}</div><div class=l>Активных</div></div>
<div class=kpi><div class=v>{len(prof)-active}</div><div class=l>Спящих</div></div>
<div class=kpi><div class=v>{total_runs:,}</div><div class=l>Выполнений (10д)</div></div>
<div class="kpi err"><div class=v>{len(err_wfs)}</div><div class=l>С ошибками</div></div>
<div class=kpi><div class=v>{webhook_ct}</div><div class=l>Webhooks</div></div>
<div class=kpi><div class=v>{sched_ct}</div><div class=l>По расписанию</div></div>
</div>
<div class=panels>
<div class=panel><h3>🔥 Чаще всего используется (за 10 дней)</h3>{use_html}</div>
<div class=panel><h3>🔴 Ошибки — почему</h3><ul style="margin:0;padding-left:18px">{broken_html}</ul></div>
</div>
<div class=note><h3>⚙️ Что разобрать (кроме ошибок)</h3><ul>
<li><b>Codex cron</b> — активен с расписанием «каждую 1 мин», но <b>0 запусков</b> за 10 дней (должно быть ~14k) → молча НЕ срабатывает.</li>
<li><b>aaaZeroInbound (+DEV)</b> — активные Telegram-триггеры, <b>0 запусков</b> → боты не получают сообщения (токен/подключение); при этом Main Agent (опрос Mongo) крутится 413/день.</li>
<li><b>Простаивают активные боты</b>: Calories counter, AI vocabulary, Number verification, MTProto Telegram (1 запуск с 2025), Talk back bot v2 (стоп с 11 июня).</li>
<li><b>Неаутентифицированные webhook'и</b>: aaapad ×4 каждый, Inner Agent DELETE-эндпоинты · коллизия пути Multi Posting ↔ MTProto.</li>
<li><b>Дубли DEV/prod активны</b>: aaaZeroInbound, send_msg_to_lead_tool · мусор: mongo test, My workflow, test python node, HH Agent (76 нод спящий).</li>
<li><b>API-ключ Claude Code → n8n истекает 2026-07-15</b> — пересоздать бессрочный.</li>
</ul></div>
<div class=bar id=fbar>
<button class=on data-f=all>Все ({len(rows)})</button>
{''.join(f'<button data-f="cl:{esc(c)}">{esc(c)} ({cl_counts[c]})</button>' for c in clusters_order if cl_counts[c])}
<button data-f=st:err>🔴 сломано</button><button data-f=st:flaky>🟠 флапает</button><button data-f=st:ok>✅ работает</button><button data-f=st:warn>⚠️ 0 runs</button><button data-f=st:tool>🔧 инстр.</button><button data-f=st:off>💤 спящие</button>
</div>
<table id=t><thead><tr><th>Кластер</th><th>Workflow</th><th>Статус</th><th>Запусков</th><th>Ноды</th><th>Триггер</th><th>Сервисы</th><th>Связи</th><th>⚑</th></tr></thead>
<tbody>{''.join(tr_html)}</tbody></table>
<div class=sub style=margin-top:16px>Конспект: _n8n-Automation-Audit-MOC · сырьё: _imports\\n8n\\ ({total_runs:,} выполнений разобрано, 0 токенов)</div>
</div><script>
const bar=document.getElementById('fbar'),rows=[...document.querySelectorAll('#t tbody tr')];
bar.onclick=e=>{{if(e.target.tagName!='BUTTON')return;[...bar.children].forEach(b=>b.classList.remove('on'));e.target.classList.add('on');
const f=e.target.dataset.f;rows.forEach(r=>{{let show=f=='all'||(f.startsWith('cl:')&&r.dataset.cluster==f.slice(3))||(f.startsWith('st:')&&r.dataset.status==f.slice(3));r.style.display=show?'':'none';}});}};
// sortable: Запусков (3) and Ноды (4)
function sortCol(i){{const tb=document.querySelector('#t tbody');[...rows].sort((a,b)=>(parseInt(b.children[i].textContent)||0)-(parseInt(a.children[i].textContent)||0)).forEach(r=>tb.appendChild(r));}}
document.querySelectorAll('#t th')[3].onclick=()=>sortCol(3);
document.querySelectorAll('#t th')[4].onclick=()=>sortCol(4);
</script></body></html>"""
open(OUT, "w", encoding="utf-8").write(html_doc)
print("Wrote dashboard:", OUT, len(html_doc), "bytes,", len(rows), "rows,", len(err_wfs), "with errors")
