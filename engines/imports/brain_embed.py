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
r"""brain_embed.py — TRUE neural-semantic search over the vault.
Multilingual sentence-transformer embeddings (ru+en). Upgrade over LSA (brain_semantic.py).

USAGE:
  python brain_embed.py --reindex            # encode whole vault (run once; minutes on CPU)
  python brain_embed.py "что я думаю про DeFi и AI"
  python brain_embed.py --ask "моя эволюция взглядов на крипту"
  python brain_embed.py --anton "..."
Cache: _brain_emb.npy (float32 matrix) + _brain_emb_meta.pkl
Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim, 50 langs)
"""
import os, re, sys, pickle
from pathlib import Path
import numpy as np

try:
    from _paths import VAULT as _VAULT
except Exception:
    _VAULT = r"%VAULT%"   # HP17 fallback
try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback

VAULT = Path(_VAULT)
EMB = Path(IMPORTS) / '_brain_emb.npy'
META = Path(IMPORTS) / '_brain_emb_meta.pkl'
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

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
            texts.append((str(title) + '. ') + ' '.join(clean.split())[:800])
    return meta, texts

def build():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    meta, texts = load_docs()
    emb = model.encode(texts, batch_size=64, show_progress_bar=False,
                       normalize_embeddings=True, convert_to_numpy=True).astype('float32')
    np.save(EMB, emb)
    META.write_bytes(pickle.dumps(meta))
    (Path(IMPORTS) / '_brain_emb_done.txt').write_text(
        f'encoded={len(meta)} dim={emb.shape[1]}', encoding='utf-8')
    return meta, emb

def search(query, anton_only=False, topn=12):
    from sentence_transformers import SentenceTransformer
    meta = pickle.loads(META.read_bytes()); emb = np.load(EMB)
    model = SentenceTransformer(MODEL_NAME)
    qv = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0].astype('float32')
    sims = emb @ qv
    order = np.argsort(-sims)
    res = []
    for i in order:
        if anton_only and not meta[i]['anton']: continue
        res.append((float(sims[i]), meta[i]))
        if len(res) >= topn: break
    return res

def main():
    args = sys.argv[1:]
    if '--reindex' in args:
        m, e = build(); print(f'encoded {len(m)} notes, dim {e.shape[1]}');
        args = [a for a in args if a != '--reindex']
        if not ' '.join(args): return
    ask = '--ask' in args;   args = [a for a in args if a != '--ask']
    anton = '--anton' in args; args = [a for a in args if a != '--anton']
    query = ' '.join(args)
    if not query: print('usage: python brain_embed.py [--reindex] [--ask] [--anton] "question"'); return
    if not EMB.exists(): print('No index. Run with --reindex first.'); return
    res = search(query, anton_only=anton)
    out = Path(IMPORTS) / '_brain_answer.txt'
    lines = [f'QUERY: {query}', f'(neural embeddings: {len(pickle.loads(META.read_bytes()))} notes)', '']
    if ask:
        lines.append('=== CONTEXT BUNDLE (paste to Claude) ===\n')
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
