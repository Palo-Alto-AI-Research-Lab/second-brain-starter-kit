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
"""
sys_coverage.py -- System Architect: COVERAGE AUDIT.
Answers "is absolutely everything covered by the architecture?" with NUMBERS, not hope.
Measures, deterministically (0 tokens):
  1. Vault knowledge  -- % of notes connected (non-orphan)        [from orphan-scan]
  2. CC sessions      -- % of on-disk sessions imported to vault   [disk UUID files vs sessions.db]
  3. Sources          -- each known source pipeline present + fresh
  4. Backups          -- each storage home mapped to a backup
Writes table `coverage` into system.db and prints. Run after sys_scan.py.
"""
import os, re, json, glob, sqlite3, time, datetime, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

IMPORTS = r"%IMPORTS%"
VAULT   = r"%VAULT%"
DB      = os.path.join(IMPORTS, "arch", "system.db")
NOW     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
rows = []   # (domain, label, value, target, pct, status, detail)

def pct(a, b): return round(100.0 * a / b, 1) if b else 0.0
def age_days(p):
    try: return (time.time() - os.path.getmtime(p)) / 86400.0
    except Exception: return None

# ---- 1. vault knowledge coverage (from orphan-scan summary) ----
try:
    s = json.load(open(os.path.join(IMPORTS, "orphan-scan", "scan-summary.json"), encoding="utf-8"))
    total = s["total_md"]; orph = s["orphans"]; conn = total - orph
    p = pct(conn, total)
    rows.append(("knowledge", "Заметки волта связаны (не сироты)", conn, total, p,
                 "ok" if p >= 80 else "warn", "%d сирот (%.1f%%), скан %s" % (orph, s["orphan_pct"], s.get("scanned_at", "?"))))
except Exception as e:
    rows.append(("knowledge", "Заметки волта связаны", 0, 0, 0, "fail", "orphan-scan summary missing: %s" % e))

# ---- 2. CC session coverage: measure against the LIVE cross-machine POOL ----
# (2026-07-07) The legacy importer (claude_sessions_to_vault.py) is DEPRECATED/Disabled: it
# scanned ONE frozen project folder (the hub's live folder moved 2026-06-23), so its
# target/imported rows measured a DEAD pipeline (looked fine, meant nothing). The live truth
# is the _session-archive pool (catalog-<machine>.json + per-machine JSONL transcripts),
# rebuilt nightly by "Claude Session Archive". Two honest rows off the live pool:
#   2a. pool size  = union of every machine's sessions (the coverage surface itself now)
#   2b. transcripts present = catalogued sessions whose FULL JSONL is actually archived
# Freshness of the pool is already asserted by the SOURCES row "Claude sessions (live pool)".
try:
    ARCH = os.path.join(VAULT, "_session-archive")
    INB  = os.path.join(VAULT, "_machine-bus", "_session-archive-inbound")
    def _pool_catalogs():
        out = []
        for pat in (os.path.join(ARCH, "catalog-*.json"),
                    os.path.join(INB, "*", "catalog-*.json")):
            out += [f for f in glob.glob(pat) if ".sync-conflict-" not in os.path.basename(f)]
        return out
    pool = {}
    for f in _pool_catalogs():
        try:
            for r in json.load(open(f, encoding="utf-8")):
                cli = r.get("cliSessionId")
                if cli:
                    pool.setdefault(cli, r)
        except Exception:
            pass
    tx = {os.path.splitext(os.path.basename(p))[0]
          for p in glob.glob(os.path.join(ARCH, "transcripts", "*", "*", "*.jsonl"))}
    by_m = {}
    for r in pool.values():
        by_m[r.get("machine", "?")] = by_m.get(r.get("machine", "?"), 0) + 1
    mdet = ", ".join("%s:%d" % (m, c) for m, c in sorted(by_m.items(), key=lambda kv: -kv[1]))
    rows.append(("sessions", "Сессии CC: живой пул (все машины)", len(pool), len(pool), 100.0,
                 "ok" if pool else "fail",
                 "%d сессий в _session-archive (%s)" % (len(pool), mdet)))
    cov = sum(1 for cli in pool if cli in tx)
    p = pct(cov, len(pool))
    rows.append(("sessions", "Сессии CC: транскрипты в пуле", cov, len(pool), p,
                 "ok" if p >= 90 else "warn",
                 "%d/%d каталожных сессий имеют полный транскрипт (остальные — только строка каталога: свежие/пиры без ingest)" % (cov, len(pool))))
    # 2c. FOREVER-FIX GUARD (2026-07-07): the reader the consumers use (vault_sessions.
    # recent_sessions) MUST return THIS machine's own recent sessions. This machine KNOWS it
    # worked (fresh JSONLs on disk); if the reader returns 0 of its label, the reader is BLIND
    # to its source (moved/froze/format changed) — the exact silent decay that hid the hub for
    # 2 weeks (rule_scan + intention_mine read a folder frozen 2026-06-23). RED, not warn:
    # this fires the DAY the source dies, instead of failing silently as "no data".
    try:
        sys.path.insert(0, IMPORTS)
        import vault_sessions as _vs
        sc = _vs.selfcheck(7)
        blind = not sc["ok"]
        rows.append(("sessions", "Потребители видят ЭТОТ компьютер", sc["my_count"],
                     max(sc["my_count"], 1), 100.0 if not blind else 0.0,
                     "fail" if blind else "ok",
                     "reader(7д)=%d сессий для %s (на диске %d свежих). 0 при непустом диске = "
                     "потребители (preference-sweep/intention/fb-diary) слепы к источнику"
                     % (sc["my_count"], sc["my_label"], sc["local_recent"])))
    except Exception as e:
        rows.append(("sessions", "Потребители видят ЭТОТ компьютер", 0, 1, 0.0, "fail",
                     "selfcheck упал: %s" % e))
