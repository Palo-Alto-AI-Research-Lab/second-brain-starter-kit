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
r"""apply_curation.py -- apply the artifact->concept curation proposals (from the
claudeai-artifact-curation Workflow result JSON) into the artifact notes, deterministically.

Safety:
  * validates every proposed concept slug against the REAL concept inventory (06-Concepts +
    09-Bridges) -- hallucinated slugs are DROPPED and logged (never invented).
  * idempotent: the inserted link block is delimited by markers and replaced on re-run.
  * never creates new concept notes -- suggested new_concepts are collected into a report
    for Anton to review.
  * Cyrillic-safe: UTF-8 read/write, ASCII-only stdout.

USAGE:
  python apply_curation.py --result <workflow .output JSON> [--dry]
"""
import argparse, json, re, sys
from pathlib import Path
from collections import Counter

VAULT = Path(r'%VAULT%')
CONCEPT_DIRS = [VAULT / '06-Concepts', VAULT / '09-Bridges']
MARK_START, MARK_END = '<!-- curation:start -->', '<!-- curation:end -->'

def real_concepts():
    s = set()
    for d in CONCEPT_DIRS:
        if d.exists():
            for f in d.glob('concept-*.md'):
                s.add(f.stem)
    return s

def find_proposals(obj):
    """Recursively locate the first list of dicts that look like curation proposals."""
    if isinstance(obj, dict):
        if 'proposals' in obj and isinstance(obj['proposals'], list):
            return obj['proposals']
        for v in obj.values():
            r = find_proposals(v)
            if r is not None:
                return r
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and 'related_concepts' in obj[0] and 'file' in obj[0]:
            return obj
        for v in obj:
            r = find_proposals(v)
            if r is not None:
                return r
    return None

def yq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', "'").replace('\n', ' ').strip() + '"'

def split_fm(text):
    if not text.startswith('---'):
        return None, text
    end = text.find('\n---', 3)
    if end == -1:
        return None, text
    fm = text[3:end].lstrip('\n')
    body = text[end + 4:]
    return fm.split('\n'), body

def set_fm_key(lines, key, value_line):
    for i, ln in enumerate(lines):
        if ln.startswith(key + ':'):
            lines[i] = value_line
            return lines
    lines.append(value_line)
    return lines

def merge_tags(lines, new_tags):
    for i, ln in enumerate(lines):
        if ln.startswith('tags:'):
            m = re.search(r'\[(.*)\]', ln)
            cur = [t.strip() for t in (m.group(1).split(',') if m else []) if t.strip()]
            for t in new_tags:
                t = re.sub(r'[^\w-]+', '-', t.strip().lower()).strip('-')
                if t and t not in cur:
                    cur.append(t)
            lines[i] = 'tags: [%s]' % ', '.join(cur)
            return lines
    return lines

def apply_one(path, prop, valid, stats):
    p = Path(path)
    if not p.exists():
        stats['missing'] += 1
        return
    cand = list(prop.get('related_concepts', []) or []) + list(prop.get('new_concepts', []) or [])
    seen = set()
    cand = [x for x in cand if not (x in seen or seen.add(x))]
    slugs = [s for s in cand if s in valid]
    dropped = [s for s in cand if s not in valid]
    stats['dropped'].update(dropped)
    if not slugs:
        stats['no_valid'] += 1
        return
    text = p.read_text(encoding='utf-8')
    lines, body = split_fm(text)
    if lines is None:
        stats['no_fm'] += 1
        return
    # frontmatter updates
    lines = set_fm_key(lines, 'related_concepts', 'related_concepts: [%s]' % ', '.join(slugs))
    if 'value_score' in prop:
        lines = set_fm_key(lines, 'value_score', 'value_score: %.2f' % float(prop['value_score']))
    summ = (prop.get('summary') or '').strip()
    if summ:
        # insert/replace a summary key right after title
        has = any(ln.startswith('summary:') for ln in lines)
        if has:
            lines = set_fm_key(lines, 'summary', 'summary: %s' % yq(summ))
        else:
            ti = next((i for i, ln in enumerate(lines) if ln.startswith('title:')), 0)
            lines.insert(ti + 1, 'summary: %s' % yq(summ))
    lines = merge_tags(lines, prop.get('tags', []))
    # body: idempotent curation block
    block = (MARK_START + '\n## 🔗 Связанные концепты\n\n' +
             ' · '.join('[[%s]]' % s for s in slugs) + '\n' +
             (('\n> %s\n' % summ) if summ else '') + MARK_END)
    if MARK_START in body and MARK_END in body:
        body = re.sub(re.escape(MARK_START) + r'.*?' + re.escape(MARK_END), block, body, flags=re.DOTALL)
    else:
        marker = '> Артефакт из claude.ai'
        idx = body.find(marker)
        if idx != -1:
            eol = body.find('\n', idx)
            ins = eol + 1
            # skip the trailing blank line after the blockquote
            body = body[:ins] + '\n' + block + '\n' + body[ins:]
        else:
            body = block + '\n\n' + body
    out = '---\n' + '\n'.join(lines) + '\n---\n' + body
    if not stats['dry']:
        p.write_text(out, encoding='utf-8')
    stats['updated'] += 1
    stats['links'] += len(slugs)
    for s in slugs:
        stats['concept_use'][s] += 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result', required=True)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    data = json.loads(Path(a.result).read_text(encoding='utf-8'))
    proposals = find_proposals(data) or []
    valid = real_concepts()
    stats = {'updated': 0, 'links': 0, 'missing': 0, 'no_valid': 0, 'no_fm': 0,
             'dropped': Counter(), 'concept_use': Counter(), 'new': Counter(), 'dry': a.dry}
    for prop in proposals:
        for nc in prop.get('new_concepts', []) or []:
            if nc not in valid:
                stats['new'][nc] += 1
        apply_one(prop['file'], prop, valid, stats)

    print('=== APPLY CURATION%s ===' % (' (DRY)' if a.dry else ''))
    print('proposals_in   :', len(proposals))
    print('notes_updated  :', stats['updated'])
    print('links_written  :', stats['links'])
    print('notes_missing  :', stats['missing'])
    print('no_valid_slug  :', stats['no_valid'])
    print('dropped_slugs  :', sum(stats['dropped'].values()), dict(stats['dropped'].most_common(8)))
    print('--- top concepts used ---')
    for s, n in stats['concept_use'].most_common(15):
        print('  %3d  %s' % (n, s))
    print('--- suggested NEW concepts (for Anton review; NOT created) ---')
    for s, n in stats['new'].most_common(25):
        print('  %3d  %s' % (n, s))
    # write the new-concept suggestions report
    if not a.dry:
        rep = Path(r'%IMPORTS%\claude-ai\new_concept_suggestions.md')
        lines = ['# Предложенные новые концепты (из связки артефактов)', '',
                 '> Кандидаты от агентов. НЕ созданы — на твоё решение.', '']
        for s, n in stats['new'].most_common():
            lines.append('- **%s** — предложен %d раз' % (s, n))
        rep.write_text('\n'.join(lines), encoding='utf-8')
        print('new-concept report ->', str(rep))

if __name__ == '__main__':
    main()
