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
"""find_chat.py -- instant local Telegram chat lookup over chats.db (0 tokens, 0 MCP).

Solves "find chat X" taking minutes of paginated MCP crawling: the chat's
telegram_id + link are already in chats.db (built from the CRM tg_entities dump).
Print id -> operate the chat directly via the Telegram MCP (get_history, send, etc).

Usage:
  python find_chat.py <query words...>     # chats first, then people
  python find_chat.py <query> --all        # include user DMs too
  python find_chat.py <query> --users      # only user DMs
  python find_chat.py <query> --limit 80

Matching catches cross-alphabet + wrong keyboard layout + light typos by reusing
the namesearch brain (name_norm.py): "lobster"/"лобстер", "ku,thconfo" layout, etc.
ASCII-safe stdout (escapes non-ascii so Windows cp1252 never crashes).
"""
import sqlite3, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "chats.db")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "namesearch"))
try:
    import name_norm as nn
except Exception:
    nn = None

TYPE_TAG = {"channel": "CHANNEL", "super_group": "SUPERGRP",
            "group": "GROUP", "user": "user", "unknown": "?"}


def q_variants(q):
    """All spellings of the query to test as a substring."""
    q = q.strip().lower()
    out = {q}
    if nn:
        out.add(nn.translit(q))                       # cyr -> lat
        cyr = nn.en_layout_to_ru(q)                   # dbrnjh -> виктор
        if nn._has_cyr(cyr):
            out.add(cyr)
            out.add(nn.translit(cyr))
        en = nn.ru_layout_to_en(q)                    # мшлещк -> viktor
        if en != q:
            out.add(en)
    return {v for v in out if v}


def norm(s):
    return (s or "").lower()


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print("usage: python find_chat.py <query> [--all|--users] [--limit N]")
        return
    limit = 50
    mode = "chats"          # chats-first (default) | all | users
    words = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--all":
            mode = "all"
        elif a == "--users":
            mode = "users"
        elif a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 1
        else:
            words.append(a)
        i += 1
    q = " ".join(words).strip().lower()
    if not q:
        print("usage: python find_chat.py <query>")
        return
    # Per-word variants: a chat matches only if EVERY query word is found
    # (each word via its own spellings). Multi-word queries are AND, not one
    # contiguous substring -- "Фокс подкаст" must hit "подкасты у Фокса".
    word_variants = [q_variants(w) for w in q.split() if w.strip()]
    if not word_variants:
        word_variants = [q_variants(q)]
    variants = set().union(*word_variants)   # for the echo count only

    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT telegram_id,name,username,link,type,is_chat,members_count,last_message_date FROM chats"
    ).fetchall()
    con.close()

    hits = []
    for tid, name, username, link, typ, is_chat, mc, lmd in rows:
        if mode == "users" and is_chat:
            continue
        hay_name = norm(name)
        hay_user = norm(username)
        hay_user_t = nn.translit(hay_user) if nn else hay_user
        hay_name_t = nn.translit(hay_name) if nn else hay_name
        hays = (hay_name, hay_user, hay_name_t, hay_user_t)
        # every word must match via at least one of its variants
        matched = all(
            any(v in h for v in vs for h in hays)
            for vs in word_variants
        )
        if matched:
            hits.append((tid, name, username, link, typ, is_chat, mc or 0, lmd or ""))

    # rank: chats before users (unless --users), bigger membership first, then recency
    def rank(h):
        tid, name, username, link, typ, is_chat, mc, lmd = h
        chat_pri = 0 if (is_chat and mode != "users") else 1
        return (chat_pri, -mc, lmd and (lmd < "0"))
    hits.sort(key=rank)

    chat_n = sum(1 for h in hits if h[5])
    print("query=%s  variants=%d  hits=%d (chats=%d, users=%d)"
          % (q.encode("ascii", "replace").decode(), len(variants), len(hits),
             chat_n, len(hits) - chat_n))
    shown = hits if mode != "chats" else (
        [h for h in hits if h[5]] + [h for h in hits if not h[5]])
    for tid, name, username, link, typ, is_chat, mc, lmd in shown[:limit]:
        safe = (name or "").encode("ascii", "replace").decode()
        tag = TYPE_TAG.get(typ, typ)
        ref = link if link else ("@" + username if username else "(private)")
        mcs = ("  %d members" % mc) if (is_chat and mc) else ""
        print("  [%-8s] %-15s %-44s %s%s" % (tag, tid, safe[:44], ref, mcs))
    if len(shown) > limit:
        print("  ... %d more (raise --limit)" % (len(shown) - limit))


if __name__ == "__main__":
    main()
