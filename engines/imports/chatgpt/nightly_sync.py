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
r"""nightly_sync.py - ORCHESTRATES the nightly ChatGPT -> vault pull, reusing the
existing single-source scripts (no logic duplication). 0 tokens, 0 LLM.

Chain:
  1) vault_backup.py            -- snapshot BEFORE any vault write (standing rule)
  2) incremental_pull.py CUTOFF -- pull only chats updated since CUTOFF -> raw zip
  3) chatgpt_export_to_vault.py -- zip -> STAGING notes (related_concepts: [])
  4) copy STAGING -> vault       -- ONLY if target absent OR not-yet-enriched
                                    (NEVER clobber concept-enriched notes)
  5) build_chatgpt_moc.py       -- rebuild the FULL vault MOC
  6) vault_backup.py            -- commit the new state

CUTOFF is computed from the newest note already in the vault (minus 1 day) so a
missed night never leaves a gap, regardless of PC downtime. Idempotent: notes are
keyed by conversation_id stub; re-pulling the same days overwrites only unenriched
notes. Exit nonzero on pull failure (token dead) -> vault goes stale -> the daily
freshness watchdog pings Anton (the assurance half).

The nightly Brain Reindex @04:00 picks up the new notes; no manual reindex here.
USAGE: python nightly_sync.py [--zip PATH]
       --zip = fold an ALREADY-PULLED zip (e.g. a --projects-only backfill from
       incremental_pull.py) through the same staging->vault->db->MOC steps, skipping
       the pull. Same idempotency guarantees.
"""
import os, sys, re, glob, shutil, sqlite3, subprocess, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable or "python"
VAULT_CONV = Path(r"E:/Obsidian/Owner-Knowledge/01-Conversations/ChatGPT/conversations")
STAGING_CONV = ROOT / "staging" / "01-Conversations" / "ChatGPT" / "conversations"
CANON_DB = ROOT / "chatgpt_conversations.db"
STAGING_DB = ROOT / "staging" / "01-Conversations" / "ChatGPT" / "chatgpt_conversations.db"
IMPORTS = ROOT.parent  # %IMPORTS%
DATE_RX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")


def run(label, args, cwd=None):
    # Force UTF-8 on every child so Cyrillic/emoji chat titles never crash a cp1252
    # console (incremental_pull.py prints titles). Robust regardless of launcher.
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    print("\n>>> %s: %s" % (label, " ".join(str(a) for a in args)), flush=True)
    rc = subprocess.run([str(a) for a in args], cwd=str(cwd) if cwd else None, env=env).returncode
    print("<<< %s rc=%d" % (label, rc), flush=True)
    return rc


def newest_vault_date():
    newest = None
    for p in VAULT_CONV.glob("*.md"):
        m = DATE_RX.match(p.name)
        if not m:
            continue
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if newest is None or d > newest:
            newest = d
    return newest


