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
r"""build_pipeline_dashboard.py — /pipeline as a visual kanban.

Read-only over the watcher's live state (tg_followups.json). Classifies every
pending lead into TODAY's-action lanes (same logic as the /pipeline skill) and
writes a self-contained HTML dashboard. Outbound stays draft->approve in Telegram;
this is the EYES-view of the funnel, it sends nothing.

  python build_pipeline_dashboard.py            # -> _Dashboards\Pipeline-Dashboard.html
"""
import json, html, datetime, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback

SRC = Path(IMPORTS) / "tg_followups.json"
OUT = Path(VAULT) / "_Dashboards" / "Pipeline-Dashboard.html"
NOW = datetime.datetime.now()

def parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(s)[:len(fmt) + 2], fmt)
        except Exception:
            pass
    return None

def hours_since(dt):
    return None if dt is None else round((NOW - dt).total_seconds() / 3600)

# ---- lanes (priority order = the skill's order) ------------------------------
LANES = [
    ("hot",    "🔥 Ответили — мяч у нас",     "Лид ответил, ход наш. Продажному — Calendly; инженеру из комьюнити — предметный ответ.", "--acc4"),
    ("nudge",  "⏰ Напомнить забронировать",   "Calendly ушёл ≥24ч назад, слот не взят. Действие: booking_nudge_text.", "--acc3"),
    ("booking","⏳ Бронь отправлена — ждём слот", "Попросили выбрать слот, ждём подтверждения от лида.", "--acc"),
    ("await",  "👀 Ждём ответа",               "Питч ушёл, ответа ещё нет. Действие: проверить новые входящие.", "--mut2"),
    ("cold",   "📇 Ещё не касались",          "Касаний НЕ БЫЛО ни одного. Не путать с «ждём ответа».", "--mut2"),
    ("booked", "✅ Забронировано",             "Встреча подтверждена. Не пинговать, закрыть.", "--acc2"),
]
DRAFT_KEY = {"hot": "calendly_text", "nudge": "booking_nudge_text"}

# Anton's two-step rule: after this many days of THEIR silence we stop, we do not nudge.
SILENCE_STOP_DAYS = 7

def classify(lead, data):
    booking_confirmed = bool(lead.get("booking_confirmed"))
    booked = bool(lead.get("booked"))
    replied = bool(lead.get("replied"))
    calendly = bool(lead.get("calendly_sent"))
    pitch = bool(lead.get("pitch_sent"))
    if booking_confirmed:
        return "booked"
    if booked:  # booking msg sent, slot not confirmed yet
        return "booking"
    if replied and not calendly:
        return "hot"
    if calendly and not booked and not booking_confirmed:
        return "nudge"
    if pitch:
        return "await"
    # Never touched at all -> its own lane. Showing these as "ждём ответа" is exactly the
    # lie the 2026-07-17 kambulov incident produced: a lead we never wrote to looked contacted.
    return "cold"

def tg_link(lead):
    u = lead.get("username")
    return f"https://t.me/{u}" if u else None

