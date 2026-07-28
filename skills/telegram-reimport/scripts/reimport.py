# -*- coding: utf-8 -*-
"""
telegram-reimport dispatcher.

Safe-by-default incremental re-import of an already-imported Telegram chat.
  DRY RUN (default): detect source, print plan + current vault counts, verify parser is override-ready.
  --apply:           run the deterministic parse/generate steps into STAGING (vault untouched),
                     diff staging vs vault, print the exact robocopy merge command + LLM hand-off.
  (merge):           the human runs the printed robocopy line after eyeballing the staging diff.

ASCII-only stdout (cp1252 safety). Parsers read the export path from env TG_EXPORT (set here).
Run with PYTHONUTF8=1.
"""
import os, sys, json, argparse, subprocess
from pathlib import Path

IMPORTS = Path(r"%IMPORTS%")
VAULT   = Path(r"%VAULT%")

SOURCES = {
    "pokupki": {
        "needs": "result.json", "detect": ["покупки", "pokupki", "approve assistant"],
        "parser": "parse_pokupki.py",
        "steps": ["parse_pokupki.py", "generate_pokupki.py", "validate_pokupki_staging.py"],
        "staging": "staging_pokupki/01-Conversations/Telegram/Pokupki",
        "vault": "01-Conversations/Telegram/Pokupki", "subdirs": ["sessions", "posts"],
        "post_merge": ["APPLY=1 python dedup_pokupki_apply.py  (collapse body-hash dups, incl. re-surfaced -2 collision stems)",
                       "python fix_repoint_pokupki.py  (repoint links after dedup)"],
        "diff_note": "NEW posts is a PRE-DEDUP upper bound: generate reproduces 5295 posts but the vault holds the deduped 5223. The post-merge dedup collapses the re-surfaced duplicates, so the true new-post count is lower than shown.",
        "llm_next": "map_concepts_pokupki.py + concept batches for NEW posts; build_rules_pokupki.py for NEW pins; build_moc_pokupki.py; then refresh build_pokupki_dashboard.py.",
    },
    "assistants-ops": {
        "needs": "messages*.html", "detect": ["all assistant", "tasks 777", "assistant's tasks"],
        "parser": "parse_assistants_ops.py", "steps": ["parse_assistants_ops.py"],
        "staging": "staging/01-Conversations/Telegram/Assistants-Ops",
        "vault": "01-Conversations/Telegram/Assistants-Ops", "subdirs": ["sessions"],
        "llm_next": "curate NEW rule_candidates.json -> build_rules2.py (guarded); dedup statement-hash vs existing reglament-*.",
    },
    "arhiv-golosa": {
        "needs": "messages*.html", "detect": ["arhiv", "golosa", "голоса", "content team"],
        "parser": "parse_telegram.py",
        "steps": ["parse_telegram.py", "triage_telegram.py", "generate_obsidian.py", "dedup_posts.py", "build_moc.py"],
        "staging": "staging/01-Conversations/Telegram/Arhiv-Golosa",
        "vault": "01-Conversations/Telegram/Arhiv-Golosa", "subdirs": ["posts", "sessions"],
        "llm_next": "(none - fully deterministic; optionally refresh concept links for new posts).",
    },
    "faaa": {
        "needs": "result.json", "detect": ["faaa", "calls", "follow up", "итоги звонков"],
        "parser": "parse_faaa.py", "steps": ["parse_faaa.py"],
        "staging": None, "vault": "04-Projects/crypto/Platinum-CRM", "subdirs": ["leads"],
        "llm_next": "batched synthesis workflow -> render_cards.py -> build_ledgers.py -> build_crm_moc.py; union new calls into existing leads by @handle/name.",
    },
}


def p(*a):
    print(" ".join(str(x) for x in a).encode("ascii", "replace").decode("ascii"))


def detect(export: Path):
    rj = export / "result.json"
    if rj.exists():
        try:
            name = (json.loads(rj.read_text(encoding="utf-8")).get("name") or "").lower()
        except Exception:
            name = ""
        for key, cfg in SOURCES.items():
            if cfg["needs"] == "result.json" and any(d in name for d in cfg["detect"]):
                return key, name
        return None, name
    # html-only export: sniff the first page header
    htmls = sorted(export.glob("messages*.html"))
    if htmls:
        head = htmls[0].read_text(encoding="utf-8", errors="replace")[:6000].lower()
        for key, cfg in SOURCES.items():
            if cfg["needs"].endswith("html") and any(d in head for d in cfg["detect"]):
                return key, "(from html header)"
    return None, ""


def count_md(d: Path, recursive=False):
    if not d.exists():
        return 0
    return len(list(d.glob("**/*.md" if recursive else "*.md")))


def vault_counts(cfg):
    base = VAULT / cfg["vault"]
    out = {}
    for sd in cfg["subdirs"]:
        out[sd] = count_md(base / sd, recursive=(sd == "leads"))
    return out


def staging_diff(cfg):
    if not cfg["staging"]:
        return None
    st = IMPORTS / cfg["staging"]
    vb = VAULT / cfg["vault"]
    diff = {}
    for sd in cfg["subdirs"]:
        s = {f.name for f in (st / sd).glob("*.md")} if (st / sd).exists() else set()
        v = {f.name for f in (vb / sd).glob("*.md")} if (vb / sd).exists() else set()
        diff[sd] = {"staging": len(s), "vault": len(v), "new": sorted(s - v)}
    return diff


