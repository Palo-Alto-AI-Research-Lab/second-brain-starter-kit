# -*- coding: utf-8 -*-
"""Backfill authored_by into Telegram post frontmatter.
human  = Anton's own voice transcripts / his messages
ai     = GPT-generated summaries
hybrid = assistant posts (translations/drafts, usually AI-assisted)
"""
import re
from pathlib import Path
from collections import Counter

POSTS = Path(r"E:/Obsidian/Anton-Knowledge/01-Conversations/Telegram/Arhiv-Golosa/posts")
SUMMARY_HEAD = re.compile(r'^(Краткое содержание|Обсуждали|Обсуждается|Summary|Резюме|Краткое резюме)', re.I)

def author_of(fm):
    m = re.search(r'^author:\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1).strip() if m else ""

stats = Counter()
for p in POSTS.glob("*.md"):
    text = p.read_text(encoding="utf-8")
    fm_m = re.match(r'^(---\n.*?\n---\n)(.*)$', text, re.DOTALL)
    if not fm_m:
        continue
    fm, body = fm_m.group(1), fm_m.group(2)
    if re.search(r'^authored_by:', fm, re.M):
        stats["already"] += 1
        continue
    author = author_of(fm)
    bodytext = body.strip()
    if author == "Personal Audio Summary":
        prov = "ai" if SUMMARY_HEAD.match(bodytext) else "human"
    elif author.startswith("Tony"):
        prov = "human"
    else:
        prov = "hybrid"
    stats[prov] += 1
    # insert authored_by right after the author: line (or before tags: as fallback)
    if re.search(r'^author:.*$', fm, re.M):
        fm = re.sub(r'^(author:.*)$', r'\1\nauthored_by: ' + prov, fm, count=1, flags=re.M)
    else:
        fm = fm.replace("tags:", f"authored_by: {prov}\ntags:", 1)
    p.write_text(fm + body, encoding="utf-8")

print(dict(stats))
