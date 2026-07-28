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
find_name.py — умный поиск имени по names.db.

  python find_name.py виктор            # таблица в консоли
  python find_name.py виктор --html     # + HTML-дашборд в _Dashboards
  python find_name.py dbrnjh            # раскладочный мусор тоже найдёт

Находит точные совпадения отпечатка + нечёткие (опечатки, расст. Левенштейна).
"""
import os, re, sys, sqlite3, html, webbrowser
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_norm import keys, tokens, lev, fuzzy_thr

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'names.db')
VAULT = r'%VAULT%'
DASH = os.path.join(VAULT, '_Dashboards')


def search(query):
    qkeys = set(keys(query))
    for t in tokens(query):
        qkeys |= keys(t)
    qkeys = {k for k in qkeys if k}
    if not qkeys:
        return [], qkeys

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 1) точные совпадения отпечатка
    ph = ','.join('?' * len(qkeys))
    cur.execute(f'SELECT path,key,tok FROM nkeys WHERE key IN ({ph})', tuple(qkeys))
    hit = {}          # path -> (dist, matched_key, matched_tok)
    for path, key, tok in cur.fetchall():
        hit[path] = (0, key, tok)

    # 2) нечёткие: только ключи близкой длины (lev >= разницы длин — фильтр без потерь)
    by_len = {}                         # длина -> список ключей
    for (k,) in cur.execute('SELECT DISTINCT key FROM nkeys'):
        by_len.setdefault(len(k), []).append(k)
    fuzzy_keys = {}                     # key -> dist
    qthr = max((fuzzy_thr(qk) for qk in qkeys), default=0)
    RAD = 2                              # максимум, что вообще прощает fuzzy_thr
    for qk in qkeys:
        thr = max(fuzzy_thr(qk), qthr)
        for L in range(len(qk) - RAD, len(qk) + RAD + 1):
            for k in by_len.get(L, ()):
                if k in qkeys:
                    continue
                d = lev(k, qk)
                if d <= max(thr, fuzzy_thr(k)) and d < fuzzy_keys.get(k, 99):
                    fuzzy_keys[k] = d
    if fuzzy_keys:
        ph2 = ','.join('?' * len(fuzzy_keys))
        cur.execute(f'SELECT path,key,tok FROM nkeys WHERE key IN ({ph2})',
                    tuple(fuzzy_keys))
        for path, key, tok in cur.fetchall():
            d = fuzzy_keys[key]
            if path not in hit or d < hit[path][0]:
                hit[path] = (d, key, tok)

    # подтянуть отображение
    rows = []
    for path, (dist, key, tok) in hit.items():
        cur.execute('SELECT kind,display FROM entries WHERE path=?', (path,))
        r = cur.fetchone()
        kind, display = (r if r else ('?', path))
        rows.append({'path': path, 'kind': kind, 'display': display,
                     'dist': dist, 'key': key, 'tok': tok})
    con.close()
    kind_order = {'company': 0, 'lead': 1, 'person': 2, 'contact': 3, 'note': 4}
    rows.sort(key=lambda r: (r['dist'], kind_order.get(r['kind'], 9),
                             r['display'].lower()))
    return rows, qkeys


def to_html(query, rows, qkeys):
    os.makedirs(DASH, exist_ok=True)
    safe = re.sub(r'[^\w]+', '_', query)[:40]
    out = os.path.join(DASH, f'Name-Search-{safe}.html')
    cards = []
    for r in rows:
        badge = {'lead': '#2a7', 'person': '#27a', 'contact': '#a62',
                 'company': '#759', 'note': '#888'}.get(r['kind'], '#555')
        tag = 'точно' if r['dist'] == 0 else f'~{r["dist"]}'
        cards.append(f'''<tr>
          <td><b>{html.escape(r["display"])}</b></td>
          <td><span style="background:{badge};color:#fff;padding:1px 7px;border-radius:8px;font-size:12px">{r["kind"]}</span></td>
          <td style="color:#999;font-size:12px">{tag} · {html.escape(r["key"])}</td>
          <td style="color:#777;font-size:12px">{html.escape(r["path"])}</td></tr>''')
    doc = f'''<!doctype html><meta charset="utf-8">
<title>Поиск: {html.escape(query)}</title>
<body style="font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:30px auto;color:#222">
<h2>🔎 «{html.escape(query)}» — найдено {len(rows)}</h2>
<p style="color:#777">Отпечатки запроса: {", ".join(sorted(qkeys))}</p>
<table style="border-collapse:collapse;width:100%">
<tr style="text-align:left;border-bottom:2px solid #ddd">
<th>Имя</th><th>Тип</th><th>Совпадение</th><th>Файл</th></tr>
{''.join(cards)}
</table></body>'''
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    want_html = '--html' in sys.argv
    if not args:
        print('использование: python find_name.py <имя> [--html]')
        return
    query = ' '.join(args)
    show_all = '--all' in sys.argv
    rows, qkeys = search(query)
    notes = [r for r in rows if r['kind'] == 'note']
    if not show_all:
        rows = [r for r in rows if r['kind'] != 'note']
    tail = f' (+{len(notes)} заметок волта — добавь --all)' if notes and not show_all else ''
    nc = sum(1 for r in rows if r['kind'] == 'contact')
    cpart = f' (вкл. {nc} Apple-контактов)' if nc else ''
    print(f'\n🔎 «{query}»  отпечатки={sorted(qkeys)}  →  люди: {len(rows)}{cpart}{tail}\n')
    for r in rows[:60]:
        tag = 'точно' if r['dist'] == 0 else f'~{r["dist"]}'
        print(f'  {r["display"][:34]:34} {r["kind"]:7} {tag:6} {r["path"]}')
    if len(rows) > 60:
        print(f'  … ещё {len(rows)-60}')
    if want_html and rows:
        out = to_html(query, rows, qkeys)
        print(f'\nHTML: {out}')
        try:
            webbrowser.open('file:///' + out.replace('\\', '/'))
        except Exception:
            pass


if __name__ == '__main__':
    main()
