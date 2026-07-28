#!/usr/bin/env python3
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
"""
content_approve.py - Phase-1 approval GATE for Anton's content factory.

The DR's Phase 1: keep draft-first, add a single approval queue with human sign-off.
This is the works-now version (visual, by-eye, no Telegram MCP needed): a tiny local
web dashboard listing the factory's plans/drafts as cards with  Approve / Edit / Reject .
Decisions persist to approval_state.json; approved items are copied to approved/ (the
Phase-2 publish queue that n8n will later drain). Pure stdlib, AK-47, repairable.

Run:  python content_approve.py --serve   ->  http://127.0.0.1:8780
"""
import argparse, html, json, os, shutil, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIRS = [os.path.join(ROOT, "plans"), os.path.join(ROOT, "drafts")]
APPROVED_DIR = os.path.join(ROOT, "approved")
STATE_PATH = os.path.join(ROOT, "approval_state.json")
PORT = 8780


def load_state():
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(st):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def list_items():
    items = []
    for d in SRC_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                items.append((os.path.basename(d) + "/" + fn, os.path.join(d, fn)))
    return items


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return "[read error: %s]" % e


STATUS_BADGE = {
    "approve": ("✅ ОДОБРЕНО", "#1a7f37", "#e6f4ea"),
    "reject":  ("❌ ОТКЛОНЕНО", "#b42318", "#fdeceb"),
    "edit":    ("✏️ НА ПРАВКУ", "#9a6700", "#fff8e1"),
}


def page():
    st = load_state()
    items = list_items()
    counts = {"approve": 0, "reject": 0, "edit": 0, "pending": 0}
    cards = []
    for cid, path in items:
        rec = st.get(cid, {})
        status = rec.get("status", "")
        counts[status if status in counts else "pending"] += 1
        badge = ""
        if status in STATUS_BADGE:
            lbl, fg, bg = STATUS_BADGE[status]
            badge = '<span class="badge" style="color:%s;background:%s">%s</span>' % (fg, bg, lbl)
        body = html.escape(read_text(path))
        cid_attr = html.escape(cid)
        cards.append("""
        <div class="card" id="card-{cid}">
          <div class="hd"><b>{cid}</b> {badge}
            <span class="path">{path}</span></div>
          <pre>{body}</pre>
          <div class="btns">
            <button class="ok"  onclick="setS('{cid}','approve')">✅ Одобрить</button>
            <button class="ed"  onclick="setS('{cid}','edit')">✏️ На правку</button>
            <button class="no"  onclick="setS('{cid}','reject')">❌ Отклонить</button>
          </div>
        </div>""".format(cid=cid_attr, badge=badge, path=html.escape(path), body=body))
    head = """<!doctype html><html><head><meta charset="utf-8">
    <title>Очередь одобрения контента</title><style>
    body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#fafafa;color:#1a1a1a}
    h1{font-size:20px} .sum{position:sticky;top:0;background:#fafafa;padding:10px 0;border-bottom:1px solid #ddd;z-index:5}
    .card{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:14px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
    .hd{display:flex;gap:10px;align-items:center;flex-wrap:wrap} .path{color:#888;font-size:12px;margin-left:auto}
    pre{white-space:pre-wrap;background:#f6f8fa;border-radius:8px;padding:10px;max-height:300px;overflow:auto;font-size:13px}
    .badge{font-size:12px;font-weight:600;padding:2px 8px;border-radius:20px}
    .btns{display:flex;gap:8px;margin-top:8px} button{font:14px;padding:8px 14px;border-radius:8px;border:1px solid #ccc;cursor:pointer}
    .ok{background:#e6f4ea;border-color:#1a7f37;color:#1a7f37} .no{background:#fdeceb;border-color:#b42318;color:#b42318}
    .ed{background:#fff8e1;border-color:#9a6700;color:#9a6700}
    </style></head><body><h1>📋 Очередь одобрения контента <span style="font-size:13px;color:#888">(draft-first, ты решаешь)</span></h1>"""
    summ = '<div class="sum">Всего: %d · ✅ %d · ✏️ %d · ❌ %d · ⏳ ждут: %d &nbsp;|&nbsp; одобренные копируются в <code>approved/</code> (очередь публикации)</div>' % (
        len(items), counts["approve"], counts["edit"], counts["reject"], counts["pending"])
    script = """<script>
    function setS(id,act){fetch('/set?id='+encodeURIComponent(id)+'&action='+act).then(r=>r.json()).then(_=>location.reload());}
    </script>"""
    return head + summ + "".join(cards) + script + "</body></html>"


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            self._send(200, page())
        elif u.path == "/set":
            q = urllib.parse.parse_qs(u.query)
            cid = q.get("id", [""])[0]
            act = q.get("action", [""])[0]
            if act not in ("approve", "reject", "edit") or not cid:
                self._send(400, json.dumps({"err": "bad"}), "application/json")
                return
            st = load_state()
            st[cid] = {"status": act, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_state(st)
            if act == "approve":
                os.makedirs(APPROVED_DIR, exist_ok=True)
                src = None
                for d in SRC_DIRS:
                    p = os.path.join(d, os.path.basename(cid))
                    if os.path.isfile(p):
                        src = p
                        break
                if src:
                    shutil.copy2(src, os.path.join(APPROVED_DIR, os.path.basename(cid)))
            self._send(200, json.dumps({"ok": True}), "application/json")
        else:
            self._send(404, "not found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    if not args.serve:
        items = list_items()
        print("plans/drafts found: %d" % len(items))
        for cid, _ in items:
            print("  -", cid)
        print("run with --serve to open the approval dashboard at http://127.0.0.1:%d" % args.port)
        return
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), H)
    print("Content approval dashboard: http://127.0.0.1:%d  (Ctrl+C to stop)" % args.port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
