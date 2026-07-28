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
"""archive_original.py — RUN AT THE START OF ANY IMPORT (Rule 0 / Phase 0).

Copies a source original (a file OR a whole folder) VERBATIM into the permanent
originals archive and NEVER deletes or edits anything. This is the safety net:
if we later delete or transform derived notes, the untouched source is still here
to lean on.

  python archive_original.py <source-path> [--source <key>] [--label <text>] [--dry-run] [--lock]

- Copy-only:   the source is never moved, edited, or deleted.
- Idempotent:  re-archiving the same content is detected by content digest and skipped.
- Integrity:   every copied file is re-hashed (sha256) and verified against the source.
- Permanent:   nothing under _originals is ever auto-deleted.

This is DISTINCT from:
  * vault_backup.py  — git-commits the VAULT state (protects derived notes), and
  * the in-note "raw text lives in one copy" rule (rule 5 of obsidian-ingest).
Those protect the *processed* layer; this preserves the *upstream source artifact*.

ASCII-only stdout (cp1252 safety). Run with PYTHONUTF8=1.
"""
import os, sys, json, hashlib, shutil, socket, argparse, stat
from datetime import datetime
from pathlib import Path

try:
    from _paths import ORIGINALS
except Exception:
    ORIGINALS = r"%VAULT_ROOT%\_originals"   # HP17 fallback
ORIGINALS = Path(ORIGINALS)
FORBIDDEN = '<>:"/\\|?*'


def p(*a):
    print(" ".join(str(x) for x in a).encode("ascii", "replace").decode("ascii"))


def safename(name: str) -> str:
    out = "".join("_" if c in FORBIDDEN else c for c in name).strip(" .")
    return out or "unnamed"


def sha256_file(path: Path, _buf=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(_buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def list_files(src: Path):
    """Return [(abs_path, rel_posix)] for a single file or a whole tree."""
    if src.is_file():
        return [(src, src.name)]
    out = []
    for root, _dirs, fnames in os.walk(src):
        for fn in fnames:
            fp = Path(root) / fn
            out.append((fp, fp.relative_to(src).as_posix()))
    return out


def combined_digest(rel_hashes: dict) -> str:
    blob = "".join("%s\0%s\n" % (k, rel_hashes[k]) for k in sorted(rel_hashes))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def manifest_digest(d: Path):
    mf = d / "_manifest.json"
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding="utf-8")).get("content_digest")
        except Exception:
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to the original file or folder to preserve")
    ap.add_argument("--source", dest="key", default="misc",
                    help="source key / namespace (e.g. pokupki, faaa, gtasks, csv-crm, dm-personal)")
    ap.add_argument("--label", default="", help="optional human note stored in the manifest")
    ap.add_argument("--dry-run", action="store_true", help="report what would be archived; copy nothing")
    ap.add_argument("--lock", action="store_true", help="mark the archived copy read-only (best effort)")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        p("ERROR source not found:", src); sys.exit(2)
    src = src.resolve()
    if src == ORIGINALS.resolve() or ORIGINALS.resolve() in src.parents:
        p("SKIP: source is already inside the originals archive:", src); return

    key = safename(args.key)
    files = list_files(src)
    total_bytes = sum(fp.stat().st_size for fp, _ in files)
    p("=" * 60)
    p("ARCHIVE ORIGINAL  source-key:", key)
    p("from:", src)
    p("files:", len(files), " size: %.1f MB" % (total_bytes / (1024 * 1024)))

    src_hashes = {rel: sha256_file(fp) for fp, rel in files}
    digest = combined_digest(src_hashes)
    short = digest[:8]

    date = datetime.now().strftime("%Y-%m-%d")
    base_name = "%s__%s" % (date, safename(src.name))
    dest = ORIGINALS / key / base_name

    # idempotency: an existing archive with identical content -> nothing to do
    if dest.exists():
        if manifest_digest(dest) == digest:
            p("ALREADY ARCHIVED (identical content):", dest); p("OK"); return
        dest = ORIGINALS / key / ("%s__%s" % (base_name, short))  # same name, different content
        if dest.exists() and manifest_digest(dest) == digest:
            p("ALREADY ARCHIVED (identical content):", dest); p("OK"); return

    if args.dry_run:
        p("DRY RUN -> would archive to:", dest)
        p("content_digest:", digest); return

    # copy verbatim (copy-only; the source is never touched)
    copied = 0
    for fp, rel in files:
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == fp.stat().st_size and sha256_file(dst) == src_hashes[rel]:
            continue
        shutil.copy2(fp, dst)
        copied += 1

    # verify the copy byte-for-byte against the source hashes
    bad = [rel for _, rel in files if not (dest / rel).exists() or sha256_file(dest / rel) != src_hashes[rel]]

    manifest = {
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "source_key": key,
        "label": args.label,
        "original_path": str(src),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "content_digest": digest,
        "files": src_hashes,
        "policy": "PERMANENT - verbatim copy of an import original. NEVER delete or edit.",
    }
    (dest / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.lock:
        for _, rel in files:
            try:
                os.chmod(dest / rel, stat.S_IREAD)
            except Exception:
                pass

    p("archived to:", dest)
    p("copied:", copied, "of", len(files), "files  digest:", short)
    p("INTEGRITY:", "PASS" if not bad else "FAIL (%d mismatched)" % len(bad))
    for rel in bad[:8]:
        p("  ! ", rel)
    if bad:
        sys.exit(1)
    p("OK")


if __name__ == "__main__":
    main()
