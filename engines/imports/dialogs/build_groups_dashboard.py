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
"""build_groups_dashboard.py -- self-contained visual dashboard over chats.db.

Anton works by eye: browse/filter every Telegram group -- per account, ours-vs-theirs,
topic, activity, and (when present) the LLM sub-classification. One static HTML, no
server, opens in a browser. Re-run after any rebuild. AK-47: stdlib only.
"""
import sqlite3, os, json, io, html

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
OUT = r"%VAULT%\_Dashboards\Telegram-Groups.html"


def main():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS group_class(
        chat_id INTEGER PRIMARY KEY, what TEXT, value TEXT, value_why TEXT,
        extract TEXT, origin TEXT, notable TEXT)""")
    rows = con.execute("""
        SELECT g.chat_id, g.name, g.link, g.type, g.members_count,
               g.origin, g.topic, g.n_our_accounts,
               (SELECT GROUP_CONCAT(DISTINCT ca.account_username)
                  FROM chat_accounts ca WHERE ca.chat_id=g.chat_id),
               gd.latest_ts, gd.n_text_msgs,
               gc.what, gc.value, gc.value_why, gc.extract, gc.origin, gc.notable
        FROM groups g
        LEFT JOIN group_digest gd ON gd.chat_id=g.chat_id
        LEFT JOIN group_class gc ON gc.chat_id=g.chat_id
    """).fetchall()
    con.close()

    data = []
    for (cid, name, link, typ, mc, origin, topic, nour, accts, ts, nmsg,
         what, value, vwhy, extract, corigin, notable) in rows:
        data.append({
            "id": cid, "n": name or "", "l": link or "", "t": typ or "",
            "mc": mc or 0, "o": (corigin or origin or ""), "tp": topic or "",
            "ac": accts or "", "act": ts or 0, "nm": nmsg or 0,
            "w": what or "", "v": value or "", "vw": vwhy or "",
            "ex": extract or "", "nt": notable or "",
        })

    n_total = len(data)
    n_class = sum(1 for d in data if d["w"])
    accs = {}
    for d in data:
        for a in (d["ac"].split(",") if d["ac"] else []):
            accs[a] = accs.get(a, 0) + 1
    topacc = sorted(accs.items(), key=lambda x: -x[1])[:12]
    n_theirs = sum(1 for d in data if d["o"] == "theirs")
    n_ours = sum(1 for d in data if str(d["o"]).startswith("ours") or d["o"] == "ours")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    accopts = "".join('<option value="%s">%s (%d)</option>' % (html.escape(a), html.escape(a), n)
                      for a, n in topacc)

    page = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Telegram Groups</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--bd:#262b36;--fg:#e6e9ef;--mut:#8b94a7;--hi:#5b9cff;--hot:#ff6b6b;--warm:#ffb454;--cool:#3ecf8e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,Segoe UI,Arial}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--mut);font-size:12px}
.wrap{padding:16px;max-width:1500px;margin:0 auto}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
.stat{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:8px 12px;min-width:110px}
.stat b{font-size:20px;display:block}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0;align-items:center}
input,select{background:var(--card);border:1px solid var(--bd);color:var(--fg);border-radius:8px;padding:7px 9px;font-size:13px}
input#q{flex:1;min-width:240px}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--bd);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;cursor:pointer;position:sticky;top:0;background:var(--bg)}
td.nm{max-width:330px}td.w{max-width:380px;color:var(--mut)}
a{color:var(--hi);text-decoration:none}a:hover{text-decoration:underline}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:6px;border:1px solid var(--bd);color:var(--mut);margin-right:3px}
.v-high{color:var(--cool);font-weight:600}.v-med{color:var(--warm)}.v-low{color:var(--mut)}
.o-theirs{color:var(--hot)}.o-ours{color:var(--hi)}
.mut{color:var(--mut)}.right{text-align:right}
</style></head><body><div class="wrap">
<h1>Telegram Groups -- карта чатов</h1>
<div class="sub">Источник: дамп CRM tg_entities + chats.jsonl. Поиск/фильтр локально, 0 запросов.</div>
<div class="stats">
<div class="stat"><b>__NTOTAL__</b>всего чатов</div>
<div class="stat"><b>__NTHEIRS__</b><span class="o-theirs">чужие</span></div>
<div class="stat"><b>__NOURS__</b><span class="o-ours">наши</span></div>
<div class="stat"><b>__NCLASS__</b>разобрано LLM</div>
</div>
<div class="filters">
<input id="q" placeholder="поиск по названию / описанию / людям...">
<select id="acc"><option value="">— аккаунт —</option>__ACCOPTS__</select>
<select id="ori"><option value="">— наши/чужие —</option><option value="theirs">чужие</option><option value="ours">наши</option></select>
<select id="tp"><option value="">— тема —</option></select>
<select id="val"><option value="">— ценность —</option><option value="high">high</option><option value="med">med</option><option value="low">low</option></select>
<label class="mut"><input type="checkbox" id="alive"> только с активностью</label>
<span class="mut" id="cnt"></span>
</div>
<table><thead><tr>
<th data-k="n">Группа</th><th data-k="o">тип</th><th data-k="tp">тема</th>
<th data-k="mc" class="right">чел.</th><th data-k="ac">аккаунты</th>
<th data-k="v">ценность</th><th data-k="w">что это / что взять</th><th data-k="act" class="right">актив.</th>
</tr></thead><tbody id="tb"></tbody></table>
</div>
<script>
const D=__PAYLOAD__;
const tb=document.getElementById('tb'),cnt=document.getElementById('cnt');
const tps=[...new Set(D.map(d=>d.tp).filter(Boolean))].sort();
const tpsel=document.getElementById('tp');tps.forEach(t=>{let o=document.createElement('option');o.value=t;o.textContent=t;tpsel.appendChild(o)});
let sortK='act',sortDir=-1;
function fdate(ts){if(!ts)return '';const d=new Date(ts*1000);return d.toISOString().slice(0,10)}
function row(d){
 const link=d.l?`<a href="${d.l}" target="_blank">${esc(d.n)}</a>`:esc(d.n);
 const oc=d.o==='theirs'?'o-theirs':(d.o&&d.o.indexOf('ours')==0?'o-ours':'mut');
 const vc=d.v?('v-'+d.v):'';
 const w=d.w?esc(d.w):'';const ex=d.ex?` <span class="tag">${esc(d.ex)}</span>`:'';
 const nt=d.nt?`<div class="mut" style="font-size:11px">${esc(d.nt)}</div>`:'';
 const idline=`<div class="mut" style="font-size:11px">id ${d.id}</div>`;
 return `<tr><td class="nm">${link}${idline}</td><td class="${oc}">${esc(d.o||'')}</td>
 <td class="mut">${esc(d.tp)}</td><td class="right">${d.mc||''}</td>
 <td class="mut" style="font-size:11px">${esc(d.ac)}</td>
 <td class="${vc}">${d.v||''}<div class="mut" style="font-size:11px">${esc(d.vw)}</div></td>
 <td class="w">${w}${ex}${nt}</td><td class="right mut">${fdate(d.act)}<div style="font-size:11px">${d.nm||''} msg</div></td></tr>`;
}
function esc(s){s=s==null?'':(''+s);return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){
 const q=document.getElementById('q').value.toLowerCase().trim();
 const acc=document.getElementById('acc').value,ori=document.getElementById('ori').value;
 const tp=document.getElementById('tp').value,val=document.getElementById('val').value;
 const alive=document.getElementById('alive').checked;
 let r=D.filter(d=>{
  if(acc&&(!d.ac||d.ac.split(',').indexOf(acc)<0))return false;
  if(ori==='theirs'&&d.o!=='theirs')return false;
  if(ori==='ours'&&!(d.o&&d.o.indexOf('ours')==0||d.o==='ours'))return false;
  if(tp&&d.tp!==tp)return false;
  if(val&&d.v!==val)return false;
  if(alive&&!d.act)return false;
  if(q&&!((d.n+' '+d.w+' '+d.nt+' '+d.vw).toLowerCase().includes(q)))return false;
  return true;});
 r.sort((a,b)=>{let x=a[sortK],y=b[sortK];if(typeof x==='string')x=x.toLowerCase(),y=(''+y).toLowerCase();return x<y?-sortDir:x>y?sortDir:0});
 cnt.textContent=r.length+' / '+D.length;
 tb.innerHTML=r.slice(0,1200).map(row).join('');
}
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortK===k)sortDir*=-1;else{sortK=k;sortDir=(k==='n'||k==='o'||k==='tp')?1:-1}render()});
['q','acc','ori','tp','val','alive'].forEach(id=>document.getElementById(id).addEventListener('input',render));
render();
</script></body></html>"""

    page = (page.replace("__NTOTAL__", str(n_total)).replace("__NTHEIRS__", str(n_theirs))
            .replace("__NOURS__", str(n_ours)).replace("__NCLASS__", str(n_class))
            .replace("__ACCOPTS__", accopts).replace("__PAYLOAD__", payload))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(page)
    print("DASHBOARD OK -> %s" % OUT)
    print("  rows=%d  classified=%d  theirs=%d  ours=%d" % (n_total, n_class, n_theirs, n_ours))


if __name__ == "__main__":
    main()
