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
r"""brain_embed_update.py v2 — CHUNKED + TAGGED + edit-aware e5 index.
Each note is split into overlapping chunks (full coverage, no 800-char truncation).
Every chunk vector carries: source_type (person/conversation/lead/concept/insight/note),
tg_id, person, date, anton, chunk_idx, mtime. Incremental keeps unchanged files (by mtime),
re-chunks NEW or EDITED files, drops deleted. GPU-aware (cuda/fp16), lock, OOM-backoff, resumable.

USAGE:
  python brain_embed_update.py            # incremental (new + edited + deleted)
  python brain_embed_update.py --full     # rebuild from scratch
  python brain_embed_update.py --cpu
Cache: _brain_e5.npy + _brain_e5_meta.pkl   (chunk-level; brain_ask.py dedups by path)
"""
import os, re, sys, pickle, time
from pathlib import Path
import numpy as np
# stdout/stderr utf-8 guard: this file has Cyrillic literals in print() (cert-fail diagnostics);
# without this, a cp1252 console raises UnicodeEncodeError mid-reindex. Closes the lint class.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass
# Force HF OFFLINE (belt; brain_common force-sets the same below). FORCE, not setdefault:
# setdefault is a no-op if the parent env pre-holds HF_HUB_OFFLINE=''/'0'/'false' -> HF goes
# online -> 199-shard hub revalidation -> 40-min stall on a blocked IP (root-fix 2026-07-23,
# proven A/B). Intentional model fetch: export BRAIN_ALLOW_HF_ONLINE=1.
_off = '0' if os.environ.get('BRAIN_ALLOW_HF_ONLINE') == '1' else '1'  # symmetric hatch (Codex t3)
os.environ['HF_HUB_OFFLINE'] = _off
os.environ['TRANSFORMERS_OFFLINE'] = _off
sys.path.insert(0, str(Path(__file__).parent))
import brain_common as bc

try:
    from _paths import VAULT as _V            # portable: reads ~/.claude/machine.env
    VAULT = Path(_V)
except Exception:
    VAULT = Path(r'%VAULT%')   # HP17 fallback
EMB = bc.IMPORTS / '_brain_e5.npy'
META = bc.IMPORTS / '_brain_e5_meta.pkl'
PROG = bc.IMPORTS / '_brain_e5_progress.txt'
DONE = bc.IMPORTS / '_brain_e5_done.txt'
MODEL_NAME = 'intfloat/multilingual-e5-base'
SAVE_EVERY = 20000        # persist every N new chunks
CHUNK_CHARS = 1500        # ~ a few paragraphs / ~15 chat messages
OVERLAP = 200
MAX_CHUNKS_PER_FILE = 400 # safety cap for monster files

# --- LAYER: essence vs evidence (2026-06-26, Anton) ---------------------------
# Curated "mind" index = ESSENCE ONLY (durable thought: concepts/insights/decisions/
# protocols/system/coach). Raw EVIDENCE (conversations/DMs, leads, session transcripts,
# bulk people-stubs, .stversions junk) is NOT embedded here — it stays on disk for grep/BM25
# + a future episodic namespace. NO default-deny: the FOLDER decides the default; a frontmatter
# `layer: essence|evidence` is only an OVERRIDE for exceptions. Canon:
# 02-Decisions/decision-essence-evidence-ontology-2026-06-25 + reglament-znat-vs-dokazat-essence-evidence.
ESSENCE_FOLDERS = ('06-Concepts', '03-Insights', '02-Decisions', '00-System',
                   '09-Bridges', '04-Coach', '08-Templates')
ESSENCE_SUBPATHS = ('05-Resources/Protocols',    # reglaments/protocols = procedural essence
                    '05-Resources/PhD')          # PhD writeups/memos/boards = durable thought (anton 17.07, class-fix: recall молчал по всей папке)
SKIP_DIRS = ('.obsidian', '.stversions', '.trash', '.git', '.claude', 'node_modules', '_sync-conflict-archive')