def card_html(lead, lane, data):
    name = html.escape(str(lead.get("lead", "—")))
    u = lead.get("username")
    chat_id = lead.get("chat_id", "")
    link = tg_link(lead)
    handle = f'<a href="{link}" target="_blank">@{html.escape(str(u))}</a>' if u else f'<span class="mut">id {chat_id}</span>'
    angle = lead.get("angle")
    replied = lead.get("replied")
    booked = lead.get("booked")
    # the proposed draft for this lane -- but NEVER a Calendly draft for a lead marked
    # no_calendly (community engineers): a slot-link to them reads as a sales blast.
    draft = ""
    dk = DRAFT_KEY.get(lane)
    if dk and data.get(dk):
        draft = data[dk]
    no_calendly = bool(lead.get("no_calendly"))
    if no_calendly and dk == "calendly_text":
        draft = ""
    # age line for calendly-sent leads
    age_line = ""
    key = f"{(u or name).split()[0]}_{chat_id}"
    sent_at = data.get("calendly_sent_at", {}).get(f"{name.split()[0]}_{chat_id}") or \
              data.get("calendly_sent_at", {}).get(key)
    h = hours_since(parse_dt(sent_at)) if sent_at else None
    if h is not None:
        age_line = f'<div class="meta">Calendly отправлен <b>{h} ч</b> назад</div>'
    bits = [f'<div class="lead">{name}</div>', f'<div class="handle">{handle}</div>']
    if angle:
        bits.append(f'<div class="meta">🎯 {html.escape(str(angle))}</div>')
    # WHO OWES THE NEXT MOVE. "ждём ответа" hid a lead who had answered 10 days ago
    # (arseniy-sp, 2026-07-17) -- so the ball is now shown, not inferred from the lane.
    if lead.get("ball") == "us":
        bits.append('<div class="ball-us">🔴 мяч у нас — ход наш, лид уже ответил</div>')
    # PROOF that the touch exists in a live thread (message_id), or an honest "not verified".
    lt = lead.get("last_touch")
    ver = lead.get("verified")
    if ver:
        bits.append(f'<div class="meta ok">✅ касание подтверждено: {html.escape(str(ver))}'
                    + (f' · {html.escape(str(lt))}' if lt else '') + '</div>')
    elif lead.get("pitch_sent"):
        bits.append('<div class="meta warn">⚠️ касание НЕ подтверждено живым тредом — считать попыткой</div>')
    else:
        bits.append('<div class="meta dim">— касаний не было</div>')
    if lead.get("history"):
        bits.append(f'<div class="meta dim">🧾 {html.escape(str(lead["history"]))}</div>')
    if replied:
        bits.append(f'<div class="reply">💬 {html.escape(str(replied))}</div>')
    # Two-step rule: their silence for 7+ days means STOP, not "nudge harder".
    days = None
    if lt and lead.get("ball") != "us":
        dt = parse_dt(lt)
        if dt:
            days = (NOW - dt).days
    if days is not None and days >= SILENCE_STOP_DAYS:
        bits.append(f'<div class="stop">🚫 молчит {days} дн. — НЕ дожимать. '
                    f'Следующий повод = новый артефакт, не пинг</div>')
    elif days is not None:
        bits.append(f'<div class="meta dim">⏳ тишина {days} дн. из {SILENCE_STOP_DAYS} до стоп-правила</div>')
    if no_calendly:
        bits.append('<div class="meta dim">⛔ без Calendly: сначала предметный диалог '
                    '(двухшаговый паттерн Антона)</div>')
    if booked and lane != "booked":
        bits.append(f'<div class="meta">📅 {html.escape(str(booked))}</div>')
    if lane == "booked" and booked:
        bits.append(f'<div class="reply ok">✅ {html.escape(str(booked))}</div>')
    bits.append(age_line)
    if draft:
        d = html.escape(draft)
        bits.append(f'<div class="draft" title="клик — скопировать черновик" '
                    f'onclick="navigator.clipboard.writeText(this.dataset.t);this.classList.add(\'copied\')" '
                    f'data-t="{d}">✍️ {d}<span class="cp"> ⧉ copy</span></div>')
    if lane in ("await", "cold") or lead.get("ball") == "us":
        chk = lead.get("check", "")
        if chk:
            bits.append(f'<div class="meta dim">проверить: {html.escape(chk[:240])}</div>')
    return f'<div class="pcard">{"".join(b for b in bits if b)}</div>'

