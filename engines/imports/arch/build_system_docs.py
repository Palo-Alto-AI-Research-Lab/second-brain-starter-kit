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
build_system_docs.py -- System Architect, Phase 2 (status + docs-as-code)
Reads system.db (from sys_scan.py) and emits:
  1) %VAULT%\\_Dashboards\\System-Health.html  (visual status)
  2) %VAULT%\\00-System\\_System-MOC.md         (architecture map)
  3) %VAULT%\\00-System\\System-Automations.md  (auto inventory)
Deterministic, 0 tokens. Markdown-in-vault (Anton's choice 2026-06-21).
Run AFTER sys_scan.py, and AFTER a vault backup (vault-backup-rule).
"""
import os, sqlite3, datetime, html
from collections import Counter

IMPORTS   = r"%IMPORTS%"
VAULT     = r"%VAULT%"
DB_PATH   = os.path.join(IMPORTS, "arch", "system.db")
DASH      = os.path.join(VAULT, "_Dashboards", "System-Health.html")
SYSDIR    = os.path.join(VAULT, "00-System")
MOC       = os.path.join(SYSDIR, "_System-MOC.md")
AUTONOTE  = os.path.join(SYSDIR, "System-Automations.md")
NOW       = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# Canonical System-Health.html/_System-MOC.md belong to the HUB's run only.
# A peer running this engine publishes to per-machine files -- two machines
# writing the same synced path silently overwrite each other (seen 2026-07-02:
# laptop's stale engine masked the hub's broken-task list all day).
HUB  = "HUB1"
HOST = (os.environ.get("COMPUTERNAME") or "unknown-host").upper()
if HOST != HUB:
    DASH     = os.path.join(VAULT, "_Dashboards", "System-Health-%s.html" % HOST)
    MOC      = os.path.join(SYSDIR, "_System-MOC-%s.md" % HOST)
    AUTONOTE = os.path.join(SYSDIR, "System-Automations-%s.md" % HOST)

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
rows = list(con.execute("SELECT * FROM asset"))
run  = con.execute("SELECT * FROM scan_run ORDER BY run_at DESC LIMIT 1").fetchone()
edges = list(con.execute("SELECT * FROM edge"))
try:
    checks = list(con.execute("SELECT * FROM check_result ORDER BY severity DESC, check_id"))
except Exception:
    checks = []
try:
    coverage = list(con.execute("SELECT * FROM coverage"))
except Exception:
    coverage = []
con.close()
chk_by = {c["check_id"]: c["status"] for c in checks}
restore_ok = chk_by.get("chk-restore-drill") == "pass"

# ---- graph insights (Phase 3): incoming edges per asset -> orphan/dead triage
indeg = {}
for e in edges:
    indeg[e["dst"]] = indeg.get(e["dst"], 0) + 1
by_id = {r["asset_id"]: r for r in rows}
kind_of = {r["asset_id"]: r["kind"] for r in rows}
# which assets have a scheduled_task pointing at them?
sched_dst = set(e["dst"] for e in edges
                if kind_of.get(e["src"]) == "scheduled_task")
dead_scripts = [r for r in rows if r["kind"] == "script" and indeg.get(r["asset_id"], 0) == 0]
unsched_pipes = [r for r in rows if r["kind"] == "import_pipeline"
                 and r["asset_id"] not in sched_dst]

total = len(rows)
ok    = sum(1 for r in rows if r["status"] == "ok")
broken = [r for r in rows if r["status"] == "broken"]
disabled = [r for r in rows if r["status"] == "disabled"]
kc = Counter(r["kind"] for r in rows)
tasks = [r for r in rows if r["kind"] == "scheduled_task"]
task_ok = sum(1 for r in tasks if r["status"] == "ok")
backups = [r for r in rows if r["kind"] == "backup_target"]

# ---- health score (pragmatic; recoverability partial until Phase-4 restore drill)
integrity   = ok / total if total else 1.0                       # 35%
operational = task_ok / len(tasks) if tasks else 1.0             # 10%
freshness   = 1.0                                                # 20% (just scanned)
docs        = 1.0                                                # 10% (regenerated now)
recover     = 1.0 if restore_ok else (0.6 if backups else 0.0)  # 25% -- restore-drill proven?
score = round(100 * (0.35*integrity + 0.25*recover + 0.20*freshness +
                     0.10*docs + 0.10*operational))

def color(s):
    return "#2ecc71" if s >= 90 else "#f1c40f" if s >= 70 else "#e74c3c"

# ============================================================= HTML dashboard
def esc(x): return html.escape(str(x or ""))

kind_rows = "".join(
    "<tr><td>%s</td><td style='text-align:right'>%d</td></tr>" % (esc(k), kc[k])
    for k in sorted(kc))

def task_badge(s):
    c = {"ok": "#2ecc71", "broken": "#e74c3c", "disabled": "#7f8c8d"}.get(s, "#f1c40f")
    return "<span style='color:%s;font-weight:600'>%s</span>" % (c, esc(s))

task_rows = "".join(
    "<tr><td>%s</td><td>%s</td><td style='color:#9aa'>%s</td></tr>" %
    (esc(r["name"]), task_badge(r["status"]), esc(r["detail"]))
    for r in sorted(tasks, key=lambda x: (x["status"] != "broken", x["name"])))

broken_html = "".join(
    "<li><b>[%s]</b> %s &mdash; <span style='color:#e74c3c'>%s</span></li>" %
    (esc(r["kind"]), esc(r["name"]), esc(r["detail"])) for r in broken) or "<li>нет</li>"

backup_rows = "".join(
    "<tr><td>%s</td><td style='color:#9aa'>%s</td></tr>" % (esc(r["name"]), esc(r["detail"]))
    for r in backups)

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<!-- arch-source: {host} @ {now} -->
<title>System Health</title>
<style>
 body{{margin:0;background:#0f1115;color:#e6e6e6;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
 .wrap{{max-width:1100px;margin:0 auto;padding:28px}}
 h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#8a93a2;margin-bottom:22px}}
 .grid{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
 .card{{background:#171a21;border:1px solid #232734;border-radius:12px;padding:18px 20px;flex:1;min-width:170px}}
 .card .n{{font-size:30px;font-weight:700}} .card .l{{color:#8a93a2;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 .score{{font-size:52px;font-weight:800}}
 table{{width:100%;border-collapse:collapse;margin:8px 0 26px}}
 th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #232734;font-size:13px}}
 th{{color:#8a93a2;text-transform:uppercase;font-size:11px;letter-spacing:.04em}}
 h2{{font-size:15px;margin:26px 0 6px;color:#cdd3df}}
 .two{{display:flex;gap:24px;flex-wrap:wrap}} .two>div{{flex:1;min-width:320px}}
 ul{{margin:6px 0}} li{{margin:3px 0}}
 .note{{color:#8a93a2;font-size:12px}}
</style></head><body><div class="wrap">
 <h1>🏛️ System Health &mdash; Personal Knowledge Platform</h1>
 <div class="sub">Авто-сгенерировано · последний скан {now} · источник: system.db</div>
 <div class="grid">
   <div class="card"><div class="l">Health Score</div><div class="score" style="color:{sc}">{score}<span style="font-size:22px;color:#8a93a2">/100</span></div></div>
   <div class="card"><div class="l">Всего активов</div><div class="n">{total}</div></div>
   <div class="card"><div class="l">OK</div><div class="n" style="color:#2ecc71">{ok}</div></div>
   <div class="card"><div class="l">Сломано</div><div class="n" style="color:#e74c3c">{nbroken}</div></div>
   <div class="card"><div class="l">Отключено</div><div class="n" style="color:#7f8c8d">{ndis}</div></div>
   <div class="card"><div class="l">Роботов (задач)</div><div class="n">{ntasks}</div><div class="note">{task_ok} ok</div></div>
 </div>

 <div class="two">
  <div>
   <h2>⚠️ Сломано / требует внимания</h2><ul>{broken}</ul>
   <h2>💾 Восстановление (резерв)</h2>
   <table><tr><th>Цель бэкапа</th><th>Класс</th></tr>{backup_rows}</table>
   <div class="note">⏳ Restore-drill (проверка восстановления) добавляется в Фазе 4 → recoverability сейчас засчитан частично (0.6).</div>
  </div>
  <div>
   <h2>📦 Каталог по типам</h2>
   <table><tr><th>Тип</th><th style="text-align:right">Кол-во</th></tr>{kind_rows}</table>
  </div>
 </div>

 <h2>🤖 Автоматизации (Windows Task Scheduler) &mdash; живой статус</h2>
 <table><tr><th>Задача</th><th>Статус</th><th>Детали (state / last / result)</th></tr>{task_rows}</table>

 <h2>🕸️ Граф-инсайты (Фаза 3) &mdash; {nedges} рёбер зависимостей</h2>
 <div class="two"><div>
   <h2 style="margin-top:0">🧹 Скрипты без робота и скилла ({ndead})</h2>
   <div class="note">Ни одна задача и ни один скилл на них не ссылаются &mdash; кандидаты в «мёртвый код» (триаж, НЕ приговор: могут быть библиотеки или ручные тулзы).</div>
   <ul>{dead_html}</ul>
 </div><div>
   <h2 style="margin-top:0">⏰ Пайплайны без расписания ({nunsched})</h2>
   <div class="note">Папки-пайплайны, к которым не привязана scheduled-задача (ручные или разовые).</div>
   <ul>{unsched_html}</ul>
 </div></div>
 <h2>📊 Покрытие &mdash; «всё ли в карте?» (измеряем, не верим на слово)</h2>
 <table><tr><th>Домен</th><th>Что</th><th>Покрытие</th><th>Статус</th><th>Детали</th></tr>{cov_rows}</table>
 <div class="note">Покрытие = доля, которую система реально видит/держит. Цель — тренд к 100% + явный список того, что вне карты. Сессии CC и сироты волта догоняются ночными задачами; offsite-бэкап `_imports` — открытая дыра.</div>

 <h2>🗺️ Визуальная карта</h2>
 <div class="note">Интерактивная топология «роботы → код → данные → лица»: <a href="System-Architecture-Map.html" style="color:#5dade2">System-Architecture-Map.html</a></div>

 <h2>🧪 Тесты по уровням (Фаза 4)</h2>
 <table><tr><th>Проверка</th><th>Частота</th><th>Важность</th><th>Статус</th><th>Детали</th></tr>{check_rows}</table>
 <div class="note">Result-коды задач: 0=ok · 267009=running · 267011=ещё не запускалась · 267014=прервана · иное=ошибка.<br>
 Будим (RED) только на critical/daily-падения (правило SRE: алерт только на симптом, требующий человека).<br>
 Этот экран и заметки 00-System пересобираются ночным архитектором.</div>
</div></body></html>""".format(
    now=NOW, host=HOST, sc=color(score), score=score, total=total, ok=ok, nbroken=len(broken),
    ndis=len(disabled), ntasks=len(tasks), task_ok=task_ok, broken=broken_html,
    backup_rows=backup_rows, kind_rows=kind_rows, task_rows=task_rows, nedges=len(edges),
    ndead=len(dead_scripts), nunsched=len(unsched_pipes),
    dead_html=("".join("<li>%s</li>" % esc(r["name"]) for r in dead_scripts[:40])
               + ("<li class='note'>… ещё %d</li>" % (len(dead_scripts)-40) if len(dead_scripts) > 40 else "")) or "<li>нет</li>",
    unsched_html="".join("<li>%s <span class='note'>(%s)</span></li>" % (esc(r["name"]), esc(r["detail"])) for r in unsched_pipes) or "<li>нет</li>",
    check_rows="".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style='color:#9aa'>%s</td></tr>" % (
            esc(c["check_id"]), esc(c["cadence"]), esc(c["severity"]),
            ("<span style='color:#2ecc71;font-weight:600'>pass</span>" if c["status"]=="pass"
             else "<span style='color:#e74c3c;font-weight:600'>FAIL</span>"),
            esc(c["detail"])) for c in sorted(checks, key=lambda x:(x["status"]=="pass", x["check_id"]))
        ) or "<tr><td colspan=5 class='note'>тесты ещё не запускались (sys_check.py)</td></tr>",
    cov_rows="".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style='color:#9aa'>%s</td></tr>" % (
            esc(c["domain"]), esc(c["label"]),
            ("%d/%d (%.0f%%)" % (c["value"], c["target"], c["pct"])) if c["target"] and c["target"] != 1 else "—",
            ("<span style='color:#2ecc71;font-weight:600'>ok</span>" if c["status"]=="ok"
             else "<span style='color:#e74c3c;font-weight:600'>FAIL</span>" if c["status"]=="fail"
             else "<span style='color:#f1c40f;font-weight:600'>warn</span>"),
            esc(c["detail"])) for c in sorted(coverage, key=lambda x:(x["domain"], x["status"]=="ok"))
        ) or "<tr><td colspan=5 class='note'>покрытие ещё не считалось (sys_coverage.py)</td></tr>")

