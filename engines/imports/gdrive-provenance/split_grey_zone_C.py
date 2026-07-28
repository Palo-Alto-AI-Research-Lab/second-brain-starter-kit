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
Schema C — split the grey zone (origin: gdrive-personal-mixed) into:
  - anton          : Anton's OWN authorship (his CV, PLATINUM FRAMEWORK, his pitch docs, his call-notes)
  - personal-docs  : documents ABOUT/belonging to Anton but authored by a counterparty
                     (visas, taxes, bank, contracts, KYC, passports, invoices) — NOT his authorship
  - external       : clearly someone else's (other projects' tokenomics, "Copy of <other>")
  - (left as mixed): genuinely ambiguous — honest, untouched

CONSERVATIVE on `anton`: mislabelling someone-else's as Anton's violates his #1 rule
("не вешай на меня то что Я НЕ ПИСАЛ"). When unsure, prefer personal-docs or leave mixed.

Only touches files currently `origin: gdrive-personal-mixed` (the B-pass neutral bucket).
Deterministic, 0 LLM tokens. Dry-run default; APPLY=1 to write. Idempotent.
Adds `provenance_split_c: 2026-06-13`.
"""
from __future__ import annotations
import os, re
from pathlib import Path
from collections import Counter

APPLY = os.environ.get("APPLY") == "1"
ROOTS = [
    r"%VAULT%\05-Resources\GDrive-Personal",
    r"%VAULT_ROOT%\_originals\gdrive-personal-archive",
]
GREY = "gdrive-personal-mixed"
STAMP = "provenance_split_c: 2026-06-13"

ANTON_RX = re.compile(r"anton|dziatkov|dzyatkov|дзятковск|дзятковсь|антон дзятк", re.I)
FM_BOUNDS = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)

# --- ANTON: his own authorship (CONSERVATIVE — needs a strong signal) ---
ANTON_DOC_RX = re.compile(
    r"platinum framework|"
    r"autonomous ai agents launchpad|l3 swarm|ai agents palo alto|"
    r"\bcanton research\b|aaa autonomous|"
    r"мысли по фандрейзу|мысли по |"
    r"резюме звонка|резюме .*звонка|"  # his call summaries (NOT a candidate CV)
    r"скрипт по работе с амбассадорами|контент hr",
    re.I)
# his self-presentation CV: must carry his name
ANTON_CV_RX = re.compile(r"(cv|resume|резюме|self.present).*", re.I)

# --- PERSONAL-DOCS: about Anton, authored by a counterparty ---
PERSONAL_FOLDER_RX = re.compile(
    r"1 visas|traveliving|! _ photo docs|5 accounting|! _ legal registered|"
    r"cars & financing|3-1 real estate|недвижимост|5 otc|81 avia|equity fundraising",
    re.I)
PERSONAL_NAME_RX = re.compile(
    r"\binvoice\b|\btax\b|налог|earnings statement|pay stub|\bkyc\b|passport|паспорт|"
    r"reference letter|rental|mortgage|\bloan\b|bank acc|выписк|notice to vacate|"
    r"residence|\bvisa\b|\bвиза\b|scholarship guidelines|criteria unfolded|"
    r"purchase and sale agreement|window.installation|dogovor_okna|furniture return|"
    r"inventory casa|employment contract|income amount|restricted unit agreement|"
    r"taxes payable|expense-reimbursement|декларац",
    re.I)

# --- EXTERNAL: clearly other people's projects (narrow, safe) ---
EXTERNAL_RX = re.compile(
    r"eesee tokenomics|dechat|secret pad tokenomics|gotbit|"
    r"копия инфлюенсеры|сидус|sidus clients|umoja web3|guild of heroes|"
    r"humanity protocol|tiktok emails|выгрузка crm",
    re.I)

def get_field(fm, name):
    m = re.search(rf"^{name}:\s*\"?(.+?)\"?\s*$", fm, re.M)
    return m.group(1) if m else None

def classify(source_path: str, filename: str, title: str):
    """Return (new_origin, extra_author_or_None, rule) or (None, None, None) to leave mixed."""
    hay = f"{source_path}\n{filename}\n{title}"
    is_anton = bool(ANTON_RX.search(hay))

    # 1) ANTON authorship — strong signals only
    if ANTON_DOC_RX.search(hay):
        return "anton", None, "anton-doc"
    if is_anton and ANTON_CV_RX.search(hay):
        return "anton", None, "anton-cv"

    # 2) EXTERNAL — other projects (but never if Anton's own name dominates a personal doc)
    if EXTERNAL_RX.search(hay) and not is_anton:
        return "external", "needs-review", "external-project"

    # 3) PERSONAL-DOCS — his documents, counterparty-authored
    if PERSONAL_FOLDER_RX.search(hay) or PERSONAL_NAME_RX.search(hay):
        return "personal-docs", None, "personal-doc"

    # 4) leave as mixed
    return None, None, None

def process(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "skip", None
    mb = FM_BOUNDS.search(text)
    if not mb:
        return "skip", None
    fm = mb.group(1)
    if get_field(fm, "origin") != GREY:
        return "skip", None
    sp = get_field(fm, "source_path") or ""
    title = get_field(fm, "title") or ""
    new_origin, author, rule = classify(sp, path.name, title)
    if not new_origin:
        return "mixed-kept", None
    new_fm = re.sub(r"^origin:.*$", f"origin: {new_origin}", fm, count=1, flags=re.M)
    if author and not get_field(new_fm, "author"):
        new_fm += f'\nauthor: "{author}"'
    if "provenance_split_c:" not in new_fm:
        new_fm += f"\n{STAMP}"
    if APPLY:
        path.write_text(text[:mb.start(1)] + new_fm + text[mb.end(1):], encoding="utf-8")
    return new_origin, rule

def main():
    counts = Counter(); rules = Counter()
    anton_samples = []; pd_samples = []
    for root in ROOTS:
        if not os.path.isdir(root): continue
        for r, _, fs in os.walk(root):
            for fn in fs:
                if not fn.endswith(".md"): continue
                p = Path(r) / fn
                res, rule = process(p)
                counts[res] += 1
                if rule: rules[rule] += 1
                if res == "anton" and len(anton_samples) < 25:
                    anton_samples.append((rule, p.name))
                if res == "personal-docs" and len(pd_samples) < 12:
                    pd_samples.append((rule, p.name))
    mode = "APPLY" if APPLY else "DRY-RUN"
    lines = [f"=== schema C grey-zone split [{mode}] ==="]
    for k in ("anton","personal-docs","external","mixed-kept","skip"):
        lines.append(f"  {counts[k]:>6}  {k}")
    lines.append("\n  by rule:")
    for rl,n in rules.most_common(): lines.append(f"    {n:>5}  {rl}")
    lines.append("\n  ANTON samples (REVIEW for false-positives):")
    for rl,nm in anton_samples: lines.append(f"    [{rl:10}] {nm}")
    lines.append("\n  personal-docs samples:")
    for rl,nm in pd_samples: lines.append(f"    [{rl:12}] {nm}")
    Path(r"%IMPORTS%\gdrive-provenance\_split_c_report.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"[{mode}] anton={counts['anton']} personal-docs={counts['personal-docs']} "
          f"external={counts['external']} mixed-kept={counts['mixed-kept']} "
          f"-> report: _split_c_report.txt")

if __name__ == "__main__":
    main()
