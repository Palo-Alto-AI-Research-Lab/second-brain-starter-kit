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
r"""coach_run.py — deterministic engine for Anton's daily coach (skill `coach`).
Judgment/language is done by Claude (the skill); THIS does the cheap deterministic parts:
  --dashboard            render _Dashboards/_Coach.html from coach_state.json + journal/
  --context "<theme>"    build a compact context pack (_coach_context.txt) for a fresh scheduled run
  --set-tone <mode>      flip tone (mirror_nudge|socrates|sergeant|warm), stamp history
  --status               print state summary
No GPU needed (brain_ask is called only with --brain). AK-47: one file, stdlib only.
"""
import sys, json, re, html, datetime
from pathlib import Path
import os

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8')
    except Exception: pass
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
try:
    from _paths import IMPORTS as _IROOT
except Exception:
    _IROOT = r"%IMPORTS%"

VAULT = Path(_VROOT)
COACH = VAULT / '04-Coach'
STATE = COACH / 'coach_state.json'
JOURNAL = COACH / 'journal'
DASH = VAULT / '_Dashboards' / '_Coach.html'
CTX = Path(os.path.join(_IROOT, "_coach_context.txt"))
TONES = ['mirror_nudge', 'socrates', 'sergeant', 'warm']
IDENTITY = ['insight-self-portrait', 'insight-core-values', 'insight-contradictions',
            'insight-affirmation-as-tell', 'insight-self-image-swings', 'insight-mortality-engine',
            'insight-people-sorting-algorithm', 'insight-graphomania-thermostat',
            'insight-intimates-as-roles', 'insight-decision-principles', 'insight-prediction-ledger']

def today_str():
    # date passed in by caller via stdin-free env is overkill; coach writes the date in journal.
    return datetime.date.today().isoformat()

def load_state():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:
        return {"tone": "mirror_nudge", "streak_days": 0, "best_streak": 0,
                "active_commitment": None, "history": [], "last_morning": None, "last_evening": None}

def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

def compute_streak(history):
    """Consecutive days (ending today or yesterday) that have a history entry."""
    dates = sorted({h.get('date') for h in history if h.get('date')}, reverse=True)
    if not dates:
        return 0
    d0 = datetime.date.fromisoformat(dates[0])
    today = datetime.date.today()
    if (today - d0).days > 1:
        return 0
    streak, prev = 0, None
    for ds in dates:
        d = datetime.date.fromisoformat(ds)
        if prev is None or (prev - d).days == 1:
            streak += 1; prev = d
        elif (prev - d).days == 0:
            continue
        else:
            break
    return streak

def recent_journal(n=2):
    if not JOURNAL.exists():
        return []
    files = sorted(JOURNAL.glob('coach-*.md'), reverse=True)[:n]
    return [(f.name, f.read_text(encoding='utf-8', errors='ignore')) for f in files]

def fm_field(text, key):
    m = re.search(r'(?m)^' + key + r'\s*:\s*"?([^"\n]+)"?', text)
    return m.group(1).strip() if m else ''

# ---------- dashboard ----------
def sparkline(vals, w=320, h=44, color='#6aa9ff'):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if len(vals) < 2:
        return '<svg width="%d" height="%d"></svg>' % (w, h)
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    step = w / (len(vals) - 1)
    pts = ' '.join('%.1f,%.1f' % (i * step, h - 4 - (v - lo) / rng * (h - 8)) for i, v in enumerate(vals))
    return ('<svg width="%d" height="%d">'
            '<polyline fill="none" stroke="%s" stroke-width="2" points="%s"/></svg>') % (w, h, color, pts)

def md_lite(t):
    t = html.escape(t)
    t = re.sub(r'^### (.+)$', r'<h4>\1</h4>', t, flags=re.M)
    t = re.sub(r'^## (.+)$', r'<h3>\1</h3>', t, flags=re.M)
    t = re.sub(r'^# (.+)$', r'<h2>\1</h2>', t, flags=re.M)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    return t.replace('\n', '<br>')

