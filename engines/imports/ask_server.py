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
r"""ask_server.py — /ask as a live visual search of the Second Brain.

Loads the e5 index + cross-encoder reranker ONCE at startup, then serves a search
box GUI at http://127.0.0.1:8770. Each query: e5 dense retrieve (top-60, dedup by
path) -> rerank -> top-12, with source filters and freshness (⚠ STALE) tags.
Same engine as brain_ask.py — reused, not duplicated (imports its freshness logic).

  python ask_server.py            # CPU by default (~3s/query, never fights the GPU fleet)
  python ask_server.py --gpu      # use CUDA (faster, but contends with the agent fleet/reindex)
  python ask_server.py --port 8771

Default is CPU on purpose: the query load is tiny, and Anton's background agent
fleet often saturates the GPU — CPU keeps search reliably responsive and holds no VRAM.
Token-cheap by design: retrieval is local/free; nothing is sent to any LLM.
"""
import sys, json, pickle, threading, html
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
IMPORTS = Path(IMPORTS)
EMB = IMPORTS / "_brain_e5.npy"
META = IMPORTS / "_brain_e5_meta.pkl"
E5_MODEL = "intfloat/multilingual-e5-base"
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
TOPK_RETRIEVE, TOPN = 60, 12
PORT = 8770
SCOPES = [("anton", "только моё"), ("concept", "концепты"), ("insight", "инсайты"),
          ("lead", "лиды"), ("person", "люди"), ("conversation", "разговоры"), ("note", "заметки")]

sys.path.insert(0, str(IMPORTS))
import brain_common as bc
import brain_ask as ba   # reuse freshness_tag / fm_meta (main() is __main__-guarded, not run)

_LOCK = threading.Lock()   # GPU inference is not thread-safe
ENC = CE = EMB_ARR = METAS = DEV = None

def load():
    global ENC, CE, EMB_ARR, METAS, DEV
    if not EMB.exists():
        print("FATAL: e5 index not found:", EMB); sys.exit(2)
    force_cpu = "--gpu" not in sys.argv   # CPU by default; opt into GPU explicitly
    DEV = bc.pick_device(force_cpu=force_cpu)
    print(f"loading models on {DEV} ...")
    from sentence_transformers import CrossEncoder
    METAS = pickle.loads(META.read_bytes())
    EMB_ARR = np.load(EMB)
    ENC = bc.load_model(E5_MODEL, DEV, fp16=True)
    CE = CrossEncoder(RERANK_MODEL, device=DEV)
    print(f"ready: {len(METAS)} chunks, {EMB_ARR.shape[0]} vectors")

def search(query, types, anton):
    with _LOCK:
        qv = ENC.encode(["query: " + query], normalize_embeddings=True,
                        convert_to_numpy=True)[0].astype("float32")
        sims = EMB_ARR @ qv
        order, seen = [], set()
        for i in np.argsort(-sims):
            m = METAS[i]
            if anton and not m.get("anton"):
                continue
            if types and m.get("source_type") not in types:
                continue
            if m["path"] in seen:
                continue
            seen.add(m["path"]); order.append(int(i))
            if len(order) >= TOPK_RETRIEVE:
                break
        pairs = [(query, METAS[i]["title"] + ". " + METAS[i]["snippet"]) for i in order]
        scores = CE.predict(pairs) if pairs else []
        reranked = sorted(zip(order, scores), key=lambda x: -x[1])[:TOPN]
    hits = []
    for rank, (i, sc) in enumerate(reranked, 1):
        m = METAS[i]
        try:
            fresh = ba.freshness_tag(m["path"])
        except Exception:
            fresh = ""
        hits.append({
            "rank": rank, "score": round(float(sc), 2), "title": m.get("title", ""),
            "date": m.get("date", ""), "type": m.get("source_type", "?"),
            "concept": m.get("concept", "") or "", "anton": bool(m.get("anton")),
            "snippet": m.get("snippet", "")[:420], "fresh": fresh,
        })
    return hits

PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Второй мозг — поиск</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;
--acc:#5b9bff;--acc2:#37d399;--acc3:#ffb454;--acc4:#ff6b8b;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:30px 22px 70px}
h1{font-size:23px;margin:0 0 4px} .sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.box{display:flex;gap:8px;margin-bottom:10px}
#q{flex:1;background:#11141a;border:1px solid var(--line);border-radius:11px;color:var(--ink);
padding:13px 15px;font-size:16px} #q:focus{outline:none;border-color:var(--acc)}
button{background:var(--acc);color:#fff;border:0;border-radius:11px;padding:0 22px;font-size:15px;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
.scopes{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:18px}
.chip{font-size:12.5px;color:var(--mut);background:#11141a;border:1px solid var(--line);
border-radius:20px;padding:5px 12px;cursor:pointer;user-select:none}
.chip.on{border-color:var(--acc);color:#fff;background:#16263f}
#status{color:var(--mut);font-size:13px;min-height:20px;margin-bottom:8px}
.hit{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 16px;margin-bottom:11px}
.hit .top{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:5px}
.hit .t{font-weight:600;font-size:15px}
.rr{font-variant-numeric:tabular-nums;font-size:11px;color:#0c0f14;background:var(--acc2);border-radius:6px;padding:1px 7px;font-weight:700}
.rr.lo{background:var(--acc3)} .rr.neg{background:var(--mut)}
.tp{font-size:10.5px;color:var(--mut);background:#222834;border-radius:5px;padding:1px 7px}
.an{font-size:10.5px;color:#bdf0d2;background:#13241a;border:1px solid #1f3a2a;border-radius:5px;padding:1px 7px}
.dt{font-size:11.5px;color:var(--mut)}
.sn{font-size:13px;color:#cdd6e2;margin-top:3px}
.fr{font-size:11px;color:var(--acc3);margin-top:5px}
.fr.stale{color:var(--acc4)}
.empty{color:var(--mut);text-align:center;padding:40px}
kbd{background:#222834;border-radius:5px;padding:1px 6px;font-size:11px}
</style></head><body><div class="wrap">
<h1>🧠 Второй мозг — поиск</h1>
<div class="sub">Семантический поиск по курированному волту (e5 + reranker). Локально, ничего не уходит в LLM.</div>
<div class="box"><input id="q" placeholder="спроси мозг своими словами…" autofocus>
<button id="go" onclick="run()">Искать</button></div>
<div class="scopes" id="scopes"></div>
<div id="status">Готов. Нажми <kbd>Enter</kbd>.</div>
<div id="res"></div>
</div><script>
const SCOPES=__SCOPES__;
const active=new Set();
const sc=document.getElementById('scopes');
SCOPES.forEach(([k,l])=>{const d=document.createElement('div');d.className='chip';d.textContent=l;
d.onclick=()=>{d.classList.toggle('on');active.has(k)?active.delete(k):active.add(k);};
sc.appendChild(d);});
const q=document.getElementById('q'),go=document.getElementById('go'),
st=document.getElementById('status'),res=document.getElementById('res');
q.addEventListener('keydown',e=>{if(e.key==='Enter')run();});
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function run(){
  const query=q.value.trim(); if(!query)return;
  go.disabled=true; st.textContent='Ищу…'; res.innerHTML='';
  const t0=performance.now();
  try{
    const u='/api?q='+encodeURIComponent(query)+'&scope='+[...active].join(',');
    const r=await fetch(u); const j=await r.json();
    const ms=Math.round(performance.now()-t0);
    if(!j.hits||!j.hits.length){res.innerHTML='<div class="empty">Ничего релевантного. Попробуй переформулировать или снять фильтры.</div>';}
    else{res.innerHTML=j.hits.map(h=>{
      const cls=h.score>=4?'':(h.score>=1?'lo':'neg');
      const fr=h.fresh?('<div class="fr'+(h.fresh.includes('STALE')?' stale':'')+'">⏳ '+esc(h.fresh)+'</div>'):'';
      const an=h.anton?'<span class="an">моё</span>':'';
      return '<div class="hit"><div class="top"><span class="rr '+cls+'">'+h.score+'</span>'+
        '<span class="t">'+esc(h.title)+'</span>'+an+'<span class="tp">'+esc(h.type)+'</span>'+
        '<span class="dt">'+esc(h.date)+'</span></div>'+
        '<div class="sn">'+esc(h.snippet)+'</div>'+fr+'</div>';
    }).join('');}
    st.textContent=(j.hits?j.hits.length:0)+' результатов · '+ms+' мс · scope: '+(j.scope||'all');
  }catch(e){st.textContent='Ошибка: '+e;}
  go.disabled=false;
}
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass   # client disconnected (e.g. closed tab / curl timeout) — harmless

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE.replace("__SCOPES__", json.dumps(SCOPES, ensure_ascii=False)))
            return
        if u.path == "/api":
            qs = parse_qs(u.query)
            query = (qs.get("q", [""])[0]).strip()
            raw = [s for s in (qs.get("scope", [""])[0]).split(",") if s]
            anton = "anton" in raw
            types = set(s for s in raw if s != "anton")
            if not query:
                self._send(400, json.dumps({"hits": [], "error": "empty"}), "application/json")
                return
            try:
                hits = search(query, types, anton)
                scope = ("+".join(sorted(types)) if types else "all") + (" /anton" if anton else "")
                self._send(200, json.dumps({"hits": hits, "scope": scope}, ensure_ascii=False),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(500, json.dumps({"hits": [], "error": str(e)[:200]}), "application/json")
            return
        self._send(404, "not found")

def main():
    global PORT
    if "--port" in sys.argv:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])
    load()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"\n  🧠 Second-Brain search ready ->  http://127.0.0.1:{PORT}\n  Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("bye")

if __name__ == "__main__":
    main()