def main():
    zip_override = None
    if "--zip" in sys.argv:
        zip_override = Path(sys.argv[sys.argv.index("--zip") + 1])
        if not zip_override.exists():
            print("--zip %s does not exist" % zip_override, flush=True)
            sys.exit(2)

    today = datetime.date.today()
    newest = newest_vault_date()
    cutoff = (newest - datetime.timedelta(days=1)) if newest else (today - datetime.timedelta(days=7))
    print("=== nightly_sync %s | newest vault note=%s | cutoff=%s | zip_override=%s ===" % (
        datetime.datetime.now().isoformat(timespec="seconds"), newest, cutoff, zip_override), flush=True)

    # 1) backup BEFORE writes (standing rule; additive run, no deletes)
    run("backup-pre", [PY, IMPORTS / "vault_backup.py", "nightly chatgpt sync (pre)"], cwd=IMPORTS)

    if zip_override:
        zip_path = zip_override
    else:
        # 2) pull updated chats -> zip
        rc = run("pull", [PY, ROOT / "incremental_pull.py", cutoff.isoformat()], cwd=ROOT)
        if rc == 7:
            # SELF-HEAL L1 (2026-07-16, root-cause fix): the bearer dies every ~5-9d,
            # but the session cookie lives months -> token_heal.py re-mints the bearer
            # deterministically (0 LLM, 0 browser) and we retry the pull ONCE.
            hrc = run("token-heal", [PY, ROOT / "token_heal.py"], cwd=ROOT)
            if hrc == 0:
                rc = run("pull(retry)", [PY, ROOT / "incremental_pull.py", cutoff.isoformat()], cwd=ROOT)
            elif os.environ.get("TOKEN_HEAL_NO_BUS") != "1":
                # L1 dead (session cookie expired/absent) -> escalate to L2: a bus TASK
                # to THIS hub so the robot runs the Chrome re-harvest skill. Dual-rail,
                # visible in TG-03. TOKEN_HEAL_NO_BUS=1 silences this for tests.
                run("heal-escalate", [
                    PY, Path.home() / ".claude" / "scripts" / "bus_send.py", "HUB1",
                    "TASK: chatgpt token self-heal L2 -- session cookie dead (token_heal.py exit %d). "
                    "Run skill local-chatgpt-token-heal (Chrome: chatgpt.com/api/auth/session -> save "
                    "accessToken->bearer.txt AND sessionToken->session_token.txt), then re-run "
                    "nightly_sync.cmd and verify exit=0." % hrc])
        if rc != 0:
            print("PULL FAILED (token likely dead) -> leaving vault as-is; freshness watchdog will ping.", flush=True)
            sys.exit(7)

        zip_path = ROOT / "raw" / ("incremental-%s.zip" % today.isoformat())
    if not zip_path.exists():
        print("no zip produced (%s) -> nothing to fold; exiting clean." % zip_path, flush=True)
        sys.exit(0)

    # 3) zip -> staging notes. Clear staging first so we only touch THIS run's chats.
    if STAGING_CONV.exists():
        for f in STAGING_CONV.glob("*.md"):
            f.unlink()
    rc = run("to-vault(staging)", [PY, ROOT / "chatgpt_export_to_vault.py", "--zip", zip_path])
    if rc != 0:
        print("staging build failed; aborting before vault copy.", flush=True)
        sys.exit(8)

    # 4) copy staging -> vault, NEVER clobbering an enriched note
    VAULT_CONV.mkdir(parents=True, exist_ok=True)
    added = updated = preserved = 0
    for src in STAGING_CONV.glob("*.md"):
        dst = VAULT_CONV / src.name
        if not dst.exists():
            shutil.copy2(src, dst); added += 1
        elif "related_concepts: []" in dst.read_text(encoding="utf-8", errors="ignore"):
            shutil.copy2(src, dst); updated += 1   # present but not yet concept-enriched
        else:
            preserved += 1                          # enriched -> keep, do NOT overwrite
    print("copy: +%d new, ~%d refreshed(unenriched), %d enriched-preserved" % (added, updated, preserved), flush=True)

    # 4.5) upsert staging DB rows into the canonical full-history DB (keyed by cid).
    # Without this the canonical DB freezes at the last FULL export while notes stay
    # fresh (downstream consumers + the coverage freshness line read the canonical DB).
    if STAGING_DB.exists():
        con = sqlite3.connect(str(CANON_DB))
        try:
            con.execute("ATTACH DATABASE ? AS s", (str(STAGING_DB),))
            n = con.execute("SELECT COUNT(*) FROM s.conversations").fetchone()[0]
            con.execute("INSERT OR REPLACE INTO conversations SELECT * FROM s.conversations")
            con.commit()
            print("db-merge: %d staging rows upserted into %s" % (n, CANON_DB.name), flush=True)
        finally:
            con.close()

    # 5) rebuild full vault MOC
    run("moc", [PY, ROOT / "build_chatgpt_moc.py"], cwd=ROOT)

    # 6) commit new state
    run("backup-post", [PY, IMPORTS / "vault_backup.py", "nightly chatgpt sync (+new chats)"], cwd=IMPORTS)

    print("=== nightly_sync DONE: +%d new chats into vault ===" % added, flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