os.makedirs(os.path.dirname(DASH), exist_ok=True)
open(DASH, "w", encoding="utf-8").write(HTML)

# ============================================================= markdown (vault)
os.makedirs(SYSDIR, exist_ok=True)

def mdtable(headers, rows_):
    out = "| " + " | ".join(headers) + " |\n| " + " | ".join("---" for _ in headers) + " |\n"
    for r in rows_:
        out += "| " + " | ".join(str(x).replace("|", "\\|") for x in r) + " |\n"
    return out

kind_md = mdtable(["Тип актива", "Кол-во"], [(k, kc[k]) for k in sorted(kc)])
broken_md = "\n".join("- **[%s]** %s — `%s`" % (r["kind"], r["name"], r["detail"])
                      for r in broken) or "- нет"

moc = """---
title: "System MOC — карта всей платформы (авто)"
type: moc
node_type: system
authored_by: machine
ai_author: claude-opus
owner: anton
machine: {host}
date_generated: {now}
status: generated
audience: both
tags: [system, architecture, moc, auto-generated, pkp]
---

# 🏛️ System MOC — Personal Knowledge Platform

> ⚙️ **Авто-сгенерировано** ночным архитектором из `system.db` ({now}). Не править руками — правки затрутся при следующем прогоне. Ручной слой = `_imports\\arch\\overlay.json` (только integrity_tier / owner / lifecycle). Канон-решение: [[decision-architect-system-platform]].

## Health
- **Score: {score}/100** · активов: **{total}** · ok: **{ok}** · сломано: **{nbroken}** · отключено: **{ndis}**
- 📊 Визуально: `_Dashboards/System-Health.html`

## ⚠️ Сломано / внимание
{broken_md}

## Каталог по типам
{kind_md}

## 🕸️ Граф-инсайты (Фаза 3)
- Рёбер зависимостей: **{nedges}** (скилл→пайплайн/БД, задача→скрипт, скрипт→БД)
- Скриптов без робота и скилла (кандидаты в мёртвый код): **{ndead}**
- Пайплайнов без расписания: **{nunsched}**

## Слои системы (5 истин)
1. **Знания** — заметки, исследования, промпты (файлы в волте/репо).
2. **Активы** — что существует (этот каталог, авто-скан).
3. **Состояние** — `system.db` (быстрые запросы, диффы, история сканов).
4. **Граф** — зависимости между активами ({nedges} рёбер, Фаза 3).
5. **Надёжность** — здоровье, тесты, restore-drill (Фаза 4).

## Подстраницы
- [[System-Automations]] — все роботы и их живой статус (авто-наследник `automation-inventory`).

## Связано
- [[decision-architect-system-platform]] · [[vault-data-architecture]] · [[decision-unified-multi-machine-platform]]
""".format(now=NOW, host=HOST, score=score, total=total, ok=ok, nbroken=len(broken),
           ndis=len(disabled), broken_md=broken_md, kind_md=kind_md, nedges=len(edges),
           ndead=len(dead_scripts), nunsched=len(unsched_pipes))
