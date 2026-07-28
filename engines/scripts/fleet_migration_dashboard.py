#!/usr/bin/env python3
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
"""Fleet migration dashboard — LIVE counts hub scheduled tasks (enabled/disabled),
ANCHOR1 crons, and the routine-health rollup, into one auto-refreshing HTML.
Truth = live `schtasks` query each run (never hard-coded), so the scoreboard can't lie.
Built 2026-07-11 (Anton demanded exact numbers + a regularly-updated dashboard)."""
import os, sys, json, subprocess, datetime, re

OUT = r"%VAULT%\_Dashboards\Fleet-Migration.html"
ANCHOR1_HEALTH_LOCAL = r"%VAULT%\_machine-bus\_heartbeat\ANCHOR1-routines-health.json"

# --- routines that STAY on hub forever (physical binding) -> never counted as "todo" ---
STAYS_FOREVER = {
  # GPU
  "HubVoiceTranscribe","Brain Reindex Daily  incremental ","Brain Reindex Weekly (--full)",
  "Brain Reindex Watchdog","Brain Near-Dup Scan",
  # Chrome / browser
  "ChatGPT Nightly Sync","Browser History to Vault Daily","Browser History Dashboard Weekly",
  "Creator Watcher (nightly)","WatchChannelsNightly",
  # desktop apps / physical monitor
  "call-monitor-daemon","Claude Cowork Reaper","cowork-watch","Granola Call Distill",
  "Granola Nightly Pull","Pulse Live Refresh","HubVoiceTranscribe",
  # local disks / accounts
  "Daily E to F Backup","Downloads Janitor Nightly","GDrive Index Refresh  monthly ",
  "Obsidian Backup to Drive",
  # hub-local servers / UI
  "Search UI Server  AtLogon ","Search UI Server Watchdog","Second Brain Search Server  AtLogon ",
  "Second Brain Server Watchdog  Daily ","Dashboards Server","Dashboards Server Watchdog",
  # MUST stay on hub by design
  "ANCHOR1 Dead-Man Watchdog","PAS ntfy Watchdog",
  # per-machine hygiene (each machine its own — nothing to "move")
  "inbox-robot","Consensus Tick","Claude Config Git Snapshot","Claude Config Integrity Gate",
  "CLAUDE.md Guard","Claude Conflict Sweeper Nightly","RecvOnly Sweeper Nightly",
  "Syncthing Hub Watchdog","Claude Cron Watchdog","OS Task Watchdog","node-health-beat",
  "ClaudeBusWipeGuard","Certifi Weekly Update","Claude Sync Monitor","Claude Git Transport Monitor",
  # git hosting + canon publisher (central hub role; wave-3 only by explicit decision)
  "Claude Git Daemon","Claude Git Daemon Guard","Claude Git Sync","Claude Git Offsite Push",
  "Claude Canon Publish","Scripts Publish to Transit","Follower Catalog Watch",
}

def ps(cmd):
    r = subprocess.run(["powershell","-NoProfile","-Command",cmd],
                       capture_output=True, text=True, timeout=90)
    return r.stdout

def hub_tasks():
    sysfilter = "@('NVIDIA*','Zoom*','*OneDrive*','*GoogleUpdate*','MicrosoftEdge*','*Office*','Adobe*','CCleaner*','CreateExplorerShell*')"
    cmd = ("$s=%s; Get-ScheduledTask -TaskPath '\\' | Where-Object {$n=$_.TaskName; "
           "-not ($s|Where-Object {$n -like $_})} | ForEach-Object {"
           "$_.TaskName + '|' + $_.State}") % sysfilter
    out = ps(cmd)
    enabled, disabled = [], []
    for line in out.splitlines():
        line = line.strip()
        if "|" not in line: continue
        name, state = line.rsplit("|",1)
        (disabled if state.strip()=="Disabled" else enabled).append(name.strip())
    return enabled, disabled

def ANCHOR1_cron_count():
    try:
        out = subprocess.run(["ssh","ANCHOR1-root",
              "crontab -u anton -l 2>/dev/null | grep -vcE '^#|^$'; crontab -l 2>/dev/null | grep -vcE '^#|^$'"],
              capture_output=True, text=True, timeout=40).stdout.split()
        return sum(int(x) for x in out if x.isdigit())
    except Exception:
        return None

def health():
    try:
        d = json.load(open(ANCHOR1_HEALTH_LOCAL, encoding="utf-8"))
        return d.get("summary",{}), d.get("routines",[])
    except Exception:
        return None, []

