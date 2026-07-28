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
WhatsApp TRAINING pull (variant A, live bridge).
Spawns ONE temporary stdio client against the already-paired @oss_maintainer/whatsapp-mcp
server, lets history sync, then pulls chats + recent messages into a local archive.
GENTLE / read-only (telegram-safety analog). No vault writes here -- this is a dry run.
NEVER run while another whatsapp node is connected (AUTH_KEY_DUPLICATED landmine).
"""
import json, subprocess, time, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

IDX = os.path.expanduser(r"~\AppData\Roaming\npm\node_modules\@oss_maintainer\whatsapp-mcp\dist\index.js")
OUT = r"%IMPORTS%\whatsapp"
RAW = os.path.join(OUT, "raw_train")
os.makedirs(RAW, exist_ok=True)

SYNC_WAIT = 45      # seconds to let companion history land
TOP_CHATS = 80      # all visible chats (text only; media files NEVER downloaded -- Anton 2026-06-15)
MSGS_PER  = 50      # recent messages per chat

proc = subprocess.Popen(["node", IDX], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
_id = [0]
def call(method, params=None, wait=60):
    _id[0] += 1
    mid = _id[0]
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

# 1) handshake
init = call("initialize", {"protocolVersion":"2024-11-05","capabilities":{},
                           "clientInfo":{"name":"train-pull","version":"1.0"}})
print("INIT:", "ok" if init else "FAIL")
notify("notifications/initialized")

# 2) profile
prof = text_of(call("tools/call", {"name":"get_my_profile","arguments":{}}, wait=40))
open(os.path.join(RAW,"profile.txt"),"w",encoding="utf-8").write(prof)
print("PROFILE:\n"+prof[:300])

# 3) let history sync
print(f"Waiting {SYNC_WAIT}s for companion history sync...")
time.sleep(SYNC_WAIT)

# 4) chats
chats_txt = text_of(call("tools/call", {"name":"list_chats","arguments":{"limit":100}}, wait=60))
open(os.path.join(RAW,"chats.txt"),"w",encoding="utf-8").write(chats_txt)
# extract JIDs (any token like <digits>@s.whatsapp.net or <...>@g.us)
import re
jids = re.findall(r"[\w\-.]+@(?:s\.whatsapp\.net|g\.us)", chats_txt)
seen=set(); jids=[j for j in jids if not (j in seen or seen.add(j))]
print(f"CHATS: {chats_txt.count(chr(10))+1} lines, {len(jids)} unique JIDs found")

# 5) pull recent messages per top chat (gentle)
manifest=[]
total_msgs=0
for i,j in enumerate(jids[:TOP_CHATS]):
    mt = text_of(call("tools/call", {"name":"list_messages","arguments":{"jid":j,"limit":MSGS_PER}}, wait=60))
    safe = re.sub(r"[^\w.\-]","_", j)[:60]
    open(os.path.join(RAW, f"msgs_{i:03d}_{safe}.txt"),"w",encoding="utf-8").write(mt)
    n = mt.count("\n")+1 if mt.strip() else 0
    total_msgs += n
    manifest.append({"jid":j,"file":f"msgs_{i:03d}_{safe}.txt","lines":n})
    time.sleep(0.4)  # gentle pacing
    if (i+1)%10==0: print(f"  pulled {i+1}/{min(TOP_CHATS,len(jids))} chats...")

json.dump({"profile":prof[:300],"chats_found":len(jids),
           "pulled":len(manifest),"approx_msg_lines":total_msgs,
           "manifest":manifest}, open(os.path.join(OUT,"train_summary.json"),"w",encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"DONE. pulled {len(manifest)} chats, ~{total_msgs} message lines -> {RAW}")
proc.terminate()
