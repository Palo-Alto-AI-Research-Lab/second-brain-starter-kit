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
"""Deterministic pre-analysis of the Apple Notes export (0 LLM tokens).

Reads notes_export.json, produces:
  - analysis.json        (machine: per-note records + flags)
  - analysis_report.md   (human, UTF-8)
  - vault_context.json   (existing concept-*/person-* basenames + canonical tags for triage agents)
Stdout stays ASCII-only (counts).
"""
import json, re, hashlib, unicodedata
from pathlib import Path
from collections import Counter

EXPORT = Path(r"E:\Google Drive on HP Palo Alto\!_Claude_Mac16\Apple Notes Export 2026-06-11")
VAULT = Path(r"%VAULT%")
OUT = Path(r"%IMPORTS%\apple-notes")
OUT.mkdir(parents=True, exist_ok=True)

data = json.loads((EXPORT / "notes_export.json").read_text(encoding="utf-8"))
notes = data["notes"]

# ---------- helpers ----------
TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
    'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}
def translit(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch in TRANSLIT: out.append(TRANSLIT[ch])
        else: out.append(ch)
    s = ''.join(out)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if ord(c) < 128)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    s = re.sub(r'-{2,}', '-', s)
    return s[:60].strip('-') or 'untitled'

def body_of(md: str, title: str) -> str:
    """Markdown body minus the leading # title line."""
    lines = md.splitlines()
    if lines and lines[0].lstrip().startswith('#'):
        lines = lines[1:]
    return '\n'.join(lines).strip()

def norm_hash(text: str) -> str:
    t = re.sub(r'\s+', ' ', text).strip().lower()
    return hashlib.sha256(t.encode('utf-8')).hexdigest()[:16]

# secret patterns (deterministic, conservative)
SECRET_PATTERNS = [
    ("password-word", re.compile(r'(?i)(парол|password|passwd|пин.?код|pin.?code)')),
    ("apple-id", re.compile(r'(?i)apple\s*id')),
    ("priv-key-hex", re.compile(r'\b(0x)?[0-9a-fA-F]{64}\b')),
    ("strong-token", re.compile(r'\b(?=\S*[a-z])(?=\S*[A-Z])(?=\S*\d)(?=\S*[!@#$%^&*])\S{8,}\b')),
    ("seed-phrase", re.compile(r'(?i)\b(seed|mnemonic|сид.?фраза|мнемоник)')),
    ("login-pair", re.compile(r'(?i)(логин|login)\s*[:\-]')),
    ("card-number", re.compile(r'\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}\b')),
]

CYR = re.compile(r'[а-яёА-ЯЁ]')
LAT = re.compile(r'[a-zA-Z]')

# ---------- vault context (for slug collisions + triage agents) ----------
concepts = sorted(p.stem for p in (VAULT / "06-Concepts").glob("concept-*.md"))
people = sorted(p.stem for p in (VAULT / "07-People").glob("person-*.md"))
vault_basenames = set()
for p in VAULT.rglob("*.md"):
    vault_basenames.add(p.stem.lower())

# ---------- per-note analysis ----------
recs, hash_map = [], {}
slug_seen = Counter()
for i, n in enumerate(notes):
    title = n.get("title") or "Untitled"
    md = n.get("markdown") or ""
    body = body_of(md, title)
    created = (n.get("created") or "")[:10]
    modified = (n.get("modified") or "")[:10]
    n_att = len(n.get("attachments") or [])
    blen = len(body)
    cyr = len(CYR.findall(body + title)); lat = len(LAT.findall(body + title))
    lang = "ru" if cyr >= lat else ("en" if lat > 0 else "none")
    h = norm_hash(body) if blen >= 20 else None
    dup_of = None
    if h:
        if h in hash_map: dup_of = hash_map[h]
        else: hash_map[h] = i
    secrets = sorted({name for name, rx in SECRET_PATTERNS if rx.search(md) or rx.search(title)})
    # base slug: created-date + translit title
    date_prefix = created if created else "0000-00-00"
    s = translit(title)
    slug = f"{date_prefix}-{s}"
    slug_seen[slug] += 1
    if slug_seen[slug] > 1:
        slug = f"{slug}-{slug_seen[slug]}"
    stub = blen < 30 and n_att == 0
    title_in_vault = title.lower().strip() in vault_basenames or s in vault_basenames
    recs.append({
        "idx": i, "title": title, "created": created, "modified": modified,
        "folder": n.get("folder"), "file": n.get("markdown_file"),
        "attachments": n_att, "body_len": blen, "lang": lang,
        "hash": h, "dup_of": dup_of, "secrets": secrets, "stub": stub,
        "slug": slug, "title_in_vault": title_in_vault,
    })

