#!/usr/bin/env python3
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
"""Phase 1 parser: Anton's personal Telegram DM markdown exports -> dm-archive.jsonl + dm-index.json
One JSONL row per message. Keep stdout ASCII-only (Windows cp1252)."""
import os
import re, json, hashlib, glob
from pathlib import Path
from collections import defaultdict
from datetime import datetime
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

# ALL account exports (multi-account), chronological
ACCT_FROM_FILE = re.compile(r'account-(\d+)-(\d{4})\.md$')
_allfiles = sorted(glob.glob(os.path.expanduser(r"~\Downloads\Telegram Desktop\account-*-*.md")))
KEEP_ACCOUNTS = {'265315838', '7303193973', '226258979'}   # @work_acct_b + @corp_acct + @work_acct_a (all confirmed)
FILES = [f for f in _allfiles if ACCT_FROM_FILE.search(f) and ACCT_FROM_FILE.search(f).group(1) in KEEP_ACCOUNTS]
SELF_ACCOUNTS = {ACCT_FROM_FILE.search(f).group(1) for f in FILES}  # Anton's own account ids
HEADER_RE = re.compile(r'Account:\s*\*\*@?([A-Za-z0-9_]+)\*\*\s*·\s*Telegram ID\s*`?(\d+)`?')
PRIMARY_ACCT = '265315838'
id2handle = {}
OUT_JSONL = Path(os.path.join(IMPORTS, "dm-archive.jsonl"))
OUT_INDEX = Path(os.path.join(IMPORTS, "dm-index.json"))

DIALOG_HEAD_RE = re.compile(r'^## Dialog: (.+?)(?: \(@([^)]+)\))?\s*$', re.M)
LEADID_RE = re.compile(r'^- Lead Telegram ID: `(\d+)`', re.M)
USER_RE   = re.compile(r'^- Username: @?(.+)$', re.M)
MSG_RE = re.compile(r'^#### (\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2}:\d{2}) UTC · (Account|Lead) · (.+?)\s*$', re.M)
EDITED_RE = re.compile(r'\n?\s*\*Edited: [^*]+\*\s*$')
URL_RE = re.compile(r'https?://\S+')

TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i',
    'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
    'у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'',
    'э':'e','ю':'yu','я':'ya',
}
def translit(s):
    out=[]
    for ch in s:
        low=ch.lower()
        if low in TRANSLIT:
            t=TRANSLIT[low]
            out.append(t.upper() if ch.isupper() and t else t)
        else:
            out.append(ch)
    return ''.join(out)

def slugify(name, username, lead_id):
    # strip trailing "(tg:NNN)" marker
    base = re.sub(r'\s*\(tg:\d+\)\s*$', '', name).strip()
    if re.fullmatch(r'(?i)lead', base) or not base:
        if username: base = username
        else: return f"lead-{lead_id}"
    s = translit(base).lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    if not s:
        s = (username or f"lead-{lead_id}").lower()
        s = re.sub(r'[^a-z0-9-]', '', s)
    return s[:50] or f"lead-{lead_id}"

def clean_body(raw):
    # raw is text between a #### header and the next header/---; strip "> " prefixes
    lines = raw.split('\n')
    lines = [re.sub(r'^> ?', '', ln) for ln in lines]
    body = '\n'.join(lines)
    # drop trailing horizontal rule
    body = re.sub(r'\n-{3,}\s*$', '', body)
    # capture edited flag then strip the footer
    edited = bool(EDITED_RE.search(body))
    body = EDITED_RE.sub('', body)
    # unwrap a ```text ... ``` or ``` ... ``` fence that wraps the whole message (export artifact)
    m = re.match(r'^\s*```(?:text)?\s*\n(.*)\n```\s*$', body, re.DOTALL)
    if m:
        body = m.group(1)
    return body.strip(), edited

def classify(text):
    L = len(text)
    urls = URL_RE.findall(text)
    nonurl = URL_RE.sub('', text).strip()
    if L == 0: return 'empty'
    if urls and len(nonurl) < 8: return 'link'
    if L < 10: return 'noise'
    if L < 30: return 'short'
    if L < 200: return 'fragment'
    return 'post'

rows = []
index = {}   # pid -> meta
seen_hash = defaultdict(int)