except Exception as e:
    rows.append(("sessions", "Сессии CC (живой пул)", 0, 0, 0, "fail", str(e)))

# ---- 3. source pipeline coverage (DB present + freshness) ----
SOURCES = [
    ("Telegram chats", r"dialogs\chats.db", 14),
    ("ChatGPT", r"chatgpt\chatgpt_conversations.db", 30),   # manual source (/chatgpt-sync, no routine) -- 7d threshold cried wolf 2026-07-04
    ("WhatsApp", r"whatsapp\whatsapp_train.db", 14),
    ("Browser history", r"browser-history\browser_history.db", 7),
    # 2026-07-07: legacy importer (claude-sessions\sessions.db) DEPRECATED — it scanned a
    # folder frozen since 2026-06-23 and only touched the db mtime, so this check read a
    # dead file that would false-RED once the nightly task stopped. Repointed to the LIVE
    # cross-machine pool (_session-archive\catalog.html, rebuilt daily by "Claude Session
    # Archive"). os.path.join(IMPORTS, <absolute>) returns the absolute path on Windows.
    ("Claude sessions (live pool)", r"%VAULT%\_session-archive\catalog.html", 3),
    ("Platinum CRM / leads", r"leads.db", 14),
    ("Names index", r"namesearch\names.db", 30),
    ("Search catalog", r"search\search_catalog.db", 14),
    ("Contacts (Apple)", r"apple-contacts\contacts.db", 90),
    ("YouTube history", r"youtube\youtube_history.db", 90),
    ("Sostav community", r"sostav\sostav.db", 45),
    ("Near-dup index", r"dedup\neardup.db", 7),
]
fresh = 0
for label, rel, max_age in SOURCES:
    p = os.path.join(IMPORTS, rel)
    if not os.path.exists(p):
        rows.append(("source", label, 0, 1, 0, "fail", "БД отсутствует (%s)" % rel)); continue
    a = age_days(p)
    ok = a is not None and a <= max_age
    if ok: fresh += 1
    rows.append(("source", label, 1 if ok else 0, 1, 100.0 if ok else 0.0,
                 "ok" if ok else "warn",
                 "обновлён %.1f дн назад (порог %d)" % (a, max_age) if a is not None else "нет mtime"))

# ---- 4. backup coverage (storage homes -> backup target; MEASURED, not assumed) ----
def newest_bundle(folder, prefix):
    """(path, age_days) of newest <prefix>-*.bundle in folder, else (None, None)."""
    best = None
    try:
        for f in glob.glob(os.path.join(folder, prefix + "-*.bundle")):
            a = age_days(f)
            if a is not None and (best is None or a < best[1]):
                best = (f, a)
    except Exception:
        pass
    return best if best else (None, None)

# Offsite resolver = the ONE from backup_to_drive.py (single source of truth).
# It knows machine.env GDRIVE_BACKUP_ROOT (the hub mounts Drive as a letter, not
# "E:\Google Drive on*"). A local twin of this logic drifted once already: the hub
# false-alarmed "GDrive нет" on 2026-07-04 because the twin missed machine.env.
sys.path.insert(0, IMPORTS)
try:
    from backup_to_drive import resolve_drive
    gdrive = resolve_drive()          # Path | None; None = no offsite mount on THIS machine
except Exception:
    gdrive = None
LOCALBK = r"C:\ObsidianBackup"
off_dir = os.path.join(gdrive, "repos") if gdrive else None
loc_dir = os.path.join(LOCALBK, "repos")
# 4a. _imports CODE bundle offsite (precious, irreplaceable layer) -- VERIFY it actually lands
_, off_age = newest_bundle(off_dir, "_imports") if off_dir else (None, None)
_, loc_age = newest_bundle(loc_dir, "_imports")
if (off_age is not None and off_age <= 2) and (loc_age is not None and loc_age <= 2):
    rows.append(("backup", "_imports КОД (скрипты)", 1, 1, 100.0, "ok",
                 "git bundle -> Google Drive offsite (%.1fд) + C: (%.1fд) = 3-2-1, ночь 02:00" % (off_age, loc_age)))