open(MOC, "w", encoding="utf-8").write(moc)

# automations note (auto inventory)
trows = [(r["name"], r["status"], r["detail"]) for r in
         sorted(tasks, key=lambda x: (x["status"] != "broken", x["name"]))]
auto = """---
title: "System Automations — живой инвентарь роботов (авто)"
type: reference
node_type: system
authored_by: machine
ai_author: claude-opus
owner: anton
machine: {host}
date_generated: {now}
status: generated
audience: both
tags: [system, automation, inventory, auto-generated]
---

# 🤖 System Automations — живой статус

> ⚙️ Авто-сгенерировано из `system.db` ({now}). Заменяет ручной `automation-inventory` (тот разъезжался). {ntasks} задач, {task_ok} ok.

{table}

Result-коды: `0`=ok · `267009`=running · `267011`=ещё не запускалась · `267014`=прервана · иное=ошибка.

⬅ назад: [[_System-MOC]]
""".format(now=NOW, host=HOST, ntasks=len(tasks), task_ok=task_ok,
           table=mdtable(["Задача", "Статус", "Детали"], trows))
open(AUTONOTE, "w", encoding="utf-8").write(auto)

# persist score/meta so /arch and other readers share one source of truth
try:
    cw = sqlite3.connect(DB_PATH)
    cw.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, val TEXT)")
    for k, v in [("score", str(score)), ("generated_at", NOW),
                 ("total", str(total)), ("broken", str(len(broken))),
                 ("disabled", str(len(disabled))), ("dead_scripts", str(len(dead_scripts))),
                 ("unsched_pipes", str(len(unsched_pipes)))]:
        cw.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))
    cw.commit(); cw.close()
except Exception as e:
    print("WARN meta write:", e)

print("Score: %d/100  | assets %d (ok %d, broken %d, disabled %d)" %
      (score, total, ok, len(broken), len(disabled)))
print("HTML ->", DASH)
print("MOC  ->", MOC)
print("AUTO ->", AUTONOTE)
