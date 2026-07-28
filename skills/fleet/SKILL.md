---
name: fleet
description: >-
  Snapshot of Anton's autonomous Claude fleet — what his background agents (the Claude Desktop "Cowork"
  app and its headless Claude Code agents) are doing right now, what they've built/committed, and whether
  anything is stuck or burning tokens. READ-ONLY diagnostic. Trigger on "/fleet", "что делают агенты",
  "что там флот", "кто копается в волте", "what are my agents doing", "сколько агентов крутится".
  Built 2026-06-08 from the live investigation; pairs with retro_inventory.py.
---

# /fleet — what are my background agents doing?

> 🧒 **When reporting to Anton:** end with a child-simple "Простыми словами" recap. (memory `eli5-always`)

Anton runs an autonomous fleet (Claude Desktop "Cowork" app → many headless `claude.exe` Code agents) building his Second Brain in the background. This answers: how many, what they're building, anything stuck/looping/burning. **READ-ONLY — never kill a process without Anton's explicit go** (killing mid-write loses uncommitted work; git holds only committed state).

## 🖥️ Визуальный дашборд первым (Антон работает глазами)
`python "$IMPORTS_ROOT/build_fleet_dashboard.py"` → открой `$OBSIDIAN_VAULT/_Dashboards/Fleet-Dashboard.html`: KPI (агенты / мастера / файлов в работе / рабочих коммитов / MCP) + флаг здоровья 🟢/🟡/🔴 + лента коммитов (работа vs авто-бэкапы) + что пишется прямо сейчас. READ-ONLY. Текст ниже — если нужно копнуть руками.

## Recipe (all read-only)
1. **Who's running + the master:**
   ```powershell
   $cl = Get-CimInstance Win32_Process -Filter "Name='claude.exe'"
   "claude agents: $($cl.Count)"
   $cl.ParentProcessId | Sort-Object -Unique | ForEach-Object { $p = Get-CimInstance Win32_Process -Filter ("ProcessId="+$_) -EA SilentlyContinue; if ($p) { "parent $_ = $($p.Name) | $($p.CommandLine.Substring(0,[Math]::Min(80,$p.CommandLine.Length)))" } }
   ```
   Many children sharing ONE `Claude.exe` parent = the Desktop "Cowork" master; an `explorer.exe` grandparent = Anton launched it from the GUI.
2. **What they built (committed):** `git -C "$OBSIDIAN_VAULT" log -20 --pretty="%cr | %s"` — DESCRIPTIVE messages are the fleet's work; terse `pre-intervention` are auto-backups. Group by theme.
3. **Writing right now:** `git -C "$OBSIDIAN_VAULT" status --short` → count = files in flight this second (re-run after ~30s; growing = actively writing).
4. **New reusable artifacts:** `python "$IMPORTS_ROOT/retro_inventory.py" 1` → read its digest (new skills/scripts/notes).
5. **MCP load (optional):** count `python.exe … telegram-mcp … main.py` processes (~2 per agent) — high = many live sessions eating memory.
6. **Collision lens — who's in which FILE right now (`session_monitor.py`, merged in here 2026-06-13):** `python "$USERPROFILE/!CLAUDE-HP17 May26\session_monitor.py"` (snapshot) · `--watch` (live terminal) · `--serve` → http://127.0.0.1:8765 (browser, auto-refresh). Parses the session `.jsonl` logs for file-level touches and flags **⚠️ COLLISIONS** (one file edited by 2+ sessions within 15 min) + hot files. Steps 1–5 answer *"what are they building / stuck / burning"*; this answers *"are any about to overwrite each other"*. **Run it before any structural / bulk vault edit when sessions run hot.** Same fleet, two lenses — `/fleet` is the front door. (memory `session-monitor`)

## Flags to surface
- 🟢 healthy = commits advancing through DIFFERENT real themes over time.
- 🟡 stuck/looping = many agents but no NEW descriptive commits for a long stretch, or the same commit message repeating.
- 🔴 burn = dozens of lingering agents / MCP procs with no progress → tell Anton; HE decides whether to stop the Desktop app (you don't kill it).

## Output
Tight one-liner + detail: "N agents (master PID …) · building: <themes> · writing now: <k> files · flags: 🟢/🟡/🔴 …". Then 🧒 recap. If you spotted something durable they built that isn't captured, mention it (or note `/retro` / the daily sweep will catch it).