def parser_overridable(cfg):
    pf = IMPORTS / cfg["parser"]
    return pf.exists() and "TG_EXPORT" in pf.read_text(encoding="utf-8", errors="replace")


def archive_export(export: Path, key: str):
    """Rule 0 / Step 0 — preserve the raw export VERBATIM before parsing. Copy-only, never deletes."""
    ar = IMPORTS / "archive_original.py"
    if not ar.exists():
        p("  ! archive_original.py missing in _imports - create it (Rule 0) before re-importing.")
        return False
    r = subprocess.run([sys.executable, str(ar), str(export), "--source", key,
                        "--label", "telegram-reimport " + export.name],
                       cwd=str(IMPORTS), env=dict(os.environ, PYTHONUTF8="1"),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for ln in (r.stdout or "").strip().splitlines():
        p("  ", ln)
    if r.returncode != 0:
        p("  ! archive FAILED rc=", r.returncode, "(stderr tail):")
        for ln in (r.stderr or "").strip().splitlines()[-6:]:
            p("    ", ln)
        return False
    return True


def run_steps(cfg, export: Path):
    env = dict(os.environ, TG_EXPORT=str(export), PYTHONUTF8="1")
    for script in cfg["steps"]:
        sp = IMPORTS / script
        if not sp.exists():
            p("  ! missing script, stop:", script); return False
        p("  > running", script, "...")
        r = subprocess.run([sys.executable, str(sp)], cwd=str(IMPORTS), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout or "").strip().splitlines()[-2:]
        for ln in tail:
            p("    ", ln)
        if r.returncode != 0:
            p("  ! FAILED rc=", r.returncode, "stderr tail:")
            for ln in (r.stderr or "").strip().splitlines()[-6:]:
                p("    ", ln)
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True, help="path to the fresh Telegram export FOLDER")
    ap.add_argument("--source", default="auto", choices=["auto"] + list(SOURCES))
    ap.add_argument("--apply", action="store_true", help="run parse/generate into staging (vault untouched)")
    ap.add_argument("--no-archive", action="store_true",
                    help="skip the Rule 0 verbatim archive of the export (NOT recommended)")
    args = ap.parse_args()

    export = Path(args.export)
    if not export.exists():
        p("ERROR export folder not found:", export); sys.exit(2)

    key = args.source
    if key == "auto":
        key, name = detect(export)
        if not key:
            p("Could not auto-detect the chat (name:", repr(name) + ").")
            p("Re-run with --source one of:", ", ".join(SOURCES)); sys.exit(2)
    cfg = SOURCES[key]
    p("=" * 60)
    p("SOURCE:", key, "  EXPORT:", export.name)
    p("vault home:", cfg["vault"])
    p("plan (deterministic):", " -> ".join(cfg["steps"]))
    ok = parser_overridable(cfg)
    p("parser honors TG_EXPORT:", "YES" if ok else "NO  (re-import would read the OLD export!)")
    vc = vault_counts(cfg)
    p("current vault:", ", ".join(f"{k}={v}" for k, v in vc.items()))

    # STEP 0 (Rule 0): preserve the raw export verbatim BEFORE anything else. Runs on dry-run too,
    # because the original may vanish from Downloads/Telegram Desktop before --apply. Idempotent.
    if not args.no_archive:
        p("-" * 60)
        p("STEP 0 - ARCHIVE ORIGINAL (verbatim copy to _originals, never deleted):")
        if not archive_export(export, key):
            p("ABORT: could not preserve the original. Fix the archive step before importing."); sys.exit(1)
    else:
        p("(--no-archive: skipping the Rule 0 verbatim archive of the export -- NOT recommended)")

    if not args.apply:
        p("-" * 60)
        p("DRY RUN only. Re-run with --apply to build into staging (vault stays untouched).")
        p("LLM next after merge:", cfg["llm_next"])
        return

    if not ok:
        p("ABORT --apply: parser not override-ready; patch it to read TG_EXPORT first."); sys.exit(2)
    p("-" * 60); p("APPLY: building into staging (vault untouched)...")
    if not run_steps(cfg, export):
        p("Stopped on error. Vault not modified."); sys.exit(1)

    diff = staging_diff(cfg)
    p("-" * 60)
    if diff is None:
        p("Source", key, "writes directly (no simple staging merge) - hand off to the LLM workflow:")
        p("  ", cfg["llm_next"]); return
    total_new = 0
    for sd, d in diff.items():
        total_new += len(d["new"])
        p(f"  {sd}: staging={d['staging']} vault={d['vault']} NEW={len(d['new'])}")
        for nm in d["new"][:8]:
            p("      +", nm)
        if len(d["new"]) > 8:
            p("      + ...", len(d["new"]) - 8, "more")
    p("-" * 60)
    p("TOTAL NEW files:", total_new)
    if cfg.get("diff_note"):
        p("NOTE:", cfg["diff_note"])
    if total_new:
        st = IMPORTS / cfg["staging"]
        vb = VAULT / cfg["vault"]
        p("To MERGE (adds new files only, never overwrites/deletes):")
        p(f'  robocopy "{st}" "{vb}" /E /XC /XN /XO')
        if cfg.get("post_merge"):
            p("Then deterministic reconcile (post-merge, in E:\\Obsidian\\_imports):")
            for step in cfg["post_merge"]:
                p("   ", step)
        p("Then LLM curation for the new items:")
        p("  ", cfg["llm_next"])
    else:
        p("Nothing new - vault already up to date.")


if __name__ == "__main__":
    main()
