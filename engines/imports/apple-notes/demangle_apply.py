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
"""Apply demangle to vault notes whose styled text the Mac exporter exploded
into heading fragments. Touches ONLY exploded runs (clean text stays identical).
- reuse an LLM repair from repaired/ if it passes strict char+wikilink check
- else deterministic run-collapse: join fragment runs, blank '#' => paragraph break,
  leading run replaced with clean `title` field.
Patches vault files in place, adds `headings_demangled:` flag. Idempotent-ish (guarded by flag).
"""
import json, re
from pathlib import Path

OUT = Path(r"%IMPORTS%\apple-notes")
EXPORT = Path(r"E:\Google Drive on HP Palo Alto\!_Claude_Mac16\Apple Notes Export 2026-06-11")
VN = Path(r"%VAULT%\01-Conversations\Apple-Notes\notes")
MDIR = OUT / "mangled"
RDIR = OUT / "repaired"

data = json.loads((EXPORT / "notes_export.json").read_text(encoding="utf-8"))
idx_list = json.loads((OUT / "mangled_list.json").read_text(encoding="utf-8"))
recs = {r["idx"]: r for r in json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["notes"]}

HEAD = re.compile(r'^#{1,6}[ ]?(.*?)\s*$')
WIKI = re.compile(r'!?\[\[[^\]]+\]\]')
def canon(s): return re.sub(r'[\s#]+', '', s)

def is_fragment(c):
    return len(c) <= 4 or (c and c[0].islower()) or (c and c[0] in '!()')

def deterministic(md, title):
    lines = md.splitlines()
    # classify each line
    kinds = []  # ('head', content) | ('blank',) | ('plain', line)
    for ln in lines:
        if ln.strip() == '':
            kinds.append(('blank',))
        else:
            m = HEAD.match(ln)
            if m is not None:
                kinds.append(('head', m.group(1)))
            else:
                kinds.append(('plain', ln))
    # find maximal runs of head/blank lines that look exploded
    out = []
    i, n = 0, len(kinds)
    while i < n:
        if kinds[i][0] in ('head', 'blank'):
            j = i
            heads = []
            while j < n and kinds[j][0] in ('head', 'blank'):
                if kinds[j][0] == 'head':
                    heads.append(kinds[j][1])
                j += 1
            frag_ct = sum(1 for h in heads if h.strip() and is_fragment(h))
            if len(heads) >= 3 and frag_ct >= 2:
                # collapse this run: join fragments, empty head => para break
                paras, cur = [], []
                for h in heads:
                    if h.strip() == '':
                        if cur: paras.append(''.join(cur)); cur = []
                    else:
                        cur.append(h)
                if cur: paras.append(''.join(cur))
                out.append(('RUN', paras))
            else:
                # not exploded -> keep verbatim
                for k in range(i, j):
                    out.append(('VERB', lines[k]))
            i = j
        else:
            out.append(('VERB', kinds[i][1]))
            i += 1
    # render; first RUN's first paragraph becomes a heading.
    # Use clean `title` ONLY when it is not truncated AND char-matches (restores lost spaces safely);
    # otherwise keep the collapsed fragments verbatim (all chars preserved) and just prefix '# '.
    rendered, used_title = [], False
    clean_title = title.rstrip('…').strip()
    title_trunc = title.rstrip().endswith('…')
    for tag, val in out:
        if tag == 'VERB':
            rendered.append(val)
        else:
            paras = val[:]
            if not used_title and paras:
                p0 = paras[0]
                if (not title_trunc) and re.sub(r'[\s#]+', '', clean_title) == re.sub(r'[\s#]+', '', p0):
                    paras[0] = '# ' + clean_title
                else:
                    paras[0] = '# ' + p0
                used_title = True
            rendered.append('\n\n'.join(paras))
    text = '\n'.join(rendered)
    text = re.sub(r'\n{3,}', '\n\n', text).strip('\n')
    return text

accepted_llm, det, failed = [], [], []
for i in idx_list:
    src = json.loads((MDIR / f"note_{i}.json").read_text(encoding="utf-8"))
    old_md = src["markdown"]; slug = src["slug"]; title = src["title"]
    rep = None
    rf = RDIR / f"note_{i}.md"
    if rf.exists():
        cand = rf.read_text(encoding="utf-8").strip("\n")
        if canon(cand) == canon(old_md) and sorted(WIKI.findall(cand)) == sorted(WIKI.findall(old_md)):
            rep = cand; accepted_llm.append(i)
    if rep is None:
        cand = deterministic(old_md, title)
        # safety: char-content must match (whitespace/# ignored)
        if canon(cand) == canon(old_md) and sorted(WIKI.findall(cand)) == sorted(WIKI.findall(old_md)):
            rep = cand; det.append(i)
        else:
            failed.append((i, "det-char-mismatch")); continue
    vf = VN / f"{slug}.md"
    text = vf.read_text(encoding="utf-8")
    if "headings_demangled:" in text:
        continue  # already patched
    if old_md not in text:
        failed.append((i, "body-not-found")); continue
    method = "llm-fable" if i in accepted_llm else "deterministic"
    text = text.replace(old_md, rep, 1)
    text = text.replace("\ntags: [", f"\nheadings_demangled: {method}\ntags: [", 1)
    vf.write_text(text, encoding="utf-8")

(OUT / "demangle_report.json").write_text(json.dumps(
    {"llm": accepted_llm, "deterministic": det, "failed": failed,
     "total": len(idx_list), "patched": len(accepted_llm) + len(det) - len(failed)},
    ensure_ascii=False), encoding="utf-8")
print("LLM:", len(accepted_llm), " DET:", len(det), " FAILED:", len(failed), " TOTAL:", len(idx_list))
for f in failed: print("FAIL:", f)
print("OK" if not failed else "HAS_FAILURES")
