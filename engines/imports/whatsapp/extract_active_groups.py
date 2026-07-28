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
# Extract compact content samples for ACTIVE groups -> active_groups.json
# Deterministic (0 tokens). Feeds a Sonnet labeler. Text-only (Anton 2026-06-15).
import sqlite3, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = "whatsapp_train.db"
MIN_MINE = 3          # "active" = Anton wrote >=3 msgs
MAX_MSGS = 14         # sample size per group (compact)
MAXLEN = 160          # truncate each msg

db = sqlite3.connect(DB); db.row_factory = sqlite3.Row
groups = db.execute(
    "select jid,n,n_mine,first,last from chats "
    "where is_group=1 and n_mine>=? order by n_mine desc", (MIN_MINE,)
).fetchall()

out = []
for g in groups:
    jid = g["jid"]
    # top senders (who talks here -> strong topic signal)
    senders = db.execute(
        "select sender,count(*) c from messages where chat_jid=? and from_me=0 "
        "and sender!='' group by sender order by c desc limit 6", (jid,)
    ).fetchall()
    # a spread of real text messages (skip empties/media-only)
    msgs = db.execute(
        "select sender,from_me,text from messages where chat_jid=? and text!='' "
        "order by ts asc", (jid,)
    ).fetchall()
    sample = []
    step = max(1, len(msgs)//MAX_MSGS)
    for i in range(0, len(msgs), step):
        m = msgs[i]
        who = "Anton" if m["from_me"] else (m["sender"] or "?")
        t = (m["text"] or "").replace("\n", " ").strip()[:MAXLEN]
        if t:
            sample.append(f"{who}: {t}")
        if len(sample) >= MAX_MSGS:
            break
    out.append({
        "jid": jid,
        "n": g["n"], "n_mine": g["n_mine"],
        "span": f'{g["first"]} -> {g["last"]}',
        "top_senders": [f'{s["sender"]} ({s["c"]})' for s in senders],
        "sample": sample,
    })

with open("active_groups.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"wrote active_groups.json: {len(out)} active groups (n_mine>={MIN_MINE})")
