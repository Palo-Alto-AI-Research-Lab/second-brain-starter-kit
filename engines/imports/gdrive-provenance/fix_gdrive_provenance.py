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
Fix the gdrive-personal-mirror provenance bug (see memory gdrive-personal-mirror-provenance-bug).

The importer stamped `origin: anton-archive` on ALL imported GDrive files regardless
of real authorship — incl. Ray Bradbury stories, candidate CVs, employee NDAs.

Schema B (Anton's choice 2026-06-13):
  1. ALL files: origin: anton-archive -> origin: gdrive-personal-mixed
     (honest: personal archive, mixed authorship; never falsely "Anton's").
  2. ON TOP — narrow, RELIABLE rules promote clearly-external to origin: external + author:
     - Ray Bradbury stories
     - candidate / employee CVs (Recruitment, CV, !Fired, Личные дела сотрудников)
     - copywriter work samples / portfolios
     - "файл от <name>" explicit third-party files
     Grey zone is LEFT as gdrive-personal-mixed (no false claim either way).

Adds `provenance_fixed: 2026-06-13` to every touched file for traceability/rollback.

Deterministic, 0 LLM tokens (per vault-data-architecture). Dry-run default; APPLY=1 to write.
Idempotent: re-running is safe (matches current origin, not the old value only).
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path
from collections import Counter

APPLY = os.environ.get("APPLY") == "1"

ROOTS = [
    r"%VAULT%\05-Resources\GDrive-Personal",
    r"%VAULT_ROOT%\_originals\gdrive-personal-archive",
]

OLD_ORIGIN = "anton-archive"
NEUTRAL    = "gdrive-personal-mixed"
FIXED_TAG  = "provenance_fixed: 2026-06-13"

# Anton's own-name markers — if present in path/filename, NEVER classify as external.
ANTON_RX = re.compile(r"anton|dziatkov|dzyatkov|дзятковск|дзятковсь", re.I)

# ---- external rules: (rule_name, compiled path/name regex, author value) ----
# Order matters — first match wins. Corporate legal templates are checked BEFORE the
# broad recruitment/fired folders so NDAs/agreements get author: corporate, not needs-review.
EXTERNAL_RULES = [
    ("bradbury",     re.compile(r"ray bradbury|/stories/.*\(\d{4}\)", re.I), "Ray Bradbury"),
    ("corporate-legal", re.compile(
        r"\bnda\b|termination|trial period|services agreement|employment agreement|"
        r"amendment to agreement|информация для договора|passport|паспорт|"
        r"non-disclosure|consulting services agreement", re.I), "corporate"),
    ("copywriter",   re.compile(r"writer_copywriter|copywriter_work|work_samples|portfolio|портфолио", re.I), "needs-review"),
    # candidate-cv: match by FOLDER only (recruitment / fired / personnel files) — NOT by
    # the word "cv/резюме" in a filename, which falsely catches "резюме звонка" (= call
    # summary, Anton's own) and his "SELF PRESENTING REZUMEs" self-pitch folder.
    ("candidate-cv", re.compile(r"/recruitment/|!fired|личные дела сотрудник", re.I), "needs-review"),
    ("file-from-x",  re.compile(r"файл от |от дениса", re.I), "needs-review"),
]

# Our OWN generated navigation files — never reclassify (they're folder maps we made).
SKIP_NAV_RX = re.compile(r"^map-|карта папки", re.I)

FM_BOUNDS = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)

def classify_external(source_path: str, filename: str):
    """Return (author, rule_name) if file is reliably external, else (None, None)."""
    hay = f"{source_path}\n{filename}"
    if ANTON_RX.search(hay):
        return None, None  # Anton's own — never external
    for rule_name, rx, author in EXTERNAL_RULES:
        if rx.search(hay):
            return author, rule_name
    return None, None

def get_field(fm: str, name: str) -> str | None:
    m = re.search(rf"^{name}:\s*\"?(.+?)\"?\s*$", fm, re.M)
    return m.group(1) if m else None

