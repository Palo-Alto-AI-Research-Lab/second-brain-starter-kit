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
"""Token-optimal step 3: stamp author: on external transcript notes via a curated
series->author map (built from the 89-unique-series list, 0 LLM calls). Unknown /
wrong-direction-risk series -> author_status: needs-review (never guessed).
Also: episodes/transcriptions authored_by: ai -> human + transcribed_by: ai
(the words are the blogger's; AI only transcribed). DRY default; APPLY=1 writes.
Stdout ASCII; report UTF-8."""
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
    t = re.sub(r"\s*-\s*US$", "", t)
    return t.strip() or title.strip()

L = str.lower
RULES = [
    (lambda k: k.startswith("Huberman"), "Andrew Huberman — Huberman Lab podcast"),
    (lambda k: L(k).startswith("beloveshkin"), "Андрей Беловешкин (Andrey Beloveshkin)"),
    (lambda k: "Randall Carlson" in k, "Randall Carlson"),
    (lambda k: k.startswith("BrienFoerster"), "Brien Foerster"),
    (lambda k: k.startswith("The Joe Rogan Experience"), "Joe Rogan — The Joe Rogan Experience"),
    (lambda k: "Michael Levin" in k, "Michael Levin (interview series)"),
    (lambda k: k == "deeplearningAI", "DeepLearning.AI (Andrew Ng)"),
    (lambda k: k == "MauroBiglino", "Mauro Biglino"),
    (lambda k: L(k).startswith("vladimir masterov"), "Vladimir Masterov"),
    (lambda k: k.startswith("роман кауфман"), "Роман Кауфман (Roman Kaufman)"),
    (lambda k: k.startswith("Sergey Ignatenko"), "Sergey Ignatenko"),
    (lambda k: k == "fuckbiohacking" or "Kasparov" in k or "fuck biohacking" in L(k), "Вадим Каспаров — «Fuck Biohacking»"),
    (lambda k: k == "Old World Exploration", "Old World Exploration (YouTube)"),
    (lambda k: L(k).startswith("mind unveiled"), "Mind Unveiled (YouTube)"),
    (lambda k: k == "No horizon", "No Horizon (YouTube)"),
    (lambda k: k == "JonLevi", "JonLevi (YouTube)"),
    (lambda k: k == "HiddenRabbit", "Hidden Rabbit (YouTube)"),
    (lambda k: k == "vita dao", "VitaDAO (longevity DAO)"),
    (lambda k: k == "Molecule", "Molecule (DeSci)"),
    (lambda k: k == "Lifespan Research Institute", "Lifespan Research Institute"),
    (lambda k: k == "pump.science", "pump.science (DeSci)"),
    (lambda k: k == "Bankless", "Bankless (Ryan Sean Adams & David Hoffman)"),
    (lambda k: k == "Cryptoinside", "Cryptoinside (channel)"),
    (lambda k: k == "thirdEyeDrops", "Third Eye Drops (Michael Phillip)"),
    (lambda k: L(k).startswith("lobster"), "LobsterDAO (community)"),
    (lambda k: k.startswith("Говорит Атеист"), "«Говорит Атеист» (channel)"),
    (lambda k: k.startswith("Просветъ"), "«Просветъ» (channel)"),
]
# wrong-direction-risk -> explicit review hint
RISK = {"my lunch Break": "verify if ANTON'S OWN voice note -> may be origin: mixed/anton",
        "chat_": "Telegram GROUP chat (multi-author) -> verify if Anton participates -> may be mixed"}

def resolve(key):
    for pred, author in RULES:
        if pred(key):
            return author, None
    for risk_k, hint in RISK.items():
        if key.startswith(risk_k) or risk_k in key:
            return None, hint
    return None, f"unidentified source: '{key[:40]}'"

def fm_split(text):
    m = re.match(r"^(---\r?\n)(.*?)(\r?\n---\r?\n)(.*)$", text, re.DOTALL)
    return list(m.groups()) if m else None

def insert_after(fm, anchor, newkey, val):
    if re.search(rf"(?m)^{newkey}:", fm):
        return re.sub(rf"(?m)^{newkey}:.*$", f"{newkey}: {val}", fm, count=1)
    if re.search(rf"(?m)^{anchor}:", fm):
        return re.sub(rf"(?m)^({anchor}:.*$)", lambda m: m.group(1) + f"\n{newkey}: {val}", fm, count=1)
    return fm + f"\n{newkey}: {val}"

def setk(fm, key, val):
    if re.search(rf"(?m)^{key}:", fm):
        return re.sub(rf"(?m)^{key}:.*$", f"{key}: {val}", fm, count=1)
    return fm + f"\n{key}: {val}"

stamped = collections.Counter(); review = collections.Counter(); ab_fixed = 0; skipped = 0
for p in ROOT.rglob("*.md"):
    rel = str(p.relative_to(VAULT))
    if "dialogues_export" in rel or "dialogues_work_acct_b" in rel:
        continue
    try:
        with open(p, "rb") as f:
            head = f.read(3500).decode("utf-8", "ignore")
    except Exception:
        continue
    if getk(head, "origin") != "external":
        continue
    if re.search(r"(?m)^author:\s*\S", head) or re.search(r"(?m)^author_status:\s*needs-review", head):
        skipped += 1
        continue
    parent = getk(head, "parent"); title = getk(head, "title")
    key = re.sub(r"^\[\[|\]\]$", "", parent).split("|")[0].strip() if parent else clean_series(title)
    author, hint = resolve(key)
    typ = getk(head, "type")
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        continue
    parts = fm_split(text)
    if not parts:
        continue
    pre, fm, mid, body = parts
    if author:
        fm = insert_after(fm, "origin", "author", f'"{author}"')
        if typ in ("transcript-episode", "transcription", "transcript") and getk(fm, "authored_by") == "ai":
            fm = setk(fm, "authored_by", "human")
            fm = insert_after(fm, "authored_by", "transcribed_by", "ai")
            ab_fixed += 1
        stamped[author] += 1
    else:
        fm = insert_after(fm, "origin", "author_status", "needs-review")
        fm = insert_after(fm, "author_status", "author_review_hint", f'"{hint}"')
        review[key.split("_")[0][:24] or "(empty)"] += 1
    if APPLY:
        p.write_text(pre + fm + mid + body, encoding="utf-8")

rep = [f"MODE: {'APPLY' if APPLY else 'DRY-RUN'}",
       f"stamped author: {sum(stamped.values())}  (distinct authors {len(stamped)})",
       f"authored_by ai->human (+transcribed_by): {ab_fixed}",
       f"needs-review: {sum(review.values())}", f"skipped (already had author/status): {skipped}", "",
       "## authors stamped (count):"]
for a, c in stamped.most_common():
    rep.append(f"  {c:5d}  {a}")
rep.append("\n## needs-review series (count):")
for k, c in review.most_common():
    rep.append(f"  {c:5d}  {k}")
(OUT / "stamp_authors_report.txt").write_text("\n".join(rep), encoding="utf-8")
print("MODE", "APPLY" if APPLY else "DRY-RUN", "stamped", sum(stamped.values()),
      "ab_fixed", ab_fixed, "needs_review", sum(review.values()), "skipped", skipped)
