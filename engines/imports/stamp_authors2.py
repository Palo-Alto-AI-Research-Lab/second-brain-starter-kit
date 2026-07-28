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
"""Step 3b: resolve the 524 author_status: needs-review notes using authors
identified from their OWN content + web-verify (Anton confirmed all external,
2026-06-09). Sets author:, removes the needs-review flags, fixes authored_by.
DRY default; APPLY=1. Stdout ASCII; report UTF-8."""
import re, os, collections
from pathlib import Path
try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"
VAULT = Path(VAULT)
ROOT = VAULT / "01-Conversations" / "_transcripts"
OUT = Path(os.path.join(IMPORTS, "qqq2"))
APPLY = os.environ.get("APPLY") == "1"

def getk(head, key):
    m = re.search(rf"(?m)^{key}:\s*(.+?)\s*$", head)
    return m.group(1).strip().strip('"\'') if m else ""

def clean_series(title):
    t = title.strip()
    t = re.sub(r"\s*\(?(video|youtube)?\s*transcri\w+\)?\s*$", "", t, flags=re.I)
    t = re.sub(r"[-_\s]*part[-_\s]*\d+.*$", "", t, flags=re.I)
    t = re.sub(r"[-_\s]*ep\.?\s*\d+.*$", "", t, flags=re.I)
    t = re.sub(r"\s*\d{1,3}p?$", "", t)
    return t.strip() or title.strip()

L = str.lower
# (predicate, author, corrupted?) — Anton: all NOT his -> external attribution
NEW = [
    (lambda k: k.startswith("Lucius Aurelian"), "Lucius Aurelian", False),
    (lambda k: k.startswith("Paul Cook"), "Paul Cook", False),
    (lambda k: k.startswith("Sergey Ignatenko"), "Sergey Ignatenko", False),
    (lambda k: k.startswith("One Spark"), "One Spark (consciousness podcast)", False),
    (lambda k: k.startswith("Satori"), "Satori (podcast/channel)", False),
    (lambda k: k.startswith("Jarid Boosters"), "Jarid Boosters (crypto/DeSci)", False),
    (lambda k: k.startswith("Terra"), "Terra (crypto project content)", False),
    (lambda k: k.startswith("История Пи"), "«История Пи» (alt-history YouTube channel)", False),
    (lambda k: k.startswith("Председатель СНТ"), "«Председатель СНТ» (alt-history YouTube channel)", False),
    (lambda k: k.startswith("my lunch Break"), "External YouTube channel (unidentified multi-episode show)", False),
    (lambda k: "chat" in L(k), "Telegram group chat — multi-author crypto/DAO community (id -1003779381054)", False),
    (lambda k: "cyrillic" in L(k), "External source (Cyrillic title corrupted on import — exact channel unrecoverable)", True),
]

def resolve(key):
    for pred, author, corrupt in NEW:
        if pred(key):
            return author, corrupt
    return None, False

def fm_split(text):
    m = re.match(r"^(---\r?\n)(.*?)(\r?\n---\r?\n)(.*)$", text, re.DOTALL)
    return list(m.groups()) if m else None

def setk(fm, key, val):
    if re.search(rf"(?m)^{key}:", fm):
        return re.sub(rf"(?m)^{key}:.*$", f"{key}: {val}", fm, count=1)
    return fm + f"\n{key}: {val}"

def insert_after(fm, anchor, newkey, val):
    if re.search(rf"(?m)^{newkey}:", fm):
        return setk(fm, newkey, val)
    if re.search(rf"(?m)^{anchor}:", fm):
        return re.sub(rf"(?m)^({anchor}:.*$)", lambda m: m.group(1) + f"\n{newkey}: {val}", fm, count=1)
    return fm + f"\n{newkey}: {val}"

def remove_key(fm, key):
    return re.sub(rf"(?m)^{key}:.*$\n?", "", fm)

resolved = collections.Counter(); still = collections.Counter(); ab = 0
for p in ROOT.rglob("*.md"):
    rel = str(p.relative_to(VAULT))
    if "dialogues_export" in rel or "dialogues_work_acct_b" in rel:
        continue
    try:
        with open(p, "rb") as f:
            head = f.read(3500).decode("utf-8", "ignore")
    except Exception:
        continue
    if not re.search(r"(?m)^author_status:\s*needs-review", head):
        continue
    parent = getk(head, "parent"); title = getk(head, "title")
    key = re.sub(r"^\[\[|\]\]$", "", parent).split("|")[0].strip() if parent else clean_series(title)
    author, corrupt = resolve(key)
    if not author:
        still[key[:24]] += 1
        continue
    typ = getk(head, "type")
    text = p.read_text(encoding="utf-8")
    parts = fm_split(text)
    if not parts:
        continue
    pre, fm, mid, body = parts
    fm = insert_after(fm, "origin", "author", f'"{author}"')
    if corrupt:
        fm = setk(fm, "author_status", "title-corrupted")
        fm = remove_key(fm, "author_review_hint")
    else:
        fm = remove_key(fm, "author_status")
        fm = remove_key(fm, "author_review_hint")
        if typ in ("transcript-episode", "transcription", "transcript") and getk(fm, "authored_by") == "ai":
            fm = setk(fm, "authored_by", "human")
            fm = insert_after(fm, "authored_by", "transcribed_by", "ai")
            ab += 1
    resolved[author] += 1
    if APPLY:
        p.write_text(pre + fm + mid + body, encoding="utf-8")

rep = [f"MODE: {'APPLY' if APPLY else 'DRY-RUN'}",
       f"resolved: {sum(resolved.values())}  ab_fixed: {ab}",
       f"still needs-review: {sum(still.values())}  -> {dict(still)}", "",
       "## resolved authors:"]
for a, c in resolved.most_common():
    rep.append(f"  {c:5d}  {a}")
(OUT / "stamp_authors2_report.txt").write_text("\n".join(rep), encoding="utf-8")
print("MODE", "APPLY" if APPLY else "DRY-RUN", "resolved", sum(resolved.values()),
      "ab", ab, "still", sum(still.values()), "stillkeys", dict(still))
