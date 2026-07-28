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
"""Second-pass integration for remaining transcript-episode subfolders.
Comprehensive heuristic mapping: subfolder name → concept + origin.
Unrecognized → concept-life-observations (safe default)."""
import re, os
from pathlib import Path

V = Path("E:/Obsidian/Owner-Knowledge")
CONC = V / "06-Concepts"
concept_files = {f.stem for f in CONC.glob("*.md")}

# Explicit name → (concept, origin, authored_by)
EXPLICIT = {
    # Alternative history / ancient mysteries
    "The Randall Carlson 4675": ("concept-alternative-history", "external", "ai"),
    "Lucius Aurelian": ("concept-alternative-history", "external", "ai"),
    "BrienFoerster": ("concept-alternative-history", "external", "ai"),
    "JonLevi": ("concept-alternative-history", "external", "ai"),
    "HiddenRabbit": ("concept-alternative-history", "external", "ai"),
    "MauroBiglino": ("concept-alternative-history", "external", "ai"),
    "Vladimir Masterov100": ("concept-alternative-history", "external", "ai"),
    "vladimir Masterov": ("concept-alternative-history", "external", "ai"),
    "История Пи_1": ("concept-alternative-history", "external", "ai"),
    "Просветъ_1": ("concept-religion-as-control", "external", "ai"),
    "No horizon": ("concept-simulation-hypothesis", "external", "ai"),
    "One Spark": ("concept-simulation-hypothesis", "external", "ai"),
    "Satori": ("concept-simulation-hypothesis", "external", "ai"),
    "Говорит Атеист_1": ("concept-religion-as-control", "external", "ai"),
    "роман кауфман ч2_1": ("concept-alternative-history", "external", "ai"),
    "Sergey Ignatenko1": ("concept-alternative-history", "external", "ai"),

    # Consciousness / philosophy
    "thirdEyeDrops": ("concept-simulation-hypothesis", "external", "ai"),
    "Mind Unveiledcyrillic1": ("concept-simulation-hypothesis", "external", "ai"),
    "Mind Unveiledcyrillic2": ("concept-simulation-hypothesis", "external", "ai"),
    "Mind Unveiledcyrillic3": ("concept-simulation-hypothesis", "external", "ai"),
    "Mind Unveiledcyrillic4": ("concept-simulation-hypothesis", "external", "ai"),

    # Biohacking / health
    "beloveshkin 1": ("concept-biomarkers", "external", "ai"),
    "beloveshkin 2": ("concept-biomarkers", "external", "ai"),
    "beloveshkin 3": ("concept-biomarkers", "external", "ai"),
    "Molecule": ("concept-molecule", "external", "ai"),
    "Jarid Boosters MD": ("concept-biohacking-nutrition", "external", "ai"),
    "fuckbiohacking": ("concept-biohacking-nutrition", "external", "ai"),
    "Kasparov Vadim Telegram fuck biohacking": ("concept-biohacking-nutrition", "external", "ai"),
    "Paul Cook": ("concept-biohacking-nutrition", "external", "ai"),
    "my lunch Break 1 (1)": ("concept-biohacking-nutrition", "external", "ai"),
    "interviews with Michael Levin": ("concept-aging", "external", "ai"),

    # Crypto
    "Crypto": ("concept-blockchain", "external", "ai"),
    "Terra1": ("concept-blockchain", "external", "ai"),
    "pump.science": ("concept-desci", "external", "ai"),
    "Cryptoinside": ("concept-blockchain", "external", "ai"),

    # AI / Tech
    "deeplearningAI": ("concept-ai-agents", "external", "ai"),

    # LobsterDAO group (ID 1002159389293)
    "chat_-1003779381054_part_001": ("concept-dao", "external", "ai"),
    "chat_-1003779381054_part_002": ("concept-dao", "external", "ai"),
    "chat_-1003779381054_part_003": ("concept-dao", "external", "ai"),
    "lobster_tg_messages_last_5_days": ("concept-dao", "external", "ai"),

    # Joe Rogan
    "The Joe Rogan Experience1": ("concept-life-observations", "external", "ai"),
    "The Joe Rogan Experience2": ("concept-life-observations", "external", "ai"),

    # Dialogues (Anton's own conversations)
    "dialogues_work_acct_b_12_months_part001": ("concept-life-observations", "mixed", "hybrid"),
    "dialogues_work_acct_b_12_months_part002": ("concept-life-observations", "mixed", "hybrid"),
    "dialogues_work_acct_b_12_months_part003": ("concept-life-observations", "mixed", "hybrid"),
    "dialogues_work_acct_b_12_months_part004": ("concept-life-observations", "mixed", "hybrid"),

    # posts tg — Telegram posts
    "posts tg": ("concept-life-observations", "mixed", "hybrid"),

    # Other
    "Other": ("concept-life-observations", "external", "ai"),
}

