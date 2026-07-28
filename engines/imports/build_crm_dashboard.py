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
"""Platinum CRM funnel dashboard -> _Dashboards/Platinum-CRM-Dashboard.html (self-contained, Chart.js CDN)."""
import csv, json, io, os, re, glob
from collections import Counter, defaultdict
csv.field_size_limit(1<<30)
EXP=r"C:$HOME/!CLAUDE-HP17 May26/crm_export"
OUT=r"E:/Obsidian/Owner-Knowledge/_Dashboards"; os.makedirs(OUT,exist_ok=True)
CARDS=r"E:/Obsidian/Owner-Knowledge/04-Projects/crypto/Platinum-CRM/leads"

INV=("INVESTOR","VC / Angel / Investor","Подозрение на инвестора")
tier_c=Counter(); status_c=Counter(); op_c=Counter(); month_c=Counter()
tag_c=Counter(); camp_c=Counter()
tot=users=live=qualified=intro=alloc=with_card=0
CAMP=re.compile(r'(pitch|offer|newsletter|linkedin|blurb|happy_new_year|auto pitch|CRM OFFER|CHARM|fundrais)',re.I)

with io.open(EXP+"/contacts.csv",encoding="utf-8-sig",newline="") as fh:
    r=csv.reader(fh); H={c:i for i,c in enumerate(next(r))}
    for row in r:
        tot+=1
        if row[H["telegram_type"]]!="user": continue
        users+=1
        islive=(row[H["active"]]=="True" and row[H["deleted"]]!="True" and row[H["deactivated"]]!="True")
        if not islive: continue
        live+=1
        t=row[H["tags_str"]]
        tl=[]
        if any(k in t for k in INV): tl.append("investor")
        if "Project/Founder" in t: tl.append("founder")
        if "KOL" in t: tl.append("kol")
        if "B2B" in t: tl.append("b2b")
        prim=tl[0] if tl else ("not_investor" if "Not investor" in t else "other")
        tier_c[prim]+=1
        if tl: qualified+=1
        if "INTRO from us" in t: intro+=1
        if "allocation was proposed" in t: alloc+=1
        for x in re.split(r"[;,|]",t):
            x=x.strip()
            if x: tag_c[x]+=1
            if x and CAMP.search(x): camp_c[x]+=1
        a=row[H["assigned"]].strip("[]")
        for o in a.split(","):
            o=o.strip()
            if o: op_c[o]+=1
        c=row[H["created_at"]][:7]
        if c and c[0].isdigit(): month_c[c]+=1

# card statuses (funnel outcome)
for f in glob.glob(CARDS+"/**/*.md",recursive=True):
    m=re.search(r'status:\s*"([^"]*)"',io.open(f,encoding="utf-8").read())
    if m: status_c[m.group(1)]+=1
    with_card+=1

