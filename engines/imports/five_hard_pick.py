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
"""Pick 5 candidate notes for /five-hard. Prefer notes whose stance hasn't been pressure-tested
in a while (oldest mtime among belief-* + concept-bible-*). ASCII-only stdout (Cyrillic-safe).
Reusable: same script feeds both /five-hard manual call and the monthly scheduled task."""
import os, sys, re, json
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
SOURCES = [
    VAULT / "03-Insights",
    VAULT / "06-Concepts",
]
PATTERNS = ("belief-", "concept-bible-")

def fm_field(text, key):
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m: return None
    fm = m.group(1)
    mm = re.search(r"(?m)^" + key + r'\s*:\s*"?([^"\n#]+)"?', fm)
    return mm.group(1).strip() if mm else None

def gather():
    items = []
    for src in SOURCES:
        if not src.exists(): continue
        for p in src.glob("*.md"):
            if not any(p.name.startswith(pfx) for pfx in PATTERNS):
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            title = fm_field(t, "title") or p.stem
            summary = fm_field(t, "summary") or ""
            mtime = p.stat().st_mtime
            items.append({"path": str(p), "stem": p.stem, "title": title,
                          "summary": summary[:240], "mtime": mtime})
    return items

def main():
    items = gather()
    items.sort(key=lambda x: x["mtime"])
    try: n = int(os.environ.get("FIVE_HARD_N", "5"))
    except ValueError: n = 5  # garbage env -> sane default, don't die
    pick = items[:n]
    print(f"five_hard: {len(items)} candidates -> picked {len(pick)} oldest")
    out = {"candidates_total": len(items), "picked": pick}
    Path(r"E:/Obsidian/_imports/_five_hard_pick.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in pick:
        print(f"  - {p['stem']}")

if __name__ == "__main__":
    main()
