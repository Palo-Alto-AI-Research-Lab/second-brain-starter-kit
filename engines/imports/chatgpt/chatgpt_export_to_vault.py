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
r"""chatgpt_export_to_vault.py — turn the OFFICIAL ChatGPT data export ZIP
(conversations-NNN.json split format) into well-linked Obsidian notes following
Anton's vault conventions, mirroring claudeai_export_to_vault.py.

One note per CONVERSATION (active leaf-path), frontmatter + provenance, a MOC
(by month), and a SQLite facts db. Deterministic scaffolding only —
related_concepts:[] left for a later LLM concept-linking pass (per the claude-ai
pattern). Canvas/code content stays inline in the dialogue. Idempotent: stable
filenames by conversation_id; re-runs overwrite in place, never delete.

Provenance: conversations -> origin: mixed (Anton asks, ChatGPT answers),
authored_by: hybrid.

USAGE:
  set PYTHONUTF8=1
  python chatgpt_export_to_vault.py --zip "<path to export.zip>" [--out <staging base>]
"""
import argparse, json, re, zipfile, sqlite3, datetime
from pathlib import Path

_CYR = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
_LAT = ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r',
        's','t','u','f','h','c','ch','sh','sch','','y','','e','yu','ya']
TRANSLIT = str.maketrans({c: l for c, l in zip(_CYR, _LAT)})
_CONV_RX = re.compile(r"(^|/)conversations(-\d+)?\.json$")


def slugify(text, fallback='chat'):
    text = (text or '').lower().translate(TRANSLIT)
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    text = text.encode('ascii', 'ignore').decode('ascii')
    return (text[:60].strip('-') or fallback)


def yq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', "'").replace('\n', ' ') + '"'


def load_conversations(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if _CONV_RX.search(n))
        if not names:
            raise SystemExit('no conversations(-NNN).json in zip')
        out = []
        for n in names:
            data = json.loads(z.read(n).decode('utf-8'))
            out.extend(data if isinstance(data, list) else [data])
        return out


def active_branch(mapping, current_node):
    chain, node = [], current_node
    while node:
        n = mapping.get(node)
        if not n:
            break
        chain.append(n)
        node = n.get('parent')
    return list(reversed(chain))


def extract_text(message):
    content = message.get('content') or {}
    ctype = content.get('content_type')
    if ctype == 'text':
        return ''.join(p for p in content.get('parts', []) if isinstance(p, str))
    if ctype == 'code':
        return '```\n' + (content.get('text') or '') + '\n```'
    parts = content.get('parts') or []
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            out.append('[%s]' % p.get('content_type', 'asset'))
    return ''.join(out)


