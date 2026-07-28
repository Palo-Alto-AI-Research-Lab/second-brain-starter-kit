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
r"""brain_search.py — "Спроси свой второй мозг". Offline BM25 retrieval over the vault.
No external deps. Cyrillic-aware. Caches a tokenized index.

USAGE:
  python brain_search.py "что я думаю про DeFi и AI"          # top matches
  python brain_search.py --ask "моя эволюция взглядов на крипту"  # context bundle for Claude
  python brain_search.py --reindex "..."                       # force rebuild index
  python brain_search.py --anton "..."                         # restrict to #anton-original
Index cache: %IMPORTS%\_brain_index.pkl
"""
import os, re, sys, math, pickle
from pathlib import Path
from collections import Counter, defaultdict

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

VAULT = Path(VAULT)
INDEX = Path(IMPORTS) / '_brain_index.pkl'

STOP = set('и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между the a an and or to of in is it for on this that with as be at by from we you i my our your their his her its'.split())
TOKEN = re.compile(r'[a-zA-Zа-яёА-ЯЁ0-9]{2,}', re.UNICODE)

def tokenize(s):
    return [w for w in TOKEN.findall(s.lower()) if w not in STOP]

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

def build_index():
    docs = []  # {path,title,concept,date,anton,snippet,tokens}
    for dp, dirs, fs in os.walk(VAULT):
        if '.obsidian' in dp: continue
        for fn in fs:
            if not fn.endswith('.md'): continue
            p = Path(dp)/fn
            t = p.read_text(encoding='utf-8', errors='ignore')
            fm, body = fm_body(t)
            if 'fb-duplicate' in fm: continue
            title = (re.search(r'^title:\s*[\'"]?(.+?)[\'"]?\s*$', fm, re.M) or [None,fn])[1]
            cm = re.search(r'^concept:\s*"?\[\[([^\]\|]+)', fm, re.M)
            concept = cm.group(1) if cm else ''
            dm = re.search(r'(\d{4}-\d{2}-\d{2})', fm) or re.search(r'(\d{4}-\d{2}-\d{2})', fn)
            date = dm.group(1) if dm else ''
            anton = 'anton-original' in fm
            cleanbody = re.split(r'## See Also|## Legacy', body)[0]
            snippet = ' '.join(cleanbody.split())[:240]
            toks = tokenize(title + ' ' + title + ' ' + cleanbody)  # title weighted 2x
            docs.append(dict(path=str(p), title=str(title)[:100], concept=concept,
                             date=date, anton=anton, snippet=snippet, tf=Counter(toks), n=len(toks)))
    df = Counter()
    for d in docs:
        for w in d['tf']: df[w] += 1
    N = len(docs)
    idf = {w: math.log(1 + (N - c + 0.5)/(c + 0.5)) for w, c in df.items()}
    avg = sum(d['n'] for d in docs)/max(N,1)
    idx = dict(docs=docs, idf=idf, avg=avg, N=N)
    INDEX.write_bytes(pickle.dumps(idx))
    return idx

def bm25(idx, query, k1=1.5, b=0.75, anton_only=False):
    q = tokenize(query)
    scored = []
    for d in idx['docs']:
        if anton_only and not d['anton']: continue
        s = 0.0
        for w in q:
            if w in d['tf']:
                tf = d['tf'][w]; idf = idx['idf'].get(w, 0)
                s += idf * (tf*(k1+1))/(tf + k1*(1 - b + b*d['n']/idx['avg']))
        if s > 0: scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return scored

def main():
    args = sys.argv[1:]
    reindex = '--reindex' in args;  args = [a for a in args if a != '--reindex']
    ask = '--ask' in args;          args = [a for a in args if a != '--ask']
    anton = '--anton' in args;      args = [a for a in args if a != '--anton']
    query = ' '.join(args)
    if not query:
        print('usage: python brain_search.py [--ask] [--anton] [--reindex] "your question"'); return
    idx = build_index() if (reindex or not INDEX.exists()) else pickle.loads(INDEX.read_bytes())
    res = bm25(idx, query, anton_only=anton)[:12]
    out = Path(IMPORTS) / '_brain_answer.txt'
    lines = [f'QUERY: {query}', f'(index: {idx["N"]} notes)', '']
    if ask:
        lines.append('=== CONTEXT BUNDLE (paste to Claude with your question) ===\n')
        for s, d in res[:8]:
            lines.append(f"## {d['title']}  [{d['date']}] ({d['concept']})")
            lines.append(d['snippet']); lines.append('')
    else:
        for i,(s,d) in enumerate(res,1):
            tag = 'ANTON' if d['anton'] else '     '
            lines.append(f"{i:2d}. [{s:5.1f}] {tag} [{d['date']}] {d['title']}")
            lines.append(f"     ({d['concept']})  {d['snippet'][:140]}")
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'{len(res)} hits -> _brain_answer.txt')

if __name__ == '__main__':
    main()
