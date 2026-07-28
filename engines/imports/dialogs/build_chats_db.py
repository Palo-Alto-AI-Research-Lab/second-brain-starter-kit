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
"""build_chats_db.py -- local index of ALL Telegram chats/entities -> chats.db.

WHY: "find chat X" used to mean paginating the live MCP dialog list for minutes.
Instead we mirror the CRM's PROVEN extraction: the CRM (mtproto-api) scrapes every
dialog into Mongo `tg_entities` with telegram_id + name + username + link + type.
That dump already sits on disk as crm_export\\contacts.csv (a near-raw tg_entities
export). We fold it into a tiny SQLite so lookup = 0 tokens, 0 MCP, instant.

Sources (most complete first):
  1. CRM dump  %WORKDIR%\\crm_export\\contacts.csv  (backbone, ~125k)
  2. live list_chats dumps per account (freshness, optional) -- see LIVE_SOURCES

Deterministic, 0 LLM. ASCII-only stdout. Idempotent (rebuilds from scratch).
Lookup = find_chat.py.
"""
import csv, json, io, os, sqlite3, sys

csv.field_size_limit(10**7)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
CRM_CSV = os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\contacts.csv")

# Optional live list_chats dumps (account label -> harness tool-result json file).
# Leave empty to build from the CRM dump alone; the refresh routine appends live rows.
LIVE_SOURCES = {}

CHAT_TYPES = ("group", "super_group", "channel")


def build_link(username, telegram_type, existing_link):
    u = (username or "").strip().lstrip("@")
    if u:
        return "https://t.me/%s" % u
    return (existing_link or "").strip()


def main():
    if not os.path.exists(CRM_CSV):
        print("ERROR: CRM dump missing: %s" % CRM_CSV)
        sys.exit(1)

    con = sqlite3.connect(DB)
    con.execute("DROP TABLE IF EXISTS chats")
    con.execute("""CREATE TABLE chats(
        telegram_id   INTEGER PRIMARY KEY,
        name          TEXT,
        username      TEXT,
        link          TEXT,
        type          TEXT,
        is_chat       INTEGER,   -- 1 = group/super_group/channel, 0 = user
        members_count INTEGER,
        last_message_date TEXT,
        tags          TEXT,
        source        TEXT)""")

    n = 0
    by_type = {}
    with io.open(CRM_CSV, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            tid = (row.get("telegram_id") or "").strip()
            if not tid:
                continue
            try:
                tid = int(tid)
            except ValueError:
                continue
            ttype = (row.get("telegram_type") or "").strip() or "unknown"
            name = (row.get("name") or "").strip()
            username = (row.get("username") or "").strip().lstrip("@")
            link = build_link(username, ttype, row.get("link"))
            is_chat = 1 if ttype in CHAT_TYPES else 0
            mc = (row.get("members_count") or "").strip()
            try:
                mc = int(float(mc)) if mc else None
            except ValueError:
                mc = None
            tags = (row.get("tags_str") or row.get("tags") or "").strip()
            con.execute(
                "INSERT OR REPLACE INTO chats VALUES(?,?,?,?,?,?,?,?,?,?)",
                (tid, name, username, link, ttype, is_chat, mc,
                 (row.get("last_message_date") or "").strip(), tags, "crm"))
            n += 1
            by_type[ttype] = by_type.get(ttype, 0) + 1

    # Optional live dumps (append; INSERT OR IGNORE keeps the richer CRM row).
    for acc, path in LIVE_SOURCES.items():
        if not os.path.exists(path):
            continue
        s = json.load(io.open(path, encoding="utf-8"))["result"]
        rows = json.loads(s[s.find("["):s.rfind("]") + 1])
        for d in rows:
            tid = d.get("chat_id") or d.get("id")
            if tid is None:
                continue
            ttype = (d.get("type") or "").strip() or "unknown"
            username = (d.get("username") or "").strip().lstrip("@")
            cur = con.execute("SELECT 1 FROM chats WHERE telegram_id=?", (tid,)).fetchone()
            if cur:
                continue
            con.execute(
                "INSERT OR IGNORE INTO chats VALUES(?,?,?,?,?,?,?,?,?,?)",
                (tid, (d.get("title") or d.get("name") or "").strip(), username,
                 build_link(username, ttype, None), ttype,
                 1 if ttype in CHAT_TYPES else 0, None, "", "", "live:%s" % acc))
            n += 1
            by_type[ttype] = by_type.get(ttype, 0) + 1

    con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS idx_name ON chats(name)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_user ON chats(username)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ischat ON chats(is_chat)")
    con.commit()
    con.close()

    chats = sum(by_type.get(t, 0) for t in CHAT_TYPES)
    print("CHATS DB OK -> chats.db")
    print("  total rows = %d" % n)
    for t in sorted(by_type, key=lambda k: -by_type[k]):
        print("  %-14s %d" % (t, by_type[t]))
    print("  CHATS (group+super_group+channel) = %d" % chats)


if __name__ == "__main__":
    main()