# ---------- aggregates ----------
years = Counter(r["created"][:4] for r in recs if r["created"])
langs = Counter(r["lang"] for r in recs)
dups = [r for r in recs if r["dup_of"] is not None]
stubs = [r for r in recs if r["stub"]]
secret_notes = [r for r in recs if r["secrets"]]
collisions = [r for r in recs if r["title_in_vault"]]
sizes = sorted(r["body_len"] for r in recs)
def pct(p): return sizes[int(len(sizes)*p)]

summary = {
    "total": len(recs), "years": dict(sorted(years.items())), "langs": dict(langs),
    "exact_dups": len(dups), "stubs": len(stubs), "secret_flagged": len(secret_notes),
    "vault_title_collisions": len(collisions),
    "body_len_p50": pct(.5), "body_len_p90": pct(.9), "body_len_max": sizes[-1],
    "with_attachments": sum(1 for r in recs if r["attachments"]),
}

(OUT / "analysis.json").write_text(json.dumps({"summary": summary, "notes": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "vault_context.json").write_text(json.dumps({"concepts": concepts, "people": people}, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- human report ----------
L = []
L.append("# Apple Notes export — deterministic analysis\n")
L.append(f"Total notes: **{summary['total']}** · attachments-bearing: {summary['with_attachments']} · exact dups: {len(dups)} · stubs(<30ch): {len(stubs)} · secret-flagged: {len(secret_notes)} · vault title collisions: {len(collisions)}\n")
L.append("## By year (created)\n")
for y, c in sorted(years.items()): L.append(f"- {y}: {c}")
L.append(f"\nLanguages: {dict(langs)} · body length p50={summary['body_len_p50']} p90={summary['body_len_p90']} max={summary['body_len_max']}\n")
L.append("## Secret-flagged notes (candidates for quarantine — review)\n")
for r in secret_notes:
    L.append(f"- [{r['idx']}] «{r['title'][:70]}» ({r['created']}, {r['body_len']}ch) → {', '.join(r['secrets'])}")
L.append("\n## Exact duplicates (same normalized body)\n")
for r in dups:
    orig = recs[r["dup_of"]]
    L.append(f"- [{r['idx']}] «{r['title'][:50]}» == [{orig['idx']}] «{orig['title'][:50]}»")
L.append("\n## Title collisions with existing vault files\n")
for r in collisions:
    L.append(f"- [{r['idx']}] «{r['title'][:70]}» ({r['created']})")
L.append("\n## Stubs (title-only, no attachments)\n")
for r in stubs:
    L.append(f"- [{r['idx']}] «{r['title'][:70]}» ({r['created']})")
(OUT / "analysis_report.md").write_text('\n'.join(L), encoding="utf-8")

print("TOTAL:", summary["total"])
print("DUPS:", len(dups), " STUBS:", len(stubs), " SECRETS:", len(secret_notes), " COLLISIONS:", len(collisions))
print("YEARS:", ",".join(f"{y}:{c}" for y, c in sorted(years.items())))
print("LANGS:", ",".join(f"{k}:{v}" for k, v in langs.items()))
print("CONCEPTS:", len(concepts), " PEOPLE:", len(people))
print("OK")
