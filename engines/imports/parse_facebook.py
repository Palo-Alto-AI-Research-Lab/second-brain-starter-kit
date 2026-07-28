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
"""Phase 1: Parse Facebook posts export (посты.md) → JSONL checkpoint.
Triage: skip empty/link-only/photo-only. Strip photo markdown from text+photo.
Detect "5 Years Ago" memory duplicates (flag for dedup). Output UTF-8 JSONL."""
import os
import re, json, hashlib
from pathlib import Path
from datetime import datetime
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

INPUT = Path(os.path.expanduser(r"~\Downloads\Telegram Desktop\посты.md"))
OUTPUT = Path(os.path.join(IMPORTS, "_fb_posts.jsonl"))

# Transliteration table (Russian → Latin)
TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
    'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
    'щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}

def transliterate(text):
    result = []
    for ch in text.lower():
        result.append(TRANSLIT.get(ch, ch))
    return ''.join(result)

def slugify(text):
    t = transliterate(text[:80])
    t = re.sub(r'[^\w\s-]', ' ', t)
    t = re.sub(r'[\s_]+', '-', t.strip())
    t = re.sub(r'-+', '-', t).strip('-')
    return t[:60]

PHOTO_RE = re.compile(r'\[!\[.*?\]\([^)]+\)\]\([^)]+\)[^\n]*\n?')
FB_LINK_RE = re.compile(r'\*\*On Facebook:\*\*.*?\n', re.DOTALL)
MEMORIES_RE = re.compile(r'\n\d+ Years? Ago\n', re.I)

MONTHS = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
          'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}

def parse_date(s):
    """'Mar 30, 2011 8:54:36 pm' → '2011-03-30'"""
    s = s.strip()
    m = re.match(r'(\w+)\s+(\d+),\s+(\d{4})\s+(\d+):(\d+):(\d+)\s+(am|pm)', s, re.I)
    if not m: return None
    mon, day, yr, hr, mi, sc, ampm = m.groups()
    mon_n = MONTHS.get(mon.lower()[:3])
    if not mon_n: return None
    hr = int(hr); yr = int(yr); day = int(day)
    if ampm.lower() == 'pm' and hr != 12: hr += 12
    if ampm.lower() == 'am' and hr == 12: hr = 0
    try:
        return datetime(yr, mon_n, day, hr, int(mi), int(sc)).strftime('%Y-%m-%d')
    except:
        return f'{yr:04d}-{mon_n:02d}-{day:02d}'

content = INPUT.read_text(encoding='utf-8', errors='ignore')
blocks = content.split('\n---\n')

posts = []
stats = {'total': 0, 'empty': 0, 'link_only': 0, 'photo_only': 0,
         'imported': 0, 'memories_flagged': 0, 'parse_err': 0}

for block in blocks:
    # Header: ## N. Month DD, YYYY HH:MM:SS am/pm
    header_m = re.search(r'^## (\d+)\.\s+(.+?\d{4}\s+\d+:\d+:\d+\s+[ap]m)', block, re.M|re.I)
    if not header_m: continue
    stats['total'] += 1
    post_num = int(header_m.group(1))
    date_str = parse_date(header_m.group(2))

    content_m = re.search(r'### Content\n\n(.+?)(?=\n###|\Z)', block, re.DOTALL)
    if not content_m:
        stats['parse_err'] += 1; continue
    raw = content_m.group(1).strip()

    # Triage
    if raw == '_[empty]_':
        stats['empty'] += 1; continue
    # Strip photo markdown
    stripped = PHOTO_RE.sub('', raw).strip()
    # Strip Facebook archive link
    stripped = FB_LINK_RE.sub('', stripped).strip()
    # Strip bare URLs
    url_only = re.match(r'^\[?https?://\S+\]?$', stripped.strip())
    if url_only:
        stats['link_only'] += 1; continue
    if len(stripped) < 30:
        if PHOTO_RE.search(raw):
            stats['photo_only'] += 1
        else:
            stats['link_only'] += 1
        continue

    # Check for "5 Years Ago" memory wrapper
    is_memory = bool(MEMORIES_RE.search(block))
    if is_memory:
        stats['memories_flagged'] += 1

    text = stripped.strip()
    body_hash = hashlib.md5(text.encode('utf-8')).hexdigest()

    posts.append({
        'id': post_num,
        'date': date_str or 'unknown',
        'year': date_str[:4] if date_str else 'unknown',
        'text': text,
        'slug': slugify(text),
        'word_count': len(text.split()),
        'is_memory': is_memory,
        'body_hash': body_hash,
    })
    stats['imported'] += 1

# Write JSONL
with open(OUTPUT, 'w', encoding='utf-8') as f:
    for p in posts:
        f.write(json.dumps(p, ensure_ascii=False) + '\n')

# Write stats
stat_lines = [f'{k}={v}' for k, v in stats.items()]
Path(os.path.join(IMPORTS, "_fb_parse_stats.txt")).write_text('\n'.join(stat_lines), encoding='utf-8')
