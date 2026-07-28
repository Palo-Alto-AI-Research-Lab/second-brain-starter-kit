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
WhatsApp NIGHTLY pull (variant A, live bridge) -- ONE client session, headless-safe.
Merges train_pull + names_fix into a SINGLE connection (1 connect/disconnect on the
main number = gentle + avoids the double-client AUTH_KEY_DUPLICATED landmine).

SAFETY:
- READ-ONLY pull: list_chats + list_messages coexist fine with the registered MCP server
  (it degrades a 2nd client to read-only, NO AUTH_KEY_DUPLICATED). So we do NOT kill the
  registered server. resolve_contacts (a WRITE) is best-effort: it errors harmlessly into
  read-only mode if another client holds the write connection, and succeeds when we're sole.
- We clean up ONLY OUR OWN spawned client with `taskkill /F /T /PID <pid>` (terminate() is
  unreliable for node on Windows -> would otherwise leave a zombie that accumulates nightly).
- Text-only (Anton 2026-06-15): never downloads media. No LLM, no paid API.
"""
import json, subprocess, time, os, sys, io, re, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

IDX = os.path.expanduser(r"~\AppData\Roaming\npm\node_modules\@oss_maintainer\whatsapp-mcp\dist\index.js")
OUT = r"%IMPORTS%\whatsapp"
RAW = os.path.join(OUT, "raw_train")
os.makedirs(RAW, exist_ok=True)

SYNC_WAIT = 45
TOP_CHATS = 100
MSGS_PER  = 50

def hardkill(pid):
    """Force-kill our own spawned node child + its tree (terminate() is unreliable on Windows)."""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, text=True, timeout=20)
        print(f"hardkill own client pid={pid}")
    except Exception as e:
        print("hardkill error:", e)

def preflight_sweep():
    """Kill ONLY true-orphan whatsapp-node left by a PREVIOUS interrupted run (parent process dead).
    Live session MCP nodes (parent=claude) and our own child (parent alive) are NEVER touched.
    Conservative: Windows PID-reuse can make a dead parent look alive -> we then SKIP (never false-kill)."""
    ps = ("$ns=Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
          "Where-Object { $_.CommandLine -like '*whatsapp-mcp*index.js*' }; "
          "foreach($n in $ns){ if(-not (Get-Process -Id $n.ParentProcessId -ErrorAction SilentlyContinue)){ $n.ProcessId } }")
    try:
        out = subprocess.run(["powershell","-NoProfile","-Command",ps],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        print("preflight_sweep query error:", e); return
    pids = [p.strip() for p in out.splitlines() if p.strip().isdigit()]
    for pid in pids:
        hardkill(pid)
    print(f"preflight_sweep: {len(pids)} orphan node(s) killed")

preflight_sweep()
proc = subprocess.Popen(["node", IDX], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)

# HARD CEILING: call()'s per-request timeout is illusory -- readline() blocks forever if
# the node child stays silent (14.07 instance hung 2 days; IgnoreNew then skipped 15-16.07).
# Normal full run is ~5-8 min; 30 min means something is wedged -> kill our client, exit 2.
MAX_RUNTIME = 30*60
def _watchdog():
    print(f"WATCHDOG: {MAX_RUNTIME}s ceiling hit -- killing own client, exit 2", flush=True)
    try: hardkill(proc.pid)
    except Exception: pass
    os._exit(2)
_wd = threading.Timer(MAX_RUNTIME, _watchdog)
_wd.daemon = True
_wd.start()
_id = [0]
def call(method, params=None, wait=60):
    _id[0] += 1; mid = _id[0]
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":mid,"method":method,"params":params or {}})+"\n")
    proc.stdin.flush()
    end = time.time()+wait
    while time.time() < end:
        line = proc.stdout.readline()
        if not line: break
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except: continue
        if m.get("id") == mid: return m
    return None
def notify(method, params=None):
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":method,"params":params or {}})+"\n")
    proc.stdin.flush()
def text_of(resp):
    if not resp or "result" not in resp: return ""
    return "\n".join(c.get("text","") for c in resp["result"].get("content",[]) if c.get("type")=="text")

try:
    init = call("initialize", {"protocolVersion":"2024-11-05","capabilities":{},
                               "clientInfo":{"name":"nightly-pull","version":"1.0"}})
    print("INIT:", "ok" if init else "FAIL")
    notify("notifications/initialized")

    prof = text_of(call("tools/call", {"name":"get_my_profile","arguments":{}}, wait=40))
    open(os.path.join(RAW,"profile.txt"),"w",encoding="utf-8").write(prof)
    print("PROFILE:", prof[:120].replace("\n"," "))

    print(f"sync wait {SYNC_WAIT}s..."); time.sleep(SYNC_WAIT)

    # resolve DM/LID names in the SAME session (folds in names_fix)
    res = text_of(call("tools/call", {"name":"resolve_contacts","arguments":{"resync":True}}, wait=120))
    print("RESOLVE:", res[:200].replace("\n"," "))
    time.sleep(8)

    chats_txt = text_of(call("tools/call", {"name":"list_chats","arguments":{"limit":100}}, wait=60))
    open(os.path.join(RAW,"chats.txt"),"w",encoding="utf-8").write(chats_txt)
    jids = re.findall(r"[\w\-.]+@(?:s\.whatsapp\.net|g\.us)", chats_txt)
    seen=set(); jids=[j for j in jids if not (j in seen or seen.add(j))]
    print(f"CHATS: {len(jids)} unique JIDs")

    manifest=[]; total=0
    for i,j in enumerate(jids[:TOP_CHATS]):
        mt = text_of(call("tools/call", {"name":"list_messages","arguments":{"jid":j,"limit":MSGS_PER}}, wait=60))
        safe = re.sub(r"[^\w.\-]","_", j)[:60]
        fn = f"msgs_{i:03d}_{safe}.txt"
        open(os.path.join(RAW, fn),"w",encoding="utf-8").write(mt)
        n = mt.count("\n")+1 if mt.strip() else 0
        total += n; manifest.append({"jid":j,"file":fn,"lines":n})
        time.sleep(0.4)
    json.dump({"profile":prof[:200],"chats_found":len(jids),"pulled":len(manifest),
               "approx_msg_lines":total,"manifest":manifest},
              open(os.path.join(OUT,"train_summary.json"),"w",encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"DONE pull: {len(manifest)} chats, ~{total} lines")
finally:
    _wd.cancel()
    try: proc.terminate()
    except Exception: pass
    time.sleep(1)
    hardkill(proc.pid)