def layer_of(path, fm):
    """essence -> embed into curated index; evidence -> skip (kept on disk for grep)."""
    m = re.search(r'(?m)^layer\s*:\s*(essence|evidence)\b', fm)
    if m:
        return m.group(1)                         # explicit frontmatter override wins
    p = path.replace('\\', '/')
    rel = p.split('/Owner-Knowledge/')[-1]
    top = rel.split('/')[0]
    if top in ESSENCE_FOLDERS:
        return 'essence'
    if any(s in p for s in ESSENCE_SUBPATHS):
        return 'essence'
    return 'evidence'

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

def source_type(path):
    p = path.replace('\\', '/')
    if '/_session-md/' in p: return 'session'   # human chat transcripts (Anton 2026-06-25): searchable but tagged
    if '/07-People/' in p: return 'person'
    if 'Personal-DMs' in p and '/conversations/' in p: return 'conversation'
    if 'Platinum-CRM' in p: return 'lead'
    if '/06-Concepts/' in p: return 'concept'
    if '/03-Insights/' in p: return 'insight'
    if '/01-Conversations/' in p: return 'conversation'
    return 'note'

def g(fm, key):
    m = re.search(r'(?m)^' + key + r'\s*:\s*"?\[?\[?([^"\]\n#]+)', fm)
    return m.group(1).strip() if m else ''

def chunks_of(body):
    clean = re.split(r'## See Also|## Legacy', body)[0]
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
    """yield per-file: (path, mtime, [ (meta, passage_text) , ... ])"""
    for dp, dirs, fs in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]   # prune junk; don't descend .stversions etc.
        if any(s in dp.replace('\\', '/') for s in SKIP_DIRS): continue
        for fn in fs:
            if not fn.endswith('.md'): continue
            if '.sync-conflict-' in fn: continue   # Syncthing дубль-конфликт => не индексируем (шум/дубли)
            if re.search(r'~\d{8}-\d{6}$', fn[:-3]): continue   # Syncthing version-tag копия (.stversions, name~YYYYMMDD-HHMMSS) просочилась в живое дерево => не индексируем (иначе дедуп склеит против фантома -> ghost-supersede, класс 2026-07-07)
            p = Path(dp) / fn; sp = str(p)
            try:
                mtime = int(p.stat().st_mtime)
                t = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            fm, body = fm_body(t)
            if 'fb-duplicate' in fm: continue
            if layer_of(sp, fm) != 'essence': continue   # curated index = ESSENCE only (evidence stays on disk)
            title = (re.search(r'^title:\s*[\'"]?(.+?)[\'"]?\s*$', fm, re.M) or [None, fn])[1]
            st = source_type(sp)
            concept = g(fm, 'concept')
            tg = g(fm, 'tg_id') or g(fm, 'contact_tg_id')
            person = g(fm, 'person')
            dm = re.search(r'(\d{4}-\d{2}-\d{2})', fm) or re.search(r'(\d{4}-\d{2}-\d{2})', fn)
            date = dm.group(1) if dm else ''
            anton = 'anton-original' in fm
            cks = chunks_of(body)
            recs = []
            for idx, ck in enumerate(cks):
                meta = dict(path=sp, chunk_idx=idx, mtime=mtime, source_type=st,
                            title=str(title)[:100], concept=concept, tg_id=tg, person=person,
                            date=date, anton=anton, snippet=ck[:240])
                recs.append((meta, 'passage: ' + str(title) + '. ' + ck))
            yield sp, mtime, recs

