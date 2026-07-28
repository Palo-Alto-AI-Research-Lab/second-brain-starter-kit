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
r"""brain_embed_e5.py — neural search with intfloat/multilingual-e5-base (sharper for Russian).
e5 requires 'query:' / 'passage:' prefixes. Separate cache so it won't clobber the MiniLM index.
USAGE: same as brain_embed.py (--reindex / --ask / --anton).
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
EMB = Path(IMPORTS) / '_brain_e5.npy'
META = Path(IMPORTS) / '_brain_e5_meta.pkl'
MODEL_NAME = 'intfloat/multilingual-e5-base'

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
            meta.append(dict(path=str(p), title=str(title)[:100], concept=concept,
                             date=date, anton=anton, snippet=' '.join(clean.split())[:240]))
            texts.append('passage: ' + (str(title) + '. ') + ' '.join(clean.split())[:800])
    return meta, texts

def build():
    import sys as _s; _s.path.insert(0, str(Path(__file__).parent)); import brain_common as bc
    dev = bc.pick_device()
    model = bc.load_model(MODEL_NAME, dev, fp16=True)
    meta, texts = load_docs()
    emb = model.encode(texts, batch_size=32, show_progress_bar=False,
                       normalize_embeddings=True, convert_to_numpy=True).astype('float32')
    np.save(EMB, emb); META.write_bytes(pickle.dumps(meta))
    (Path(IMPORTS) / '_brain_e5_done.txt').write_text(
        f'encoded={len(meta)} dim={emb.shape[1]}', encoding='utf-8')
    return meta, emb

def main():
    args = sys.argv[1:]
    if '--reindex' in args:
        m,e = build(); print(f'encoded {len(m)} dim {e.shape[1]}')
        args=[a for a in args if a!='--reindex']
        if not ' '.join(args): return
    ask='--ask' in args; args=[a for a in args if a!='--ask']
    anton='--anton' in args; args=[a for a in args if a!='--anton']
    query=' '.join(args)
    if not query or not EMB.exists():
        print('need index (--reindex) and a query'); return
    import sys as _s; _s.path.insert(0, str(Path(__file__).parent)); import brain_common as bc
    meta=pickle.loads(META.read_bytes()); emb=np.load(EMB)
    model=bc.load_model(MODEL_NAME, bc.pick_device(), fp16=True)
    qv=model.encode(['query: '+query], normalize_embeddings=True, convert_to_numpy=True)[0].astype('float32')
    sims=emb@qv; order=np.argsort(-sims); res=[]
    for i in order:
        if anton and not meta[i]['anton']: continue
        res.append((float(sims[i]),meta[i]))
        if len(res)>=12: break
    lines=[f'QUERY: {query}', f'(e5-base: {len(meta)} notes)','']
    if ask:
        lines.append('=== CONTEXT BUNDLE ===\n')
        for s,m in res[:8]:
            lines.append("## " + m['title'] + "  [" + m['date'] + "] (" + m['concept'] + ")  sim=%.2f" % s)
            lines.append(m['snippet']); lines.append('')
    else:
        for i,(s,m) in enumerate(res,1):
            tag='ANTON' if m['anton'] else '     '
            lines.append("%2d. [%.3f] %s [%s] %s" % (i, s, tag, m['date'], m['title']))
            lines.append("     (" + m['concept'] + ")  " + m['snippet'][:140])
    (Path(IMPORTS) / '_brain_answer_e5.txt').write_text('\n'.join(lines),encoding='utf-8')
    print(f'{len(res)} hits -> _brain_answer_e5.txt')

if __name__=='__main__':
    main()
