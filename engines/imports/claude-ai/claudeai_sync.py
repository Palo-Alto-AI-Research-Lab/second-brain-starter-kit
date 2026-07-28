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
r"""claudeai_sync.py -- idempotent one-command sync of a claude.ai export into the live vault.

Pipeline (deterministic; safe to re-run):
  1. resolve newest export bundle in raw\  (or --in)
  2. convert it to a CLEAN temp staging (claudeai_export_to_vault.py)
  3. copy ONLY NEW per-note files into the live vault -- existing notes are LEFT UNTOUCHED
     so prior concept-curation (the <!-- curation --> blocks + related_concepts) is preserved
  4. always refresh the wholesale artifacts: _Claude-AI-MOC.md + the dashboard
  5. emit the list of NEW artifact paths (-> _new_artifacts.txt) for the curation step
  6. optional: --reindex (brain_embed_update) and --commit (vault_backup)

So: new chats/artifacts get added; nothing already curated is overwritten. Cyrillic-safe,
ASCII stdout. The PULL (browser export) and the rich LLM concept-curation of the NEW
artifacts are driven by the `claudeai-sync` skill around this runner.

USAGE:
  python claudeai_sync.py [--in raw\claude-ai-export-YYYY-MM-DD.json] [--reindex] [--commit]
"""
import argparse, subprocess, sys, shutil
from pathlib import Path

HERE = Path(r'%IMPORTS%\claude-ai')
RAW = HERE / 'raw'
TMP = HERE / '_sync_tmp'
LIVE = Path(r'%VAULT%\01-Conversations\Claude-AI')
PY = sys.executable
SUBDIRS = ('conversations', 'artifacts', 'projects')

def newest_export(explicit):
    if explicit:
        return Path(explicit)
    cands = sorted(RAW.glob('claude-ai-export-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        sys.exit('ERROR: no export bundle in %s -- run the browser pull first' % RAW)
    return cands[0]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if r.returncode != 0:
        print('  ! step failed:', ' '.join(str(c) for c in cmd))
        print(r.stdout[-800:]); print(r.stderr[-800:])
        sys.exit(r.returncode)
    return r.stdout

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default=None)
    ap.add_argument('--reindex', action='store_true')
    ap.add_argument('--commit', action='store_true')
    a = ap.parse_args()

    bundle = newest_export(a.inp)
    print('SYNC source :', bundle.name)

    # 1. convert to clean temp staging
    if TMP.exists():
        shutil.rmtree(TMP)
    tmp_out = TMP / '01-Conversations' / 'Claude-AI'
    run([PY, str(HERE / 'claudeai_export_to_vault.py'), '--in', str(bundle), '--out', str(tmp_out)])

    # 2. copy ONLY NEW per-note files into live (preserve curated/existing)
    LIVE.mkdir(parents=True, exist_ok=True)
    new = {k: [] for k in SUBDIRS}
    for sub in SUBDIRS:
        src_dir = tmp_out / sub
        dst_dir = LIVE / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            continue
        for f in src_dir.glob('*.md'):
            dst = dst_dir / f.name
            if dst.exists():
                continue  # preserve existing (may be curated)
            shutil.copy2(f, dst)
            new[sub].append(dst)

    # 3. wholesale refresh: MOC (full regen reflects everything)
    moc = tmp_out / '_Claude-AI-MOC.md'
    if moc.exists():
        shutil.copy2(moc, LIVE / '_Claude-AI-MOC.md')

    # 4. emit new-artifact list for the curation step
    (HERE / '_new_artifacts.txt').write_text(
        '\n'.join(str(p) for p in new['artifacts']), encoding='utf-8')

    # 5. refresh dashboard (wholesale)
    run([PY, str(HERE / 'build_claudeai_dashboard.py'), '--in', str(bundle)])

    # 6. optional reindex + commit
    if a.reindex:
        r = subprocess.run([PY, str(Path(r'%IMPORTS%') / 'brain_embed_update.py')],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        print('reindex rc =', r.returncode, '(3/lock = another instance; nightly @04:00 will catch up)')
    if a.commit:
        subprocess.run([PY, str(Path(r'%IMPORTS%') / 'vault_backup.py')],
                       capture_output=True, text=True, encoding='utf-8', errors='ignore')

    nc, na, npj = len(new['conversations']), len(new['artifacts']), len(new['projects'])
    print('=== SYNC DONE ===')
    print('new_conversations :', nc)
    print('new_artifacts     :', na, '(paths -> _new_artifacts.txt; curate them next)')
    print('new_projects      :', npj)
    print('dashboard         : refreshed')
    if na == 0 and nc == 0:
        print('NOTE: nothing new since last sync.')

if __name__ == '__main__':
    main()
