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
"""Integrate 02-Decisions, 03-Insights, 05-Resources into the knowledge graph.
Adds: origin: anton, concept: "[[primary]]", ## Смежные концепты secondaries.
Domain-based primary; tries to match concepts: list to existing files for secondaries.
Never deletes existing fields."""
import re, os, glob
from pathlib import Path

V = Path("E:/Obsidian/Owner-Knowledge")
CONC = V / "06-Concepts"

concept_files = {f.stem for f in CONC.glob("*.md")}
# file index (basename → path) for all vault files
idx = {}
for f in glob.glob(str(V / "**/*.md"), recursive=True):
    idx.setdefault(os.path.splitext(os.path.basename(f))[0], f)

# Domain → primary concept
DOMAIN_CONCEPT = {
    "Portugal": "concept-place-livability",
    "Construction": "concept-construction-renovation",
    "Cars": "concept-cars",
    "Business-Finance": "concept-personal-finance",
    "Family-Kids": "concept-parenting",
    "Home-Life": "concept-life-observations",
    "Biohacking": "concept-biohacking-nutrition",
    "Medicine": "concept-medicine-health",
    "AI-Tech": "concept-ai-agents",
    "Translation": "concept-language-learning",
    "Crypto-Web3": "concept-blockchain",
    "Personal-Growth": "concept-life-observations",
    "General-Tech": "concept-tech-tools",
    "Games-Entertainment": "concept-tap-to-earn-games",
    "crypto-security": "concept-hardware-wallet-supply-chain-attack",
    "pkm": "concept-tech-tools",
    "payment-processing": "concept-personal-finance",
}

# Build normalized lookup: normalized_slug → actual concept stem
def norm(s):
    s = s.strip().lower()
    s = re.sub(r"[^\wЀ-ӿ\-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

lookup = {}  # norm → stem
for stem in concept_files:
    lookup[norm(stem)] = stem
    # also index without "concept-" prefix
    if stem.startswith("concept-"):
        lookup[norm(stem[8:])] = stem

def canon_term(t):
    """Try to match a free-text concepts: entry to an existing concept file."""
    t = t.strip().strip("'\"")
    n = norm(t)
    if n in lookup: return lookup[n]
    # try with concept- prefix
    cn = "concept-" + n
    if cn in concept_files: return cn
    # cyrillic exact
    if t in concept_files: return t
    return None

SME = "## Смежные концепты"

FOLDERS = ["02-Decisions", "03-Insights", "05-Resources"]

applied = 0
skipped = 0
log = []

def ensure_concept(slug):
    if slug in concept_files: return
    path = CONC / f"{slug}.md"
    title = slug.replace("concept-", "").replace("-", " ")
    path.write_text("\n".join([
        "---", f'title: "{title}"', "type: concept", "status: stub",
        "authored_by: hybrid", "origin: anton", "created_by: obsidian-ingest",
        "tags: [concept]", "---", "", f"# {title}", "",
        "## Определение", "_Стаб. Доработать._", "", "## See Also", "- [[00-HOME]]", ""
    ]), encoding="utf-8")
    concept_files.add(slug)

for folder in FOLDERS:
    folder_path = V / folder
    files = [f for f in folder_path.rglob("*.md") if f.name != "_index.md"]
    for fpath in files:
        try:
            t = open(fpath, encoding="utf-8", errors="ignore").read()
        except:
            skipped += 1; continue
        m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
        if not m:
            skipped += 1; continue
        h, fm, e, body = m.groups()

        # Skip if already fully integrated
        has_origin = bool(re.search(r"^origin:", fm, re.M))
        has_concept = bool(re.search(r"^concept:\s", fm, re.M))
        if has_origin and has_concept:
            skipped += 1; continue

        changed = False

        # 1. Add origin: anton
        if not has_origin:
            fm = fm.rstrip() + "\norigin: anton"
            changed = True

        # 2. Determine primary concept from domain
        domain_m = re.search(r"^domain:\s*(.+)$", fm, re.M)
        domain = domain_m.group(1).strip() if domain_m else None
        prim = DOMAIN_CONCEPT.get(domain) if domain else None

        # 3. Parse concepts: list for secondaries
        concepts_m = re.search(r"^concepts:(.*?)(?=\n[a-zA-ZЀ-ӿ_]|\Z)", fm, re.DOTALL | re.M)
        raw_terms = []
        if concepts_m:
            raw_terms = re.findall(r"-\s*(.+)", concepts_m.group(1))

        secondaries = []
        for t_raw in raw_terms:
            c = canon_term(t_raw)
            if c and c != prim:
                secondaries.append(c)
        # deduplicate keeping order
        seen = set()
        sec_dedup = []
        for s in secondaries:
            if s not in seen:
                seen.add(s); sec_dedup.append(s)
        secondaries = sec_dedup[:5]  # cap at 5 to avoid noise

        # 4. Set primary concept: field
        if prim and not has_concept:
            ensure_concept(prim)
            fm = fm.rstrip() + f'\nconcept: "[[{prim}]]"'
            changed = True

        # 5. Merge secondaries into ## Смежные концепты
        if secondaries:
            for s in secondaries:
                ensure_concept(s)
            if SME in body:
                seg = body.split(SME, 1)[1]
                have = set(re.findall(r"\[\[([^\]|#]+)\]\]", seg.split("\n##")[0]))
                add = [s for s in secondaries if s not in have]
                if add:
                    lines = body.split(SME, 1)
                    rest = lines[1]
                    body = lines[0] + SME + rest.split("\n", 1)[0] + "\n" + \
                           "\n".join(f"- [[{s}]]" for s in add) + \
                           ("\n" + rest.split("\n", 1)[1] if "\n" in rest else "\n")
                    changed = True
            else:
                body = body.rstrip() + "\n\n" + SME + "\n" + \
                       "\n".join(f"- [[{s}]]" for s in secondaries) + "\n"
                changed = True

        if changed:
            open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
            applied += 1
            log.append(f"OK {fpath.name} | domain={domain} | prim={prim}")
        else:
            skipped += 1

log.append(f"\nTOTAL applied={applied} skipped={skipped}")
open("E:/Obsidian/_imports/_integrate_distilled_log.txt", "w", encoding="utf-8").write("\n".join(log))
