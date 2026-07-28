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
r"""brain_sessions_index.py — "Книга чатов" (episodic-namespace index, Этап 2).

A SEPARATE searchable index over exported session transcripts (_session-md/<machine>/<cli>.md),
kept DISTINCT from the curated essence index (_brain_e5) so raw chat chatter never pollutes the
sharp /ask "mind" (decision-essence-evidence-ontology-2026-06-25 / [[essence-index-live]]).

Same e5-base model + GPU rules as brain_embed_update (via brain_common), own lock name
('brain_sessions') so it coexists with the essence reindex. Incremental by mtime. Atomic save.
Only HUMAN sessions reach here — export_sessions_md already filtered service/robot chats out.

USAGE:
  python brain_sessions_index.py            # incremental (new + edited + deleted)
  python brain_sessions_index.py --full     # rebuild from scratch
  python brain_sessions_index.py --cpu
Output: _brain_sessions.npy + _brain_sessions_meta.pkl   (searched by chat_search.py)
"""
import os, re, sys, pickle, time, hashlib
from pathlib import Path
import numpy as np
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
sys.path.insert(0, str(Path(__file__).parent))
import brain_common as bc

try:
    from _paths import VAULT as _V             # portable: reads ~/.claude/machine.env
    VAULT = Path(_V)
except Exception:
    VAULT = Path(r'%VAULT%')   # HP17 fallback
SESS_DIR = VAULT / '_session-md'
EMB = bc.IMPORTS / '_brain_sessions.npy'
META = bc.IMPORTS / '_brain_sessions_meta.pkl'
DONE = bc.IMPORTS / '_brain_sessions_done.txt'
MODEL_NAME = 'intfloat/multilingual-e5-base'
CHUNK_CHARS = 1500
OVERLAP = 200
MAX_CHUNKS_PER_FILE = 400
SKIP_DIRS = ('.stversions', '.trash', '.git', '.claude')

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

def g(fm, key):
    m = re.search(r'(?m)^' + key + r'\s*:\s*"?\[?\[?([^"\]\n#]+)', fm)
    return m.group(1).strip() if m else ''

# Whisper voice-notes leave runs of empty "* " bullets in the transcript; drop those lines
# (pure noise) BEFORE collapsing whitespace, else they become "* * * *" garbage chunks.
_EMPTY_BULLET = re.compile(r'(?m)^\s*[\*\-]\s*$')

def chunks_of(body):
    clean = _EMPTY_BULLET.sub('', body)
    clean = ' '.join(clean.split())
    if not clean:
        return []
    if len(clean) <= CHUNK_CHARS:
        return [clean]
    out, i = [], 0
    while i < len(clean) and len(out) < MAX_CHUNKS_PER_FILE:
        out.append(clean[i:i + CHUNK_CHARS])
        i += CHUNK_CHARS - OVERLAP
    return out

