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
Vault-wide orphan scanner.

Per [[no-orphan-notes-rule]]: every live-vault .md must have >=1 incoming wikilink
from another file. This script builds a reverse index of [[targets]] and writes
a report of files with 0 incoming links.

EXCLUDED folders (per the rule): _originals, _drafts, _imports
EXCLUDED files: index/MOC files, daily-note hubs (auto-list pages), .obsidian/*

Output:
- %IMPORTS%\orphan-scan\orphans.csv         (all orphans)
- %IMPORTS%\orphan-scan\orphans-by-folder.csv (counts per folder)
- %IMPORTS%\orphan-scan\orphans.html         (visual dashboard)
- %IMPORTS%\orphan-scan\scan-summary.txt     (counters)

Token-economy: deterministic (0 LLM tokens). Per [[vault-data-architecture]].
"""
from __future__ import annotations
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os
import re
import csv
import sys
import time
import json
from pathlib import Path
from collections import defaultdict, Counter

VAULT = Path(r"%VAULT%")
OUT   = Path(r"%IMPORTS%\orphan-scan")
OUT.mkdir(parents=True, exist_ok=True)

# Scope (what the rule applies to) lives in ONE place -- orphan_scope.py, shared with
# the PostToolUse hook. Do NOT re-list folders here (that drift is what blocked
# `_machine-bus/_deploy/payloads/*/MANIFEST.md`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orphan_scope import EXCLUDED_PREFIXES, is_excluded, is_infra  # noqa: E402

# MOCs / index pages — they LINK OUT to many, by design no one links TO them as a "note".
# We still want to know if a MOC is orphaned (it should be reachable from somewhere),
# but they're a separate report bucket.
MOC_PATTERNS = (
    re.compile(r"^_.*-MOC\.md$", re.I),
    re.compile(r"^_index\.md$", re.I),
    re.compile(r"^_Life-OS.*\.md$", re.I),
)

# Wikilink pattern: [[target]], [[target|display]], [[target#heading]], [[target#heading|display]]
# We strip .md, lowercase, and only take the basename portion of nested paths like [[folder/note]].
WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")

def normalize_target(raw: str) -> str:
    # Strip display alias, heading, and leading path.
    # Obsidian sometimes writes escaped pipe `\|` (the MOC builder for Apple Notes did this).
    # Normalize escaped pipe to plain pipe BEFORE splitting.
    t = raw.replace(r"\|", "|")
    t = t.split("|", 1)[0]
    t = t.split("#", 1)[0]
    t = t.strip().rstrip("\\")  # belt-and-braces: any leftover trailing backslash
    # Allow nested paths like "folder/note" — keep last segment as basename
    if "/" in t:
        t = t.rsplit("/", 1)[-1]
    if "\\" in t:
        t = t.rsplit("\\", 1)[-1]
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.strip().lower()

def is_moc(filename: str) -> bool:
    return any(p.match(filename) for p in MOC_PATTERNS)

def main():
    t0 = time.time()

    # Single-instance lock: 2026-07-21 two concurrent scans (manual + manual) ran
    # ~20 min each thrashing the disk and interleaved writes into reverse-index.json
    # (corrupt JSON -> hook fail-open). One scan at a time; a lock older than 2h is
    # considered stale (crashed run) and taken over.
    lock = OUT / "_scan.lock"
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        if age < 2 * 3600:
            print(f"[scan] another scan holds {lock} ({age/60:.0f} min old) — exiting. "
                  f"Delete the lock to force.", flush=True)
        else:
            print(f"[scan] stale lock ({age/3600:.1f}h old) — taking over.", flush=True)
            lock.unlink(missing_ok=True)
        if lock.exists():
            return
    lock.write_text(f"{os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")

    try:
        _run(t0)
    finally:
        lock.unlink(missing_ok=True)


def _run(t0):
    print(f"[scan] walking {VAULT} ...", flush=True)

    all_files = []          # list of (rel_path: Path, abs_path: Path)
    basenames = {}          # lowercase basename (no .md) -> rel_path (first occurrence)
    basename_dups = defaultdict(list)  # basename -> [rel_paths] if dupes
    # Build file index first
    for root, dirs, files in os.walk(VAULT):
        # prune excluded dirs in-place for speed
        rel_root = Path(root).relative_to(VAULT)
        rel_root_parts = rel_root.parts
        if rel_root_parts and rel_root_parts[0] in EXCLUDED_PREFIXES:
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in EXCLUDED_PREFIXES and not d.startswith(".")]
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            abs_p = Path(root) / fn
            rel_p = abs_p.relative_to(VAULT)
            if is_excluded(rel_p):
                continue
            all_files.append((rel_p, abs_p))
            key = fn[:-3].lower()
            if key in basenames:
                basename_dups[key].append(rel_p)
            else:
                basenames[key] = rel_p

    print(f"[scan] indexed {len(all_files):,} .md files in {time.time()-t0:.1f}s", flush=True)
    print(f"[scan] basename collisions: {len(basename_dups)}", flush=True)

    # Reverse-index pass: for each file, extract its outgoing wikilinks
    incoming = defaultdict(set)   # target_basename_lower -> set of source rel_paths (as str)
    outgoing_count = Counter()
    t1 = time.time()
    parsed = 0
    errors = 0
    for rel_p, abs_p in all_files:
        try:
            text = abs_p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            errors += 1
            continue
        src_key = rel_p.name[:-3].lower()
        targets = WIKILINK_RE.findall(text)
        outgoing_count[src_key] = len(targets)
        seen_this_file = set()
        for raw in targets:
            tgt = normalize_target(raw)
            if not tgt or tgt == src_key:
                continue
            if tgt in seen_this_file:
                continue
            seen_this_file.add(tgt)
            incoming[tgt].add(str(rel_p).replace("\\", "/"))
        parsed += 1
        if parsed % 10000 == 0:
            print(f"[scan]   parsed {parsed:,}/{len(all_files):,}", flush=True)

    print(f"[scan] parsed {parsed:,} files in {time.time()-t1:.1f}s ({errors} read errors)", flush=True)

    # Compute orphans: file whose basename has 0 incoming sources
    orphans = []
    moc_orphans = []
    infra_skipped = 0
    for rel_p, abs_p in all_files:
        # Machine-infra docs (bus/deploy/transit manifests) were parsed above as link
        # SOURCES, but the orphan verdict does not apply to them: they are referenced by
        # PENDING-*.jsonl manifests, never by wikilinks.
        if is_infra(rel_p):
            infra_skipped += 1
            continue
        key = rel_p.name[:-3].lower()
        in_count = len(incoming.get(key, ()))
        if in_count == 0:
            row = {
                "rel_path": str(rel_p).replace("\\", "/"),
                "basename": rel_p.name,
                "folder": str(rel_p.parent).replace("\\", "/") if rel_p.parent != Path(".") else "(root)",
                "outgoing": outgoing_count.get(key, 0),
                "size_bytes": abs_p.stat().st_size if abs_p.exists() else 0,
            }
            if is_moc(rel_p.name):
                moc_orphans.append(row)
            else:
                orphans.append(row)

    # Folder summary
    folder_counts = Counter(r["folder"] for r in orphans)
    folder_totals = Counter(str(p.parent).replace("\\", "/") if p.parent != Path(".") else "(root)"
                            for p, _ in all_files)

    # Write CSVs
    with open(OUT / "orphans.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rel_path", "basename", "folder", "outgoing", "size_bytes"])
        w.writeheader()
        for r in sorted(orphans, key=lambda x: (x["folder"], x["basename"])):
            w.writerow(r)

    with open(OUT / "orphans-mocs.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rel_path", "basename", "folder", "outgoing", "size_bytes"])
        w.writeheader()
        for r in sorted(moc_orphans, key=lambda x: x["basename"]):
            w.writerow(r)

    with open(OUT / "orphans-by-folder.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["folder", "orphans", "total_md", "orphan_pct"])
        for folder, total in sorted(folder_totals.items(), key=lambda x: -folder_counts.get(x[0], 0)):
            orph = folder_counts.get(folder, 0)
            pct = (orph / total * 100.0) if total else 0.0
            w.writerow([folder, orph, total, f"{pct:.1f}"])

    # Reverse-index JSON (basename_lower -> count of incoming sources).
    # Used by the PostToolUse orphan-check hook so it never has to grep the vault.
    # Store just COUNTS — keeps the file small (~few MB instead of dozens).
    # ATOMIC write (tmp + os.replace): 2026-07-21 two concurrent scans interleaved
    # writes into this file -> corrupt JSON ("Extra data") -> the hook silently
    # failed OPEN (every write approved, gate off). A consumer must never observe
    # a half-written index.
    reverse_index = {k: len(v) for k, v in incoming.items()}
    tmp = OUT / "reverse-index.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "vault": str(VAULT),
            "total_basenames": len(reverse_index),
            "incoming_counts": reverse_index,
        }, f, ensure_ascii=False)
    os.replace(tmp, OUT / "reverse-index.json")

    # JSON for the HTML dashboard
    summary = {
        "total_md": len(all_files),
        "orphans": len(orphans),
        "moc_orphans": len(moc_orphans),
        "infra_skipped": infra_skipped,
        "orphan_pct": (len(orphans) / len(all_files) * 100.0) if all_files else 0.0,
        "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "by_folder_top": [
            {"folder": f, "orphans": c, "total": folder_totals[f],
             "pct": (c / folder_totals[f] * 100.0) if folder_totals[f] else 0.0}
            for f, c in folder_counts.most_common(30)
        ],
    }
    with open(OUT / "scan-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    txt = (
        f"Vault orphan scan @ {summary['scanned_at']}\n"
        f"--------------------------------------------\n"
        f"Total live .md files:   {summary['total_md']:,}\n"
        f"Orphans (0 incoming):   {summary['orphans']:,}  ({summary['orphan_pct']:.1f}%)\n"
        f"  of which MOCs/index:  {summary['moc_orphans']:,}  (reported separately)\n"
        f"Machine-infra exempt:   {summary['infra_skipped']:,}  (bus/deploy/transit; see orphan_scope.py)\n"
        f"Basename collisions:    {len(basename_dups):,}\n"
        f"Read errors:            {errors}\n"
        f"Scan time:              {time.time()-t0:.1f}s\n\n"
        f"Top folders by orphan count:\n"
    )
    for row in summary["by_folder_top"]:
        txt += f"  {row['orphans']:>6,} / {row['total']:>6,}  ({row['pct']:5.1f}%)  {row['folder']}\n"
    (OUT / "scan-summary.txt").write_text(txt, encoding="utf-8")
    # Avoid Windows cp1252 print crash on Cyrillic folder names
    # (per [[deterministic-script-gotchas]]). Print ASCII-safe headline only.
    print(f"[scan] DONE — {summary['orphans']:,}/{summary['total_md']:,} orphans "
          f"({summary['orphan_pct']:.1f}%). Full report -> scan-summary.txt", flush=True)

    print(f"[scan] outputs in {OUT}", flush=True)

if __name__ == "__main__":
    main()