def fix_file(path: Path):
    """Return (action, author, rule) — action: 'neutral'|'external'|'skip'|'nochange'."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "skip", None, None
    mb = FM_BOUNDS.search(text)
    if not mb:
        return "skip", None, None
    fm = mb.group(1)
    origin = get_field(fm, "origin")
    if origin not in (OLD_ORIGIN, NEUTRAL, "external"):
        return "skip", None, None

    # never touch our own folder-map navigation files
    title = get_field(fm, "title") or ""
    if SKIP_NAV_RX.search(path.name) or SKIP_NAV_RX.search(title):
        return "skip", None, None

    source_path = get_field(fm, "source_path") or ""
    author_needed, rule = classify_external(source_path, path.name)

    new_fm = fm
    action = "nochange"

    if author_needed:
        if origin != "external":
            new_fm = re.sub(r"^origin:.*$", "origin: external", new_fm, count=1, flags=re.M)
            action = "external"
        if get_field(new_fm, "author"):
            new_fm = re.sub(r"^author:.*$", f'author: "{author_needed}"', new_fm, count=1, flags=re.M)
        else:
            new_fm = new_fm + f'\nauthor: "{author_needed}"'
            action = "external"
    else:
        if origin == OLD_ORIGIN:
            new_fm = re.sub(r"^origin:.*$", f"origin: {NEUTRAL}", new_fm, count=1, flags=re.M)
            action = "neutral"

    if action == "nochange":
        return "nochange", None, None

    if "provenance_fixed:" not in new_fm:
        new_fm = new_fm + f"\n{FIXED_TAG}"

    if APPLY:
        new_text = text[:mb.start(1)] + new_fm + text[mb.end(1):]
        path.write_text(new_text, encoding="utf-8")
    return action, author_needed, rule

def main():
    counts = Counter()
    by_rule = Counter()
    anton_falsepos = []   # external files whose path mentions Anton — should be ZERO
    ext_samples = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for r, _, fs in os.walk(root):
            for fn in fs:
                if not fn.endswith(".md"): continue
                p = Path(r) / fn
                act, author, rule = fix_file(p)
                counts[act] += 1
                if act == "external":
                    by_rule[rule] += 1
                    # guard: check the SOURCE_PATH (not the full disk path, which
                    # contains the vault name "Owner-Knowledge").
                    try:
                        fmtxt = p.read_text(encoding="utf-8", errors="replace")[:1500]
                        msp = re.search(r'^source_path:\s*"?(.+?)"?\s*$', fmtxt, re.M)
                        sp_check = msp.group(1) if msp else p.name
                    except Exception:
                        sp_check = p.name
                    if ANTON_RX.search(sp_check):
                        anton_falsepos.append(str(p))
                    if len(ext_samples) < 20:
                        ext_samples.append((rule, author, p.name))

    mode = "APPLY" if APPLY else "DRY-RUN"
    lines = [f"=== gdrive provenance fix [{mode}] ==="]
    for k in ("neutral", "external", "nochange", "skip"):
        lines.append(f"  {counts[k]:>6}  {k}")
    lines.append("\n  external by rule:")
    for rl, n in by_rule.most_common():
        lines.append(f"    {n:>5}  {rl}")
    lines.append(f"\n  ANTON false-positives in external (MUST be 0): {len(anton_falsepos)}")
    for fp in anton_falsepos[:10]:
        lines.append(f"    !! {fp}")
    lines.append("\n  external samples (rule | author | file):")
    for rl, au, nm in ext_samples:
        lines.append(f"    [{rl:12}] {au:14} {nm}")
    out = "\n".join(lines)
    Path(r"%IMPORTS%\gdrive-provenance\_dryrun_report.txt").write_text(out, encoding="utf-8")
    # ASCII-safe console line
    print(f"[{mode}] neutral={counts['neutral']} external={counts['external']} "
          f"skip={counts['skip']} anton_falsepos={len(anton_falsepos)} "
          f"-> report: _dryrun_report.txt")

if __name__ == "__main__":
    main()