def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    pending = data.get("pending", [])
    buckets = {k: [] for k, *_ in LANES}
    for lead in pending:
        buckets[classify(lead, data)].append(lead)

    cols = []
    for key, title, cap, color in LANES:
        leads = buckets[key]
        cards = "".join(card_html(l, key, data) for l in leads) or '<div class="empty">— пусто —</div>'
        cols.append(f'''<div class="lane">
      <div class="lane-h" style="border-color:var({color})">
        <span class="lane-t">{html.escape(title)}</span><span class="lane-n">{len(leads)}</span>
      </div>
      <div class="lane-cap">{html.escape(cap)}</div>
      <div class="lane-body">{cards}</div>
    </div>''')

    total = len(pending)
    action = len(buckets["hot"]) + len(buckets["nudge"]) + len(buckets["booking"])
    kpis = [
        (total, "лидов в воронке"),
        (action, "требуют действия сегодня"),
        (len(buckets["await"]), "ждут ответа (проверить)"),
        (len(buckets["booked"]), "забронировано"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="n">{n}</div><div class="l">{html.escape(l)}</div></div>' for n, l in kpis)
    stage_counts = [len(buckets[k]) for k, *_ in LANES]
    stage_labels = ["Ответили", "Напомнить", "Бронь", "Ждём", "Готово"]
    gen = NOW.strftime("%Y-%m-%d %H:%M")

    doc = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Пайплайн лидов — дашборд</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--mut2:#7c8696;--line:#262b35;
--acc:#5b9bff;--acc2:#37d399;--acc3:#ffb454;--acc4:#ff6b8b;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
header{{padding:26px 28px 6px}} h1{{margin:0 0 4px;font-size:23px}}
.sub{{color:var(--mut);font-size:13px}} .wrap{{padding:14px 28px 60px;max-width:1500px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:14px 0 18px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.kpi .n{{font-size:26px;font-weight:700}} .kpi .l{{color:var(--mut);font-size:12px;margin-top:2px}}
.funnel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin-bottom:18px}}
.funnel h3{{margin:0 0 8px;font-size:15px}} canvas{{max-height:150px}}
.board{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}}
.lane{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;min-width:0;display:flex;flex-direction:column}}
.lane-h{{display:flex;justify-content:space-between;align-items:center;border-left:3px solid;padding-left:8px;margin-bottom:2px}}
.lane-t{{font-size:13px;font-weight:600}} .lane-n{{font-size:13px;color:var(--mut);background:#11141a;border-radius:8px;padding:0 8px}}
.lane-cap{{color:var(--mut);font-size:11px;margin:4px 0 10px;min-height:30px}}
.lane-body{{display:flex;flex-direction:column;gap:10px}}
.pcard{{background:#11141a;border:1px solid var(--line);border-radius:11px;padding:10px 11px}}
.lead{{font-weight:600;font-size:14px}} .handle{{font-size:12px;margin-bottom:4px}}
a{{color:var(--acc);text-decoration:none}} .mut{{color:var(--mut)}} .dim{{opacity:.7}}
.meta{{color:var(--mut);font-size:11.5px;margin-top:4px}}
.reply{{font-size:12px;color:#cdd6e2;background:#1a2330;border-radius:8px;padding:5px 8px;margin-top:6px}}
.reply.ok{{background:#13241a;color:#bdf0d2}}
.meta.ok{{color:#7fd8a5}} .meta.warn{{color:#ffb454}}
.ball-us{{font-size:12px;font-weight:700;color:#ffd9e0;background:#2a1219;border:1px solid #5c2231;border-radius:8px;padding:5px 8px;margin-top:6px}}
.stop{{font-size:12px;color:#ffc9c9;background:#2a1414;border:1px solid #5c2626;border-radius:8px;padding:5px 8px;margin-top:6px}}
.draft{{font-size:12px;color:#f4d6a6;background:#1c1207;border:1px solid #4a3413;border-radius:8px;padding:6px 9px;margin-top:7px;cursor:pointer}}
.draft .cp{{color:var(--mut);font-size:10px}} .draft.copied{{border-color:var(--acc2);color:#bdf0d2}}
.draft.copied .cp::after{{content:" ✓ скопировано"}}
.empty{{color:var(--mut);font-size:12px;text-align:center;padding:14px 0}}
.note{{background:#1c1207;border:1px solid #4a3413;color:#f4d6a6;border-radius:12px;padding:10px 16px;font-size:12.5px;margin:0 0 14px}}
@media(max-width:1100px){{.board{{grid-template-columns:1fr 1fr}}}}
@media(max-width:680px){{.board{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>🎯 Пайплайн лидов — кого пинговать сегодня</h1>
<div class="sub">Источник: tg_followups.json · сгенерировано {gen} · Claude Code</div></header>
<div class="wrap">
<div class="note">👁️ Только просмотр. Отправка по-прежнему через <b>draft→approve</b> в Telegram (/pipeline). Дашборд ничего не шлёт сам.</div>
<div class="kpis">{kpi_html}</div>
<div class="funnel"><h3>Воронка по стадиям</h3><canvas id="f"></canvas></div>
<div class="board">{"".join(cols)}</div>
</div>
<script>
new Chart(document.getElementById('f'),{{type:'bar',
data:{{labels:{json.dumps(stage_labels, ensure_ascii=False)},
datasets:[{{data:{json.dumps(stage_counts)},backgroundColor:['#ff6b8b','#ffb454','#5b9bff','#7c8696','#37d399'],borderRadius:6}}]}},
options:{{indexAxis:'y',plugins:{{legend:{{display:false}}}},
scales:{{x:{{ticks:{{precision:0}},grid:{{color:'#262b35'}}}},y:{{grid:{{display:false}}}}}}}});
</script></body></html>'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"OK pipeline: {total} leads -> {OUT}")
    for k, t, *_ in LANES:
        print(f"   {t}: {len(buckets[k])}")

if __name__ == "__main__":
    main()