def main():
    enabled, disabled = hub_tasks()
    # migrated this effort = disabled tasks that are OUR routines (not pre-existing-off noise)
    migrated_markers = {"peer-watch","heartbeat-relay","ack-watchdog","bus-guard","fold-all-shards",
      "ON AIR board GC (expire stale)","Alpha Judge Nightly","DR Collect Nightly","DR Synthesize Nightly",
      "ChatGPT Vault Freshness","Lead Reply Watch","Vault Orphan Index Refresh","Search Catalog Weekly Rebuild",
      "Obsidian Weekly Digest","Obsidian Weekly Resurface","Declined-Decisions Nightly Scan",
      "VC Nightly Warm Refresh","Pub-Metrics-Nightly","Content-Debt-Checker","UFO-UAP Digest Weekly",
      "Import Coverage Nightly","Fireflies Nightly Pull","Entity Graph Nightly","Unified SQL Refresh",
      "Tasks Journal Index"}
    migrated = [t for t in disabled if t in migrated_markers]
    other_off = [t for t in disabled if t not in migrated_markers]
    stays = [t for t in enabled if t in STAYS_FOREVER]
    migratable = [t for t in enabled if t not in STAYS_FOREVER]
    total_ours = len(enabled)+len(disabled)
    ANCHOR1 = ANCHOR1_cron_count()
    summ, routines = health()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def rows(lst):
        return "".join("<li>%s</li>" % t for t in sorted(lst))
    hstrip = ""
    if summ:
        hstrip = ("<div class='health'>🩺 Сторож рутин Якорьа: "
          "<b class='g'>%s green</b> · <b class='y'>%s stale</b> · <b class='r'>%s failed</b> "
          "(из %s)</div>") % (summ.get("green","?"),summ.get("stale","?"),summ.get("failed","?"),summ.get("total","?"))
    else:
        hstrip = "<div class='health'>🩺 Сторож рутин Якорьа: ⏳ ещё не отрапортовал (стройка)</div>"

    html = """<!DOCTYPE html><html lang=ru><head><meta charset=UTF-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv=refresh content=900>
<title>🚚 Флот: миграция хаб→Якорь</title><style>
:root{{--bg:#0f1420;--card:#1a2232;--ink:#e8ecf4;--mut:#8b96ab;--line:#2a3550;--g:#3ddc84;--y:#ffd166;--r:#ff6b6b;--b:#5aa9ff}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--ink);padding:22px;max-width:1150px;margin:0 auto}}
h1{{font-size:24px}}.sub{{color:var(--mut);font-size:13px;margin:4px 0 16px}}
.score{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px}}
.s{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:140px}}
.s b{{display:block;font-size:30px}}.s.g b{{color:var(--g)}}.s.b b{{color:var(--b)}}.s.y b{{color:var(--y)}}.s.m b{{color:var(--mut)}}
.s span{{color:var(--mut);font-size:12px}}
.health{{background:#14202e;border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin-bottom:16px;font-size:14px}}
.health .g{{color:var(--g)}}.health .y{{color:var(--y)}}.health .r{{color:var(--r)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}
.col{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}
.col h2{{font-size:15px;margin-bottom:8px}}ul{{list-style:none}}li{{padding:4px 2px;border-bottom:1px solid var(--line);font-size:12.5px;color:#cdd6e6}}
.bar{{height:20px;border-radius:10px;overflow:hidden;display:flex;margin-bottom:16px;border:1px solid var(--line)}}
.bar i{{display:block;height:100%}}.foot{{color:var(--mut);font-size:11px;margin-top:16px}}
</style></head><body>
<h1>🚚 Флот: миграция рутин хаб → Якорь</h1>
<div class=sub>Обновлено {now} · авто-рефреш 15 мин · цифры из живого schtasks (не захардкожены)</div>
{hstrip}
<div class=score>
<div class="s m"><b>{total}</b><span>всего наших задач на хабе</span></div>
<div class="s g"><b>{migN}</b><span>✅ перевезено на Якорь</span></div>
<div class="s b"><b>{migable}</b><span>🔜 можно ещё перевезти</span></div>
<div class="s y"><b>{stayN}</b><span>⚓ остаётся на хабе навсегда</span></div>
<div class="s m"><b>{ANCHOR1}</b><span>🛰️ активных рутин на Якорье</span></div>
</div>
<div class=bar>
<i style="width:{pmig}%;background:var(--g)"></i>
<i style="width:{pable}%;background:var(--b)"></i>
<i style="width:{pstay}%;background:#3a4560"></i>
</div>
<div class=grid>
<div class=col><h2 style="color:var(--g)">✅ Перевезено ({migN})</h2><ul>{rmig}</ul></div>
<div class=col><h2 style="color:var(--b)">🔜 Кандидаты на перенос ({migable})</h2><ul>{rable}</ul></div>
<div class=col><h2 style="color:var(--y)">⚓ Остаётся на хабе ({stayN})</h2><ul>{rstay}</ul></div>
</div>
<div class=foot>Осталось выключенным по др. причинам: {otherN} · генератор: scripts\\fleet_migration_dashboard.py · регламент границ: GPU/Chrome/десктоп/пер-машинная гигиена = хаб навсегда</div>
</body></html>""".format(
        now=now, hstrip=hstrip, total=total_ours, migN=len(migrated), migable=len(migratable),
        stayN=len(stays), ANCHOR1=(ANCHOR1 if ANCHOR1 is not None else "?"),
        pmig=round(100*len(migrated)/max(total_ours,1)), pable=round(100*len(migratable)/max(total_ours,1)),
        pstay=round(100*len(stays)/max(total_ours,1)),
        rmig=rows(migrated), rable=rows(migratable), rstay=rows(stays), otherN=len(other_off))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT,"w",encoding="utf-8").write(html)
    print("WROTE %s | total=%d migrated=%d migratable=%d stays=%d ANCHOR1=%s" % (
        OUT,total_ours,len(migrated),len(migratable),len(stays),ANCHOR1))

if __name__=="__main__":
    main()
