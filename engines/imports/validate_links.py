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
"""
Vault link integrity check + RATCHET gate.

Forever-fix 2026-07-04: previously scanned only 4 hardcoded roots (Telegram,
Concepts, Insights, People) -> broken links in 02-Decisions / 05-Resources /
04-Projects / 00-System / 90_MOCs were INVISIBLE (this let a [[memory-name]]
leak survive). Now scans ALL curated (digit-prefixed) top dirs by a structural
rule, not a cherry-picked list. Underscore/dot dirs (_originals, _imports,
_drafts, _Dashboards, .obsidian, .git ...) stay raw-exempt.

Also detects the exact class that bit us: a [[wikilink]] whose target is a
MEMORY file name (not a vault note) -> should be a `backtick` reference, not a
wikilink. These are reported separately as MEMORY-LEAK (high priority).

ROOT-FIX 2026-07-22 (three roots, found via the dangling `concept-second-brain`):

  ROOT-1  BLIND SPOT: only body [[wikilinks]] were checked. A frontmatter
          `concept: concept-second-brain` is NOT a wikilink -> dangling concept
          pointers accumulated completely unseen. Now frontmatter reference
          FIELDS (concept/concepts/related/parent/moc/up) are validated too.

  ROOT-2  FALSE SILENCE: MEMORY_DIR was hardcoded to the HUB's project dir
          (E---CLAUDE-HUB1-June26). On any other machine that path does
          not exist -> memory_stems = empty set -> MEMORY-LEAK silently ALWAYS
          reported 0 = a green tick over zero work. The helper that solves this
          (_paths.memory_dir(), reading CLAUDE_MEMORY_NAME from machine.env)
          already existed and simply was not adopted. Now adopted, and a
          missing memory dir is a LOUD warning, never a silent zero.

  ROOT-3  REPORT WITHOUT A GATE: this file said "it does not gate writes", so
          dangling refs piled up for months with nobody reading the report.
          Now `--gate` enforces a BASELINE RATCHET (same pattern as
          lint_cli_argparse): existing debt is frozen in a baseline, any NEW
          dangling frontmatter concept ref exits 1. Debt can only shrink.

Aliases are honoured: a link to a note's `aliases:` entry is NOT broken.

Legitimate DANGLING body forward-links ("link liberally" - a [[name]] not yet
created) are EXPECTED and only listed, never gated. Frontmatter reference
fields are DIFFERENT: they are machine-read pointers, not prose, so a dangling
one is always a defect.

Usage:
    python validate_links.py                 # report (exit 0)
    python validate_links.py --gate          # ratchet: exit 1 on NEW fm debt
    python validate_links.py --write-baseline  # freeze current fm debt
    python validate_links.py --json out.json # machine-readable dump
"""
import re, os, sys, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _paths import VAULT as _VAULT, memory_dir as _memory_dir
except Exception:                                   # never break on a partial box
    _VAULT = r"E:/Obsidian/Owner-Knowledge"
    def _memory_dir():
        return os.path.join(os.path.expanduser("~"), ".claude", "projects",
                            "C--Users----CLAUDE-HP17-May26", "memory")

VAULT = Path(_VAULT)
MEMORY_DIR = Path(_memory_dir())
BASELINE = Path(__file__).with_name("validate_links_baseline.json")

# frontmatter fields whose values are NOTE POINTERS (machine-read, not prose).
# A dangling value here is always a defect -> this is what --gate ratchets.
FM_REF_FIELDS = ("concept", "concepts", "related", "parent", "moc", "up")

RAW_DIRS = {"01-Conversations"}     # raw chat archive: verbatim text, not authored links

LINK = re.compile(r"\[\[([^\]|#^]+)")
FM_FIELD = re.compile(
    r"^(%s)\s*:\s*(.*?)(?=^\S|\Z)" % "|".join(FM_REF_FIELDS), re.M | re.S)
ALIAS_FIELD = re.compile(r"^aliases\s*:\s*(.*?)(?=^\S|\Z)", re.M | re.S)


