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
"""Apply merged concept map (strong deterministic + LLM) to Pokupki post notes:
   write concept wikilink + domain tag. ASCII stdout."""
import re, json
from collections import Counter
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
OUT = Path(r"E:/Obsidian/_imports")
POSTS = VAULT / "01-Conversations/Telegram/Pokupki/posts"

strong = json.loads((OUT / "pokupki_strong.json").read_text(encoding="utf-8"))
llm = json.loads((OUT / "pokupki_llm_concepts.json").read_text(encoding="utf-8"))
FALLBACK = "concept-procurement-vendors"
TAG_OF = {
 "concept-construction-renovation":"construction","concept-home-goods":"home-goods",
 "concept-garden-landscaping":"garden","concept-cars":"cars","concept-parenting":"kids",
 "concept-tech-tools":"electronics","concept-travel-logistics":"travel",
 "concept-groceries-food":"groceries","concept-personal-finance":"finance",
 "concept-procurement-vendors":"procurement","concept-place-livability":"portugal"}

dist = Counter(); applied = 0; src = Counter()
backlinks = {}   # concept -> [stems]
for p in POSTS.glob("*.md"):
    stem = p.stem
    if stem in strong:
        concept = strong[stem]["concept"]; src["strong"] += 1
    elif stem in llm:
        concept = llm[stem]; src["llm"] += 1
    else:
        concept = FALLBACK; src["fallback"] += 1
    dist[concept] += 1
    backlinks.setdefault(concept, []).append(stem)
    txt = p.read_text(encoding="utf-8")
    new = re.sub(r"(?m)^concept:\s*$", f'concept: "[[{concept}]]"', txt, count=1)
    tag = TAG_OF[concept]
    def add_tag(m):
        inner = m.group(1)
        return f"tags: [{inner}, {tag}]" if tag not in inner else m.group(0)
    new = re.sub(r"tags: \[([^\]]*)\]", add_tag, new, count=1)
    if new != txt:
        p.write_text(new, encoding="utf-8"); applied += 1

(OUT / "pokupki_backlinks.json").write_text(json.dumps(backlinks, ensure_ascii=False), encoding="utf-8")
print("applied", applied, "| sources", dict(src))
for c, n in dist.most_common():
    print(f"  {n:5d}  {c}")