for fp in FILES:
    text = Path(fp).read_text(encoding='utf-8')
    account_id = ACCT_FROM_FILE.search(fp).group(1)
    hh = HEADER_RE.search(text[:600])
    if hh: id2handle.setdefault(account_id, hh.group(1))
    year = re.search(r'-(\d{4})\.md$', fp).group(1)
    parts = re.split(r'(?m)^## Dialog: ', text)[1:]
    for part in parts:
        block = "## Dialog: " + part
        hm = DIALOG_HEAD_RE.search(block)
        if not hm: continue
        name = hm.group(1).strip().replace('\\|', '|').replace('[[', '(').replace(']]', ')')
        username = hm.group(2)
        lid_m = LEADID_RE.search(block)
        lead_id = lid_m.group(1) if lid_m else None
        um = USER_RE.search(block)
        if not username and um and um.group(1).strip() not in ('', 'None'):
            username = um.group(1).strip()
        pid = lead_id or ("name:" + name)
        slug = slugify(name, username, lead_id or pid)
        if pid not in index:
            index[pid] = dict(pid=pid, lead_id=lead_id, name=name, username=username,
                              slug=slug, years=set(), total=0,
                              cls=defaultdict(int), per_year=defaultdict(int),
                              first_ts=None, last_ts=None, acct=0, lead=0,
                              domains=defaultdict(int), accounts=set())
        meta = index[pid]
        meta['accounts'].add(account_id)
        if username and not meta['username']: meta['username'] = username
        # iterate messages
        headers = list(MSG_RE.finditer(block))
        for i, m in enumerate(headers):
            y, mo, d, hms, role, speaker = m.groups()
            start = m.end()
            end = headers[i+1].start() if i+1 < len(headers) else len(block)
            body_raw = block[start:end]
            body, edited = clean_body(body_raw)
            ts = f"{y}-{mo}-{d}T{hms}Z"
            date = f"{y}-{mo}-{d}"
            cls = classify(body)
            rowrole = 'account' if role == 'Account' else 'lead'
            h = hashlib.md5((pid + '|' + body).encode('utf-8')).hexdigest()[:12]
            seen_hash[pid + h] += 1
            for u in URL_RE.findall(body):
                dm = re.search(r'https?://([^/\s]+)', u)
                if dm: meta['domains'][dm.group(1).lower().lstrip('www.')] += 1
            row = dict(pid=pid, slug=meta['slug'], name=name, username=meta['username'],
                       year=y, date=date, ts=ts, role=rowrole, speaker=speaker,
                       text=body, cls=cls, edited=edited, len=len(body), h=h,
                       account=account_id)
            rows.append(row)
            meta['total'] += 1
            meta['years'].add(y); meta['per_year'][y] += 1
            meta['cls'][cls] += 1
            meta['acct' if rowrole == 'account' else 'lead'] += 1
            if meta['first_ts'] is None or ts < meta['first_ts']: meta['first_ts'] = ts
            if meta['last_ts'] is None or ts > meta['last_ts']: meta['last_ts'] = ts

# resolve slug collisions across different pids
slug_owner = {}
for pid, meta in index.items():
    s = meta['slug']
    if s in slug_owner and slug_owner[s] != pid:
        n = 2
        while f"{s}-{n}" in slug_owner: n += 1
        meta['slug'] = f"{s}-{n}"
    slug_owner[meta['slug']] = pid
# rewrite slug onto rows via pid map
slug_by_pid = {pid: meta['slug'] for pid, meta in index.items()}
for r in rows:
    r['slug'] = slug_by_pid[r['pid']]

# write JSONL
with OUT_JSONL.open('w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

# serialize index (sets/defaultdicts -> plain)
def topn(dd, n=8):
    return sorted(dd.items(), key=lambda kv: -kv[1])[:n]
idx_out = {}
for pid, m in index.items():
    idx_out[pid] = dict(
        pid=pid, lead_id=m['lead_id'], name=m['name'], username=m['username'],
        slug=m['slug'], years=sorted(m['years']), total=m['total'],
        acct=m['acct'], lead=m['lead'],
        per_year={y: m['per_year'][y] for y in sorted(m['per_year'])},
        cls=dict(m['cls']),
        first_ts=m['first_ts'], last_ts=m['last_ts'],
        top_domains=topn(m['domains']),
        accounts=sorted(m['accounts']),
        is_self=(pid in SELF_ACCOUNTS),
        is_person_note=(m['total'] >= 20 and pid not in SELF_ACCOUNTS),
        unidentified=bool(re.fullmatch(r'(?i)lead', re.sub(r'\s*\(tg:\d+\)\s*$','',m['name']).strip())),
    )
OUT_INDEX.write_text(json.dumps(idx_out, ensure_ascii=False, indent=1), encoding='utf-8')
Path(os.path.join(IMPORTS, "dm-accounts.json")).write_text(
    json.dumps(dict(id2handle=id2handle, self_accounts=sorted(SELF_ACCOUNTS), primary=PRIMARY_ACCT),
               ensure_ascii=False, indent=1), encoding='utf-8')

# ASCII stats
n_person = sum(1 for m in idx_out.values() if m['is_person_note'])
n_unid = sum(1 for m in idx_out.values() if m['unidentified'])
print("rows=%d people=%d person_notes(>=20)=%d unidentified=%d" % (
    len(rows), len(idx_out), n_person, n_unid))
print("jsonl ->", OUT_JSONL)
print("index ->", OUT_INDEX)
