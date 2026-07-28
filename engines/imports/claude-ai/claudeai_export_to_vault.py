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
r"""claudeai_export_to_vault.py -- convert a claude.ai account export bundle
(produced by the browser dump: schema 'claude-ai-export/v1') into well-linked,
atomic Obsidian notes following Anton's vault conventions.

Lossless by design:
  * one note per CONVERSATION (active leaf-path dialogue, attachments inline)
  * every unique ARTIFACT becomes its OWN first-class note (deduped by identifier,
    longest version kept) -- artifacts extracted from ALL branches so none are lost
  * one note per PROJECT (description + prompt_template) + each knowledge doc as a note
  * a MOC index (by month + project) with counts
  * binary files (images/docs) are listed by manifest; actual download is a 2nd pass

Provenance (two-axis), per Anton's rules:
  * conversations  -> origin: mixed   (Anton asks, Claude answers)  authored_by: hybrid
  * artifacts      -> origin: claude-ai (authored by Claude, commissioned by Anton)
  * project instr. -> origin: anton   (his own custom instructions / style guides)
  * knowledge docs -> origin: external (uploaded reference material)

Deterministic scaffolding only. Cyrillic-safe: writes UTF-8, prints ASCII only
(Windows cp1252 stdout rule). Idempotent: stable filenames by conversation/artifact id,
re-runs overwrite in place, never deletes.

USAGE:
  python claudeai_export_to_vault.py --in raw\claude-ai-export-2026-06-11.json \
      [--out <staging base>]   (default: _imports\claude-ai\staging\01-Conversations\Claude-AI)
"""
import argparse, json, re, hashlib, datetime
from pathlib import Path

_CYR = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
_LAT = ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r',
        's','t','u','f','h','c','ch','sh','sch','','y','','e','yu','ya']
TRANSLIT = str.maketrans({c: l for c, l in zip(_CYR, _LAT)})

ART_RE = re.compile(r'<antArtifact\b([^>]*)>(.*?)</antArtifact>', re.DOTALL)
ATTR_RE = lambda name, s: (re.search(name + r'="([^"]*)"', s) or [None, ''])[1]
ROOT_SENTINEL = '00000000-0000-4000-8000-000000000000'

def slugify(text, fallback='note'):
    text = (text or '').lower().translate(TRANSLIT)
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    return (text[:60].strip('-') or fallback)

def yq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', "'").replace('\n', ' ') + '"'

def leaf_path(msgs, leaf_uuid):
    """Reconstruct the active conversation path from current_leaf back to root."""
    by_uuid = {m.get('uuid'): m for m in msgs}
    if leaf_uuid not in by_uuid:
        return sorted(msgs, key=lambda m: (m.get('index', 0), m.get('created_at', '')))
    path, seen, node = [], set(), by_uuid.get(leaf_uuid)
    while node and node.get('uuid') not in seen:
        seen.add(node.get('uuid'))
        path.append(node)
        p = node.get('parent_message_uuid')
        if not p or p == ROOT_SENTINEL or p not in by_uuid:
            break
        node = by_uuid.get(p)
    return list(reversed(path))

def msg_text(m):
    """Flatten a message to plain text (text + nothing else; thinking omitted from body)."""
    cont = m.get('content')
    if isinstance(cont, list):
        return '\n\n'.join((b.get('text') or '') for b in cont if b.get('type') == 'text').strip()
    return (m.get('text') or '').strip()

