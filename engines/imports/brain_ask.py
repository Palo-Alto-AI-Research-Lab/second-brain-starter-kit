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
r"""brain_ask.py v2 — chunked + tagged retrieval. e5-base dense (top-60, dedup by path)
-> cross-encoder rerank -> top-12. Source-type filters let you trade recall<->precision.
Reranker: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (multilingual incl RU).

USAGE:
  python brain_ask.py "вопрос"                 # all sources
  python brain_ask.py --ask "вопрос"           # context bundle for Claude
  python brain_ask.py --anton "вопрос"         # only #anton-original
  python brain_ask.py --person "вопрос"        # only people/lead cards
  python brain_ask.py --conv  "вопрос"         # only conversations (raw chat chunks)
  python brain_ask.py --leads "вопрос"         # only CRM lead cards
  python brain_ask.py --concepts/--insights/--notes ...
Filters combine (union of chosen types); default = every source.
"""
import os, re, sys, pickle, datetime, sqlite3, time
from pathlib import Path
import numpy as np

# cp1252-crash fix (2026-06-29): make stdout/stderr UTF-8 so `print(text)` with Cyrillic
# never throws UnicodeEncodeError on a plain Windows console (no PYTHONIOENCODING needed).
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8')
    except Exception: pass

try:
    from _paths import IMPORTS as _IMP        # portable: reads ~/.claude/machine.env
except Exception:
    _IMP = r'%IMPORTS%'            # HP17 fallback
AB_DB = Path(_IMP) / 'turnstate' / 'turnstate.db'   # shared A/B + turn ledger
E5_MODEL = 'intfloat/multilingual-e5-base'
# --- Embedding backend switch (Anton mandate 2026-07-04: USE OpenAI embeddings in prod) ---
# Two indexes live side by side: OpenAI (cloud, DEFAULT) + e5 (local GPU, free, A/B + FALLBACK).
# BRAIN_EMB_BACKEND=openai|e5 (default openai). If the OpenAI index or API is unavailable,
# retrieval SILENTLY falls back to e5 so /ask never dies ("главное чтоб не падало").
OAI_EMB  = Path(_IMP) / '_brain_oai.npy'
OAI_META = Path(_IMP) / '_brain_oai_meta.pkl'
E5_EMB   = Path(_IMP) / '_brain_e5.npy'
E5_META  = Path(_IMP) / '_brain_e5_meta.pkl'
OAI_MODEL   = os.getenv('OPENAI_EMB_MODEL', 'text-embedding-3-large')
try:
    from _paths import SECRETS as _SECRETS    # portable: machine.env SECRETS_DIR / home-relative
except Exception:
    _SECRETS = os.path.expanduser(r'~\!CLAUDE-HP17 May26\secrets')
OAI_SECRET  = os.getenv('OPENAI_SECRET_FILE') or os.path.join(_SECRETS, 'openai.env')

def _oai_key():
    for l in open(OAI_SECRET, encoding='utf-8'):
        if l.startswith('OPENAI_API_KEY='):
            return l.split('=', 1)[1].strip()
    raise RuntimeError('no OPENAI_API_KEY')

def _oai_embed_query(q):
    """Embed ONE query via OpenAI; returns normalized float32 vector. Raises on any failure."""
    import json as _j, urllib.request as _u
    req = _u.Request('https://api.openai.com/v1/embeddings',
        data=_j.dumps({'model': OAI_MODEL, 'input': q}).encode(),
        headers={'Authorization': 'Bearer ' + _oai_key(), 'Content-Type': 'application/json'})
    v = np.asarray(_j.load(_u.urlopen(req, timeout=30))['data'][0]['embedding'], dtype='float32')
    return v / (np.linalg.norm(v) + 1e-9)