def conv_stub(conv):
    ct = conv.get('create_time')
    d = datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d') if ct else '0000-00-00'
    cid = (conv.get('conversation_id') or conv.get('id') or '')
    return '%s-%s-%s' % (d, slugify(conv.get('title') or 'chat'), re.sub(r'[^0-9A-Za-z]', '', cid)[:8] or 'x')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', dest='zip', required=True)
    ap.add_argument('--out', dest='out',
                    default=r'%IMPORTS%\chatgpt\staging\01-Conversations\ChatGPT')
    a = ap.parse_args()
    today = datetime.date.today().isoformat()

    convos = load_conversations(Path(a.zip))
    base = Path(a.out)
    d_conv = base / 'conversations'
    d_conv.mkdir(parents=True, exist_ok=True)

    stats = {'conversations': 0, 'skipped_empty': 0, 'archived': 0, 'canvas': 0}
    moc_rows = []       # (updated, title, stub, msgcount, model, archived)
    db_rows = []

    for conv in convos:
        cid = conv.get('conversation_id') or conv.get('id') or 'unknown'
        title = (conv.get('title') or '').strip() or 'Untitled'
        mapping = conv.get('mapping') or {}
        cur = conv.get('current_node')
        chain = active_branch(mapping, cur) if cur else list(mapping.values())
        is_arch = bool(conv.get('is_archived'))
        gizmo = conv.get('gizmo_id') or ''

        lines, models, n_msg, has_canvas = [], set(), 0, False
        for node in chain:
            m = node.get('message')
            if not m:
                continue
            role = (m.get('author') or {}).get('role')
            if role not in ('user', 'assistant'):
                continue
            text = extract_text(m).strip()
            if not text:
                continue
            if 'canvas' in text.lower() or 'textdoc' in text.lower():
                has_canvas = True
            ts = m.get('create_time')
            tstr = datetime.datetime.fromtimestamp(ts).isoformat(timespec='seconds') if ts else ''
            model = (m.get('metadata') or {}).get('model_slug')
            if model:
                models.add(model)
            who = 'Anton' if role == 'user' else 'ChatGPT'
            n_msg += 1
            lines.append('**%s:**%s\n\n%s' % (who, (' · `%s`' % model) if model else '', text))

        if not lines:
            stats['skipped_empty'] += 1
            continue

        ct = conv.get('create_time'); ut = conv.get('update_time')
        created = datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d') if ct else today
        updated = datetime.datetime.fromtimestamp(ut).strftime('%Y-%m-%d') if ut else created
        model_main = conv.get('default_model_slug') or (sorted(models)[0] if models else '')
        stub = conv_stub(conv)

        fm = (
            '---\n'
            'title: %s\n' % yq(title) +
            'type: ai-conversation\n'
            'source: chatgpt\n'
            'origin: mixed\n'
            'authored_by: hybrid\n'
            'conversation_id: %s\n' % cid +
            'model: %s\n' % yq(model_main) +
            ('gizmo_id: %s\n' % gizmo if gizmo else '') +
            'url: "https://chatgpt.com/c/%s"\n' % cid +
            'date_recorded: %s\n' % updated +
            'date_added: %s\n' % today +
            'valid_as_of: %s\n' % updated +
            'archived: %s\n' % ('true' if is_arch else 'false') +
            'volatility: slow\n'
            'interpretation_confidence: high\n'
            'intent: ""\n'
            'language: ru\n'
            'tags: [chatgpt, ai-conversation%s]\n' % (', archived' if is_arch else '') +
            'value_score: 0.0\n'
            'msg_count: %d\n' % n_msg +
            'related_concepts: []\n'
            'revisit_if: ""\n'
            '---\n\n'
        )
        meta = '> ChatGPT · %s%s · %d сообщений%s\n\n' % (
            updated, (' · `%s`' % model_main) if model_main else '', n_msg,
            ' · 🗄 архив' if is_arch else '')
        body = '# %s\n\n' % title + meta + '## Диалог\n\n' + '\n\n---\n\n'.join(lines) + '\n'
        (d_conv / (stub + '.md')).write_text(fm + body, encoding='utf-8')

        stats['conversations'] += 1
        if is_arch:
            stats['archived'] += 1
        if has_canvas:
            stats['canvas'] += 1
        moc_rows.append((updated, title, stub, n_msg, model_main, is_arch))
        db_rows.append((cid, created, updated, title, model_main, int(is_arch), n_msg, stub))

    # ---- MOC (by month) ----
    moc_rows.sort(reverse=True)
    by_month = {}
    for r in moc_rows:
        by_month.setdefault(r[0][:7], []).append(r)
    moc = ['---', 'title: "ChatGPT — все разговоры (MOC)"', 'type: moc', 'source: chatgpt',
           'date_added: %s' % today, 'tags: [chatgpt, moc]', '---', '',
           '# ChatGPT — карта всех разговоров', '',
           '> Официальный экспорт · **%d** чатов (%d архивных) · %d с Canvas · спрашивай через `/ask`' % (
               stats['conversations'], stats['archived'], stats['canvas']),
           '']
    for month in sorted(by_month, reverse=True):
        rows = by_month[month]
        moc.append('### %s (%d)' % (month, len(rows)))
        moc.append('')
        for updated, title, stub, mc, model, arch in rows:
            tag = ' · %d' % mc
            tag += (' · ' + model) if model else ''
            tag += ' · 🗄' if arch else ''
            moc.append('- [[%s|%s]] (%s%s)' % (stub, title.replace('|', '/')[:80], updated, tag))
        moc.append('')
    (base / '_ChatGPT-MOC.md').write_text('\n'.join(moc), encoding='utf-8')

    # ---- SQLite facts ----
    con = sqlite3.connect(str(base / 'chatgpt_conversations.db'))
    con.executescript('DROP TABLE IF EXISTS conversations;'
                      'CREATE TABLE conversations(cid TEXT PRIMARY KEY, created TEXT, updated TEXT,'
                      ' title TEXT, model TEXT, archived INT, msg_count INT, note TEXT);')
    con.executemany('INSERT OR REPLACE INTO conversations VALUES (?,?,?,?,?,?,?,?)', db_rows)
    con.commit(); con.close()

    print('=== CHATGPT -> VAULT (STAGING) ===')
    print('out base        :', str(base))
    for k in ('conversations', 'archived', 'canvas', 'skipped_empty'):
        print('%-16s: %d' % (k, stats[k]))
    print('MOC             : _ChatGPT-MOC.md')
    print('SQLite          : chatgpt_conversations.db')


if __name__ == '__main__':
    main()
