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
r"""build_fleet_dashboard.py — /fleet as a visual snapshot.

READ-ONLY. Collects: how many claude.exe agents run + their parents (the Desktop
"Cowork" master), what the vault git log shows they committed, how many files are
in flight this second, and the MCP load. Writes a self-contained HTML snapshot.
Never kills anything.

  python build_fleet_dashboard.py     # -> _Dashboards\Fleet-Dashboard.html
"""
import subprocess, json, html, datetime, re, collections, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback
OUT = Path(VAULT) / "_Dashboards" / "Fleet-Dashboard.html"
NOW = datetime.datetime.now()

def ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        return r.stdout
    except Exception as e:
        return ""

def git(*args):
    try:
        r = subprocess.run(["git", "-C", VAULT, *args], capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        return r.stdout
    except Exception:
        return ""

# ---- 1. processes -----------------------------------------------------------
def collect_procs():
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
             "Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress")
    procs = []
    out = out.strip()
    if out:
        try:
            j = json.loads(out)
            procs = j if isinstance(j, list) else [j]
        except Exception:
            procs = []
    parents = collections.Counter(p.get("ParentProcessId") for p in procs)
    # mcp load: python procs running a telegram mcp main.py
    mcp = ps("(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*telegram*main.py*' }).Count")
    try:
        mcp_n = int(mcp.strip() or 0)
    except Exception:
        mcp_n = 0
    return procs, parents, mcp_n

# ---- 2. git ----------------------------------------------------------------
AUTO_RE = re.compile(r"pre-intervention|auto-?backup|pre-edit|snapshot|wip\b", re.I)

def collect_git():
    log = git("log", "-30", "--pretty=%cr\x1f%s")
    commits = []
    for line in log.splitlines():
        if "\x1f" not in line:
            continue
        ago, msg = line.split("\x1f", 1)
        commits.append({"ago": ago.strip(), "msg": msg.strip(), "auto": bool(AUTO_RE.search(msg))})
    status = git("status", "--short")
    inflight = [l for l in status.splitlines() if l.strip()]
    return commits, inflight

def health(agents, commits, inflight):
    work = [c for c in commits if not c["auto"]]
    recent_work = work[:8]
    distinct = len({c["msg"][:40] for c in recent_work})
    if agents == 0 and not inflight:
        return "idle", "💤 Флот спит", "Агентов нет, файлов в работе нет — тихо."
    if agents and distinct >= 3:
        return "green", "🟢 Здоровый", "Агенты коммитят разные реальные темы — нормальная работа."
    if agents and distinct <= 1 and len(recent_work) >= 2:
        return "yellow", "🟡 Возможно застрял", "Много агентов, но свежие коммиты повторяются/однотипны — проверь."
    if agents > 20 and not work:
        return "red", "🔴 Жжёт без прогресса", "Десятки агентов без новых осмысленных коммитов — реши, гасить ли Desktop."
    return "green", "🟢 Похоже норм", "Агенты есть, прогресс идёт."