else:
    rows.append(("backup", "_imports КОД (скрипты)", 0, 1, 0.0, "warn",
                 "offsite bundle нет/устарел (GDrive %s, C: %s) -- backup_to_drive.py" % (
                    "%.1fд" % off_age if off_age is not None else "нет",
                    "%.1fд" % loc_age if loc_age is not None else "нет")))
# 4b. _imports DBs -- regenerable by design; RAW sources live in _originals (which IS offsite)
rows.append(("backup", "_imports БАЗЫ (SQLite)", 1, 1, 100.0, "ok",
             "пересоздаваемы повторным импортом; сырьё в _originals -> offsite by design (НЕ дыра)"))
# 4c. Vault bundle -- MEASURED the same way (was a hardcoded "ok": same trap, other row)
_, v_off = newest_bundle(os.path.join(gdrive, "vault"), "Owner-Knowledge") if gdrive else (None, None)
_, v_loc = newest_bundle(os.path.join(LOCALBK, "vault"), "Owner-Knowledge")
if (v_off is not None and v_off <= 2) and (v_loc is not None and v_loc <= 2):
    rows.append(("backup", "Волт (Owner-Knowledge)", 1, 1, 100.0, "ok",
                 "git bundle -> Google Drive offsite (%.1fд) + C: (%.1fд) + Syncthing = 3-2-1" % (v_off, v_loc)))
else:
    rows.append(("backup", "Волт (Owner-Knowledge)", 0, 1, 0.0, "warn",
                 "vault bundle нет/устарел (GDrive %s, C: %s) -- backup_to_drive.py" % (
                    "%.1fд" % v_off if v_off is not None else "нет",
                    "%.1fд" % v_loc if v_loc is not None else "нет")))
# 4d. memory/config -- check the REAL git repos (~/.claude itself has no .git;
# config snapshots live in _config-backup, memory has its own repo inside projects/)
# The memory dir name is the ENCODED cwd of the session that owns it -> differs per machine
# AND per working dir, so it can never be hardcoded or guessed by listing projects/.
# (2026-07-20) This row false-FAILed on the hub: it read CLAUDE_MEMORY_NAME from os.environ
# ONLY, but that key lives in the machine.env FILE -- never exported into the process env.
# So it silently fell back to the HP17 literal and measured a path that does not exist here.
# Root fix = ask the SAME resolver the memory importer uses (_paths.memory_dir(), which reads
# machine.env then os.environ), instead of re-deriving the path. Lesson 3: never fork the
# twin resolver -- the fork is what drifts.
CLAUDE_HOME = os.path.join(os.path.expanduser("~"), ".claude")
try:
    from _paths import memory_dir            # IMPORTS already on sys.path (see 4-preamble)
    MEMORY_DIR = memory_dir()
except Exception:
    MEMORY_DIR = os.path.join(CLAUDE_HOME, "projects",
                              os.environ.get("CLAUDE_MEMORY_NAME", "C--Users----CLAUDE-HP17-May26"),
                              "memory")
GIT_HOMES = [
    ("Память (~/.claude memory)",
     os.path.join(MEMORY_DIR, ".git"),
     "свой git-репо + Syncthing claude-memory"),
    ("Конфиг (~/.claude)",
     os.path.join(CLAUDE_HOME, "_config-backup", ".git"),
     "git snapshot 15м (_config-backup) + Syncthing claude-config"),
]
for label, gitpath, detail in GIT_HOMES:
    present = os.path.isdir(gitpath)
    rows.append(("backup", label, 1 if present else 0, 1, 100.0 if present else 0.0,
                 "ok" if present else "fail", detail if present else "%s не найден" % gitpath))

# ---- write + print ----
con = sqlite3.connect(DB)
con.execute("DROP TABLE IF EXISTS coverage")
con.execute("""CREATE TABLE coverage(domain TEXT, label TEXT, value INT, target INT,
               pct REAL, status TEXT, detail TEXT, run_at TEXT)""")
for r in rows:
    con.execute("INSERT INTO coverage VALUES(?,?,?,?,?,?,?,?)", r + (NOW,))
con.commit(); con.close()

print("=== COVERAGE @ %s ===" % NOW)
for dom in ["knowledge", "sessions", "source", "backup"]:
    print("\n[%s]" % dom.upper())
    for r in rows:
        if r[0] != dom: continue
        mark = "OK " if r[5] == "ok" else ("XX " if r[5] == "fail" else ".. ")
        val = ("%d/%d %.0f%%" % (r[2], r[3], r[4])) if r[3] and r[3] != 1 else r[5]
        print("  %s %-34s %-12s %s" % (mark, r[1], val, r[6]))
