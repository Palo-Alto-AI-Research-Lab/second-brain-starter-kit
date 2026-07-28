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
r"""hub_boot_report.py -- after a reboot the hub CHECKS ITSELF and REPORTS, so Anton
never has to remote-in "to switch the robots back on" (Anton 2026-07-14, away-mode).

What it does (stdlib only, 0 tokens, idempotent per boot):
  1. Detect boot time (GetTickCount64) + estimate downtime (gap since the last
     high-frequency state stamp before the boot).
  2. Run N deterministic health checks: Syncthing process + REST port, dashboards
     server port, critical scheduled tasks present & healthy.
  3. Send ONE report per boot:
       all green -> chat 03 via bus_send.py (dual rail): "rebooted, N/N green, no action needed"
       any red   -> ALSO ping 02 POLICE via bus_ping.post_police (needs a human / a look)
  4. State file remembers the reported boot -> hourly catch-up trigger never duplicates.

Registered as Windows task "Hub Boot Self-Report": ON-LOGON (delay 2 min, lets the
autostart chain settle) + hourly repetition as a missed-trigger safety net.
Test hooks: HBR_FORCE=1 re-report same boot; HBR_DRY=1 print only, send nothing.
Canon: memory hub-reboot-selfreport; sibling of hub_reboot_resilience.ps1 (that one ARMS
unattended recovery; this one PROVES each recovery and reports it).
"""
import ctypes, datetime, json, os, socket, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME    = os.path.expanduser("~")
SCRIPTS = os.path.join(HOME, ".claude", "scripts")
STATE   = os.path.join(SCRIPTS, "_hub_boot_report.state.json")
MACHINE = os.environ.get("COMPUTERNAME", "?")

# high-frequency stamps: newest pre-boot mtime ~= "last alive" -> downtime estimate
ALIVE_STAMPS = [os.path.join(SCRIPTS, "_session_wait_state.json"),
                os.path.join(SCRIPTS, "_heartbeat_relay_state.json")]

CRITICAL_TASKS = ["Claude Session-Wait Watchdog",
                  "Syncthing Hub Watchdog",
                  "Claude Config Git Snapshot"]

def now():
    return datetime.datetime.now()

def boot_time():
    up_ms = ctypes.windll.kernel32.GetTickCount64()
    return now() - datetime.timedelta(milliseconds=int(up_ms))

def port_open(port, host="127.0.0.1", timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def proc_running(image):
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s" % image],
                             capture_output=True, text=True, timeout=30).stdout
        return image.lower() in out.lower()
    except Exception:
        return False

def task_health(name):
    """(ok, detail) via PowerShell structured query (never grep schtasks csv)."""
    ps = ("$t=Get-ScheduledTask -TaskName '%s' -ErrorAction Stop;"
          "$i=Get-ScheduledTaskInfo -TaskName '%s';"
          "@{s=[string]$t.State;r=$i.LastTaskResult} | ConvertTo-Json -Compress") % (name, name)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        d = json.loads(out)
        state, res = d.get("s", "?"), d.get("r")
        # healthy: task exists, not Disabled; result 0 ok / 267009 running / 267011 never-yet
        ok = state not in ("Disabled", "?") and res in (0, 267009, 267011)
        return ok, "%s res=%s" % (state, res)
    except Exception as e:
        return False, "missing/err (%s)" % e.__class__.__name__

def run_checks():
    checks = []
    checks.append(("syncthing.exe", proc_running("syncthing.exe"), "process"))
    checks.append(("syncthing REST :8384", port_open(8384), "port"))
    checks.append(("dashboards :8777", port_open(8777), "port"))
    for t in CRITICAL_TASKS:
        ok, det = task_health(t)
        checks.append((t, ok, det))
    return checks

def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}

def send_report(text, red):
    """Green -> chat 03 (dual rail). Red -> ALSO 02 POLICE. Returns True if delivered."""
    ok = False
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "bus_send.py"), text],
                           capture_output=True, text=True, timeout=180)
        ok = r.returncode in (0, 1)  # 1 = one rail degraded but delivered
        print("bus_send rc=%s" % r.returncode)
    except Exception as e:
        print("bus_send FAILED: %s" % e)
    if red:
        try:
            sys.path.insert(0, SCRIPTS)
            import bus_ping
            bus_ping.post_police(text)
            ok = True
            print("post_police sent")
        except Exception as e:
            print("post_police FAILED: %s" % e)
    return ok

def main():
    bt = boot_time()
    st = load_state()
    force = os.environ.get("HBR_FORCE") == "1"
    dry   = os.environ.get("HBR_DRY") == "1"

    prev = st.get("reported_boot")
    if prev and not force:
        try:
            if abs((bt - datetime.datetime.fromisoformat(prev)).total_seconds()) < 120:
                print("already reported boot %s -- nothing to do" % prev)
                return 0
        except Exception:
            pass

    # downtime = boot minus last CLEAN SHUTDOWN from the Windows event log (exact truth;
    # Kernel-General Id=13). Fallback for power-loss (no Id13): newest alive-stamp mtime.
    last_alive = None
    try:
        ps = ("Get-WinEvent -FilterHashtable @{LogName='System';"
              "ProviderName='Microsoft-Windows-Kernel-General';Id=13} -MaxEvents 12 "
              "-ErrorAction Stop | ForEach-Object { $_.TimeCreated.ToString('s') }")
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                             capture_output=True, text=True, timeout=60).stdout
        cand = [datetime.datetime.fromisoformat(x.strip()) for x in out.splitlines() if x.strip()]
        cand = [x for x in cand if x < bt - datetime.timedelta(seconds=20)]
        if cand:
            last_alive = max(cand)
    except Exception:
        pass
    if last_alive is None:
        for p in ALIVE_STAMPS:
            try:
                m = datetime.datetime.fromtimestamp(os.path.getmtime(p))
                if m < bt and (last_alive is None or m > last_alive):
                    last_alive = m
            except OSError:
                continue
    down_txt = ""
    if last_alive:
        mins = int((bt - last_alive).total_seconds() // 60)
        if mins >= 2:
            down_txt = " (простой ~%dч %02dм)" % (mins // 60, mins % 60)

    checks = run_checks()
    bad = [(n, d) for n, ok, d in checks if not ok]
    n_ok, n_all = len(checks) - len(bad), len(checks)

    if not bad:
        text = ("🔄 [%s] перезагрузка в %s%s · автовосстановление: %d/%d 🟢 — "
                "роботы поднялись сами, вмешательство не нужно"
                % (MACHINE, bt.strftime("%H:%M"), down_txt, n_ok, n_all))
    else:
        lines = "; ".join("❌ %s (%s)" % (n, d) for n, d in bad)
        text = ("🔄 [%s] перезагрузка в %s%s · автовосстановление: %d/%d — НЕ поднялось: %s. "
                "Сторожа попробуют сами; если через час не зелёное — нужен взгляд."
                % (MACHINE, bt.strftime("%H:%M"), down_txt, n_ok, n_all, lines))

    print(text)
    if dry:
        print("(dry run -- not sent, state untouched)")
        return 0

    delivered = send_report(text, red=bool(bad))
    if delivered:
        st["reported_boot"] = bt.isoformat(timespec="seconds")
        st["reported_at"] = now().isoformat(timespec="seconds")
        st["result"] = "%d/%d" % (n_ok, n_all)
        json.dump(st, open(STATE, "w", encoding="utf-8"))
    else:
        print("delivery failed -> state NOT advanced, hourly net will retry")
        return 3
    return 0 if not bad else 2

if __name__ == "__main__":
    sys.exit(main())
