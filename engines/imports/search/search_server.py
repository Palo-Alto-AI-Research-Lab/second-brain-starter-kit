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
"""search_server.py — visual local search UI over the chat-content catalog.

Self-contained (Python stdlib only, no deps = AK-47). Serves a search box at
http://127.0.0.1:8771 and a JSON API /api?q=...&k=... backed by search_catalog.db
(FTS5/BM25) + dialogs.db chat-title hits. Read-only; 0 GPU; 0 tokens.

Run:  pythonw search_server.py   (or python for a console)
Stop: close the process / Ctrl-C.
"""
import os, sqlite3, json, re, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "search_catalog.db")
DIALOGS = os.path.join(os.path.dirname(HERE), "dialogs", "dialogs.db")
PORT = 8771

def fts_query(words):
    toks = [t for t in re.split(r"\s+", (words or "").strip()) if t]
    return " ".join('"%s"' % t.replace('"', "") for t in toks)

def search(q, k=20):
    out = {"query": q, "docs": [], "chats": [], "corpus": 0}
    if not q or not os.path.exists(CATALOG):
        return out
    con = sqlite3.connect(CATALOG)
    try:
        rows = con.execute(
            "SELECT path, source, date, snippet(docs_fts,1,'<<','>>',' ... ',16), "
            "bm25(docs_fts) AS r, title FROM docs_fts WHERE docs_fts MATCH ? "
            "ORDER BY r LIMIT ?", (fts_query(q), k)).fetchall()
        for path, source, date, snip, r, title in rows:
            out["docs"].append({"path": path, "source": source, "date": date,
                                "snippet": snip, "score": round(r, 1), "title": title})
        c = con.execute("SELECT v FROM meta WHERE k='doc_count'").fetchone()
        out["corpus"] = int(c[0]) if c else 0
    except sqlite3.OperationalError as e:
        out["error"] = str(e)
    con.close()
    if os.path.exists(DIALOGS):
        dq = q.lower()
        d = sqlite3.connect(DIALOGS)
        for a, cid, t, ti in d.execute("SELECT account,chat_id,type,title FROM dialogs"):
            if dq in (ti or "").lower():
                out["chats"].append({"account": a, "chat_id": cid, "type": t, "title": ti})
                if len(out["chats"]) >= 25:
                    break
        d.close()
    return out

PAGE = """<!doctype html><html lang=ru><head><meta charset=utf-8>
<title>Поиск по Второму Мозгу</title>
<style>
 body{font:16px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#0f1115;color:#e6e6e6}
 h1{font-size:20px;font-weight:600} .sub{color:#8a93a2;font-size:13px;margin-bottom:14px}
 #q{width:100%;font-size:18px;padding:12px 14px;border-radius:10px;border:1px solid #2a2f3a;background:#171a21;color:#fff;box-sizing:border-box}
 .hit{padding:12px 14px;margin:10px 0;background:#161a22;border:1px solid #232838;border-radius:10px}
 .t{font-weight:600;color:#cfe3ff} .meta{color:#7f8a9c;font-size:12px;margin:2px 0 6px}
 .snip{color:#c7cdd6;font-size:14px} .snip mark{background:#3a4a2a;color:#dfffbf;padding:0 2px;border-radius:3px}
 .path{color:#5d6675;font-size:11px;margin-top:6px;word-break:break-all}
 .chat{display:inline-block;margin:3px 6px 3px 0;padding:4px 9px;background:#1d2740;border-radius:20px;font-size:13px;color:#bcd0ff}
 .sec{color:#8a93a2;font-size:12px;text-transform:uppercase;letter-spacing:.04em;margin:18px 0 6px}
</style></head><body>
<h1>🔎 Поиск по Второму Мозгу <span class=sub id=corpus></span></h1>
<div class=sub>Поиск по словам внутри всех чатов (Telegram, Facebook, ChatGPT, Claude…). Лексический lane (BM25). Смысловой lane — скоро.</div>
<input id=q placeholder="например: давление магний  ·  L-тирозин дофамин  ·  голодание" autofocus>
<div id=chats></div>
<div id=res></div>
<script>
const q=document.getElementById('q'),res=document.getElementById('res'),chats=document.getElementById('chats'),corpus=document.getElementById('corpus');
let timer;
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function mark(s){return esc(s).replace(/&lt;&lt;/g,'<mark>').replace(/&gt;&gt;/g,'</mark>')}
async function go(){
 const v=q.value.trim(); if(!v){res.innerHTML='';chats.innerHTML='';return}
 const r=await fetch('/api?q='+encodeURIComponent(v)+'&k=25'); const d=await r.json();
 corpus.textContent='('+d.corpus.toLocaleString('ru')+' переписок)';
 chats.innerHTML = d.chats.length ? '<div class=sec>Чаты по названию</div>'+d.chats.map(c=>`<span class=chat title="${esc(c.account)} ${c.chat_id}">${esc(c.title)}</span>`).join('') : '';
 res.innerHTML='<div class=sec>'+d.docs.length+' совпадений по контенту</div>'+d.docs.map(h=>`
  <div class=hit><div class=t>${esc(h.title)}</div>
  <div class=meta>${esc(h.source)} · ${esc(h.date)} · score ${h.score}</div>
  <div class=snip>${mark(h.snippet)}</div><div class=path>${esc(h.path)}</div></div>`).join('');
}
q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(go,180)});
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api":
            qs = parse_qs(u.query)
            q = (qs.get("q", [""])[0])
            try: k = int(qs.get("k", ["20"])[0])
            except ValueError: k = 20
            body = json.dumps(search(q, k), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json")
        else:
            self._send(200, PAGE.encode("utf-8"), "text/html")

if __name__ == "__main__":
    print("Search UI -> http://127.0.0.1:%d" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
