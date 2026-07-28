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
"""Gather Anton's OWN writing from the last N days (default 7) for /wisdom-distill.
Deterministic + 0 LLM tokens: the distiller LLM reads ONLY the digest this script writes,
never the corpus. ASCII-only stdout (Cyrillic-safe); UTF-8 output files.

Selection: vault .md where frontmatter says origin: anton (or tag anton-original),
and the note is fresh (frontmatter date >= today-N; fallback = file mtime).
Excludes _originals/_imports/dashboards and obvious non-content.

Usage:
    python wisdom_week_gather.py            # last 7 days
    python wisdom_week_gather.py 14         # last 14 days
Output:
    %IMPORTS%\\_wisdom_week_digest.md   (the ONLY thing the LLM reads)
    stdout: counts
"""
import sys, re, datetime
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
OUT = Path(r"E:/Obsidian/_imports/_wisdom_week_digest.md")
EXCLUDE_PARTS = {"_originals", "_imports", "_Dashboards", "_machine-bus", ".trash",
                 ".obsidian", "_cowork-inbox", "_sync-conflict-archive"}
MAX_FILES = 60          # hard cap: digest stays judge-sized
SNIPPET = 500           # chars of body per note

def fm(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    return (m.group(1), text[m.end():]) if m else ("", text)

def fm_get(fmtext, key):
    m = re.search(r"(?m)^" + key + r'\s*:\s*"?([^"\n#]+)"?', fmtext)
    return m.group(1).strip() if m else None

def parse_date(s):
    if not s: return None
    for n, f in ((10, "%Y-%m-%d"), (7, "%Y-%m"), (4, "%Y")):
        try: return datetime.datetime.strptime(str(s)[:n], f).date()
        except Exception: pass
    return None

def main():
    try: days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    except ValueError: days = 7  # garbage arg -> sane default, don't die
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    cutoff_ts = datetime.datetime.combine(cutoff, datetime.time()).timestamp()
    picked, scanned = [], 0
    for p in VAULT.rglob("*.md"):
        parts = set(p.parts)
        if EXCLUDE_PARTS & parts:
            continue
        # prune ANY dot-dir (.stversions Syncthing history, .git, etc.) and stray
        # *.sync-conflict-* copies -- else the digest fills with duplicate ghosts
        # ([[stversions-scan-class]] vault-walker gotcha).
        if any(part.startswith(".") for part in p.parts) or ".sync-conflict-" in p.name:
            continue
        # cheap mtime pre-filter: skip files untouched since cutoff (a note edited
        # after cutoff still passes even if its date field is old; date decides below)
        try: st = p.stat()
        except Exception: continue
        if st.st_mtime < cutoff_ts:
            continue
        scanned += 1
        try: t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        fmtext, body = fm(t)
        origin = (fm_get(fmtext, "origin") or "").lower()
        tags = fm_get(fmtext, "tags") or ""
        if origin != "anton" and "anton-original" not in tags and "anton-original" not in fmtext:
            continue
        d = parse_date(fm_get(fmtext, "date") or fm_get(fmtext, "date_established"))
        if d and d < cutoff:
            continue  # old note merely re-touched by tooling -> not this week's thinking
        title = fm_get(fmtext, "title") or p.stem
        snippet = re.sub(r"\s+", " ", body).strip()[:SNIPPET]
        picked.append({"path": p, "title": title, "date": str(d or ""), "snippet": snippet})
        if len(picked) >= MAX_FILES:
            break
    lines = [f"# Wisdom week digest — {cutoff} .. {today} ({len(picked)} notes, scanned {scanned} fresh files)", ""]
    for it in picked:
        rel = str(it["path"]).replace(str(VAULT), "").lstrip("\\/")
        lines += [f"## {it['title']}  [{it['date']}]", f"({rel})", it["snippet"], ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wisdom_gather: days={days} fresh_scanned={scanned} anton_notes={len(picked)} -> {OUT}")

if __name__ == "__main__":
    main()
