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
r"""chat_search.py — search INSIDE old chats ("Книга чатов" / episodic index).

Queries the SEPARATE sessions index (_brain_sessions.*) built by brain_sessions_index.py —
NOT the essence /ask index. e5-base dense (top-60, dedup by path) -> cross-encoder rerank
-> top-N. Each hit prints machine/date/title/snippet + a ready-to-run resume command so
Anton can jump back into that exact chat.

USAGE:
  python chat_search.py "что обсуждали про токеномику"
  python chat_search.py --machine LAPTOP1 "..."      # scope to one machine
  python chat_search.py -n 8 "..."                       # top-N (default 10)
"""
import os, re, sys, pickle
from pathlib import Path
import numpy as np
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8')
    except Exception: pass

try:
    from _paths import IMPORTS as _IMP
except Exception:
    _IMP = r'%IMPORTS%'
EMB = Path(_IMP) / '_brain_sessions.npy'
META = Path(_IMP) / '_brain_sessions_meta.pkl'
CONT = Path(_IMP) / 'claude_sessions' / 'continue_session.py'
E5_MODEL = 'intfloat/multilingual-e5-base'
RERANK_MODEL = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
TOPK_RETRIEVE = 60
TOPN_DEFAULT = 10

def main():
    args = sys.argv[1:]
    topn = TOPN_DEFAULT; machine = None
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-n', '--top') and i + 1 < len(args):
            try: topn = int(args[i + 1])
            except Exception: pass
            i += 2; continue
        if a == '--machine' and i + 1 < len(args):
            machine = args[i + 1]; i += 2; continue
        rest.append(a); i += 1
    query = ' '.join(rest)
    if not query:
        print('usage: python chat_search.py [--machine NAME] [-n N] "вопрос"'); return
    if not EMB.exists() or not META.exists():
        print('Книга чатов ещё не построена. Запусти: python brain_sessions_index.py --full'); return

    # brain_common FIRST: it sets HF_HUB_OFFLINE before sentence_transformers can phone home
    sys.path.insert(0, str(Path(__file__).parent)); import brain_common as bc
    from sentence_transformers import CrossEncoder
    dev = bc.pick_device()
    meta = pickle.loads(META.read_bytes()); emb = np.load(EMB)
    if len(meta) == 0:
        print('Книга чатов пуста (0 чанков). Запусти: python brain_sessions_index.py --full'); return
    enc = bc.load_model(E5_MODEL, dev, fp16=True)
    qv = enc.encode(['query: ' + query], normalize_embeddings=True, convert_to_numpy=True)[0].astype('float32')
    sims = emb @ qv

    def machine_match(m, want):
        """Match by frontmatter `machine:` OR by the _session-md/<dir> folder name.
        Closes the friendly-name vs hostname split (folder=NAT1-Nina,
        frontmatter=NATALY-WIN-NB) — either spelling finds the chats."""
        w = want.lower()
        if (m.get('machine') or '').lower() == w:
            return True
        return Path(m['path']).parent.name.lower() == w

    order, seen = [], set()
    for j in np.argsort(-sims):
        m = meta[j]
        if machine and not machine_match(m, machine):
            continue
        if m['path'] in seen:
            continue
        seen.add(m['path']); order.append(int(j))
        if len(order) >= TOPK_RETRIEVE:
            break
    if not order:
        print('Ничего не нашлось' + (f' на машине {machine}' if machine else '') + f' по запросу: {query}'); return

    ce = CrossEncoder(RERANK_MODEL, device=dev)
    pairs = [(query, meta[j]['title'] + '. ' + meta[j]['snippet']) for j in order]
    sc = ce.predict(pairs)
    ranked = sorted(zip(order, sc), key=lambda x: -x[1])[:topn]

    lines = [f'КНИГА ЧАТОВ — поиск: {query}',
             f'(scope={"machine "+machine if machine else "все машины"}; '
             f'{len(meta)} чанков · {len(seen)} чатов-кандидатов -> rerank top-{topn})', '']
    for rank, (j, s) in enumerate(ranked, 1):
        m = meta[j]
        lines.append('%2d. [rr=%6.2f] %s · %s · %s' %
                     (rank, float(s), m.get('date', '?'), m.get('machine', '?'), m['title']))
        lines.append('     %s' % m['snippet'][:160].replace('\n', ' '))
        lines.append('     ▶ продолжить: python "%s" %s' % (CONT, m.get('cli', '')))
        lines.append('')
    text = '\n'.join(lines)
    out = Path(os.getenv('CHAT_SEARCH_OUT') or str(Path(_IMP) / '_chat_search_out.txt'))
    out.write_text(text, encoding='utf-8')
    print(text)

if __name__ == '__main__':
    main()
