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
"""Step 3c: merge agent synthesis bodies into 06-Concepts notes.
- new note = enhanced frontmatter + synthesis body + '## Legacy' + old body (preserved).
- validate every [[link]] in synthesis; strip broken ones to plain text (keep 0 broken links).
- log per-concept broken-link counts for review."""
import os, re, json
from pathlib import Path

try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"

VAULT = Path(VAULT)
CONCEPTS = VAULT / '06-Concepts'
SYNTH_OUT = Path(os.path.join(IMPORTS, '_synth_out'))
PKG = Path(os.path.join(IMPORTS, '_synth'))

# all basenames for link validation
basenames = set()
for dp, dirs, fs in os.walk(VAULT):
    if '.obsidian' in dp: continue
    for f in fs:
        if f.endswith('.md'): basenames.add(Path(f).stem)

def fm_body(t):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else ('', t)

def strip_broken_links(text):
    """Replace [[stem|alias]] or [[stem]] with alias/stem if stem not in vault. Returns (text, n_broken)."""
    broken = [0]
    def repl(m):
        target = m.group(1).strip()
        alias = m.group(2)
        if target in basenames:
            return m.group(0)
        broken[0] += 1
        return (alias[1:] if alias else target)  # alias without leading |
    fixed = re.sub(r'\[\[([^\]\|#]+)(?:#[^\]\|]+)?(\|[^\]]+)?\]\]', repl, text)
    return fixed, broken[0]

def get_fm_field(fm, name):
    m = re.search(rf'^{name}:\s*(.+)$', fm, re.M)
    return m.group(1).strip() if m else None

log = []
merged = total_broken_stripped = 0
for outf in sorted(SYNTH_OUT.glob('concept-*.md')):
    slug = outf.stem
    target = CONCEPTS / f'{slug}.md'
    if not target.exists():
        log.append(f'SKIP {slug}: no vault concept file'); continue
    synth = outf.read_text(encoding='utf-8').strip()
    synth, nbroken = strip_broken_links(synth)
    total_broken_stripped += nbroken

    old = target.read_text(encoding='utf-8')
    ofm, obody = fm_body(old)
    obody = obody.strip()

    # idempotency guard: never double-merge (would nest Legacy sections)
    if 'synthesis_built:' in ofm or '## Legacy (исходная нота)' in obody:
        log.append(f'SKIP {slug}: already merged (synthesis_built present)'); continue

    # preserve title/aliases/tags from old frontmatter
    title = get_fm_field(ofm, 'title') or slug
    aliases = get_fm_field(ofm, 'aliases')
    tagline = ''
    tm = re.search(r'^tags:\s*(\[.*?\])\s*$', ofm, re.M)
    tags = tm.group(1) if tm else '[concept]'

    # sources count from package (prefer richer _synth_b total_notes for new concepts)
    src = 0
    pb = Path(os.path.join(IMPORTS, '_synth_b')) / f'{slug}.json'
    pf = PKG / f'{slug}.json'
    if pb.exists():
        src = json.loads(pb.read_text(encoding='utf-8')).get('total_notes', 0)
    elif pf.exists():
        src = json.loads(pf.read_text(encoding='utf-8')).get('anton_original_notes', 0)

    nf = ['---', f'title: {title}', 'type: concept', 'authored_by: hybrid', 'origin: anton',
          'synthesis_built: 2026-05-30', f'synthesis_sources: {src}']
    if aliases: nf.append(f'aliases: {aliases}')
    nf.append(f'tags: {tags}')
    nf.append('---')
    newnote = '\n'.join(nf) + '\n\n' + synth.strip() + \
              '\n\n---\n## Legacy (исходная нота)\n\n' + obody + '\n'

    target.write_text(newnote, encoding='utf-8')
    merged += 1
    if nbroken:
        log.append(f'{slug}: stripped {nbroken} broken link(s)')

summary = [f'merged={merged}', f'total_broken_links_stripped={total_broken_stripped}', '']
summary += log
Path(os.path.join(IMPORTS, '_synth_merge_log.txt')).write_text('\n'.join(summary), encoding='utf-8')
print(f'merged={merged}, broken_stripped={total_broken_stripped}')
