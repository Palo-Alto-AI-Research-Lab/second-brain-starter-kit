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
r"""brain_semantic.py — semantic search over the vault via LSA (TF-IDF + TruncatedSVD).
Genuinely semantic (latent topic space), Cyrillic-aware, offline, only needs numpy+sklearn.
Upgrade path: swap the vectorizer for sentence-transformers embeddings if torch is installed.

USAGE:
  python brain_semantic.py "что я думаю про DeFi и AI"
  python brain_semantic.py --ask "моя эволюция взглядов на крипту"   # context bundle for Claude
  python brain_semantic.py --anton "..."        # restrict to #anton-original
  python brain_semantic.py --reindex "..."      # rebuild LSA model
Model cache: %IMPORTS%\_brain_lsa.pkl
"""
import os, re, sys, pickle
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

VAULT = Path(VAULT)
MODEL = Path(IMPORTS) / '_brain_lsa.pkl'

STOP = 'и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя the a an and or to of in is it for on this that with as be at by from we you your our их это как'.split()

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

def load_docs():
    meta, texts = [], []
    for dp, dirs, fs in os.walk(VAULT):
        if '.obsidian' in dp: continue
        for fn in fs:
            if not fn.endswith('.md'): continue
            p = Path(dp)/fn
            t = p.read_text(encoding='utf-8', errors='ignore')
            fm, body = fm_body(t)
            if 'fb-duplicate' in fm: continue
            title = (re.search(r'^title:\s*[\'"]?(.+?)[\'"]?\s*$', fm, re.M) or [None, fn])[1]
            cm = re.search(r'^concept:\s*"?\[\[([^\]\|]+)', fm, re.M)
            concept = cm.group(1) if cm else ''
            dm = re.search(r'(\d{4}-\d{2}-\d{2})', fm) or re.search(r'(\d{4}-\d{2}-\d{2})', fn)
            date = dm.group(1) if dm else ''
            anton = 'anton-original' in fm
            clean = re.split(r'## See Also|## Legacy', body)[0]
            snippet = ' '.join(clean.split())[:240]
            meta.append(dict(path=str(p), title=str(title)[:100], concept=concept,
                             date=date, anton=anton, snippet=snippet))
            texts.append((str(title) + ' ') * 3 + clean[:4000])  # title weighted 3x, body capped
    return meta, texts

def build():
    meta, texts = load_docs()
    vec = TfidfVectorizer(stop_words=STOP, max_features=60000, min_df=2,
                          ngram_range=(1, 2), sublinear_tf=True)
    X = vec.fit_transform(texts)
    k = min(300, X.shape[1] - 1)
    svd = TruncatedSVD(n_components=k, random_state=42)
    D = normalize(svd.fit_transform(X)).astype('float32')
    model = dict(meta=meta, vec=vec, svd=svd, D=D)
    MODEL.write_bytes(pickle.dumps(model))
    return model

def search(model, query, anton_only=False, topn=12):
    q = model['vec'].transform([query])
    qv = normalize(model['svd'].transform(q)).astype('float32')[0]
    sims = model['D'] @ qv
    order = np.argsort(-sims)
    res = []
    for i in order:
        m = model['meta'][i]
        if anton_only and not m['anton']: continue
        res.append((float(sims[i]), m))
        if len(res) >= topn: break
    return res

def main():
    args = sys.argv[1:]
    reindex = '--reindex' in args; args = [a for a in args if a != '--reindex']
    ask = '--ask' in args;         args = [a for a in args if a != '--ask']
    anton = '--anton' in args;     args = [a for a in args if a != '--anton']
    query = ' '.join(args)
    if not query:
        print('usage: python brain_semantic.py [--ask] [--anton] [--reindex] "your question"'); return
    model = build() if (reindex or not MODEL.exists()) else pickle.loads(MODEL.read_bytes())
    res = search(model, query, anton_only=anton)
    out = Path(IMPORTS) / '_brain_answer.txt'
    lines = [f'QUERY: {query}', f'(LSA semantic index: {len(model["meta"])} notes, {model["D"].shape[1]} dims)', '']
    if ask:
        lines.append('=== CONTEXT BUNDLE (paste to Claude with your question) ===\n')
        for s, m in res[:8]:
            lines.append(f"## {m['title']}  [{m['date']}] ({m['concept']})  sim={s:.2f}")
            lines.append(m['snippet']); lines.append('')
    else:
        for i, (s, m) in enumerate(res, 1):
            tag = 'ANTON' if m['anton'] else '     '
            lines.append(f"{i:2d}. [{s:.3f}] {tag} [{m['date']}] {m['title']}")
            lines.append(f"     ({m['concept']})  {m['snippet'][:140]}")
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'{len(res)} hits -> _brain_answer.txt')

if __name__ == '__main__':
    main()
