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
"""build_group_graph.py -- the group-graph layer on top of chats.db.

Prepares the data for "link everything":
  * chat_accounts : which of OUR accounts sits in which chat   (from chats.jsonl)
  * csv_members  : who else is in a (small/private) chat       (from contacts.csv members[])
  * groups        : per-chat meta + ours-vs-theirs flag + topic bucket

Authoritative membership = chats.jsonl (entity.chats[].account[].telegram_id).
Member rosters = contacts.csv `members` (FULL for small private groups med~4,
partial/empty for big public groups -- by design of the CRM export).

Deterministic, 0 LLM, idempotent. ASCII-only stdout. Run after build_chats_db.py.
"""
# NOTE 2026-07-16: output table renamed chat_members -> csv_members. The LIVE chat_members
# table now belongs EXCLUSIVELY to scrape_chat_members.py (single-writer). This script once
# DROPped it and silently destroyed 10 days of live member scraping. Never write to chat_members here.
import csv, json, io, os, sqlite3, re

csv.field_size_limit(10**7)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
CRM_CSV = os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\contacts.csv")
CHATS_JSONL = os.path.expanduser(r"~\!CLAUDE-HP17 May26\crm_export\chats.jsonl")
CHAT_TYPES = ("group", "super_group", "channel")

# "We created / branded it" name signals (Anton's Palo Alto network + intro groups).
OURS_HIGH = [r"by palo alto", r"palo alto research", r"research lab",
             r"c\(h\+a\)rm", r"charm", r"\baaa\b"]
OURS_MED = [r"🤝", r" <> ", r"<>", r"palo alto", r"openclaw"]

# Cheap topic buckets from name keywords (refined later by CRM tags / LLM).
TOPIC = [
    ("vc_invest",   r"\bvc\b|invest|fund|angel|lp\b|capital|raise"),
    ("founders",    r"founder|startup|builder|entrepreneur"),
    ("ai",          r"\bai\b|agent|ml\b|llm|gpt|neural"),
    ("crypto_defi", r"defi|dao|web3|crypto|token|nft|chain|eth|solana"),
    ("events_geo",  r"event|meetup|summit|conf|miami|france|dubai|singapore|lisbon|london|berlin"),
    ("intro_deal",  r"🤝| <> |<>|deal|intro"),
    ("longevity",   r"longevity|health|biohack|weight|fasting|nootrop"),
    ("ops_team",    r"team|ops|assist|support|admin|staff"),
]


def topic_of(name):
    n = (name or "").lower()
    for label, pat in TOPIC:
        if re.search(pat, n):
            return label
    return "other"


def ours_flag(name):
    n = (name or "").lower()
    for p in OURS_HIGH:
        if re.search(p, n):
            return "ours_high"
    for p in OURS_MED:
        if re.search(p, n):
            return "ours_med"
    return "theirs"


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 1) chat_accounts from chats.jsonl --------------------------------------
    cur.execute("DROP TABLE IF EXISTS chat_accounts")
    cur.execute("""CREATE TABLE chat_accounts(
        chat_id INTEGER, account_username TEXT, account_telegram_id INTEGER,
        PRIMARY KEY(chat_id, account_telegram_id))""")
    acct_rows = 0
    accounts = {}
    with io.open(CHATS_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            try:
                cid = int(d.get("telegram_id"))
            except (TypeError, ValueError):
                continue
            seen = set()
            for ch in d.get("chats", []):
                for a in ch.get("account", []):
                    atid = a.get("telegram_id")
                    if atid is None or atid in seen:
                        continue
                    seen.add(atid)
                    cur.execute("INSERT OR IGNORE INTO chat_accounts VALUES(?,?,?)",
                                (cid, a.get("username") or "", atid))
                    acct_rows += 1
                    u = a.get("username") or str(atid)
                    accounts[u] = accounts.get(u, 0) + 1

    # 2) csv_members + groups meta from contacts.csv ------------------------
    cur.execute("DROP TABLE IF EXISTS csv_members")
    cur.execute("""CREATE TABLE csv_members(
        chat_id INTEGER, member_id INTEGER, member_username TEXT, member_name TEXT)""")
    cur.execute("DROP TABLE IF EXISTS groups")
    cur.execute("""CREATE TABLE groups(
        chat_id INTEGER PRIMARY KEY, name TEXT, username TEXT, link TEXT,
        type TEXT, members_count INTEGER, tags TEXT, topic TEXT, origin TEXT,
        n_members_known INTEGER, n_our_accounts INTEGER)""")
    mem_rows = 0
    grp = 0
    with io.open(CRM_CSV, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get("telegram_type") or "") not in CHAT_TYPES:
                continue
            try:
                cid = int(row.get("telegram_id"))
            except (TypeError, ValueError):
                continue
            grp += 1
            name = (row.get("name") or "").strip()
            nm = 0
            for m in json.loads(row.get("members") or "[]") if (row.get("members") or "").strip() else []:
                if not isinstance(m, dict):
                    continue
                cur.execute("INSERT INTO csv_members VALUES(?,?,?,?)",
                            (cid, m.get("id"), m.get("username") or "", m.get("name") or ""))
                mem_rows += 1
                nm += 1
            mc = (row.get("members_count") or "").strip()
            try:
                mc = int(float(mc)) if mc else None
            except ValueError:
                mc = None
            n_our = cur.execute(
                "SELECT COUNT(*) FROM chat_accounts WHERE chat_id=?", (cid,)).fetchone()[0]
            cur.execute("INSERT OR REPLACE INTO groups VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, name, (row.get("username") or "").strip(),
                         (row.get("link") or "").strip(), row.get("telegram_type"),
                         mc, (row.get("tags_str") or "").strip(),
                         topic_of(name), ours_flag(name), nm, n_our))

    con.commit()
    for stmt in ("CREATE INDEX IF NOT EXISTS idx_ca_acc ON chat_accounts(account_telegram_id)",
                 "CREATE INDEX IF NOT EXISTS idx_csvm_mem ON csv_members(member_id)",
                 "CREATE INDEX IF NOT EXISTS idx_csvm_chat ON csv_members(chat_id)",
                 "CREATE INDEX IF NOT EXISTS idx_g_origin ON groups(origin)",
                 "CREATE INDEX IF NOT EXISTS idx_g_topic ON groups(topic)"):
        cur.execute(stmt)
    con.commit()

    # 3) report --------------------------------------------------------------
    print("GROUP GRAPH OK -> chats.db")
    print("  chat_accounts rows = %d | csv_members rows = %d | groups = %d"
          % (acct_rows, mem_rows, grp))
    print("  -- groups per account (top 12) --")
    for u, n in sorted(accounts.items(), key=lambda x: -x[1])[:12]:
        gc = cur.execute("""SELECT COUNT(*) FROM chat_accounts ca JOIN groups g
                            ON ca.chat_id=g.chat_id WHERE ca.account_username=?""", (u,)).fetchone()[0]
        print("     %-22s chats=%-6d groups=%d" % (u, n, gc))
    print("  -- ours vs theirs --")
    for o, n in cur.execute("SELECT origin, COUNT(*) FROM groups GROUP BY origin ORDER BY 2 DESC"):
        print("     %-12s %d" % (o, n))
    print("  -- topic buckets --")
    for t, n in cur.execute("SELECT topic, COUNT(*) FROM groups GROUP BY topic ORDER BY 2 DESC"):
        print("     %-12s %d" % (t, n))
    con.close()


if __name__ == "__main__":
    main()