def resolve_backend():
    """-> (backend_name, EMB_path, META_path). Honors BRAIN_EMB_BACKEND, falls back to e5."""
    want = os.getenv('BRAIN_EMB_BACKEND', 'openai').lower()
    if want == 'openai' and OAI_EMB.exists() and OAI_META.exists():
        return 'openai', OAI_EMB, OAI_META
    if want == 'openai':
        sys.stderr.write('openai index missing -> fallback e5\n')
    return 'e5', E5_EMB, E5_META

BACKEND, EMB, META = resolve_backend()
RERANK_MODEL = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
TOPK_RETRIEVE = 60
TOPN = 12
GHOPS, GMAX = 15, 40   # graph-expansion: hops from top-N hits, max neighbours (shared with ab_batch.py)
TYPE_FLAGS = {'--person': 'person', '--conv': 'conversation', '--conversations': 'conversation',
              '--leads': 'lead', '--lead': 'lead', '--concepts': 'concept', '--concept': 'concept',
              '--insights': 'insight', '--notes': 'note'}
# Path-prefix filters: scope retrieval to a vault subfolder by substring match on m['path']
PATH_FLAGS = {'--decisions': '02-Decisions', '--beliefs': 'belief-', '--protocols': 'reglament-'}

VOL_MAXAGE = {'volatile': 90, 'slow': 720}
KNOWN_VOL = {'durable', 'slow', 'volatile'}
def _parse_date(s):
    if not s: return None
    s = str(s).strip().strip('"').strip("'")
    for n, fmt in ((10, '%Y-%m-%d'), (7, '%Y-%m'), (4, '%Y')):
        try: return datetime.datetime.strptime(s[:n], fmt).date()
        except Exception: pass
    return None
def fm_meta(path):
    try: t = Path(path).read_text(encoding='utf-8', errors='ignore')
    except Exception: return {}
    m = re.match(r'^---\r?\n(.*?)\r?\n---', t, re.S); fm = m.group(1) if m else ''
    def g(key):
        mm = re.search(r'(?m)^' + key + r'\s*:\s*"?([^"\n#]+)"?', fm)
        return mm.group(1).strip() if mm else None
    return {'valid_as_of': g('valid_as_of'), 'volatility': g('volatility'),
            'date': g('valid_as_of') or g('date_added') or g('date_recorded') or g('date')}
ENTITY_TOOLS = {'n8n', 'codex', 'granola', 'notebooklm', 'cowork', 'eliza', 'gitbook',
                'airtable', 'syncthing', 'telethon', 'whatsapp', 'lobsterdao', 'qdao',
                'mempalace', 'memsearch', 'obsidian', 'calendly', 'platinum', 'charm', 'telegram', 'crm'}
def looks_like_entity(q):
    """True if the query is a NAME / tool / project lookup (graph-expansion HURTS these:
    A/B 2026-06-26 = 1👍/5👎 on entity vs 5👍/1👎 on themes; decision-always-on-memory-architecture).
    CONSERVATIVE: only fires when confident → on doubt returns False → graph stays ON (no regression).
    Themes (lowercase common-noun phrases) never trip it; names/tools (capitalised / CamelCase /
    snake_case / known tool token) do. Detection is QUERY-side (the essence-index hides hit types)."""
    q = (q or '').strip()
    toks = q.split()
    if not toks or len(toks) > 5:
        return False
    for idx, t in enumerate(toks):
        core = t.strip('«».,:;"\'()?!')
        if not core:
            continue
        low = core.lower()
        if low in ENTITY_TOOLS:        return True   # known product/project name
        if '_' in low:                 return True   # snake_case tool (vault_backup)
        if len(core) >= 4 and any(c.isupper() for c in core[1:]) and any(c.islower() for c in core):
            return True                              # CamelCase (LobsterDAO, NotebookLM)
        if core[:1].isupper() and (idx > 0 or len(toks) <= 2):
            if not (core.isupper() and len(core) <= 3):   # ignore bare topic-acronyms (AI, RAG, DAO, MCP)
                return True                          # proper noun (Синклер, Бутерин, Платина)
    return False

