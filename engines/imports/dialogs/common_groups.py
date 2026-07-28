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
"""common_groups.py -- "do we share any groups with this person/company?"

Deterministic join over chats.db (chat_members x chat_accounts). 0 tokens, instant.
Answers Anton's prep question: for a target person (or each employee of a company)
list the groups where one of OUR accounts is present alongside them.

Usage:
  python common_groups.py @handle
  python common_groups.py 712617695            # telegram_id
  python common_groups.py "Firstname Lastname" # fuzzy name over known members
  python common_groups.py @handle --account corp_acct   # restrict to one account

COVERAGE NOTE: member rosters come from the CRM export `members` field, which is
FULL for small private/curated groups (intro & deal rooms -- the ones that matter
for "near the right people") but PARTIAL/empty for big public groups. For an
authoritative per-person answer use the live MCP tool get_common_chats(user, account).
ASCII-safe stdout.
"""
import sqlite3, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "namesearch"))
try:
    import name_norm as nn
except Exception:
    nn = None


def resolve_targets(con, arg):
    """arg -> set of (telegram_id, label) of the person(s) it matches in chat_members."""
    arg = arg.strip()
    rows = con.execute(
        "SELECT DISTINCT member_id, member_username, member_name FROM chat_members").fetchall()
    if arg.lstrip("-").isdigit():
        tid = int(arg)
        labs = [r for r in rows if r[0] == tid]
        return {(tid, (labs[0][2] if labs else str(tid)))}
    if arg.startswith("@"):
        u = arg[1:].lower()
        return {(r[0], r[2] or r[1]) for r in rows if (r[1] or "").lower() == u}
    # fuzzy name
    q = arg.lower()
    qv = {q}
    if nn:
        qv.add(nn.translit(q))
    out = set()
    for mid, mu, mname in rows:
        hay = (mname or "").lower()
        hayt = nn.translit(hay) if nn else hay
        if any(v in hay or v in hayt for v in qv):
            out.add((mid, mname or mu or str(mid)))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: python common_groups.py <@handle|telegram_id|name> [--account X]")
        return
    account = None
    words = []
    i = 0
    while i < len(args):
        if args[i] == "--account" and i + 1 < len(args):
            account = args[i + 1]; i += 2; continue
        words.append(args[i]); i += 1
    arg = " ".join(words)

    con = sqlite3.connect(DB)
    targets = resolve_targets(con, arg)
    if not targets:
        print("no known member matches '%s' in chat_members (try live get_common_chats)"
              % arg.encode("ascii", "replace").decode())
        return

    print("target(s) matched: %d" % len(targets))
    for tid, label in sorted(targets):
        # groups where this target is a known member AND one of our accounts sits
        q = """SELECT g.chat_id, g.name, g.link, g.type, g.origin, g.topic,
                      GROUP_CONCAT(DISTINCT ca.account_username)
               FROM chat_members cm
               JOIN groups g ON g.chat_id = cm.chat_id
               JOIN chat_accounts ca ON ca.chat_id = cm.chat_id
               WHERE cm.member_id = ?"""
        params = [tid]
        if account:
            q += " AND ca.account_username = ?"
            params.append(account)
        q += " GROUP BY g.chat_id ORDER BY g.origin, g.name"
        rows = con.execute(q, params).fetchall()
        lab = (label or "").encode("ascii", "replace").decode()
        print("\n== %s (id=%s) -> %d common group(s) ==" % (lab, tid, len(rows)))
        for cid, name, link, typ, origin, topic, accs in rows:
            safe = (name or "").encode("ascii", "replace").decode()[:46]
            ref = link if link else "(private id=%s)" % cid
            print("  [%-9s|%-10s] %-46s via %-22s %s"
                  % (origin, topic, safe, accs or "?", ref))
    con.close()


if __name__ == "__main__":
    main()