partners=status_c.get("partner",0)+status_c.get("won",0)
data=dict(
 kpis=dict(total=tot,users=users,live=live,qualified=qualified,with_card=with_card,
           intro=intro,alloc=alloc,partners=partners,
           investors=tier_c.get("investor",0),founders=tier_c.get("founder",0)),
 funnel=[["Живые лиды",live],["Квалифицированы",qualified],["В работе (карточка)",with_card],
         ["INTRO от нас",intro],["Предложена аллокация",alloc],["Партнёры/закрыты",partners]],
 tiers=[[k,tier_c[k]] for k in ("investor","founder","kol","b2b","not_investor","other") if tier_c.get(k)],
 status=status_c.most_common(),
 operators=op_c.most_common(15),
 campaigns=camp_c.most_common(14),
 months=sorted(month_c.items()),
 toptags=tag_c.most_common(25),
)
HTML=r"""<!doctype html><html lang=ru><head><meta charset=utf-8>
<title>Platinum CRM — Воронка</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
h1{font-weight:600;margin:0 0 4px}.sub{color:#9aa0a6;font-size:13px;margin-bottom:18px}
.wrap{max-width:1180px;margin:0 auto;padding:24px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:22px}
.kpi{background:#1a1d24;border:1px solid #262a33;border-radius:12px;padding:14px}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{color:#9aa0a6;font-size:12px;margin-top:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:#1a1d24;border:1px solid #262a33;border-radius:12px;padding:16px;margin-bottom:16px}
.card h3{margin:0 0 10px;font-size:14px;font-weight:600;color:#c9cdd3}
.full{grid-column:1/3}table{width:100%;border-collapse:collapse;font-size:13px}
td,th{text-align:left;padding:4px 8px;border-bottom:1px solid #23262e}th{color:#9aa0a6}
.accent{color:#8ab4f8}
</style></head><body><div class=wrap>
<h1>Platinum CRM — воронка фандрейзинга</h1>
<div class=sub id=sub></div>
<div class=kpis id=kpis></div>
<div class=card full><h3>Воронка</h3><canvas id=funnel height=90></canvas></div>
<div class=grid>
<div class=card><h3>По тиру (квалификация)</h3><canvas id=tiers></canvas></div>
<div class=card><h3>Статусы карточек</h3><canvas id=status></canvas></div>
<div class=card><h3>Топ операторы (назначено сущностей)</h3><canvas id=ops></canvas></div>
<div class=card><h3>Кампании</h3><canvas id=camp></canvas></div>
</div>
<div class=card full><h3>Заведение лидов по месяцам</h3><canvas id=months height=70></canvas></div>
<div class=card full><h3>Топ-25 тегов CRM</h3><table id=tags><tr><th>Тег</th><th>Кол-во</th></tr></table></div>
</div>
<script>const D=__DATA__;
const K=D.kpis;document.getElementById('sub').textContent=`Сущностей: ${K.total.toLocaleString()} · живых лидов: ${K.live.toLocaleString()} · карточек: ${K.with_card.toLocaleString()} · сборка ${new Date().toISOString().slice(0,10)}`;
const kp=[['Живые лиды',K.live],['Инвесторы',K.investors],['Фаундеры',K.founders],['INTRO от нас',K.intro],['Аллокация',K.alloc],['Партнёры/закрыты',K.partners],['Квалифицированы',K.qualified],['В работе',K.with_card],['Всего сущностей',K.total],['Юзеров',K.users]];
document.getElementById('kpis').innerHTML=kp.map(x=>`<div class=kpi><div class=v>${x[1].toLocaleString()}</div><div class=l>${x[0]}</div></div>`).join('');
const c1='#8ab4f8',gr='#2a2e37';Chart.defaults.color='#9aa0a6';Chart.defaults.borderColor=gr;
new Chart(funnel,{type:'bar',data:{labels:D.funnel.map(x=>x[0]),datasets:[{data:D.funnel.map(x=>x[1]),backgroundColor:c1}]},options:{indexAxis:'y',plugins:{legend:{display:false}}}});
new Chart(tiers,{type:'doughnut',data:{labels:D.tiers.map(x=>x[0]),datasets:[{data:D.tiers.map(x=>x[1]),backgroundColor:['#8ab4f8','#81c995','#fdd663','#f28b82','#9aa0a6','#c58af9']}]}});
new Chart(status,{type:'bar',data:{labels:D.status.map(x=>x[0]),datasets:[{data:D.status.map(x=>x[1]),backgroundColor:'#81c995'}]},options:{plugins:{legend:{display:false}}}});
new Chart(ops,{type:'bar',data:{labels:D.operators.map(x=>x[0]),datasets:[{data:D.operators.map(x=>x[1]),backgroundColor:'#fdd663'}]},options:{indexAxis:'y',plugins:{legend:{display:false}}}});
new Chart(camp,{type:'bar',data:{labels:D.campaigns.map(x=>x[0].slice(0,28)),datasets:[{data:D.campaigns.map(x=>x[1]),backgroundColor:'#c58af9'}]},options:{indexAxis:'y',plugins:{legend:{display:false}}}});
new Chart(months,{type:'line',data:{labels:D.months.map(x=>x[0]),datasets:[{data:D.months.map(x=>x[1]),borderColor:c1,backgroundColor:'rgba(138,180,248,.15)',fill:true,tension:.3}]},options:{plugins:{legend:{display:false}}}});
document.getElementById('tags').innerHTML+=D.toptags.map(x=>`<tr><td>${x[0].replace(/</g,'&lt;')}</td><td class=accent>${x[1].toLocaleString()}</td></tr>`).join('');
</script></body></html>"""
open(OUT+"/Platinum-CRM-Dashboard.html","w",encoding="utf-8").write(HTML.replace("__DATA__",json.dumps(data,ensure_ascii=False)))
print("dashboard written:",OUT+"/Platinum-CRM-Dashboard.html")
print("KPIs:",data["kpis"])
