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
"""Strip unresolved wikilinks from 02-Decisions, 03-Insights, 05-Resources bodies.
Checks each [[link]] against file index; if unresolved → plain text.
Already-bridged terms (09-Bridges) count as resolved.
Additive: never touches frontmatter."""
import re, os, glob
from pathlib import Path

V = Path("E:/Obsidian/Owner-Knowledge")

# Build full file index (all basenames → path)
idx = set()
for f in glob.glob(str(V / "**/*.md"), recursive=True):
    idx.add(os.path.splitext(os.path.basename(f))[0])

FOLDERS = ["02-Decisions", "03-Insights", "05-Resources"]

stripped = 0; files_changed = 0; log = []

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")

def resolve(name):
    name = name.strip()
    if name in idx: return True
    # try lowercase / hyphenated
    slug = re.sub(r"[^\wЀ-ӿ]", "-", name.lower()).strip("-")
    if slug in idx: return True
    if "concept-" + slug in idx: return True
    return False

for folder in FOLDERS:
    for fpath in (V / folder).rglob("*.md"):
        if fpath.name == "_index.md": continue
        try:
            t = open(fpath, encoding="utf-8", errors="ignore").read()
        except: continue
        m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
        if not m: continue
        h, fm, e, body = m.groups()

        # find all links, check which are unresolved
        all_links = LINK_RE.findall(body)
        unresolved = [(t, d) for t, d in all_links if not resolve(t)]
        count = len(unresolved)

        if count == 0:
            continue

        def make_replacer():
            def replace_link(match):
                target = match.group(1).strip()
                display = match.group(2)
                if resolve(target):
                    return match.group(0)
                return display if display else target
            return replace_link

        new_body = LINK_RE.sub(make_replacer(), body)

        if count > 0:
            open(fpath, "w", encoding="utf-8").write(h + fm + e + new_body)
            files_changed += 1
            stripped += count
            if count > 3:
                log.append(f"{fpath.name}: stripped {count} links")

log.insert(0, f"files_changed={files_changed} total_stripped={stripped}")
open("E:/Obsidian/_imports/_ghost_strip_new_log.txt", "w", encoding="utf-8").write("\n".join(log))