def split_fm(text):
    """Return (frontmatter, body). Empty frontmatter if the note has none."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[3:end], text[end + 4:]


WIKI_INLINE = re.compile(r"\[\[([^\[\]|#^]+?)(?:[#^|][^\[\]]*)?\]\]")


def yaml_values(blob):
    """Values of a scalar-or-list YAML field, as plain note-name strings.

    Handles the shapes Anton's notes actually use:
      concept: concept-x                      -> [concept-x]
      concept: "[[concept-x]]"                -> [concept-x]
      related: [[a]] · [[b]], [[c]]           -> [a, b, c]   (inline list)
      related:\\n  - "[[a]]"\\n  - "[[b]]"       -> [a, b]      (block list)
      related: a, b                           -> [a, b]      (bare csv)

    Root-fix 2026-07-22: the old parser took only splitlines()[0] and stripped a
    single outer [[ ]], so an inline `[[a]] · [[b]]` list collapsed into one
    garbage token like `a]] · [[b` -> dozens of phantom "dangling" refs. Now: if
    the value contains ANY [[wikilink]], every wikilink target is extracted;
    otherwise it is parsed as a bare scalar/list.
    """
    blob = blob.strip()
    if not blob:
        return []
    wl = [w.strip() for w in WIKI_INLINE.findall(blob) if w.strip()]
    if wl:                                     # any [[ ]] present -> those ARE the values
        return wl
    if blob.startswith("-") or "\n-" in blob:
        raw = re.findall(r"^\s*-\s*(.+?)\s*$", blob, re.M)
    elif blob.startswith("["):
        raw = blob.strip("[]").split(",")
    else:
        raw = re.split(r"\s*,\s*", blob.splitlines()[0])
    out = []
    for v in raw:
        v = v.strip().strip('"\'').split("|")[0].split("#")[0].strip()
        if v and v.lower() not in ("", "~", "null", "[]", "none"):
            out.append(v)
    return out


# ---------------------------------------------------------------- index -----
# Heavy/raw dirs skipped for the SCAN. Structural skip, not a cherry-pick.
# `.claude` (config synced into the vault) and 01-Conversations (verbatim chat
# archive) hold ~135k of the vault's ~208k md files and define no canonical
# links -> walking their NAMES is fine (cheap) but READING each head for
# aliases is what timed the old approach out.
SKIP_DIRS = {".stversions", ".git", ".obsidian", ".trash", "node_modules",
             ".claude", "_backups", "_originals", "_imports", "_session-md",
             "_sync-conflict-archive", "_machine-bus.preD2-bak"}
# Only these roots define aliases that a curated link could target -> only these
# get a head READ. Names from everywhere still populate the stem index for free.
ALIAS_ROOTS = {"06-Concepts", "07-People", "09-Bridges", "02-Decisions",
               "03-Insights", "04-Projects", "05-Resources", "90_MOCs",
               "00-System", "08-Templates", "10-Tasks", "04-Coach", "00-HOME"}

files = set()
aliases = {}
for root, dirs, fns in os.walk(VAULT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    top = os.path.relpath(root, VAULT).split(os.sep)[0]
    read_aliases = top in ALIAS_ROOTS
    for fn in fns:
        if not fn.lower().endswith(".md") or ".sync-conflict-" in fn:
            continue
        files.add(fn[:-3])                   # stem, no I/O
        if not read_aliases:
            continue
        try:
            head = open(os.path.join(root, fn), encoding="utf-8",
                        errors="replace").read(1200)
        except Exception:
            continue
        fm, _ = split_fm(head)
        if not fm:
            continue
        m = ALIAS_FIELD.search(fm)
        if m:
            for a in yaml_values(m.group(1)):
                aliases[a] = fn[:-3]


def resolves(target):
    t = target.strip().rstrip("\\")
    if not t:
        return True
    t = t.split("/")[-1].split("\\")[-1]
    return t in files or t in aliases


# ROOT-2: a missing memory dir must SCREAM, never silently zero the detector.
memory_ok = MEMORY_DIR.is_dir()
memory_stems = {p.stem for p in MEMORY_DIR.glob("*.md")} if memory_ok else set()

scan_roots = sorted(d for d in VAULT.iterdir()
                    if d.is_dir() and d.name[:1].isdigit() and d.name not in RAW_DIRS)

broken = {}        # body [[target]] -> [sources]        (report only)
mem_leak = {}      # body [[memory-name]] -> [sources]   (high priority)
fm_broken = {}     # "field:value" -> [sources]          (GATED)
total = fm_total = scanned = 0

# FAST gate path: the ratchet only needs frontmatter, not the 342k body links.
# `--gate` alone reads just each note's HEAD (frontmatter) -> ~minutes not ~8min,
# so /tt and pre-commit can afford it. Add `--full` (or use report/--json mode)
# to also scan body links + MEMORY-LEAK.
FM_ONLY = ("--gate" in sys.argv) and not any(
    a in sys.argv for a in ("--full", "--json")) and "--write-baseline" not in sys.argv

for root in scan_roots:
    for p in root.rglob("*.md"):
        if ".sync-conflict-" in p.name:
            continue
        scanned += 1
        try:
            if FM_ONLY:
                text = open(p, encoding="utf-8", errors="replace").read(8000)
            else:
                text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(p.relative_to(VAULT))
        fm, body = split_fm(text)

        if not FM_ONLY:
            for m in LINK.finditer(body):
                tgt = m.group(1).strip().rstrip("\\")
                if not tgt:
                    continue
                total += 1
                if resolves(tgt):
                    continue
                (mem_leak if tgt in memory_stems else broken).setdefault(tgt, []).append(rel)

        # ROOT-1: frontmatter pointer fields, the former blind spot
        for fm_m in FM_FIELD.finditer(fm):
            field = fm_m.group(1)
            for val in yaml_values(fm_m.group(2)):
                fm_total += 1
                if resolves(val):
                    continue
                if val in memory_stems:
                    mem_leak.setdefault(val, []).append(rel + f" (fm:{field})")
                else:
                    fm_broken.setdefault(f"{field}:{val}", []).append(rel)

# ---------------------------------------------------------------- report ----
print(f"vault      {VAULT}")
print(f"memory     {MEMORY_DIR}  " + ("OK" if memory_ok else "*** MISSING ***"))
if not memory_ok:
    print("!! MEMORY-LEAK detector is BLIND on this machine (memory dir not found).")
    print("!! Fix CLAUDE_MEMORY_NAME in ~/.claude/machine.env -- do NOT read the 0 as clean.")
print(f"scanned    {scanned} files in {len(scan_roots)} curated dirs")
print(f"body links {total} | broken {len(broken)} | MEMORY-LEAK {len(mem_leak)}")
print(f"fm refs    {fm_total} in {'/'.join(FM_REF_FIELDS)} | DANGLING {len(fm_broken)} "
      f"({sum(len(v) for v in fm_broken.values())} occurrences)")

if mem_leak:
    print("\n=== MEMORY-LEAK (use `backtick`, not [[wikilink]]) ===")
    for t, srcs in sorted(mem_leak.items()):
        print(f"  [[{t}]] x{len(srcs)} <- {', '.join(sorted(set(srcs))[:4])}")

if fm_broken:
    print("\n=== DANGLING FRONTMATTER REFS (defects: machine-read pointers) ===")
    for t, srcs in sorted(fm_broken.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(srcs):3} -> {t}  ({sorted(set(srcs))[0]})")

if broken:
    print("\n=== BROKEN / dangling body links (top 30; forward-links may be intentional) ===")
    for t, srcs in sorted(broken.items(), key=lambda kv: -len(kv[1]))[:30]:
        s = t.encode("ascii", "replace").decode()
        print(f"  {len(srcs):3} -> {s}  ({sorted(set(srcs))[0]})")

if "--json" in sys.argv:
    out = sys.argv[sys.argv.index("--json") + 1]
    json.dump({"vault": str(VAULT), "memory_ok": memory_ok, "scanned": scanned,
               "body_broken": broken, "memory_leak": mem_leak, "fm_broken": fm_broken},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\njson -> {out}")

# ---------------------------------------------------------------- ratchet ---
# ROOT-3: existing debt is frozen; only NEW dangling frontmatter refs fail.
if "--write-baseline" in sys.argv:
    json.dump({"note": "frozen dangling frontmatter refs; ratchet may only shrink",
               "written": "2026-07-22", "fm_broken": sorted(fm_broken)},
              open(BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nbaseline written: {len(fm_broken)} known dangling fm refs -> {BASELINE}")
    sys.exit(0)

if "--gate" in sys.argv:
    if not memory_ok:
        print("\nGATE: FAIL -- memory dir missing, detector blind (false silence).")
        sys.exit(1)
    try:
        base = set(json.load(open(BASELINE, encoding="utf-8"))["fm_broken"])
    except Exception:
        print(f"\nGATE: FAIL -- no baseline at {BASELINE}. Run --write-baseline first.")
        sys.exit(1)
    new = sorted(set(fm_broken) - base)
    fixed = sorted(base - set(fm_broken))
    if fixed:
        print(f"\nGATE: {len(fixed)} baseline ref(s) FIXED -- rerun --write-baseline to tighten.")
    if new:
        print(f"\nGATE: FAIL -- {len(new)} NEW dangling frontmatter ref(s):")
        for t in new:
            print(f"  {t}  <- {sorted(set(fm_broken[t]))[0]}")
        sys.exit(1)
    print("\nGATE: PASS -- no new dangling frontmatter refs.")
    sys.exit(0)