# Lobster subfolders (lobster1 through lobster15)
for i in range(1, 16):
    EXPLICIT[f"lobster{i}"] = ("concept-dao", "external", "ai")

# Dialogues export parts (Anton's conversations with Tony/others)
for i in range(1, 25):
    EXPLICIT[f"dialogues_export_part_{i:03d}"] = ("concept-life-observations", "mixed", "hybrid")
    EXPLICIT[f"dialogues_export_part_{i:03d} (2)"] = ("concept-life-observations", "mixed", "hybrid")
    EXPLICIT[f"dialogues_export_part_{i:03d} (3)"] = ("concept-life-observations", "mixed", "hybrid")

# Cyrillic-named subfolders → crypto (based on sample showing 700k lost = crypto context)
# These likely have Cyrillic names mangled by the importer
for name in ["cyrillic cyrillic 25 cyrillic", "cyrillic cyrillic cyrillic2",
             "cyrillic cyrillic cyrillic3", "cyrillic cyrillic cyrillic",
             "cyrillic (3)"]:
    EXPLICIT[name] = ("concept-investment-risk", "external", "ai")

DEFAULT = ("concept-life-observations", "external", "ai")
SME = "## Смежные концепты"

def get_mapping(subfolder_name):
    if subfolder_name in EXPLICIT:
        return EXPLICIT[subfolder_name]
    # Heuristic fallback
    n = subfolder_name.lower()
    if any(k in n for k in ["randall", "levi", "foerster", "lucius", "aurelian", "megali", "biglino", "masterov"]):
        return ("concept-alternative-history", "external", "ai")
    if any(k in n for k in ["lobster", "dao"]):
        return ("concept-dao", "external", "ai")
    if any(k in n for k in ["biohack", "beloveshkin", "health", "huberman", "levin"]):
        return ("concept-biohacking-nutrition", "external", "ai")
    if any(k in n for k in ["crypto", "token", "blockchain", "defi"]):
        return ("concept-blockchain", "external", "ai")
    if any(k in n for k in ["mind", "satori", "horizon", "spiritual", "consciousness"]):
        return ("concept-simulation-hypothesis", "external", "ai")
    if "dialogues" in n or "work_acct_b" in n:
        return ("concept-life-observations", "mixed", "hybrid")
    return DEFAULT

conv_path = V / "01-Conversations"
applied = 0; skipped = 0; unmapped = set()
log = []

for fpath in conv_path.rglob("*.md"):
    try:
        t = open(fpath, encoding="utf-8", errors="ignore").read()
    except:
        skipped += 1; continue
    m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", t, re.DOTALL)
    if not m:
        skipped += 1; continue
    h, fm, e, body = m.groups()

    # Only handle transcript-episode type that lacks concept:
    if "type: transcript-episode" not in fm:
        skipped += 1; continue
    if re.search(r"^concept:\s", fm, re.M):
        skipped += 1; continue

    subfolder = fpath.parent.name
    prim_concept, origin, authored_by = get_mapping(subfolder)

    # Track unmapped
    if (prim_concept, origin, authored_by) == DEFAULT and subfolder not in EXPLICIT:
        unmapped.add(subfolder)

    if prim_concept not in concept_files:
        skipped += 1; continue

    changed = False
    if not re.search(r"^origin:", fm, re.M):
        fm = fm.rstrip() + f"\norigin: {origin}"
        changed = True
    if not re.search(r"^authored_by:", fm, re.M):
        fm = fm.rstrip() + f"\nauthored_by: {authored_by}"
        changed = True
    fm = fm.rstrip() + f'\nconcept: "[[{prim_concept}]]"'
    changed = True

    if changed:
        open(fpath, "w", encoding="utf-8").write(h + fm + e + body)
        applied += 1
    else:
        skipped += 1

log.append(f"applied={applied} skipped={skipped}")
if unmapped:
    log.append(f"Unmapped subfolders ({len(unmapped)}):")
    for u in sorted(unmapped):
        log.append(f"  {u}")

open("E:/Obsidian/_imports/_integrate_transcripts2_log.txt", "w", encoding="utf-8").write("\n".join(log))