def main():
    procs, parents, mcp_n = collect_procs()
    commits, inflight = collect_git()
    agents = len(procs)
    state, badge, expl = health(agents, commits, inflight)
    work = [c for c in commits if not c["auto"]]
    auto = [c for c in commits if c["auto"]]

    COLOR = {"green": "--acc2", "yellow": "--acc3", "red": "--acc4", "idle": "--mut", "interesting": "--acc"}
    kpis = [
        (agents, "агентов (claude.exe)"),
        (len([p for p, n in parents.items() if n > 1]) or len(parents), "мастер-процессов"),
        (len(inflight), "файлов в работе сейчас"),
        (len(work), "рабочих коммитов (из 30)"),
        (mcp_n, "MCP-процессов (нагрузка)"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="n">{n}</div><div class="l">{html.escape(l)}</div></div>'
                       for n, l in kpis)

    parent_rows = "".join(
        f'<tr><td class="mono">PID {html.escape(str(p))}</td><td class="num">{n}</td></tr>'
        for p, n in parents.most_common()) or '<tr><td class="mut" colspan="2">— агентов нет —</td></tr>'

    def commit_li(c):
        cls = "auto" if c["auto"] else "work"
        return f'<li class="{cls}"><span class="ago">{html.escape(c["ago"])}</span> {html.escape(c["msg"])}</li>'
    work_li = "".join(commit_li(c) for c in work[:16]) or '<li class="mut">— нет рабочих коммитов —</li>'
    auto_li = "".join(commit_li(c) for c in auto[:8]) or '<li class="mut">—</li>'

    flight_li = "".join(f'<li class="mono">{html.escape(l)}</li>' for l in inflight[:40]) \
        or '<li class="mut">— ничего не пишется прямо сейчас —</li>'

    gen = NOW.strftime("%Y-%m-%d %H:%M:%S")
    doc = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Флот агентов — дашборд</title>
<style>
:root{{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;
--acc:#5b9bff;--acc2:#37d399;--acc3:#ffb454;--acc4:#ff6b8b;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
header{{padding:26px 28px 6px}} h1{{margin:0 0 4px;font-size:23px}}
.sub{{color:var(--mut);font-size:13px}} .wrap{{padding:14px 28px 60px;max-width:1320px}}
.health{{display:inline-block;border:1px solid var(--line);border-left:4px solid var({COLOR.get(state,'--mut')});
border-radius:12px;background:var(--card);padding:12px 18px;margin:8px 0 16px}}
.health .b{{font-size:18px;font-weight:700}} .health .e{{color:var(--mut);font-size:13px;margin-top:2px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:6px 0 20px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.kpi .n{{font-size:26px;font-weight:700}} .kpi .l{{color:var(--mut);font-size:12px;margin-top:2px}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;min-width:0}}
.card h3{{margin:0 0 2px;font-size:15px}} .card .cap{{color:var(--mut);font-size:12px;margin:0 0 10px}}
ul{{margin:0;padding:0;list-style:none}} li{{padding:5px 0;border-bottom:1px solid var(--line);font-size:13px}}
li.work .ago,li.auto .ago{{display:inline-block;min-width:96px;color:var(--mut);font-size:11px}}
li.auto{{opacity:.5}} li.work{{border-left:2px solid var(--acc2);padding-left:8px}}
.mono{{font-family:Consolas,monospace;font-size:12px}} .mut{{color:var(--mut)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td{{padding:5px 6px;border-bottom:1px solid var(--line)}}
td.num{{text-align:right}}
.note{{background:#101a14;border:1px solid #1f3a2a;color:#bdf0d2;border-radius:12px;padding:10px 16px;font-size:12.5px;margin:0 0 14px}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>🤖 Флот агентов — что делают мои фоновые Claude</h1>
<div class="sub">Снимок состояния · {gen} · только просмотр, ничего не гасим</div></header>
<div class="wrap">
<div class="note">👁️ READ-ONLY. Гасить Desktop/агентов — только решение Антона: убить процесс на середине записи = потерять незакоммиченное.</div>
<div class="health"><div class="b">{html.escape(badge)}</div><div class="e">{html.escape(expl)}</div></div>
<div class="kpis">{kpi_html}</div>
<div class="grid">
  <div class="card">
    <h3>Что построили (коммиты волта)</h3>
    <p class="cap">Зелёные — работа флота · тусклые — авто-бэкапы (pre-intervention)</p>
    <ul>{work_li}</ul>
    <p class="cap" style="margin-top:12px">Авто-бэкапы</p><ul>{auto_li}</ul>
  </div>
  <div>
    <div class="card" style="margin-bottom:16px">
      <h3>Мастер-процессы</h3>
      <p class="cap">Много детей у одного PID = Desktop «Cowork»</p>
      <table>{parent_rows}</table>
    </div>
    <div class="card">
      <h3>Пишется прямо сейчас</h3>
      <p class="cap">git status — файлы в работе ({len(inflight)})</p>
      <ul>{flight_li}</ul>
    </div>
  </div>
</div></div></body></html>'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"OK fleet: agents={agents} masters={len(parents)} inflight={len(inflight)} "
          f"work_commits={len(work)} mcp={mcp_n} state={state} -> {OUT}")

if __name__ == "__main__":
    main()
