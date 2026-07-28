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
"""Build WhatsApp dashboard HTML from SQLite + export valuable named chats for summarization."""
import sqlite3, os, io, sys, json, html
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT=r"%IMPORTS%\whatsapp"; DB=os.path.join(OUT,"whatsapp_train.db")
DASH=r"%VAULT%\_Dashboards\WhatsApp-Dashboard.html"
con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; cur=con.cursor()

chats=[dict(r) for r in cur.execute("SELECT * FROM chats ORDER BY n DESC")]
tot_msg=cur.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
cats={}
for c in chats: cats[c["category"]]=cats.get(c["category"],0)+1

COLORS={"work/biz":"#4ea1ff","household":"#ffb24e","personal/dm":"#a06bff","group/other":"#5fd38a",
        "work-business":"#4ea1ff","household-community":"#ffb24e","family-personal":"#a06bff",
        "project-windmill":"#5fd38a","services-vendors":"#ff8f6b","crypto-web3":"#f6c945",
        "longevity-health":"#4ee0c0","other":"#888"}
rows=""
for c in chats:
    col=COLORS.get(c["category"],"#888")
    one=html.escape(c["one_line"] or "") if "one_line" in c.keys() and c["one_line"] else ""
    if c["named"]==1:                               # real resolved name
        nm=f'<span title="{one}">{html.escape(c["name"][:48])}</span>'
    elif c["named"]==2:                             # inferred from content
        nm=f'<span style="font-style:italic" title="✎ выведено из содержимого. {one}">✎ {html.escape(c["name"][:48])}</span>'
    else:                                           # still numeric
        nm=f'<span style="opacity:.45">{html.escape(c["name"][:30])}</span>'
    rows+=f'<tr data-cat="{c["category"]}" data-named="{c["named"]}"><td>{nm}</td>'\
          f'<td><span class="chip" style="background:{col}22;color:{col}">{c["category"]}</span></td>'\
          f'<td>{"G" if c["is_group"] else "DM"}</td><td class="n">{c["n"]}</td>'\
          f'<td class="n">{c["n_mine"]}</td><td class="d">{c["first"]}</td><td class="d">{c["last"]}</td></tr>\n'
catchips="".join(f'<span class="catchip" style="--c:{COLORS.get(k,"#888")}">{k}: {v}</span>' for k,v in sorted(cats.items(),key=lambda x:-x[1]))

HTML=f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>WhatsApp — Второй Мозг</title><style>
body{{background:#0b141a;color:#e9edef;font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:#8696a0;margin-bottom:16px}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}}
.kpi{{background:#202c33;border-radius:12px;padding:14px 18px;min-width:120px}}
.kpi b{{font-size:26px;display:block}}.kpi span{{color:#8696a0;font-size:12px}}
.catchip{{display:inline-block;background:#202c33;border-left:4px solid var(--c);padding:6px 12px;border-radius:6px;margin:0 8px 8px 0;font-size:13px}}
input,select{{background:#202c33;color:#e9edef;border:1px solid #2a3942;border-radius:8px;padding:8px 12px;font-size:13px}}
table{{width:100%;border-collapse:collapse;margin-top:14px;background:#111b21;border-radius:12px;overflow:hidden}}
th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #1f2c33}}th{{color:#8696a0;font-size:12px;text-transform:uppercase;cursor:pointer}}
td.n,td.d{{text-align:right;color:#8696a0;font-variant-numeric:tabular-nums}}
.chip{{padding:2px 8px;border-radius:10px;font-size:11px}}tr:hover{{background:#182229}}
.bar{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
</style></head><body>
<h1>📱 WhatsApp — тренировочная выгрузка</h1>
<div class="sub">Живой мост (вариант А) · только текст · {len(chats)} чатов · {tot_msg} сообщений · обновлено вручную</div>
<div class="kpis">
<div class="kpi"><b>{len(chats)}</b><span>чатов</span></div>
<div class="kpi"><b>{tot_msg}</b><span>сообщений</span></div>
<div class="kpi"><b>{sum(c['n_mine'] for c in chats)}</b><span>моих</span></div>
<div class="kpi"><b>{sum(1 for c in chats if c['named']==1)}</b><span>реальных имён</span></div>
<div class="kpi"><b>{sum(1 for c in chats if c['named']==2)}</b><span>✎ выведено</span></div>
</div>
<div>{catchips}</div>
<div class="bar"><input id="q" placeholder="🔍 фильтр по имени..." oninput="f()">
<select id="cat" onchange="f()"><option value="">все категории</option>{"".join(f'<option>{k}</option>' for k in cats)}</select>
<label style="color:#8696a0"><input type="checkbox" id="named" onchange="f()"> только названные (real+✎)</label></div>
<table id="t"><thead><tr><th onclick="srt(0)">Чат</th><th onclick="srt(1)">Категория</th><th>Тип</th>
<th onclick="srt(3)" class="n">Сообщ.</th><th onclick="srt(4)" class="n">Мои</th><th class="d">С</th><th class="d">По</th></tr></thead>
<tbody>{rows}</tbody></table>
<script>
function f(){{let q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('cat').value,n=document.getElementById('named').checked;
document.querySelectorAll('#t tbody tr').forEach(r=>{{let ok=r.cells[0].innerText.toLowerCase().includes(q)&&(!c||r.dataset.cat==c)&&(!n||r.dataset.named!='0');r.style.display=ok?'':'none';}});}}
function srt(i){{let tb=document.querySelector('#t tbody'),rs=[...tb.rows];let num=i>=3;
rs.sort((a,b)=>num?(+b.cells[i].innerText||0)-(+a.cells[i].innerText||0):a.cells[i].innerText.localeCompare(b.cells[i].innerText));
rs.forEach(r=>tb.appendChild(r));}}
</script></body></html>"""
os.makedirs(os.path.dirname(DASH),exist_ok=True)
open(DASH,"w",encoding="utf-8").write(HTML)
print("Dashboard ->", DASH)

# export valuable named chats (named=1, n>=20) for summarization
val=[dict(r) for r in cur.execute("SELECT * FROM chats WHERE named=1 AND n>=20 ORDER BY n DESC")]
exp=[]
for c in val:
    msgs=cur.execute("SELECT from_me,sender,ts,text FROM messages WHERE chat_jid=? AND text IS NOT NULL AND text!='' ORDER BY ts",(c["jid"],)).fetchall()
    lines=[f'[{m["ts"][:16]}] {"Я" if m["from_me"] else m["sender"]}: {m["text"]}' for m in msgs]
    exp.append({"name":c["name"],"jid":c["jid"],"category":c["category"],"is_group":c["is_group"],
                "n":c["n"],"span":f'{c["first"]}->{c["last"]}',"text":"\n".join(lines)})
json.dump(exp, open(os.path.join(OUT,"valuable_chats.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Exported {len(exp)} valuable named chats -> valuable_chats.json")
for c in exp: print(f"  {c['name'][:40]:40} {c['category']:12} msgs={c['n']}")
con.close()