def run():
    t0 = time.time()
    args = sys.argv[1:]
    full = '--full' in args
    dev = bc.pick_device(force_cpu=('--cpu' in args))
    print('device:', dev); model = bc.load_model(MODEL_NAME, dev, fp16=True)

    # old index keyed by path -> (mtime, [row indices], [metas])
    old_by_path = {}
    oe = None
    if not full and EMB.exists() and META.exists():
        om = pickle.loads(META.read_bytes()); oe = np.load(EMB)
        for i, m in enumerate(om):
            d = old_by_path.setdefault(m['path'], [m.get('mtime'), [], []])
            d[1].append(i); d[2].append(m)

    reuse_rows, reuse_meta = [], []
    new_texts, new_meta = [], []
    seen_paths = set()
    for sp, mtime, recs in load_chunks():
        seen_paths.add(sp)
        old = old_by_path.get(sp)
        if old is not None and old[0] == mtime and oe is not None:
            for ridx, m in zip(old[1], old[2]):   # unchanged file -> reuse vectors
                reuse_rows.append(ridx); reuse_meta.append(m)
        else:                                     # new or edited -> embed
            for meta, txt in recs:
                new_meta.append(meta); new_texts.append(txt)

    reused_vecs = oe[reuse_rows] if (oe is not None and reuse_rows) else None
    dim = (oe.shape[1] if oe is not None else 768)
    bs = 64 if dev == 'cuda' else (32 if dev == 'mps' else 16)
    parts = []; i = 0; last = 0
    def save(n):
        blocks = ([reused_vecs] if reused_vecs is not None else []) + parts
        emb = np.vstack(blocks) if blocks else np.zeros((0, dim), 'float32')
        # ATOMIC: write temp then os.replace, so an interrupted/killed save never
        # leaves a truncated _brain_e5.npy that breaks brain_ask.py (seen 2026-06-13).
        tmp_emb = str(EMB) + '.tmp'; tmp_meta = str(META) + '.tmp'
        with open(tmp_emb, 'wb') as f: np.save(f, emb)
        with open(tmp_meta, 'wb') as f: f.write(pickle.dumps(reuse_meta + new_meta[:n]))
        os.replace(tmp_emb, EMB); os.replace(tmp_meta, META)
        PROG.write_text('chunks=%d reused=%d new=%d/%d dev=%s secs=%d' %
                        (len(reuse_meta)+n, len(reuse_meta), n, len(new_texts), dev, int(time.time()-t0)), encoding='utf-8')
    while i < len(new_texts):
        ck = new_texts[i:i+2000]
        while True:
            try:
                v = model.encode(ck, batch_size=bs, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False).astype('float32'); break
            except RuntimeError as e:
                if dev == 'cuda' and 'out of memory' in str(e).lower():
                    import torch; torch.cuda.empty_cache()
                    if bs > 4:
                        bs //= 2; continue
                    # bs already at floor and still OOM (contended GPU on a --full re-embed of
                    # ALL chunks) -> degrade GRACEFULLY to CPU instead of crashing exit 1. This
                    # is the weekly '--full' 0x1 failure mode (hub 2026-06-22); incremental runs
                    # embed few chunks and never hit it. Slower, but the rebuild completes.
                    print('CUDA OOM at bs=%d -> falling back to CPU for remaining chunks' % bs)
                    model = model.to('cpu'); dev = 'cpu'; bs = 16; continue
                raise
        parts.append(v); i += len(ck)
        if i - last >= SAVE_EVERY: save(i); last = i
    save(i)
    blocks = ([reused_vecs] if reused_vecs is not None else []) + parts
    emb = np.vstack(blocks) if blocks else np.zeros((0, dim), 'float32')
    files = len(seen_paths)
    DONE.write_text('chunks=%d files=%d reused=%d new=%d dim=%d dev=%s secs=%d' %
                    (len(emb), files, len(reuse_meta), len(new_texts), (emb.shape[1] if len(emb) else dim), dev, int(time.time()-t0)), encoding='utf-8')
    print('index: %d chunks over %d files (reused=%d new=%d) dev=%s %ds' %
          (len(emb), files, len(reuse_meta), len(new_texts), dev, int(time.time()-t0)))

COOLDOWN_MIN = int(os.environ.get('REINDEX_COOLDOWN_MIN', '15'))
# If the index hasn't successfully refreshed in this many hours, staleness is a REAL alarm,
# not a benign collision. The task runs daily, so a healthy DONE marker is < 24h old.
STALE_HOURS = float(os.environ.get('REINDEX_STALE_HOURS', '26'))

def index_age_hours():
    """Hours since the last SUCCESSFUL reindex (DONE marker). Large number if never built."""
    if not DONE.exists():
        return 1e9
    return (time.time() - DONE.stat().st_mtime) / 3600.0

