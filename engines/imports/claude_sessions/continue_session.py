#!/usr/bin/env python3
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
continue_session.py - "continue an old conversation as a NEW session" (Anton 2026-06-23).

Native --resume/fork of a foreign session does NOT work (proven: post-v2.1.9 rejects it).
So the reliable way to continue = start a brand-new NATIVE session pre-loaded with the old
history. This tool builds a seed (the full conversation + a "continue from here" instruction),
copies it to the CLIPBOARD, and writes a .seed.md. Then: open "New session" and paste (Ctrl+V).
Works on ANY machine (the MD is synced via the vault).

Usage: python continue_session.py <cliSessionId>
"""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os, sys, glob, json, subprocess
from export_md import conversation_text, iter_sources

VAULT_ROOT = os.environ.get("CLAUDE_VAULT_ROOT", r"%VAULT%")
SEEDDIR = os.path.join(VAULT_ROOT, "_Dashboards", "sessions-md", "_continue")
ARCHIVE = os.path.join(VAULT_ROOT, "_session-archive")
INBOUND = os.path.join(VAULT_ROOT, "_machine-bus", "_session-archive-inbound")
MAX = 120_000  # char cap for the seed; longer sessions keep the tail (full text stays in catalog)

def find_transcript(cli):
    for p, _ in iter_sources():
        if os.path.basename(p).startswith(cli):
            return p
    return None

def _service_clis():
    """cliSessionIds flagged service/robot across all catalogs (reuses the canonical classifier)."""
    svc = set()
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from session_archive import session_author
        cats = glob.glob(os.path.join(ARCHIVE, "catalog-*.json"))
        cats += glob.glob(os.path.join(INBOUND, "*", "catalog-*.json"))
        cats = [c for c in cats if ".sync-conflict-" not in c]  # drop Syncthing conflict copies — see session_archive.catalog_jsons
        for cf in cats:
            try:
                for r in json.load(open(cf, encoding="utf-8")):
                    if session_author(r)[1]:
                        svc.add(r.get("cliSessionId"))
            except Exception:
                pass
    except Exception:
        pass
    return svc

def latest_human_cli():
    """Most-recent HUMAN session transcript (live projects + archive), service excluded."""
    svc = _service_clis()
    best, best_mt = None, -1
    for p, _ in iter_sources():
        cli = os.path.splitext(os.path.basename(p))[0]
        if cli in svc:
            continue
        try:
            mt = os.path.getmtime(p)
        except Exception:
            continue
        if mt > best_mt:
            best, best_mt = cli, mt
    return best

def main():
    cli = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    if not cli and "--last" in sys.argv:
        cli = latest_human_cli()
        if cli:
            print("last human session:", cli)
    if not cli:
        print("usage: python continue_session.py <cliSessionId> | --last"); return
    path = find_transcript(cli)
    if not path:
        print("transcript not found for", cli); return
    convo = conversation_text(path)
    if not convo.strip():
        print("session has no text content"); return
    note = ""
    if len(convo) > MAX:
        convo = "...[начало обрезано, полный текст в каталоге]...\n\n" + convo[-MAX:]
        note = " (история длинная — вложен хвост; полностью в catalog.html)"
    seed = ("Ниже — ПОЛНАЯ история моего прошлого разговора с тобой (Claude) из другой сессии"
            f"{note}. Прочитай её и продолжай с того места, где мы остановились, "
            "как будто это та же беседа. Не пересказывай — просто продолжаем.\n\n"
            "========== ПРОШЛЫЙ РАЗГОВОР ==========\n\n" + convo +
            "\n\n========== КОНЕЦ ИСТОРИИ — ПРОДОЛЖАЙ ОТСЮДА ==========\n")
    os.makedirs(SEEDDIR, exist_ok=True)
    seedfile = os.path.join(SEEDDIR, f"{cli}.seed.md")
    open(seedfile, "w", encoding="utf-8").write(seed)
    # copy to clipboard (PowerShell Set-Clipboard handles unicode)
    copied = False
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Content -Raw -Encoding UTF8 -LiteralPath '{seedfile}' | Set-Clipboard"],
                       check=True, timeout=30)
        copied = True
    except Exception as e:
        print("clipboard copy failed:", e)
    print("seed written:", seedfile)
    print("clipboard:", "OK" if copied else "FAILED (open the .seed.md and copy manually)")
    print(">> Открой в Claude 'New session' и вставь (Ctrl+V) — разговор продолжится.")

if __name__ == "__main__":
    main()
