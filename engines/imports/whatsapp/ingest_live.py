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
"""Bridge: convert a live MCP pull (live_pull.json) into the raw_train/ + manifest
format that build_db.py expects. SAFE path: no extra Baileys client is spawned
(the agent pulls via the already-connected mcp__whatsapp__* tools), so it can NEVER
trigger AUTH_KEY_DUPLICATED. Text-only (Anton 2026-06-15): media flags kept, files never fetched.

live_pull.json schema (written by the agent from MCP results):
  [ { "jid": "...", "name": "...", "isGroup": true/false,
      "messages": [ {id, from, fromMe, type, text, timestamp, hasMedia}, ... ] }, ... ]
"""
import json, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = r"%IMPORTS%\whatsapp"
RAW = os.path.join(OUT, "raw_train")
os.makedirs(RAW, exist_ok=True)

src = json.load(open(os.path.join(OUT, "live_pull.json"), encoding="utf-8"))
chats, manifest = [], []
for i, ch in enumerate(src):
    jid = ch["jid"]
    chats.append({"jid": jid, "name": ch.get("name", jid),
                  "isGroup": bool(ch.get("isGroup", jid.endswith("@g.us")))})
    fn = f"{i:03d}.json"
    json.dump(ch.get("messages", []), open(os.path.join(RAW, fn), "w", encoding="utf-8"),
              ensure_ascii=False)
    manifest.append({"jid": jid, "file": fn})

json.dump(chats, open(os.path.join(RAW, "chats.txt"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"manifest": manifest, "n_chats": len(chats),
           "n_msgs": sum(len(c.get("messages", [])) for c in src)},
          open(os.path.join(OUT, "train_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"ingest_live: {len(chats)} chats, {sum(len(c.get('messages',[])) for c in src)} msgs -> raw_train/ + manifest")
