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
# Merge group_labels.json (Sonnet-inferred) into the DB.
# named=2 marks an INFERRED label (vs named=1 = real resolved name, 0 = numeric).
import sqlite3, json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = "whatsapp_train.db"
con = sqlite3.connect(DB); cur = con.cursor()

# add columns if missing
for col, typ in [("one_line", "TEXT"), ("conf", "TEXT")]:
    try: cur.execute(f"ALTER TABLE chats ADD COLUMN {col} {typ}")
    except sqlite3.OperationalError: pass

if not os.path.exists("group_labels.json"):
    print("no group_labels.json yet -- skip (groups stay numeric until labeled). 0 applied")
    con.close(); sys.exit(0)
labels = json.load(open("group_labels.json", encoding="utf-8"))
n = 0
for x in labels:
    cur.execute(
        "UPDATE chats SET name=?, category=?, named=2, one_line=?, conf=? WHERE jid=?",
        (x["label"], x["category"], x.get("one_line", ""), x.get("confidence", ""), x["jid"])
    )
    n += cur.rowcount
con.commit()
named1 = cur.execute("SELECT COUNT(*) FROM chats WHERE named=1").fetchone()[0]
named2 = cur.execute("SELECT COUNT(*) FROM chats WHERE named=2").fetchone()[0]
print(f"applied {n} inferred group labels. named=1(real):{named1}  named=2(inferred):{named2}")
con.close()