WIKILINK_RX = re.compile(r'\[\[([^\]\|#]+)')
def _links_in(path):
    """Outgoing wikilink TARGETS in a note (alias/heading stripped)."""
    try: t = Path(path).read_text(encoding='utf-8', errors='ignore')
    except Exception: return []
    return [m.strip() for m in WIKILINK_RX.findall(t)]

def freshness_tag(path, today=None):
    today = today or datetime.date.today(); md = fm_meta(path)
    vol = (md.get('volatility') or '').strip().lower()
    if vol not in KNOWN_VOL: return ''                 # unset/unknown volatility => silent (unset = no flag)
    d = _parse_date(md.get('date'))
    if d and (d.year < 2005 or d > today): d = None    # ignore malformed / implausible dates
    age = (today - d).days if d else None
    base = ('as-of ' + str(md['valid_as_of']).strip()) if md.get('valid_as_of') else (('%dd old' % age) if age is not None else '')
    base = (base + ' ·' + vol).strip()
    if vol in VOL_MAXAGE and age is not None and age > VOL_MAXAGE[vol]:
        base += '  ⚠ STALE (>%dd, re-verify)' % VOL_MAXAGE[vol]
    return base.strip()

def main():
    args = sys.argv[1:]
    ask = '--ask' in args; anton = '--anton' in args
    graph = '--graph' in args; ab = '--ab' in args
    types = set(TYPE_FLAGS[a] for a in args if a in TYPE_FLAGS)
    path_subs = [PATH_FLAGS[a] for a in args if a in PATH_FLAGS]
    flags = set(TYPE_FLAGS) | set(PATH_FLAGS) | {'--ask', '--anton', '--graph', '--ab'}
    query = ' '.join(a for a in args if a not in flags)
    if not query or not EMB.exists():
        print('need e5 index (_brain_e5.npy) and a query'); return
    # brain_common FIRST: it sets HF_HUB_OFFLINE before sentence_transformers can phone home
    sys.path.insert(0, str(Path(__file__).parent)); import brain_common as bc
    from sentence_transformers import CrossEncoder
    dev = bc.pick_device()
    backend, emb_path, meta_path = BACKEND, EMB, META
    # Query embedding: OpenAI backend embeds via API; on ANY failure, fall back to the e5 index
    # so retrieval degrades gracefully instead of dying (reliability > cloud purity).
    qv = None
    if backend == 'openai':
        try:
            qv = _oai_embed_query(query)
        except Exception as e:
            sys.stderr.write('OpenAI query-embed failed (%s) -> fallback e5\n' % str(e)[:120])
            backend, emb_path, meta_path = 'e5', E5_EMB, E5_META
    meta = pickle.loads(meta_path.read_bytes()); emb = np.load(emb_path)
    # Union peer shards (canon-proposal MAC1 2026-07-14, Anton mandate "не ждать хаб"):
    # peers embed their own fresh essence notes into <vault>/_machine-bus/_brain-shards/<machine>/;
    # e5-space ONLY (openai index is a different space — never mix). Dedup-by-path below already
    # drops duplicates once the hub's nightly reindex catches up with the same note.
    if backend == 'e5':
        import glob as _glob
        try:
            from _paths import VAULT as _VLT
        except Exception:
            _VLT = r'%VAULT%'
        _shards_dir = os.path.join(str(_VLT), '_machine-bus', '_brain-shards')
        for _npy in sorted(_glob.glob(os.path.join(_shards_dir, '*', 'shard.npy'))):
            _mp = Path(_npy).with_name('shard_meta.pkl')
            if not _mp.exists(): continue
            try:
                _e = np.load(_npy); _m = pickle.loads(_mp.read_bytes())
                if len(_e) == len(_m) and len(_e) and _e.shape[1] == emb.shape[1]:
                    emb = np.concatenate([emb, _e]); meta = list(meta) + list(_m)
            except Exception as _ex:
                sys.stderr.write('skip shard %s (%s)\n' % (_npy, str(_ex)[:80]))
    if qv is None:
        enc = bc.load_model(E5_MODEL, dev, fp16=True)
        qv = enc.encode(['query: ' + query], normalize_embeddings=True, convert_to_numpy=True)[0].astype('float32')
    sims = emb @ qv
    # dense retrieve -> dedup by path (best chunk per file) -> top-K unique files
    order, seen = [], set()
    for i in np.argsort(-sims):
        m = meta[i]
        if anton and not m.get('anton'): continue
        if types and m.get('source_type') not in types: continue
        if path_subs and not any(s in str(m.get('path','')).replace('\\','/') for s in path_subs): continue
        if m['path'] in seen: continue
        seen.add(m['path']); order.append(int(i))
        if len(order) >= TOPK_RETRIEVE: break
    # graph-expansion (Phase 2 of always-on memory, decision-always-on-memory-architecture):
    # follow 1-hop OUTGOING wikilinks from the top vector hits, pull in those neighbour notes
    # (resolved to already-indexed chunks), then let the reranker decide if they're relevant.
    # Bounded + opt-in (--graph) so base recall is untouched. Serendipity the reranker keeps honest.
    # CRASH-SAFETY: the "Associative" (graph) process is wrapped so ANY failure degrades to
    # "Direct" (vector-only) — worst case you get the OLD result, never an empty/broken recall.
    base_order = list(order); added = []
    if (graph or ab) and order:
        try:
            GHOPS, GMAX = 15, 40            # expand from top-15 hits, add at most 40 neighbours
            by_base = {}                     # basename(no .md) -> meta indices (resolve link targets)
            for j, mm in enumerate(meta):
                by_base.setdefault(Path(mm['path']).stem.lower(), []).append(j)
            in_order = set(base_order)
            for i in base_order[:GHOPS]:
                for tgt in _links_in(meta[i]['path']):
                    idxs = by_base.get(tgt.lower())
                    if not idxs: continue
                    best = max(idxs, key=lambda j: sims[j])   # best chunk of neighbour for THIS query
                    if best in in_order: continue
                    mm = meta[best]
                    if anton and not mm.get('anton'): continue
                    if types and mm.get('source_type') not in types: continue
                    if path_subs and not any(s in str(mm.get('path','')) for s in path_subs): continue
                    in_order.add(best); added.append(best)
                    if len(added) >= GMAX: break
                if len(added) >= GMAX: break
        except Exception as e:
            added = []                       # graph failed -> fall back to Direct (vector) only
            sys.stderr.write("graph-expansion fell back to vector (%s)\n" % e)
    graph_order = base_order + added; graph_set = set(added)

    # entity-полоса (Phase 2.5, рецепт Арсёнова без spaCy, A/B 2026-07-02: 3 WIN / 0 вреда):
    # карточки людей/лидов и ноты-упоминания из _brain_entity.db (evidence-слой, в векторном
    # индексе их НЕТ по essence/evidence-онтологии) идут кандидатами прямо с диска — реранкеру
    # эмбеддинги не нужны. Пропускается при type/path-фильтрах (скоуп задан явно).
    # CRASH-SAFETY: любой сбой полосы -> ent_added=[] -> ровно старое поведение.
    ent_added, ent_pen = [], {}
    if (graph or ab) and not types and not path_subs and not anton:
        try:
            import brain_entity
            meta = list(meta)
            known = {meta[i]['path'] for i in graph_order}
            for c in brain_entity.lane(query):
                if c['path'] in known: continue
                known.add(c['path'])
                meta.append({'path': c['path'], 'title': c['title'], 'snippet': c['snippet'],
                             'date': '', 'concept': '', 'source_type': 'entity', 'anton': False})
                j = len(meta) - 1
                ent_added.append(j)
                if c['fuzzy']: ent_pen[j] = brain_entity.FUZZY_PENALTY
        except Exception as e:
            ent_added, ent_pen = [], {}
            sys.stderr.write("entity lane fell back (%s)\n" % e)
    ent_set = set(ent_added)

    # rerank on the matched chunk (precise); fuzzy-entity кандидаты со штрафом (шум Lino Gandola)
    ce = CrossEncoder(RERANK_MODEL, device=dev)
    def rerank(cand):
        pairs = [(query, meta[i]['title'] + '. ' + meta[i]['snippet']) for i in cand]
        sc = ce.predict(pairs) if pairs else []
        sc = [s - ent_pen.get(i, 0.0) for i, s in zip(cand, sc)]
        return sorted(zip(cand, sc), key=lambda x: -x[1])[:TOPN]

    # --ab: run BOTH paths in ONE process, diff, log. Answers "does the pilot REALLY help?"
    if ab:
        A = rerank(base_order); B = rerank(graph_order + ent_added)
        a_paths = {meta[i]['path'] for i, _ in A}
        promoted = [(r, meta[i]['title']) for r, (i, _) in enumerate(B, 1)
                    if i in graph_set or i in ent_set]        # graph/entity notes that reached top-N
        new_in_B = [(r, meta[i]['title']) for r, (i, _) in enumerate(B, 1)
                    if meta[i]['path'] not in a_paths]        # any note B surfaced that A missed
        out = [f'A/B RECALL: {query}',
               f'(ПРЯМАЯ={len(base_order)} vector / АССОЦИАТИВНАЯ=+{len(added)} graph +{len(ent_added)} entity; '
               f'Ассоциативная подняла {len(new_in_B)} новых в топ-{TOPN}, {len(promoted)} из них через граф/entity)', '',
               '--- ПРЯМАЯ память (Direct / vector) ---']
        for r, (i, sc) in enumerate(A, 1):
            out.append('%2d. [%6.2f] %s' % (r, float(sc), meta[i]['title']))
        out += ['', '--- АССОЦИАТИВНАЯ память (Associative / vector+graph+entity) ---']
        for r, (i, sc) in enumerate(B, 1):
            mk = ('  <== +entity' if i in ent_set else
                  ('  <== +граф' if i in graph_set else
                   ('  <== НОВОЕ' if meta[i]['path'] not in a_paths else '')))
            out.append('%2d. [%6.2f] %s%s' % (r, float(sc), meta[i]['title'], mk))
        text = '\n'.join(out)
        try:
            con = sqlite3.connect(str(AB_DB), timeout=3.0)
            con.execute("""CREATE TABLE IF NOT EXISTS ab_recall(
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, query TEXT,
                cand_added INTEGER, new_in_top INTEGER, promoted_via_graph INTEGER,
                promoted_titles TEXT, source TEXT)""")
            for _c in ("source", "gate_pred"):   # back-compat for old table
                try: con.execute("ALTER TABLE ab_recall ADD COLUMN %s TEXT" % _c)
                except Exception: pass
            # ROOT-FIX 2026-07-27: метку гейта ставим ЗДЕСЬ, в единственном живом пути A/B.
            # Раньше её проставлял только ab_batch.py (свой дубль пайплайна) => у ВСЕХ 420 рабочих
            # и ночных строк gate_pred=None, а батч с 26.06 мёртв (индекс 3072 vs модель 768) =>
            # за месяц НОЛЬ строк entity, и entity-половина гейта не измерялась. Теперь каждая
            # строка --ab (work и nightly) сама несёт метку, посчитанную ТОЙ ЖЕ looks_like_entity,
            # что решает в бою -- измеряем ровно то, что работает.
            con.execute("INSERT INTO ab_recall(ts,query,cand_added,new_in_top,promoted_via_graph,promoted_titles,source,gate_pred)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (time.strftime('%Y-%m-%d %H:%M:%S'), query, len(added), len(new_in_B),
                         len(promoted), '; '.join(t for _, t in promoted)[:1000],
                         os.getenv('AB_SOURCE', 'work'),
                         'entity' if looks_like_entity(query) else 'thematic'))
            con.commit(); con.close()
        except Exception:
            pass
        jpath = os.getenv('BRAIN_AB_JSON')   # structured A/B for the visual dashboard
        if jpath:
            import json as _json
            def _ser(lst):
                return [{'rank': r, 'title': meta[i]['title'], 'score': round(float(sc), 2),
                         'type': meta[i].get('source_type', '?'), 'date': meta[i].get('date', ''),
                         'snippet': meta[i].get('snippet', '')[:200],
                         'graph': i in graph_set, 'entity': i in ent_set,
                         'new': meta[i]['path'] not in a_paths}
                        for r, (i, sc) in enumerate(lst, 1)]
            try:
                Path(jpath).write_text(_json.dumps(
                    {'query': query, 'added': len(added), 'new_in_top': len(new_in_B),
                     'direct': _ser(A), 'associative': _ser(B)}, ensure_ascii=False), encoding='utf-8')
            except Exception:
                pass
        _out = Path(os.getenv('BRAIN_ANSWER_OUT') or str(Path(_IMP) / '_brain_answer_rr.txt'))
        _out.write_text(text, encoding='utf-8'); print(text)
        return

    # GATE (2026-06-26): wiki-graph helps THEMES, hurts ENTITY/name queries -> skip wiki for
    # entities. Entity-ПОЛОСА при этом остаётся ВКЛ (2026-07-02): она для имён и создана.
    gated = graph and looks_like_entity(query)
    if gated:
        sys.stderr.write("wiki-graph gated OFF (entity-like query) -> Direct + entity lane\n")
    order = (graph_order if (graph and not gated) else base_order) + ent_added
    reranked = rerank(order)
    scope = ('+'.join(sorted(types)) if types else 'all') + (' /anton' if anton else '') + ((' /path:' + ','.join(path_subs)) if path_subs else '') + (' /graph+%d' % len(graph_set) if graph else '') + (' /entity+%d' % len(ent_set) if ent_set else '')
    lines = [f'QUERY: {query}', f'(scope={scope}; e5 {len(order)} files -> rerank; {len(meta)} chunks)', '']
    if ask:
        lines.append('=== CONTEXT BUNDLE (paste to Claude) ===\n')
        for i, sc in reranked[:8]:
            m = meta[i]
            hdr = "## %s  [%s] (%s) {%s} rr=%.2f%s" % (m['title'], m['date'], m['concept'] or '-', m.get('source_type','?'), float(sc), ' +graph' if i in graph_set else (' +entity' if i in ent_set else ''))
            hdr += "\n<!-- src: %s -->" % m['path']   # SCM-трассировка: путь к первоисточнику (decision-2026-07-27-scm-circuit-breaker-v-rag §C2)
            ft = freshness_tag(m['path'])
            if ft: hdr += "  — ⏳ " + ft
            lines += [hdr, m['snippet'], '']
    else:
        for rank, (i, sc) in enumerate(reranked, 1):
            m = meta[i]; tag = 'ANTON' if m.get('anton') else m.get('source_type','')[:5].ljust(5)
            gmark = ' +graph' if i in graph_set else (' +entity' if i in ent_set else '')
            lines.append("%2d. [rr=%6.2f] %s [%s] %s%s" % (rank, float(sc), tag, m['date'], m['title'], gmark))
            lines.append("     {%s} %s" % (m.get('source_type','?'), m['snippet'][:140]))
            lines.append("     src: %s" % m['path'])   # SCM-трассировка (см. decision-2026-07-27-scm-circuit-breaker-v-rag §C2)
            ft = freshness_tag(m['path'])
            if ft: lines.append("     ⏳ " + ft)
    _out = Path(os.getenv('BRAIN_ANSWER_OUT') or str(Path(_IMP) / '_brain_answer_rr.txt'))
    _out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'{len(reranked)} hits (scope={scope}) -> {_out}')

if __name__ == '__main__':
    main()