def collect_artifacts(msgs):
    """All artifacts across ALL branches, deduped by identifier (keep longest body)."""
    best = {}
    for m in msgs:
        cont = m.get('content')
        blocks = cont if isinstance(cont, list) else [{'type': 'text', 'text': m.get('text') or ''}]
        for b in blocks:
            if b.get('type') != 'text':
                continue
            for am in ART_RE.finditer(b.get('text') or ''):
                attrs, body = am.group(1), am.group(2)
                ident = ATTR_RE('identifier', attrs) or hashlib.md5(body.encode('utf-8')).hexdigest()[:12]
                title = ATTR_RE('title', attrs) or 'Untitled artifact'
                atype = ATTR_RE('type', attrs) or 'text/markdown'
                prev = best.get(ident)
                if prev is None or len(body) > len(prev['body']):
                    best[ident] = {'identifier': ident, 'title': title, 'type': atype, 'body': body}
    return best

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', dest='out',
                    default=r'%IMPORTS%\claude-ai\staging\01-Conversations\Claude-AI')
    a = ap.parse_args()
    today = datetime.date.today().isoformat()

    data = json.loads(Path(a.inp).read_text(encoding='utf-8'))
    convs = data.get('conversations', {})
    projects = data.get('projects', [])
    files_manifest = data.get('filesManifest', [])
    proj_name_by_uuid = {p.get('uuid'): p.get('name') for p in projects}

    base = Path(a.out)
    d_conv = base / 'conversations'; d_art = base / 'artifacts'; d_proj = base / 'projects'
    for d in (d_conv, d_art, d_proj):
        d.mkdir(parents=True, exist_ok=True)

    files_by_conv = {}
    for f in files_manifest:
        files_by_conv.setdefault(f.get('conv'), []).append(f)

    stats = {'conversations': 0, 'artifacts': 0, 'projects': 0, 'knowledge_docs': 0,
             'artifact_links': 0, 'attachments': 0, 'files_listed': 0}
    art_slug_by_ident = {}
    moc_rows = []  # (updated, name, conv_file, msgcount, artcount, project)

    # ---- pass 1: artifacts (so conversation notes can link them) ----
    conv_artifacts = {}  # conv_uuid -> list of artifact dicts (with slug)
    for cid, c in convs.items():
        msgs = c.get('chat_messages', []) or []
        arts = collect_artifacts(msgs)
        local = []
        for ident, art in arts.items():
            h = hashlib.md5(ident.encode('utf-8')).hexdigest()[:6]
            slug = 'claudeai-art-' + slugify(art['title'], 'artifact') + '-' + h
            art_slug_by_ident[ident] = slug
            art['slug'] = slug
            art['conv_uuid'] = cid
            art['conv_name'] = c.get('name') or 'Untitled'
            local.append(art)
        conv_artifacts[cid] = local

    # write artifact notes
    for cid, c in convs.items():
        for art in conv_artifacts[cid]:
            ext = 'html' if 'html' in art['type'] else 'md'
            fm = (
                '---\n'
                'title: %s\n' % yq(art['title']) +
                'type: claude-artifact\n'
                'source: claude-ai\n'
                'origin: claude-ai\n'
                'author: "Claude (Anthropic), commissioned by Anton"\n'
                'authored_by: claude\n'
                'artifact_type: %s\n' % art['type'] +
                'from_conversation: %s\n' % yq(art['conv_name']) +
                'conversation_uuid: %s\n' % cid +
                'date_added: %s\n' % today +
                'volatility: volatile\n'
                'interpretation_confidence: high\n'
                'language: ru\n'
                'tags: [claude-ai, claude-artifact]\n'
                'value_score: 0.0\n'
                'related_concepts: []\n'
                'revisit_if: ""\n'
                '---\n\n'
            )
            body = (
                '# %s\n\n' % art['title'] +
                '> Артефакт из claude.ai. Источник: [[%s]]. Сохранён дословно.\n\n' % conv_filename_stub(c) +
                art['body'].strip() + '\n'
            )
            (d_art / (art['slug'] + '.md')).write_text(fm + body, encoding='utf-8')
            stats['artifacts'] += 1

    # ---- pass 2: conversations ----
    for cid, c in convs.items():
        msgs = c.get('chat_messages', []) or []
        path = leaf_path(msgs, c.get('current_leaf_message_uuid'))
        name = c.get('name') or 'Untitled'
        updated = (c.get('updated_at') or c.get('created_at') or today)[:10]
        proj_uuid = c.get('project_uuid')
        proj = proj_name_by_uuid.get(proj_uuid, '')
        stub = conv_filename_stub(c)
        local_arts = conv_artifacts[cid]
        linked = set()

        lines = []
        n_attach = 0
        for m in path:
            sender = m.get('sender')
            who = 'Anton' if sender == 'human' else 'Claude'
            txt = msg_text(m)
            # replace artifact tags inline with links
            def repl(am):
                ident = ATTR_RE('identifier', am.group(1))
                slug = art_slug_by_ident.get(ident)
                if slug:
                    linked.add(ident)
                    return '\n\n> 📄 **Артефакт:** [[%s]]\n\n' % slug
                return ''
            txt = ART_RE.sub(repl, txt)
            # attachments (uploaded docs -> extracted text)
            att_block = ''
            for att in (m.get('attachments') or []):
                ec = att.get('extracted_content') or ''
                if ec.strip():
                    n_attach += 1
                    att_block += '\n\n> 📎 **Вложение:** %s\n\n```\n%s\n```\n' % (att.get('file_name', 'file'), ec.strip()[:20000])
            if txt or att_block:
                lines.append('**%s:**\n\n%s%s' % (who, txt, att_block))

        # artifacts that belong to this conv but were not on the active path
        extra = [a for a in local_arts if a['identifier'] not in linked]
        art_index = ''
        if local_arts:
            art_index = '\n## Артефакты этого чата (%d)\n\n' % len(local_arts)
            for a in local_arts:
                art_index += '- [[%s]]\n' % a['slug']
        extra_note = ''
        if extra:
            extra_note = '\n> ℹ️ %d артефакт(ов) — из других веток диалога (regenerations), линки выше.\n' % len(extra)

        cfiles = files_by_conv.get(cid, [])
        files_block = ''
        if cfiles:
            kinds = {}
            for f in cfiles:
                kinds[f.get('kind', '?')] = kinds.get(f.get('kind', '?'), 0) + 1
            files_block = '\n## Прикреплённые файлы (%d)\n\n> Бинарники (%s) — докачка отдельным проходом.\n\n' % (
                len(cfiles), ', '.join('%s:%d' % (k, v) for k, v in sorted(kinds.items())))
            for f in cfiles[:50]:
                files_block += '- %s `%s`\n' % (f.get('name', 'file'), f.get('kind', '?'))

        fm = (
            '---\n'
            'title: %s\n' % yq(name) +
            'type: ai-conversation\n'
            'source: claude-ai\n'
            'origin: mixed\n'
            'authored_by: hybrid\n'
            'conversation_uuid: %s\n' % cid +
            'model: %s\n' % yq(c.get('model') or '') +
            'project: %s\n' % yq(proj) +
            'url: "https://claude.ai/chat/%s"\n' % cid +
            'date_recorded: %s\n' % updated +
            'date_added: %s\n' % today +
            'valid_as_of: %s\n' % updated +
            'volatility: slow\n'
            'interpretation_confidence: high\n'
            'intent: ""\n'
            'language: ru\n'
            'tags: [claude-ai, ai-conversation%s]\n' % ((', ' + slugify(proj, '')) if proj else '') +
            'value_score: 0.0\n'
            'msg_count: %d\n' % len(path) +
            'artifact_count: %d\n' % len(local_arts) +
            'file_count: %d\n' % len(cfiles) +
            'related_concepts: []\n'
            'revisit_if: ""\n'
            '---\n\n'
        )
        header = '# %s\n\n' % name
        meta = '> claude.ai · %s%s · %d сообщений · %d артефактов\n\n' % (
            updated, (' · проект: ' + proj) if proj else '', len(path), len(local_arts))
        body = header + meta + art_index + extra_note + '\n## Диалог\n\n' + '\n\n---\n\n'.join(lines) + '\n' + files_block
        (d_conv / (stub + '.md')).write_text(fm + body, encoding='utf-8')
        stats['conversations'] += 1
        stats['artifact_links'] += len(linked)
        stats['attachments'] += n_attach
        stats['files_listed'] += len(cfiles)
        moc_rows.append((updated, name, stub, len(path), len(local_arts), proj))

    # ---- pass 3: projects + knowledge docs ----
    for p in projects:
        pname = p.get('name') or 'Untitled project'
        pslug = 'claudeai-project-' + slugify(pname, 'project')
        instr = (p.get('prompt_template') or '') or (p.get('description') or '')
        desc = p.get('description') or ''
        docs = p.get('docs') or []
        doc_links = []
        for d in docs:
            dname = d.get('name') or 'doc'
            dslug = pslug + '--' + slugify(dname, 'doc')
            dfm = (
                '---\n'
                'title: %s\n' % yq(dname) +
                'type: claude-project-knowledge\n'
                'source: claude-ai\n'
                'origin: external\n'
                'project: %s\n' % yq(pname) +
                'date_added: %s\n' % today +
                'tags: [claude-ai, project-knowledge]\n'
                '---\n\n# %s\n\n> База знаний проекта [[%s]] (claude.ai).\n\n%s\n' % (dname, pslug, (d.get('content') or ''))
            )
            (d_proj / (dslug + '.md')).write_text(dfm, encoding='utf-8')
            doc_links.append('- [[%s]]\n' % dslug)
            stats['knowledge_docs'] += 1
        pfm = (
            '---\n'
            'title: %s\n' % yq(pname) +
            'type: claude-project\n'
            'source: claude-ai\n'
            'origin: anton\n'
            'authored_by: anton\n'
            'project_uuid: %s\n' % p.get('uuid', '') +
            'date_added: %s\n' % today +
            'tags: [claude-ai, claude-project]\n'
            'instr_chars: %d\n' % len(instr) +
            'knowledge_docs: %d\n' % len(docs) +
            '---\n\n'
        )
        pbody = '# Проект: %s\n\n' % pname
        if desc and desc != instr:
            pbody += '## Описание\n\n%s\n\n' % desc
        pbody += '## Инструкции проекта (custom instructions)\n\n%s\n\n' % (instr or '_нет_')
        if doc_links:
            pbody += '## База знаний (%d)\n\n%s\n' % (len(docs), ''.join(doc_links))
        (d_proj / (pslug + '.md')).write_text(pfm + pbody, encoding='utf-8')
        stats['projects'] += 1

    # ---- MOC ----
    moc_rows.sort(reverse=True)
    by_month = {}
    for updated, name, stub, mc, ac, proj in moc_rows:
        by_month.setdefault(updated[:7], []).append((updated, name, stub, mc, ac, proj))
    moc = ['---', 'title: "Claude.ai — все разговоры (MOC)"', 'type: moc', 'source: claude-ai',
           'date_added: %s' % today, 'tags: [claude-ai, moc]', '---', '',
           '# Claude.ai — карта всех разговоров', '',
           '> Импорт аккаунта **%s** · %d чатов · %d артефактов · %d проектов · %d док. знаний' % (
               data.get('account', ''), stats['conversations'], stats['artifacts'],
               stats['projects'], stats['knowledge_docs']),
           '', '## Проекты', '']
    for p in projects:
        moc.append('- [[claudeai-project-%s]]' % slugify(p.get('name') or 'project', 'project'))
    moc += ['', '## Разговоры по месяцам', '']
    for month in sorted(by_month, reverse=True):
        rows = by_month[month]
        moc.append('### %s (%d)' % (month, len(rows)))
        moc.append('')
        for updated, name, stub, mc, ac, proj in rows:
            tag = (' · %d арт.' % ac) if ac else ''
            tag += (' · ' + proj) if proj else ''
            moc.append('- [[%s|%s]] (%s%s)' % (stub, name.replace('|', '/')[:80], updated, tag))
        moc.append('')
    (base / '_Claude-AI-MOC.md').write_text('\n'.join(moc), encoding='utf-8')

    # ---- report (ASCII only) ----
    print('=== CLAUDE.AI -> VAULT (STAGING) ===')
    print('out base        :', str(base))
    for k in ('conversations', 'artifacts', 'projects', 'knowledge_docs',
              'artifact_links', 'attachments', 'files_listed'):
        print('%-16s: %d' % (k, stats[k]))
    print('MOC             : _Claude-AI-MOC.md')


def conv_filename_stub(c):
    updated = (c.get('updated_at') or c.get('created_at') or '0000-00-00')[:10]
    uid8 = (c.get('uuid') or '')[:8]
    return '%s-%s-%s' % (updated, slugify(c.get('name') or 'chat', 'chat'), uid8)


if __name__ == '__main__':
    main()
