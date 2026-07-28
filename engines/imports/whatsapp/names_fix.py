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
"""Phase 1: ask WhatsApp to refresh contact/LID names, then re-snapshot chat list."""
import json, subprocess, time, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
IDX = os.path.expanduser(r"~\AppData\Roaming\npm\node_modules\@oss_maintainer\whatsapp-mcp\dist\index.js")
OUT = r"%IMPORTS%\whatsapp"; RAW = os.path.join(OUT,"raw_train")

proc = subprocess.Popen(["node", IDX], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
_id=[0]
def call(method, params=None, wait=90):
    _id[0]+=1; mid=_id[0]
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":mid,"method":method,"params":params or {}})+"\n"); proc.stdin.flush()
    end=time.time()+wait
    while time.time()<end:
        l=proc.stdout.readline()
        if not l: break
        l=l.strip()
        if not l: continue
        try: m=json.loads(l)
        except: continue
        if m.get("id")==mid: return m
    return None
def notify(m,p=None): proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":m,"params":p or {}})+"\n"); proc.stdin.flush()
def text_of(r): return "\n".join(c.get("text","") for c in r["result"].get("content",[]) if c.get("type")=="text") if r and "result" in r else ""

call("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"names","version":"1.0"}})
notify("notifications/initialized")
time.sleep(8)
print("resolve_contacts(resync=true)... (slow)")
res = text_of(call("tools/call",{"name":"resolve_contacts","arguments":{"resync":True}}, wait=120))
print("RESOLVE:", res[:400])
time.sleep(10)
chats = text_of(call("tools/call",{"name":"list_chats","arguments":{"limit":100}}, wait=60))
open(os.path.join(RAW,"chats2.txt"),"w",encoding="utf-8").write(chats)
try:
    arr=json.loads(chats)
    named=[c for c in arr if not c["name"].startswith(c["jid"].split("@")[0])]
    numeric=[c for c in arr if c["name"].startswith(c["jid"].split("@")[0])]
    print(f"chats={len(arr)}  named={len(named)}  still-numeric={len(numeric)}")
    print("NAMED sample:", [c["name"] for c in named[:15]])
except Exception as e:
    print("parse err", e)
proc.terminate()