def load_chunks():
    """yield per-file: (path, chash, [ (meta, passage_text) , ... ]) over _session-md/**.

    chash = SHA1 of the actual embed-input (the passage texts). Reuse is keyed on CONTENT,
    not mtime: Syncthing rewrites mtime when it pulls a peer's export, which made the old
    mtime-check re-embed thousands of UNCHANGED chats every night (03:30 run: new=16098 on a
    churny night). Hashing costs ~nothing — we already read+chunk every file here."""
    if not SESS_DIR.exists():
        return
    for dp, dirs, fs in os.walk(SESS_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if any(s in dp.replace('\\', '/') for s in SKIP_DIRS):
            continue
        for fn in fs:
            if not fn.endswith('.md'):
                continue
            p = Path(dp) / fn; sp = str(p)
            try:
                mtime = int(p.stat().st_mtime)
                t = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            fm, body = fm_body(t)
            title = g(fm, 'title') or fn[:60]
            machine = g(fm, 'machine') or Path(dp).name
            operator = g(fm, 'operator')
            date = g(fm, 'date')
            cli = g(fm, 'cli') or fn[:-3]
            passages = ['passage: ' + str(title) + '. ' + ck for ck in chunks_of(body)]
            chash = hashlib.sha1('\n'.join(passages).encode('utf-8', 'ignore')).hexdigest()
            recs = []
            for idx, (ck, txt) in enumerate(zip(chunks_of(body), passages)):
                meta = dict(path=sp, chunk_idx=idx, mtime=mtime, chash=chash,
                            title=str(title)[:100], machine=machine, operator=operator,
                            date=date, cli=cli, snippet=ck[:240])
                recs.append((meta, txt))
            if recs:
                yield sp, chash, recs

def run():
    t0 = time.time()
    full = '--full' in sys.argv[1:]
    dev = bc.pick_device(force_cpu=('--cpu' in sys.argv[1:]))
    print('device:', dev); model = bc.load_model(MODEL_NAME, dev, fp16=True)

    old_by_path = {}; oe = None
    if not full and EMB.exists() and META.exists():
        om = pickle.loads(META.read_bytes()); oe = np.load(EMB)
        for i, m in enumerate(om):
            # key reuse on CONTENT hash (mtime-independent). Old indices lack chash ->
            # None != any real hash -> they re-embed ONCE on the upgrade, then stick.
            d = old_by_path.setdefault(m['path'], [m.get('chash'), [], []])
            d[1].append(i); d[2].append(m)

    reuse_rows, reuse_meta = [], []
    new_texts, new_meta = [], []
    seen_paths = set()
    for sp, chash, recs in load_chunks():
        seen_paths.add(sp)
        old = old_by_path.get(sp)
        if old is not None and old[0] == chash and oe is not None:
            for ridx, m in zip(old[1], old[2]):
                reuse_rows.append(ridx); reuse_meta.append(m)
        else:
            for meta, txt in recs:
                new_meta.append(meta); new_texts.append(txt)

    reused_vecs = oe[reuse_rows] if (oe is not None and reuse_rows) else None
    dim = (oe.shape[1] if oe is not None else 768)
    bs = 64 if dev == 'cuda' else (32 if dev == 'mps' else 16)
    parts = []; i = 0
    while i < len(new_texts):
        ck = new_texts[i:i + 2000]
        while True:
            try:
                v = model.encode(ck, batch_size=bs, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False).astype('float32'); break
            except RuntimeError as e:
                if dev == 'cuda' and 'out of memory' in str(e).lower():
                    import torch; torch.cuda.empty_cache()
                    if bs > 4:
                        bs //= 2; continue
                    print('CUDA OOM at bs=%d -> CPU for remaining' % bs)
                    model = model.to('cpu'); dev = 'cpu'; bs = 16; continue
                raise
        parts.append(v); i += len(ck)

    blocks = ([reused_vecs] if reused_vecs is not None else []) + parts
    emb = np.vstack(blocks) if blocks else np.zeros((0, dim), 'float32')
    all_meta = reuse_meta + new_meta
    # ATOMIC write (temp -> os.replace) so a kill never leaves a truncated index.
    tmp_emb = str(EMB) + '.tmp'; tmp_meta = str(META) + '.tmp'
    with open(tmp_emb, 'wb') as f: np.save(f, emb)
    with open(tmp_meta, 'wb') as f: f.write(pickle.dumps(all_meta))
    os.replace(tmp_emb, EMB); os.replace(tmp_meta, META)
    files = len(seen_paths)
    DONE.write_text('chunks=%d files=%d reused=%d new=%d dim=%d dev=%s secs=%d' %
                    (len(emb), files, len(reuse_meta), len(new_texts),
                     (emb.shape[1] if len(emb) else dim), dev, int(time.time() - t0)), encoding='utf-8')
    print('sessions index: %d chunks over %d files (reused=%d new=%d) dev=%s %ds' %
          (len(emb), files, len(reuse_meta), len(new_texts), dev, int(time.time() - t0)))

def main():
    # Own lock name -> coexists with the essence reindex (brain_e5) on the GPU.
    with bc.Lock('brain_sessions', busy_exit_code=0):
        run()

if __name__ == '__main__':
    main()