def build_dashboard():
    s = load_state()
    s['streak_days'] = compute_streak(s.get('history', []))
    hist = s.get('history', [])[-21:]
    moods = [h.get('mood') for h in hist]
    energies = [h.get('energy') for h in hist]
    journ = recent_journal(1)
    latest = md_lite(journ[0][1]) if journ else '<i>Журнал пуст — первая сессия впереди.</i>'
    rows = ''
    for h in reversed(s.get('history', [])[-10:]):
        mark = {True: '✓', False: '✗', None: '⏳'}.get(h.get('done'), '⏳')
        rows += '<tr><td>%s</td><td>%s</td><td class="c">%s</td><td class="c">%s/%s</td></tr>' % (
            h.get('date', ''), html.escape(str(h.get('commitment', '') or '')), mark,
            h.get('mood', '–'), h.get('energy', '–'))
    commit = html.escape(str(s.get('active_commitment') or '— не задан —'))
    css = ('body{background:#0f1320;color:#e6e9f0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}'
           '.wrap{max-width:760px;margin:0 auto}.card{background:#171c2e;border:1px solid #26304d;border-radius:14px;padding:18px 20px;margin:14px 0}'
           'h1{font-size:22px;margin:0 0 4px}h2{font-size:19px}h3{font-size:16px;color:#9fb3d8}h4{color:#9fb3d8;margin:.4em 0}'
           '.big{font-size:20px;font-weight:700;color:#ffd479}.muted{color:#8a93ab}.kpi{display:flex;gap:24px;flex-wrap:wrap}'
           '.kpi div{text-align:center}.kpi .n{font-size:26px;font-weight:700;color:#6aa9ff}'
           'table{width:100%;border-collapse:collapse}td,th{padding:6px 8px;border-bottom:1px solid #232c47;text-align:left}'
           '.c{text-align:center}a{color:#6aa9ff}')
    tone = s.get('tone', 'mirror_nudge')
    html_doc = f"""<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Коуч — {today_str()}</title>
<style>{css}</style><div class="wrap">
<h1>🧭 Коуч Антона</h1><div class="muted">обновлено {today_str()} · тон: <b>{tone}</b> (с {s.get('tone_since','?')}) · такт: {s.get('cadence','')}</div>
<div class="card kpi">
<div><div class="n">{s['streak_days']}</div><div class="muted">дней подряд</div></div>
<div><div class="n">{s.get('best_streak',0)}</div><div class="muted">лучшая серия</div></div>
<div><div class="n">{len(s.get('history',[]))}</div><div class="muted">всего дней</div></div>
</div>
<div class="card"><h3>🎯 Сегодняшний камень</h3><div class="big">{commit}</div></div>
<div class="card"><h3>📈 Настроение · энергия (21 день)</h3>
<div class="muted">настроение</div>{sparkline(moods, color='#7ee0a6')}
<div class="muted">энергия</div>{sparkline(energies, color='#ffd479')}</div>
<div class="card"><h3>📓 Последняя сессия</h3>{latest}</div>
<div class="card"><h3>✅ Обязательства (последние 10)</h3>
<table><tr><th>Дата</th><th>Камень</th><th class="c">Итог</th><th class="c">М/Э</th></tr>{rows or '<tr><td colspan=4 class=muted>пока пусто</td></tr>'}</table></div>
<div class="muted">Источник правды о тебе — identity-слой в 03-Insights. Этот экран — только витрина состояния.</div>
</div></html>"""
    DASH.parent.mkdir(parents=True, exist_ok=True)
    DASH.write_text(html_doc, encoding='utf-8')
    print(f'dashboard -> {DASH}  (streak={s["streak_days"]}, days={len(s.get("history",[]))})')
    save_state(s)

# ---------- context pack ----------
def build_context(theme=''):
    s = load_state()
    out = []
    out.append(f"=== COACH CONTEXT ({today_str()}) ===")
    out.append(f"TONE: {s.get('tone')}  STREAK: {compute_streak(s.get('history',[]))}  CADENCE: {s.get('cadence')}")
    out.append(f"ACTIVE COMMITMENT (yesterday's rock): {s.get('active_commitment')}")
    if s.get('history'):
        last = s['history'][-1]
        out.append(f"LAST DAY: {last}")
    out.append("\n--- LAST JOURNAL ---")
    for name, txt in recent_journal(1):
        out.append(f"[{name}]\n{txt.strip()[:1200]}")
    # the 12 contradictions (headers only = compact, high-signal)
    cpath = VAULT / '03-Insights' / 'insight-contradictions.md'
    if cpath.exists():
        heads = re.findall(r'(?m)^##\s+(.+)$', cpath.read_text(encoding='utf-8', errors='ignore'))
        out.append("\n--- ПРОТИВОРЕЧИЯ (лови в моменте) ---\n" + "\n".join('• ' + h for h in heads))
    # emotional-layer one-liners (applicability from frontmatter)
    out.append("\n--- ЭМОЦИОНАЛЬНЫЙ СЛОЙ ---")
    for n in ['insight-affirmation-as-tell','insight-self-image-swings','insight-mortality-engine',
              'insight-people-sorting-algorithm','insight-graphomania-thermostat','insight-intimates-as-roles']:
        p = VAULT / '03-Insights' / (n + '.md')
        if p.exists():
            out.append(f"• {n}: {fm_field(p.read_text(encoding='utf-8',errors='ignore'),'applicability')}")
    if theme:
        out.append(f"\n--- ТЕМА ДНЯ: {theme} ---")
        out.append("(если нужно — подними детали через: python %IMPORTS%\\brain_ask.py --ask \"%s\")" % theme)
    CTX.write_text("\n".join(out), encoding='utf-8')
    print(f'context -> {CTX} ({len(chr(10).join(out))} chars)')

def set_tone(mode):
    if mode not in TONES:
        print('tone must be one of: ' + ', '.join(TONES)); return
    s = load_state()
    s['tone'] = mode; s['tone_since'] = today_str()
    s.setdefault('history', [])
    save_state(s)
    print(f'tone -> {mode} (since {today_str()})')

def status():
    s = load_state()
    s['streak_days'] = compute_streak(s.get('history', []))
    print(json.dumps({k: s[k] for k in ('tone','streak_days','best_streak','active_commitment','cadence') if k in s},
                     ensure_ascii=False, indent=2))

def main():
    a = sys.argv[1:]
    if '--dashboard' in a: build_dashboard()
    elif '--set-tone' in a: set_tone(a[a.index('--set-tone')+1] if len(a) > a.index('--set-tone')+1 else '')
    elif '--context' in a: build_context(a[a.index('--context')+1] if len(a) > a.index('--context')+1 else '')
    elif '--status' in a: status()
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
