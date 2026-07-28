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
"""build_group_digest.py -- compact per-group material for LLM sub-classification.

Activity = recency of the last real message (decoded from the Mongo ObjectId _id:
first 8 hex chars = unix seconds) + members_count. We don't have messages_count in
the export, so "alive" = recently-talking.

Writes table group_digest(chat_id, latest_ts, n_text_msgs, bio, recent_text) into
chats.db and prints the top-N activity slice. Deterministic, 0 LLM, idempotent.
Run after build_group_graph.py.
"""
import csv, json, io, os, sqlite3

csv.field_size_limit(10**7)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
CRM_CSV = os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\contacts.csv")
CHATS_JSONL = os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\chats.jsonl")
CHAT_TYPES = ("group", "super_group", "channel")
MAX_TEXT = 1800


def oid_ts(oid):
    try:
        return int(str(oid)[:8], 16)
    except (ValueError, TypeError):
        return 0


def main():
    # bios from contacts.csv
    bio = {}
    with io.open(CRM_CSV, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get("telegram_type") or "") not in CHAT_TYPES:
                continue
            try:
                cid = int(row.get("telegram_id"))
            except (TypeError, ValueError):
                continue
            b = (row.get("bio") or "").strip()
            if b:
                bio[cid] = b[:600]

    con = sqlite3.connect(DB)
    con.execute("DROP TABLE IF EXISTS group_digest")
    con.execute("""CREATE TABLE group_digest(
        chat_id INTEGER PRIMARY KEY, latest_ts INTEGER, n_text_msgs INTEGER,
        bio TEXT, recent_text TEXT)""")

    n = 0
    with io.open(CHATS_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            tid = d.get("telegram_id", "")
            if not str(tid).startswith("-"):
                continue
            try:
                cid = int(tid)
            except ValueError:
                continue
            seen = {}
            for ch in d.get("chats", []):
                for m in ch.get("last_messages", []):
                    msg = (m.get("message") or "").strip()
                    if not msg:
                        continue
                    oid = m.get("_id")
                    seen[oid] = (oid_ts(oid), (m.get("sender") or {}).get("username", ""), msg)
            if not seen:
                continue
            msgs = sorted(seen.values(), key=lambda x: -x[0])
            latest = msgs[0][0]
            parts, total = [], 0
            for ts, snd, msg in msgs:
                line_s = "<%s> %s" % (snd or "?", msg.replace("\n", " "))
                if total + len(line_s) > MAX_TEXT:
                    break
                parts.append(line_s)
                total += len(line_s)
            con.execute("INSERT OR REPLACE INTO group_digest VALUES(?,?,?,?,?)",
                        (cid, latest, len(msgs), bio.get(cid, ""), "\n".join(parts)))
            n += 1
    con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS idx_gd_ts ON group_digest(latest_ts)")
    con.commit()

    print("GROUP DIGEST OK -> chats.db  (%d chats with text)" % n)
    print("  -- top 12 by activity (recency) --")
    q = """SELECT g.name, g.origin, g.topic, g.members_count, gd.n_text_msgs,
                  datetime(gd.latest_ts,'unixepoch')
           FROM group_digest gd JOIN groups g ON g.chat_id=gd.chat_id
           ORDER BY gd.latest_ts DESC LIMIT 12"""
    for name, origin, topic, mc, nt, dt in con.execute(q):
        safe = (name or "").encode("ascii", "replace").decode()[:42]
        print("  %s  [%-9s|%-10s] mc=%-6s msgs=%-3s last=%s"
              % (safe.ljust(42), origin, topic, mc, nt, dt))
    # how many in the top-activity window we'd classify
    for cut in (500, 1000, 1500, 2000):
        row = con.execute("""SELECT COUNT(*) FROM (
            SELECT chat_id FROM group_digest ORDER BY latest_ts DESC LIMIT ?)""", (cut,)).fetchone()
        print("  top %d cutoff ready" % cut)
        break
    con.close()


if __name__ == "__main__":
    main()