def _chain_openai():
    """OpenAI-индекс — прод-дефолт ([[openai-embeddings-prod]], Антон '+' 05.07): после УСПЕШНОГО
    e5-обновления зовём brain_embed_openai.py, чтобы ЛЮБАЯ точка входа реиндекса (ручной после
    импорта, scheduled, watchdog) освежала ОБА индекса, а не только e5 (иначе прод-индекс тихо
    отстаёт на машинах без ночного cmd, класс-баг ноута 04.07). Best-effort: сбой не валит
    e5-прогон, прежний OpenAI-индекс цел (там atomic write). Kill-switch: BRAIN_OAI_CHAIN=0."""
    if os.environ.get('BRAIN_OAI_CHAIN', '1') == '0':
        print('openai chain: disabled (BRAIN_OAI_CHAIN=0)')
        return
    import subprocess
    try:
        # capture output: the child's traceback is the ROOT diagnosis; without it the log
        # showed only 'exit 1' + a hardcoded cert hypothesis (hub 2026-07-20: real cause was
        # a corrupt secrets junction -> OSError 22, while cert-health was honestly GREEN).
        r = subprocess.run([sys.executable, str(Path(__file__).parent / 'brain_embed_openai.py')],
                           timeout=1800, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.stdout:
            print(r.stdout, end='')
        print('openai chain: exit %s' % r.returncode)
        if r.returncode != 0:
            tail = (r.stderr or '').strip().splitlines()[-12:]
            print('!!! openai chain FAILED, stderr-хвост (реальная причина ниже):')
            for ln in tail:
                print('   | ' + ln)
            # cert_health_check остаётся ВТОРИЧНОЙ диагностикой (один из возможных корней,
            # класс 2026-07-07), а не единственным объяснением сбоя.
            print('доп. диагностика cert_health_check (SSL — лишь ОДИН из возможных корней):')
            # flush: наш stdout буферизуется при pipe, а ребёнок пишет в консоль напрямую ->
            # без flush GREEN-строки cert-check печатались РАНЬШЕ вердикта (та самая
            # «GREEN первой строкой при FAIL» путаница в ночном логе).
            sys.stdout.flush()
            try:
                subprocess.run([sys.executable, str(Path(__file__).parent / 'cert_health_check.py')],
                               timeout=120)
            except Exception as ce:
                print('cert_health_check не запустился (%s)' % str(ce)[:120])
    except Exception as e:
        print('openai chain skipped (%s)' % str(e)[:120])

def main():
    args = sys.argv[1:]
    force = ('--force' in args) or ('--full' in args)
    # Debounce: if a reindex COMPLETED < COOLDOWN_MIN ago, no-op instantly (don't even
    # load the model or contend for the lock). Kills the 40-parallel-session churn:
    # only one real reindex per cooldown window; everyone else exits in milliseconds.
    if not force and DONE.exists():
        age_min = (time.time() - DONE.stat().st_mtime) / 60.0
        if age_min < COOLDOWN_MIN:
            print('cooldown: index refreshed %.1fm ago (<%dm) -> skip. Use --force for now.' % (age_min, COOLDOWN_MIN))
            return
    # Lock-collision policy: if another LIVE instance already holds the reindex lock, this run
    # has nothing to do -- the other instance is keeping the index fresh. That is BENIGN, so we
    # exit 0 (don't flash the daily scheduled task red on a transient overlap with one of the
    # many parallel sessions). EXCEPTION: if the index is genuinely STALE (no successful reindex
    # in STALE_HOURS), the holder may be hung and masking a real failure -> exit 3 (loud alarm).
    busy_code = 3 if index_age_hours() > STALE_HOURS else 0
    # max_age_min=720 (12h): a crashed run leaves its lock; if Windows recycles the dead PID to
    # an unrelated LIVE process, pid_alive() lies True and every future reindex silently skips.
    # 720min is deliberately FAR above any legit run — normal 1-2h, but --full/slow-card/
    # mtime-bump rebuilds have hit 5-11h (see the O(n^2) gotcha). Codex t3 (2026-07-23) flagged
    # that a lower bound (180) could RECLAIM a still-LIVE slow reindex -> two writers on
    # _brain_e5.npy -> corruption. The common crash leaves a DEAD pid (auto-reclaimed instantly
    # anyway); the tripwire only exists for the RARE recycled-PID case, so a high bound costs
    # ~nothing and removes the steal-a-live-lock risk. Anton-approved hardening.
    with bc.Lock('brain_e5', busy_exit_code=busy_code, max_age_min=720):
        run()
    _chain_openai()   # после отпускания лока: облачной части GPU/лок не нужны

if __name__ == '__main__':
    main()
