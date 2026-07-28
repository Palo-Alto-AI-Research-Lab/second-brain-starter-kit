"""
precheck_corpus.py — RE-IMPORT GATE for obsidian-ingest.

Before ANY "import this corpus" task runs, this script asks:
    "Did I already import this exact byte-stream?"
by comparing the source's sha256 against everything under E:\\Obsidian\\_originals\\
(Rule 0's permanent archive).

USAGE:
    python precheck_corpus.py <source-file>

EXIT CODE: always 0 (decision tool, not failure tool).
The caller reads STDOUT line 1 to decide:
    NO_OP   — source is byte-identical to a prior archived original. DO NOT RE-IMPORT.
    CHANGED — same basename exists in _originals but hash differs. PROCEED as incremental.
    NEW     — no match in _originals. PROCEED with full first-time ingest (Rule 0 first).

OUTPUT FORMAT (line 1 machine-readable, rest human-readable):
    <DECISION>\\t<sha256>\\t<bytes>\\t<match-path-or-empty>
    ...
Deterministic, stdlib-only, idempotent. Token-cheap (0 LLM).
Enforces the rule in memory crypto-essays-reimport-idempotent + SKILL.md Rule 0'.
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

ORIGINALS = Path(r"%VAULT_ROOT%\_originals")
CHUNK = 1 << 20


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def find_matches(source: Path, source_hash: str) -> tuple[Path | None, list[Path]]:
    if not ORIGINALS.exists():
        return None, []
    name = source.name
    same_name: list[Path] = []
    exact: Path | None = None
    src_size = source.stat().st_size
    for p in ORIGINALS.rglob("*"):
        if not p.is_file():
            continue
        if p.name != name:
            continue
        same_name.append(p)
        if exact is not None:
            continue
        try:
            if p.stat().st_size != src_size:
                continue
            if sha256_file(p) == source_hash:
                exact = p
        except OSError:
            continue
    return exact, same_name


def main() -> int:
    if len(sys.argv) != 2:
        print("USAGE\t-\t-\t-")
        print("USAGE: python precheck_corpus.py <source-file>", file=sys.stderr)
        return 0
    source = Path(sys.argv[1])
    if not source.exists():
        print("MISSING\t-\t-\t-")
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 0
    if not source.is_file():
        print("DIR_MODE_NOT_IMPLEMENTED\t-\t-\t-")
        print(f"NOTE: v1 handles single files only. For dirs: hash each top item separately.",
              file=sys.stderr)
        return 0

    size = source.stat().st_size
    src_hash = sha256_file(source)
    exact, same_name = find_matches(source, src_hash)

    if exact is not None:
        rel = exact.relative_to(ORIGINALS)
        print(f"NO_OP\t{src_hash}\t{size}\t{exact}")
        print()
        print("=" * 60)
        print("RE-IMPORT GATE: NO_OP")
        print("=" * 60)
        print(f"Source : {source}")
        print(f"  size : {size:,} bytes")
        print(f"  hash : {src_hash}")
        print(f"Match  : {exact}")
        print(f"  (under _originals/{rel.parts[0]}/{rel.parts[1] if len(rel.parts) > 1 else ''})")
        print()
        print("This source is BYTE-IDENTICAL to a prior archived original.")
        print("DO NOT re-run the import pipeline. The existing vault notes are")
        print("authoritative. Report to Anton with the existing import location.")
        return 0

    if same_name:
        print(f"CHANGED\t{src_hash}\t{size}\t{same_name[0]}")
        print()
        print("=" * 60)
        print("RE-IMPORT GATE: CHANGED")
        print("=" * 60)
        print(f"Source : {source}")
        print(f"  size : {size:,} bytes")
        print(f"  hash : {src_hash}")
        print(f"Existing same-basename archives ({len(same_name)}):")
        for p in same_name[:5]:
            try:
                old_size = p.stat().st_size
                delta = size - old_size
                sign = "+" if delta >= 0 else ""
                print(f"  - {p}  ({old_size:,} bytes, delta {sign}{delta:,})")
            except OSError:
                print(f"  - {p}  (stat failed)")
        if len(same_name) > 5:
            print(f"  ... and {len(same_name) - 5} more")
        print()
        print("Same basename, different bytes. Proceed as INCREMENTAL re-import:")
        print("  1. Archive THIS version via Rule 0 (archive_original.py) as new snapshot.")
        print("  2. Diff against the latest prior snapshot for ONLY new content.")
        print("  3. Run the source's idempotent pipeline on the diff (parsers are")
        print("     dedup-safe by id / content-hash).")
        return 0

    print(f"NEW\t{src_hash}\t{size}\t")
    print()
    print("=" * 60)
    print("RE-IMPORT GATE: NEW (first-time ingest)")
    print("=" * 60)
    print(f"Source : {source}")
    print(f"  size : {size:,} bytes")
    print(f"  hash : {src_hash}")
    print()
    print("No prior archive in _originals with this basename. Proceed FIRST-TIME:")
    print("Rule 0 (archive_original.py) THEN the rest of the pipeline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
