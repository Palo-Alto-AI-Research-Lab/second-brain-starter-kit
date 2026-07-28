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
Build a self-contained HTML spending/activity dashboard from the Pokupki import.

Sources:
  - pokupki-archive.jsonl  (48k msgs, full text for every message)
  - vault posts/*.md       (concept = category, via frontmatter msg_id -> concept)

Outputs (all UTF-8; ASCII-only stdout per the cp1252 gotcha):
  - %VAULT%\\_Dashboards\\Pokupki-Dashboard.html  (standalone, data embedded)
  - %IMPORTS%\\pokupki_dashboard.json                      (aggregations, reusable)
  - %IMPORTS%\\pokupki_prices.csv                          (row per detected price)
  - %IMPORTS%\\pokupki_dashboard_summary.txt               (human summary)

HONESTY MODEL: prices are CURRENCY-ANCHORED detections in free chat text. A number is
only counted if it is glued to a currency token (eur/евро/€/usd/$/руб/...). This filters
out phone numbers, SSNs, zoom ids, activation codes. It is a *signal of shopping volume*,
NOT a verified ledger of actual spend (research posts list several options/prices each).
"""
import re, json, statistics
from collections import defaultdict, Counter
from pathlib import Path

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback

IMP   = Path(IMPORTS)
VAULT = Path(VAULT)
POSTS = VAULT / "01-Conversations" / "Telegram" / "Pokupki" / "posts"
DASHDIR = VAULT / "_Dashboards"
DASHDIR.mkdir(parents=True, exist_ok=True)

rows = [json.loads(l) for l in (IMP / "pokupki-archive.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

# ---------------------------------------------------------------- category map
FM_MSGID   = re.compile(r'^msg_id:\s*(\d+)', re.M)
FM_CONCEPT = re.compile(r'^concept:\s*"?\[\[([^\]\|]+?)\]\]"?', re.M)
FM_NOTETYPE= re.compile(r'^note_type:\s*(\S+)', re.M)

msgid2concept = {}
post_files = 0
for fp in POSTS.glob("*.md"):
    post_files += 1
    head = fp.read_text(encoding="utf-8", errors="replace")[:1600]
    mid = FM_MSGID.search(head)
    con = FM_CONCEPT.search(head)
    if mid and con:
        c = con.group(1).strip()
        if c:
            msgid2concept[int(mid.group(1))] = c

LABELS = {
    'concept-home-goods': 'Дом и быт',
    'concept-garden-landscaping': 'Сад и ландшафт',
    'concept-groceries-food': 'Продукты и еда',
    'concept-travel-logistics': 'Путешествия и логистика',
    'concept-procurement-vendors': 'Закупки и поставщики',
    'concept-cars': 'Авто',
    'concept-construction-renovation': 'Стройка и ремонт',
    'concept-child-education': 'Дети и образование',
    'concept-medicine-health': 'Здоровье и медицина',
    'concept-tech-tools': 'Техника и инструменты',
    'concept-defi': 'DeFi / крипто',
}
def clabel(slug):
    if slug in LABELS: return LABELS[slug]
    return slug.replace('concept-', '').replace('-', ' ').strip().capitalize()

# ---------------------------------------------------------------- price parsing
CUR = {
    'eur':'EUR','euro':'EUR','euros':'EUR','евро':'EUR','евра':'EUR','eвро':'EUR','€':'EUR',
    'usd':'USD','dollar':'USD','dollars':'USD','долл':'USD','доллар':'USD','$':'USD',
    'gbp':'GBP','фунт':'GBP','£':'GBP',
    'rub':'RUB','руб':'RUB','рублей':'RUB','₽':'RUB',
}
NUM    = r'(\d{1,3}(?:[  .]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)'
CURTOK = r'(€|\$|£|₽|euros?|eur|евро|евра|usd|dollars?|долл(?:ар)?|gbp|фунт|рублей|руб|rub)'
RE_NC  = re.compile(NUM + r'\s{0,3}' + CURTOK, re.I)
RE_CN  = re.compile(CURTOK + r'\s{0,3}' + NUM, re.I)

def parse_num(s):
    s = s.strip().replace(' ', '').replace(' ', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')          # 1.234,56 -> 1234.56
    elif ',' in s:
        s = s.replace(',', '.') if re.search(r',\d{1,2}$', s) else s.replace(',', '')
    else:
        p = s.split('.')
        if len(p) > 2:                                     # 1.234.567
            s = ''.join(p)
        elif len(p) == 2 and len(p[1]) == 3:               # 1.660 -> thousands
            s = ''.join(p)
    try:
        return float(s)
    except ValueError:
        return None

def norm_cur(tok):
    t = tok.lower()
    if t in CUR: return CUR[t]
    return CUR.get(tok, None)

def extract_prices(text):
    out = []
    if not text: return out
    for rx, gi_num, gi_cur in ((RE_NC, 1, 2), (RE_CN, 2, 1)):
        for m in rx.finditer(text):
            v = parse_num(m.group(gi_num)); c = norm_cur(m.group(gi_cur))
            if v is not None and c and 0 < v < 1_000_000:
                out.append((round(v, 2), c))
    return out

# ---------------------------------------------------------------- vendors
RE_URL = re.compile(r'https?://([^/\s)]+)', re.I)
# non-shopping domains: link shorteners, search, chat, internal tools -> excluded from vendor chart
NON_VENDOR = ('goo.gl','google.','youtube','youtu.be','chatgpt','openai','t.me','telegram',
              'zoom.us','zoom.com','wa.me','whatsapp','bit.ly','tinyurl','trello','drive.google',
              'docs.google','maps.google','facebook','instagram','wikipedia','yadi.sk','disk.yandex')
VENDOR_CANON = [
    ('amazon','Amazon'),('amzn','Amazon'),('ebay','eBay'),('aliexpress','AliExpress'),('decathlon','Decathlon'),
    ('thule','Thule'),('ikea','IKEA'),('booking.','Booking'),('airbnb','Airbnb'),
    ('leroymerlin','Leroy Merlin'),('leroy','Leroy Merlin'),('worten','Worten'),
    ('continente','Continente'),('pingodoce','Pingo Doce'),('auchan','Auchan'),
    ('olx.','OLX'),('standvirtual','StandVirtual'),('litres','Litres'),('ozon','Ozon'),
    ('wildberries','Wildberries'),('wb.ru','Wildberries'),('etsy','Etsy'),('apple.','Apple'),
    ('zoom.us','Zoom'),('trello','Trello'),('youtube','YouTube'),('google.','Google'),
    ('temu','Temu'),('shein','SHEIN'),('fnac','Fnac'),('mediamarkt','MediaMarkt'),
    ('castorama','Castorama'),('kuantokusta','KuantoKusta'),('nutri-bay','Nutri-Bay'),
]
def canon_vendor(host):
    host = host.lower()
    if host.startswith('www.'): host = host[4:]
    for k, v in VENDOR_CANON:
        if k in host: return v
    parts = host.split('.')
    if len(parts) >= 3 and parts[-2] in ('com','co','org','net','gov','edu'):
        return '.'.join(parts[-3:])          # something.com.pt / shop.co.uk
    return '.'.join(parts[-2:]) if len(parts) >= 2 else host

def vendors(text):
    if not text: return []
    seen = []
    for m in RE_URL.finditer(text):
        host = m.group(1).lower()
        if any(bad in host for bad in NON_VENDOR):
            continue
        v = canon_vendor(host)
        if v not in seen:
            seen.append(v)
    return seen

# ---------------------------------------------------------------- aggregate
by_month = defaultdict(lambda: {"messages":0,"posts":0,"voice":0,"anton":0,
                                "eur_sum":0.0,"price_posts":0,"price_mentions":0})
origin_ct   = Counter()
cat_posts   = Counter()
cat_pricesum= defaultdict(float)
cat_pricecnt= Counter()
cat_eur_vals= defaultdict(list)
cur_ct      = Counter()
cur_sum     = defaultdict(float)
vendor_ct   = Counter()
eur_all     = []
csv_lines   = ["date,month,category,amount,currency,vendor,origin,author,msg_id"]
top_prices  = []   # (amount, cur, date, vendor, category, snippet, msg_id)
active_days = set()
voice_total = 0
posts_total = 0
price_posts_total = 0

def csv_esc(s):
    s = (str(s) if s is not None else "").replace('"', "'").replace("\n", " ").replace("\r", " ")
    return '"' + s + '"' if (',' in s or ';' in s) else s

for r in rows:
    month = (r.get("date") or "")[:7]
    if not month: continue
    by_month[month]["messages"] += 1
    if r.get("date"): active_days.add(r["date"])
    o = r.get("origin") or "external"
    origin_ct[o] += 1
    if o == "anton": by_month[month]["anton"] += 1
    if r.get("media_kind") == "voice":
        by_month[month]["voice"] += 1; voice_total += 1

    mid = r.get("id")
    concept = msgid2concept.get(mid)
    is_post = bool(r.get("knowledge"))
    if is_post:
        by_month[month]["posts"] += 1; posts_total += 1
        if concept: cat_posts[concept] += 1

    text = r.get("text") or ""
    prices = extract_prices(text)
    vs = vendors(text)
    for v in vs:
        vendor_ct[v] += 1

    if prices:
        if is_post:
            by_month[month]["price_posts"] += 1; price_posts_total += 1
        by_month[month]["price_mentions"] += len(prices)
        vlabel = vs[0] if vs else ""
        for (amt, cur) in prices:
            cur_ct[cur] += 1; cur_sum[cur] += amt
            if cur == "EUR":
                by_month[month]["eur_sum"] += amt
                eur_all.append(amt)
                if concept:
                    cat_pricesum[concept] += amt; cat_pricecnt[concept] += 1
                    cat_eur_vals[concept].append(amt)
                top_prices.append((amt, cur, r.get("date"), vlabel,
                                   clabel(concept) if concept else "—",
                                   re.sub(r'\s+', ' ', text)[:120], mid))
            csv_lines.append(",".join(csv_esc(x) for x in
                [r.get("date"), month, clabel(concept) if concept else "", amt, cur,
                 vlabel, o, r.get("from"), mid]))

months_sorted = sorted(by_month.keys())
def med(xs): return round(statistics.median(xs), 2) if xs else 0.0
def pct(xs, q):
    if not xs: return 0.0
    xs = sorted(xs); k = max(0, min(len(xs)-1, int(q*(len(xs)-1))))
    return round(xs[k], 2)

top_prices.sort(key=lambda t: t[0], reverse=True)

agg = {
    "meta": {
        "span": [months_sorted[0], months_sorted[-1]] if months_sorted else ["",""],
        "messages": len(rows),
        "active_days": len(active_days),
        "posts": posts_total,
        "voice_total": voice_total,
        "price_posts": price_posts_total,
        "post_files": post_files,
        "eur_median": med(eur_all),
        "eur_p25": pct(eur_all, .25),
        "eur_p75": pct(eur_all, .75),
        "eur_mentions": len(eur_all),
        "eur_sum": round(sum(eur_all), 2),
    },
    "months": months_sorted,
    "by_month": {m: by_month[m] for m in months_sorted},
    "origin": dict(origin_ct),
    "categories": [
        {"slug": s, "label": clabel(s), "posts": cat_posts[s],
         "eur_sum": round(cat_pricesum[s], 2), "eur_cnt": cat_pricecnt[s],
         "eur_median": med(cat_eur_vals[s])}
        for s in sorted(cat_posts, key=lambda s: cat_posts[s], reverse=True)
    ],
    "currencies": [{"cur": c, "count": cur_ct[c], "sum": round(cur_sum[c], 2)}
                   for c in sorted(cur_ct, key=lambda c: cur_ct[c], reverse=True)],
    "vendors": [{"vendor": v, "count": n} for v, n in vendor_ct.most_common(20)],
    "top_prices": [
        {"amount": a, "cur": c, "date": d, "vendor": ven, "category": cat, "snippet": sn, "msg_id": mid}
        for (a, c, d, ven, cat, sn, mid) in top_prices[:25]
    ],
}

(IMP / "pokupki_dashboard.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")
(IMP / "pokupki_prices.csv").write_text("\n".join(csv_lines), encoding="utf-8-sig")

# ---------------------------------------------------------------- HTML render
DATA_JSON = json.dumps(agg, ensure_ascii=False).replace("</", "<\\/")
HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Покупки — дашборд</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;
        --acc:#5b9bff;--acc2:#37d399;--acc3:#ffb454;--acc4:#ff6b8b;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
  header{padding:28px 28px 8px}
  h1{margin:0 0 4px;font-size:24px}
  .sub{color:var(--mut);font-size:13px;max-width:1100px}
  .wrap{padding:16px 28px 60px;max-width:1320px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0 22px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .kpi .n{font-size:24px;font-weight:700}
  .kpi .l{color:var(--mut);font-size:12px;margin-top:2px}
  .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;min-width:0}
  .card h3{margin:0 0 2px;font-size:15px}
  .card .cap{color:var(--mut);font-size:12px;margin:0 0 10px}
  .full{grid-column:1/-1}
  canvas{max-height:300px}
  .controls{margin:0 0 14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  select,button{background:#11141a;color:var(--ink);border:1px solid var(--line);
                border-radius:9px;padding:7px 11px;font-size:13px;cursor:pointer}
  button.on{border-color:var(--acc);color:#fff}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--mut);font-weight:600;cursor:pointer;user-select:none}
  td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  .tag{display:inline-block;background:#222834;border-radius:6px;padding:1px 7px;font-size:11px;color:var(--mut)}
  a{color:var(--acc);text-decoration:none}
  .note{background:#1c1207;border:1px solid #4a3413;color:#f4d6a6;border-radius:12px;
        padding:12px 16px;font-size:13px;margin:14px 0 0}
  @media(max-width:820px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>🛒 Покупки — дашборд расходов и активности</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="wrap">
  <div class="note">⚠️ <b>Цены — это сигнал, а не бухгалтерия.</b> Сумма берётся только из чисел, приклеенных к валюте
  (€/eur/евро/$/usd/руб) в свободном тексте чата — это отсекает телефоны, коды и ID, но research-посты часто перечисляют
  по несколько вариантов цен, поэтому «сумма упоминаний» завышает реальные траты. Голосовые директивы (<span id="vk"></span>)
  пока не транскрибированы — настоящие суммы там. Считай это нижней границей активности, не итоговым чеком.</div>

  <div class="kpis" id="kpis"></div>

  <div class="controls">
    <span style="color:var(--mut);font-size:13px">Год:</span>
    <span id="yearbtns"></span>
  </div>

  <div class="grid">
    <div class="card full">
      <h3>Активность по месяцам</h3>
      <p class="cap">Сообщений в чате и из них — атомарных заметок-покупок</p>
      <canvas id="activity"></canvas>
    </div>
    <div class="card full">
      <h3>Ценовой сигнал по месяцам (EUR)</h3>
      <p class="cap">Сумма всех упоминаний цен в евро · столбец = месяц</p>
      <canvas id="spend"></canvas>
    </div>
    <div class="card">
      <h3>Кто пишет</h3>
      <p class="cap">Распределение сообщений по ролям</p>
      <canvas id="roles"></canvas>
    </div>
    <div class="card">
      <h3>Валюта упоминаний</h3>
      <p class="cap">Сколько раз встречалась каждая валюта</p>
      <canvas id="currency"></canvas>
    </div>
    <div class="card">
      <h3>Категории покупок</h3>
      <p class="cap">Заметок-покупок по концепту (top-12)</p>
      <canvas id="cats"></canvas>
    </div>
    <div class="card">
      <h3>Топ площадок / вендоров</h3>
      <p class="cap">По числу ссылок в чате (top-15)</p>
      <canvas id="vendors"></canvas>
    </div>
    <div class="card full">
      <h3>Категории — таблица</h3>
      <p class="cap">Клик по заголовку — сортировка. «Медиана EUR» устойчивее суммы.</p>
      <table id="cattable"><thead><tr>
        <th data-k="label">Категория</th><th data-k="posts" class="num">Заметок</th>
        <th data-k="eur_cnt" class="num">Упом. цен</th><th data-k="eur_median" class="num">Медиана €</th>
        <th data-k="eur_sum" class="num">Σ упоминаний €</th>
      </tr></thead><tbody></tbody></table>
    </div>
    <div class="card full">
      <h3>Самые крупные упоминания цен (EUR)</h3>
      <p class="cap">Топ-25 по сумме · проверь глазами — крупные числа иногда per-kg или опечатки</p>
      <table id="toptable"><thead><tr>
        <th class="num">€</th><th>Дата</th><th>Вендор</th><th>Категория</th><th>Фрагмент</th>
      </tr></thead><tbody></tbody></table>
    </div>
  </div>
</div>
<script>
const DATA = __DATA__;
const C = {acc:'#5b9bff',acc2:'#37d399',acc3:'#ffb454',acc4:'#ff6b8b',mut:'#9aa4b2',line:'#262b35'};
const PALETTE=['#5b9bff','#37d399','#ffb454','#ff6b8b','#a78bfa','#4dd0e1','#f06292','#9ccc65','#ffd54f','#7986cb','#4db6ac','#ba68c8'];
Chart.defaults.color=C.mut; Chart.defaults.borderColor=C.line; Chart.defaults.font.family='Segoe UI,system-ui,sans-serif';
const fmt=n=>n.toLocaleString('ru-RU');
const eur=n=>'€'+Math.round(n).toLocaleString('ru-RU');

// ---- subtitle + KPIs
const M=DATA.meta;
document.getElementById('sub').textContent =
  `Источник: Telegram-чат «Покупки» · ${M.span[0]} → ${M.span[1]} · ${fmt(M.messages)} сообщений · `+
  `${fmt(M.active_days)} активных дней · сгенерировано Claude Code`;
document.getElementById('vk').textContent = fmt(M.voice_total)+' голосовых';
const ROLE_LABEL={anton:'Антон',Alina:'Алина',mixed:'Ассистенты',assistant:'Ассистенты',external:'Внешние'};
const kpis=[
  [fmt(M.messages),'сообщений всего'],
  [fmt(M.posts),'заметок-покупок'],
  [fmt(M.price_posts),'постов с ценой'],
  [eur(M.eur_median),'медиана цены (EUR)'],
  [fmt(M.eur_mentions),'упоминаний € цен'],
  [fmt(M.voice_total),'голосовых (не расшифр.)'],
  [DATA.categories[0]?DATA.categories[0].label:'—','топ-категория'],
  [DATA.vendors[0]?DATA.vendors[0].vendor:'—','топ-вендор'],
];
document.getElementById('kpis').innerHTML = kpis.map(k=>
  `<div class="kpi"><div class="n">${k[0]}</div><div class="l">${k[1]}</div></div>`).join('');

// ---- year filter
const years=[...new Set(DATA.months.map(m=>m.slice(0,4)))];
let curYear='all';
const yb=document.getElementById('yearbtns');
yb.innerHTML = ['all',...years].map(y=>
  `<button data-y="${y}" class="${y==='all'?'on':''}">${y==='all'?'Все':y}</button>`).join(' ');
yb.querySelectorAll('button').forEach(b=>b.onclick=()=>{
  curYear=b.dataset.y; yb.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));
  drawTime();
});
const monFilter=()=>DATA.months.filter(m=>curYear==='all'||m.startsWith(curYear));

// ---- charts
let actChart,spendChart;
function drawTime(){
  const ms=monFilter();
  const msgs=ms.map(m=>DATA.by_month[m].messages);
  const posts=ms.map(m=>DATA.by_month[m].posts);
  const spend=ms.map(m=>Math.round(DATA.by_month[m].eur_sum));
  if(actChart)actChart.destroy(); if(spendChart)spendChart.destroy();
  actChart=new Chart(document.getElementById('activity'),{type:'line',
    data:{labels:ms,datasets:[
      {label:'Сообщений',data:msgs,borderColor:C.acc,backgroundColor:'transparent',tension:.3,yAxisID:'y'},
      {label:'Заметок-покупок',data:posts,borderColor:C.acc2,backgroundColor:'transparent',tension:.3,yAxisID:'y1'}]},
    options:{responsive:true,interaction:{mode:'index',intersect:false},
      scales:{y:{position:'left',title:{display:true,text:'сообщения'}},
              y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'заметки'}}}}});
  spendChart=new Chart(document.getElementById('spend'),{type:'bar',
    data:{labels:ms,datasets:[{label:'Σ упоминаний € за месяц',data:spend,backgroundColor:C.acc3}]},
    options:{responsive:true,plugins:{tooltip:{callbacks:{label:c=>eur(c.raw)+' (сумма упоминаний)'}}},
      scales:{y:{title:{display:true,text:'EUR'}}}}});
}
drawTime();

const ro=DATA.origin; const roAgg={};
Object.keys(ro).forEach(k=>{const L=ROLE_LABEL[k]||k; roAgg[L]=(roAgg[L]||0)+ro[k];});
new Chart(document.getElementById('roles'),{type:'doughnut',
  data:{labels:Object.keys(roAgg),datasets:[{data:Object.values(roAgg),backgroundColor:PALETTE}]},
  options:{plugins:{legend:{position:'right'}}}});

new Chart(document.getElementById('currency'),{type:'doughnut',
  data:{labels:DATA.currencies.map(c=>c.cur),datasets:[{data:DATA.currencies.map(c=>c.count),backgroundColor:PALETTE}]},
  options:{plugins:{legend:{position:'right'}}}});

const cats=DATA.categories.slice(0,12);
new Chart(document.getElementById('cats'),{type:'bar',
  data:{labels:cats.map(c=>c.label),datasets:[{label:'заметок',data:cats.map(c=>c.posts),backgroundColor:C.acc}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}}}});

const vd=DATA.vendors.slice(0,15);
new Chart(document.getElementById('vendors'),{type:'bar',
  data:{labels:vd.map(v=>v.vendor),datasets:[{label:'ссылок',data:vd.map(v=>v.count),backgroundColor:C.acc2}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}}}});

// ---- tables
let csort={k:'posts',dir:-1};
function drawCat(){
  const rows=[...DATA.categories].sort((a,b)=>{
    const x=a[csort.k],y=b[csort.k];
    return (typeof x==='string'?x.localeCompare(y):x-y)*csort.dir;});
  document.querySelector('#cattable tbody').innerHTML=rows.map(c=>
    `<tr><td>${c.label}</td><td class="num">${fmt(c.posts)}</td><td class="num">${fmt(c.eur_cnt)}</td>
     <td class="num">${c.eur_median?eur(c.eur_median):'—'}</td><td class="num">${c.eur_sum?eur(c.eur_sum):'—'}</td></tr>`).join('');
}
document.querySelectorAll('#cattable th').forEach(th=>th.onclick=()=>{
  const k=th.dataset.k; csort.dir=(csort.k===k)?-csort.dir:-1; csort.k=k; drawCat();});
drawCat();

document.querySelector('#toptable tbody').innerHTML=DATA.top_prices.map(p=>
  `<tr><td class="num"><b>${eur(p.amount)}</b></td><td>${p.date||''}</td>
   <td>${p.vendor?'<span class="tag">'+p.vendor+'</span>':''}</td><td>${p.category}</td>
   <td>${p.snippet.replace(/</g,'&lt;')}</td></tr>`).join('');
</script>
</body>
</html>
"""
(DASHDIR / "Pokupki-Dashboard.html").write_text(HTML.replace("__DATA__", DATA_JSON), encoding="utf-8")

# ---------------------------------------------------------------- summary (UTF-8 file; ASCII stdout)
lines = []
lines.append("POKUPKI DASHBOARD — build summary")
lines.append(f"span {agg['meta']['span']}  messages {agg['meta']['messages']}  active_days {agg['meta']['active_days']}")
lines.append(f"post .md files scanned: {post_files}  | knowledge posts: {posts_total}  | with-concept: {len(msgid2concept)}")
lines.append(f"voice (not transcribed): {voice_total}  | posts with price: {price_posts_total}")
lines.append(f"EUR mentions: {len(eur_all)}  median {agg['meta']['eur_median']}  p25 {agg['meta']['eur_p25']}  p75 {agg['meta']['eur_p75']}  sum {agg['meta']['eur_sum']}")
lines.append("origin: " + ", ".join(f"{k}={v}" for k, v in origin_ct.most_common()))
lines.append("currencies: " + ", ".join(f"{c['cur']}={c['count']}(sum {c['sum']})" for c in agg["currencies"]))
lines.append("top categories: " + " | ".join(f"{c['label']}:{c['posts']}" for c in agg["categories"][:12]))
lines.append("top vendors: " + " | ".join(f"{v['vendor']}:{v['count']}" for v in agg["vendors"][:15]))
(IMP / "pokupki_dashboard_summary.txt").write_text("\n".join(lines), encoding="utf-8")

print("OK")
print("posts_scanned", post_files, "concepts", len(msgid2concept))
print("messages", len(rows), "voice", voice_total, "eur_mentions", len(eur_all))
print("html", str(DASHDIR / "Pokupki-Dashboard.html"))
