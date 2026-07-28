# -*- coding: utf-8 -*-
"""Systematic exact-duplicate detection across Telegram post files.
- body = text between frontmatter and '## See Also', whitespace-normalized
- exact dups (same hash) -> keep earliest by filename, delete rest, record remap
- near dups (same normalized first 300 chars, different hash) -> REPORT only
Writes dedup_report.json. Does NOT delete unless APPLY=1 env is set.
"""
import re, json, hashlib, os
from pathlib import Path
from collections import defaultdict

POSTS = Path(r"E:/Obsidian/Owner-Knowledge/01-Conversations/Telegram/Arhiv-Golosa/posts")
SESS = Path(r"E:/Obsidian/Owner-Knowledge/01-Conversations/Telegram/Arhiv-Golosa/sessions")
IMP = Path(r"E:/Obsidian/_imports")
APPLY = os.environ.get("APPLY") == "1"

def body_of(text):
    # strip frontmatter
    m = re.match(r'^---\n.*?\n---\n', text, re.DOTALL)
    if m:
        text = text[m.end():]
    text = text.split("## See Also")[0]
    return re.sub(r'\s+', ' ', text).strip()

posts = list(POSTS.glob("*.md"))
by_hash = defaultdict(list)
by_head = defaultdict(list)
for p in posts:
    b = body_of(p.read_text(encoding="utf-8"))
    if len(b) < 20:
        continue
    h = hashlib.md5(b.encode("utf-8")).hexdigest()
    by_hash[h].append(p.stem)
    by_head[b[:300]].append((p.stem, h))

exact = {h: sorted(v) for h, v in by_hash.items() if len(v) > 1}
# near = same head, but >1 distinct hash
near = []
for head, items in by_head.items():
    hashes = {h for _, h in items}
    if len(items) > 1 and len(hashes) > 1:
        near.append(sorted({s for s, _ in items}))

# build remap: keep first (earliest filename), delete rest
remap = {}
to_delete = []
for h, stems in exact.items():
    keeper = stems[0]
    for d in stems[1:]:
        remap[d] = keeper
        to_delete.append(d)

report = {
    "total_posts": len(posts),
    "exact_dup_groups": len(exact),
    "files_to_delete": len(to_delete),
    "near_dup_groups": len(near),
    "exact_groups_sample": list(exact.values())[:10],
    "near_groups_sample": near[:10],
    "remap": remap,
}
(IMP / "dedup_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

if APPLY and to_delete:
    # repoint session links deleted -> keeper, then delete
    sess_files = list(SESS.glob("*.md"))
    repointed = 0
    for sf in sess_files:
        t = sf.read_text(encoding="utf-8")
        orig = t
        for d, k in remap.items():
            t = t.replace(f"[[{d}|", f"[[{k}|").replace(f"[[{d}]]", f"[[{k}]]")
        if t != orig:
            sf.write_text(t, encoding="utf-8")
            repointed += 1
    for d in to_delete:
        f = POSTS / f"{d}.md"
        if f.exists():
            f.unlink()
    report["applied"] = True
    report["session_files_repointed"] = repointed
    (IMP / "dedup_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print("total_posts", len(posts))
print("exact_dup_groups", len(exact), "| files_to_delete", len(to_delete))
print("near_dup_groups", len(near))
print("APPLIED" if (APPLY and to_delete) else "DETECT-ONLY (set APPLY=1 to delete)")
