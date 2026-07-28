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
sys_scan.py  --  System Architect, Phase 1 (catalog) + Phase 3 (graph edges)
Deterministic, 0 tokens, READ-ONLY discovery of every meaningful asset in
Anton's Personal Knowledge Platform -> system.db (SQLite).

Design (AK-47, per Decision Memo "Architect", 2026-06-21):
  - AUTO-SCAN is the source of truth (assets that exist on disk are found).
  - overlay.json is a THIN human layer: integrity_tier / owner / lifecycle
    overrides keyed by asset_id (nothing else is hand-maintained).
  - No external services. One SQLite file, one Python script.

Run:  python sys_scan.py
Output: %IMPORTS%\\arch\\system.db  (+ console summary)
"""
import os, sys, re, json, hashlib, sqlite3, subprocess, datetime, glob

# ---- roots (hard paths today; Phase-P3 of platform memo moves these to env) ----
HOME          = os.path.expanduser("~")
SKILLS_DIR    = os.path.join(HOME, ".claude", "skills")

# ONE fleet map of designed-signal exit codes (see scan_scheduled_tasks). Deliberately read by
# path, not imported: this engine lives on E:\ and must not grow a cross-drive import of
# ~/.claude/scripts. Fail-safe: unreadable map -> nothing is a signal -> nonzero stays broken.
# Map lives in scripts/_shared/ so it AUTO-TRAVELS via Syncthing to every fleet machine (same lane
# as cron_watchdog.py). scripts/ ROOT was machine-local (/scripts/** ignored) -> hub never got it
# -> hub scoreboards stuck in fail-safe (relocated 2026-07-26 root-fix).
SIGNAL_MAP_PATH = os.path.join(HOME, ".claude", "scripts", "_shared", "expected_exit_codes.json")

def _load_signal_map(path=SIGNAL_MAP_PATH):
    """{taskname.lower(): {codes}}. Never raises -- a missing map must not kill the whole scan.
    A duplicate key after normalization would silently let the last entry win (two sources of
    truth again) -> refuse the whole map instead."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        out = {}
        for k, v in doc.get("expected", {}).items():
            kk = k.strip().lower()
            if kk in out:
                raise ValueError("duplicate key after normalization: %r" % kk)
            out[kk] = set(int(c) for c in v.get("signal", []))
        return out
    except Exception as e:
        print("WARN signal map unreadable (%s) -> every nonzero task result counts as broken"
              % str(e)[:90])
        return {}
# Memory dir name = ENCODED cwd of the owning session -> per-machine. Same false-path trap
# as sys_coverage.py 4d (2026-07-20): CLAUDE_MEMORY_NAME lives in the machine.env FILE, not
# in os.environ, so an environ-only read fell back to the HP17 literal and this scan
# catalogued ZERO memory notes on the hub -- silently, because the dir just "wasn't there".
# Ask the shared resolver (_paths.memory_dir()), the one the memory importer uses.
sys.path.insert(0, r"%IMPORTS%")
try:
    from _paths import memory_dir
    MEMORY_DIR = memory_dir()
except Exception:
    MEMORY_DIR = os.path.join(HOME, ".claude", "projects",
                              os.environ.get("CLAUDE_MEMORY_NAME", "C--Users----CLAUDE-HP17-May26"),
                              "memory")
CLAUDE_JSON   = os.path.join(HOME, ".claude.json")
CONFIG_DIR    = os.path.join(HOME, ".claude")
IMPORTS       = r"%IMPORTS%"
VAULT         = r"%VAULT%"
DECISIONS     = os.path.join(VAULT, "02-Decisions")
DASHBOARDS    = os.path.join(VAULT, "_Dashboards")
ARCH_DIR      = os.path.join(IMPORTS, "arch")
DB_PATH       = os.path.join(ARCH_DIR, "system.db")
OVERLAY_PATH  = os.path.join(ARCH_DIR, "overlay.json")
MACHINE_ENV   = os.path.join(HOME, ".claude", "machine.env")

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# scratch / backup dirs we never treat as real assets
DIR_DENY = {"__pycache__", ".git", "staging", "staging_airtable", "staging_pokupki",
            "gold_corpus", "retro_candidates", "rule_candidates", "desc_opt",
            "_identity_out", "_synth", "_synth_b", "_synth_out", "branches"}
# vendor scheduled tasks (not ours)
VENDOR_DENY = ("Adobe", "MicrosoftEdge", "OneDrive", "Zoom", "Kaspersky", "nWizard",
               "GoogleUpdate", "Google Update", "CCleaner", "Dropbox", "NVIDIA",
               "NvNode", "NvTmRep", "NvProfile", "NvDriver",  # NVIDIA root tasks (Nv* not caught by "NVIDIA")
               "Intel", "Dell", "Brave", "Firefox", "Opera", "Steam", "Spotify",
               "user_feed", "Microsoft\\")

DEFAULT_TIER = {
    "backup_target": "critical", "machine": "critical",
    "sqlite_db": "important", "scheduled_task": "important",
    "mcp_server": "important", "import_pipeline": "important",
    "skill": "reference", "script": "reference",
    "decision_note": "reference", "memory_note": "reference", "vault_moc": "reference",
}

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def file_hash(path, cap=2_000_000):
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            h.update(f.read(cap))
        return h.hexdigest()
    except Exception:
        return ""

def load_overlay():
    if os.path.exists(OVERLAY_PATH):
        try:
            return json.load(open(OVERLAY_PATH, encoding="utf-8"))
        except Exception as e:
            print("WARN overlay.json unreadable:", e)
    return {}

# ---------------------------------------------------------------- discovery ----
assets = []   # dicts
edges  = []   # (src_id, edge_type, dst_id, evidence)
TASK_ACTIONS = {}  # task asset_id -> action command line

def add(kind, name, path, sor, status="ok", detail="", chash="", lifecycle="active"):
    aid = "%s:%s" % (kind, slug(name))
    assets.append(dict(asset_id=aid, kind=kind, name=name, canonical_path=path,
                       system_of_record=sor, lifecycle_state=lifecycle,
                       status=status, detail=detail, content_hash=chash,
                       last_seen=NOW))
    return aid

def scan_skills():
    if not os.path.isdir(SKILLS_DIR):
        return
    for d in sorted(os.listdir(SKILLS_DIR)):
        p = os.path.join(SKILLS_DIR, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        skill_md = os.path.join(p, "SKILL.md")
        ok = os.path.exists(skill_md)
        add("skill", d, p, "local_fs",
            status="ok" if ok else "broken",
            detail="" if ok else "no SKILL.md")

def scan_pipelines():
    if not os.path.isdir(IMPORTS):
        return
    for d in sorted(os.listdir(IMPORTS)):
        p = os.path.join(IMPORTS, d)
        if not os.path.isdir(p):
            continue
        if d in DIR_DENY or d.startswith("_"):
            continue
        # count scripts inside
        n = 0
        for _r, _ds, _fs in os.walk(p):
            if "__pycache__" in _r:
                continue
            n += sum(1 for f in _fs if f.endswith((".py", ".cmd", ".ps1")))
        add("import_pipeline", d, p, "local_fs", detail="%d scripts" % n)

def scan_scripts():
    for f in sorted(glob.glob(os.path.join(IMPORTS, "*.py")) +
                    glob.glob(os.path.join(IMPORTS, "*.cmd"))):
        name = os.path.basename(f)
        if name.startswith("_"):
            continue
        add("script", name, f, "local_fs", chash=file_hash(f))

def scan_dbs():
    for f in sorted(glob.glob(os.path.join(IMPORTS, "**", "*.db"), recursive=True)):
        if any(x in f.lower() for x in ("_archive", "_bak", "_backup", "__pycache__")):
            continue
        name = os.path.basename(f)
        try:
            mb = os.path.getsize(f) / 1e6
        except Exception:
            mb = 0
        add("sqlite_db", name, f, "sqlite", detail="%.1f MB" % mb)

def scan_dashboards():
    for f in sorted(glob.glob(os.path.join(DASHBOARDS, "**", "*.html"), recursive=True)):
        add("dashboard", os.path.basename(f), f, "local_fs")

def scan_memory():
    if not os.path.isdir(MEMORY_DIR):
        return
    for f in sorted(glob.glob(os.path.join(MEMORY_DIR, "*.md"))):
        name = os.path.basename(f)
        if name.upper() == "MEMORY.MD":
            continue
        add("memory_note", name[:-3], f, "git")

def scan_decisions():
    for f in sorted(glob.glob(os.path.join(DECISIONS, "*.md"))):
        add("decision_note", os.path.basename(f)[:-3], f, "obsidian")

def scan_mocs():
    for f in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        if "MOC" not in os.path.basename(f).upper():
            continue
        if any(x in f.lower() for x in ("_backup", "_archive", "_originals")):
            continue
        add("vault_moc", os.path.basename(f)[:-3], f, "obsidian")

def scan_mcp():
    if not os.path.exists(CLAUDE_JSON):
        return
    try:
        d = json.load(open(CLAUDE_JSON, encoding="utf-8"))
    except Exception as e:
        print("WARN .claude.json unreadable:", e)
        return
    seen = set()
    def grab(mc, scope):
        for k in (mc or {}):
            if k in seen:
                continue
            seen.add(k)
            add("mcp_server", k, "%s (%s)" % (CLAUDE_JSON, scope), "github", detail=scope)
    grab(d.get("mcpServers"), "global")
    for proj, pv in (d.get("projects") or {}).items():
        grab(pv.get("mcpServers"), "project:%s" % os.path.basename(proj.rstrip("\\/")))

def scan_tasks():
    """Windows Task Scheduler -- our tasks + live health (LastTaskResult/State)."""
    ps = (
        "Get-ScheduledTask | Where-Object {$_.TaskPath -eq '\\'} | ForEach-Object {"
        " $i = $_ | Get-ScheduledTaskInfo;"
        " $a = ($_.Actions | ForEach-Object {\"$($_.Execute) $($_.Arguments)\"}) -join ' ;; ';"
        " [pscustomobject]@{name=$_.TaskName; state=[string]$_.State;"
        " last=[string]$i.LastRunTime; result=$i.LastTaskResult; action=$a} }"
        " | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        data = json.loads(out) if out else []
        if isinstance(data, dict):
            data = [data]
    except Exception as e:
        print("WARN scheduled-task scan failed:", e)
        return
    # ok / running / never-run-yet / no-more-runs / READY ... plus 0x800710E0 =
    # "an instance of this task is already running": the STEADY state of a single-instance
    # always-on daemon (e.g. call-monitor-daemon) whose keep-alive trigger re-fires while the
    # one instance is healthily running -> NOT broken (same class cron_watchdog already whitelists).
    OKRES = {0, 267008, 267009, 267010, 267011, 1803543125}
    # Designed-signal exits: these tasks use a nonzero exit as the CHECK RESULT by design and
    # already DELIVERED their own alert (bus/TG ping), so a nonzero here means "check fired",
    # not "script crashed" -> not broken. Exit 3 = alarm undeliverable and must STAY broken.
    #
    # ONE MAP for the whole fleet (2026-07-24): this list used to be hardcoded here AND in
    # cron_watchdog.py SIGNAL_OK AND in expected_exit_codes.json -- three copies with a
    # "KEEP IN SYNC" comment that did not hold (incident 2026-07-22: this scan painted a
    # healthy sentry broken). Now all scoreboards read the same file; add robots THERE.
    SIGNAL_RES = _load_signal_map()
    for t in data:
        name = (t.get("name") or "").strip()
        if not name or any(v in name for v in VENDOR_DENY):
            continue
        state = (t.get("state") or "").strip()
        res = t.get("result")
        try:
            res = int(res)
        except Exception:
            res = None
        if state.lower() == "disabled":
            status, life = "disabled", "deprecated"
        elif state.lower() == "running":
            # an instance is alive RIGHT NOW -> healthy, even if the PREVIOUS one
            # died ugly (2026-07-03: call-monitor-daemon auto-restarted fine but
            # its stale result=0xC000013A kept flagging the living daemon broken)
            status, life = "ok", "active"
        elif res is None or res in OKRES or res in SIGNAL_RES.get(name.strip().lower(), ()):
            status, life = "ok", "active"
        else:
            status, life = "broken", "active"
        aid = add("scheduled_task", name, "Windows Task Scheduler", "local_fs",
                  status=status, lifecycle=life,
                  detail="state=%s last=%s result=%s" % (state, t.get("last"), res))
        TASK_ACTIONS[aid] = (t.get("action") or "")

def scan_machines():
    # machine.env (this host) + known roster from memory
    if os.path.exists(MACHINE_ENV):
        add("machine", "this-host (machine.env)", MACHINE_ENV, "local_fs",
            detail="machine.env present")
    for m in ["LAPTOP1 (LAPTOP1)", "PaloAlto-Desktop (HUB1)"]:
        add("machine", m, "roster", "git", detail="from session-machine-tagging")

def scan_backup_targets():
    # git repos under ~/.claude
    for d in sorted(glob.glob(os.path.join(CONFIG_DIR, "*"))):
        if os.path.isdir(os.path.join(d, ".git")):
            add("backup_target", "git:" + os.path.basename(d), d, "git",
                detail="git-backed config repo")
    # offsite / sync targets (known classes)
    for name, detail in [
        ("Google Drive (vault offsite)", "3-2-1 nightly 03:00"),
        ("C: mirror (vault)", "3-2-1 local mirror"),
        ("Syncthing star (vault+memory+config)", "live cross-machine sync"),
    ]:
        add("backup_target", name, "external", "backup_repo", detail=detail)

# --------------------------------------------------------------- edges (P3) ----
def build_edges(by_id):
    """Deterministic dependency edges (text references only, 0 tokens)."""
    pipe_names = {a["name"]: a["asset_id"] for a in assets if a["kind"] == "import_pipeline"}
    db_names   = {a["name"]: a["asset_id"] for a in assets if a["kind"] == "sqlite_db"}
    scripts    = {a["name"]: a["asset_id"] for a in assets if a["kind"] == "script"}

    # skill -> pipeline / db  (SKILL.md mentions a path / db name)
    for a in assets:
        if a["kind"] != "skill":
            continue
        try:
            txt = open(os.path.join(a["canonical_path"], "SKILL.md"),
                       encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pn, pid in pipe_names.items():
            if ("_imports\\%s" % pn) in txt or ("_imports/%s" % pn) in txt:
                edges.append((a["asset_id"], "uses", pid, "SKILL.md path"))
        for dn, did in db_names.items():
            if dn in txt:
                edges.append((a["asset_id"], "reads", did, "SKILL.md db"))

    # scheduled_task -> script / pipeline  (action command line)
    for tid, action in TASK_ACTIONS.items():
        al = action.lower()
        for sn, sid in scripts.items():
            if sn.lower() in al:
                edges.append((tid, "runs", sid, "task action"))
        for pn, pid in pipe_names.items():
            if ("_imports\\%s" % pn).lower() in al or ("_imports/%s" % pn).lower() in al:
                edges.append((tid, "runs", pid, "task action"))

    # script -> sqlite_db / other scripts  (body references)
    script_by_file = {a["name"].lower(): a["asset_id"] for a in assets if a["kind"] == "script"}
    for a in assets:
        if a["kind"] != "script":
            continue
        try:
            txt = open(a["canonical_path"], encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for dn, did in db_names.items():
            if dn in txt:
                edges.append((a["asset_id"], "writes", did, "script db ref"))
        low = txt.lower()
        for sn, sid in script_by_file.items():
            if sid != a["asset_id"] and sn in low:
                edges.append((a["asset_id"], "calls", sid, "script import/call"))

    # *.cmd / *.ps1 wrappers (anywhere under _imports) -> script  (they keep scripts alive)
    for w in (glob.glob(os.path.join(IMPORTS, "**", "*.cmd"), recursive=True) +
              glob.glob(os.path.join(IMPORTS, "**", "*.ps1"), recursive=True)):
        if any(x in w.lower() for x in ("_archive", "_bak", "_backup", "__pycache__")):
            continue
        try:
            wl = open(w, encoding="utf-8", errors="ignore").read().lower()
        except Exception:
            continue
        wname = os.path.basename(w)
        for sn, sid in script_by_file.items():
            if sn in wl:
                edges.append(("wrapper:" + slug(wname), "runs", sid, "cmd/ps1 wrapper"))

# ------------------------------------------------------------------- write -----
def write_db(overlay):
    os.makedirs(ARCH_DIR, exist_ok=True)
    by_id = {}
    for a in assets:
        tier = DEFAULT_TIER.get(a["kind"], "reference")
        owner = "chief-knowledge-architect"
        life = a["lifecycle_state"]
        ov = overlay.get(a["asset_id"], {})
        tier = ov.get("integrity_tier", tier)
        owner = ov.get("owner", owner)
        life = ov.get("lifecycle_state", life)
        a["integrity_tier"], a["owner"], a["lifecycle_state"] = tier, owner, life
        by_id[a["asset_id"]] = a  # last wins on dup id

    build_edges(by_id)

    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.executescript("""
        DROP TABLE IF EXISTS asset;
        DROP TABLE IF EXISTS edge;
        CREATE TABLE asset(
            asset_id TEXT PRIMARY KEY, kind TEXT, name TEXT, canonical_path TEXT,
            system_of_record TEXT, lifecycle_state TEXT, integrity_tier TEXT,
            owner TEXT, status TEXT, detail TEXT, content_hash TEXT, last_seen TEXT);
        CREATE TABLE edge(
            src TEXT, edge_type TEXT, dst TEXT, evidence TEXT);
        CREATE TABLE IF NOT EXISTS scan_run(
            run_at TEXT, total INT, ok INT, broken INT, disabled INT);
    """)
    for a in by_id.values():
        c.execute("""INSERT INTO asset VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (a["asset_id"], a["kind"], a["name"], a["canonical_path"],
                   a["system_of_record"], a["lifecycle_state"], a["integrity_tier"],
                   a["owner"], a["status"], a["detail"], a["content_hash"], a["last_seen"]))
    for e in edges:
        c.execute("INSERT INTO edge VALUES(?,?,?,?)", e)

    vals = list(by_id.values())
    ok = sum(1 for a in vals if a["status"] == "ok")
    broken = sum(1 for a in vals if a["status"] == "broken")
    disabled = sum(1 for a in vals if a["status"] == "disabled")
    c.execute("INSERT INTO scan_run VALUES(?,?,?,?,?)",
              (NOW, len(vals), ok, broken, disabled))
    con.commit()
    con.close()
    return len(vals), ok, broken, disabled

def main():
    print("System Architect scan @", NOW)
    overlay = load_overlay()
    for fn in (scan_skills, scan_pipelines, scan_scripts, scan_dbs, scan_dashboards,
               scan_memory, scan_decisions, scan_mocs, scan_mcp, scan_tasks,
               scan_machines, scan_backup_targets):
        try:
            fn()
        except Exception as e:
            print("WARN", fn.__name__, "failed:", e)
    total, ok, broken, disabled = write_db(overlay)
    # per-kind summary
    from collections import Counter
    kc = Counter(a["kind"] for a in {x["asset_id"]: x for x in assets}.values())
    print("\n--- catalog ---")
    for k in sorted(kc):
        print("  %-16s %4d" % (k, kc[k]))
    print("  %-16s %4d" % ("EDGES", len(edges)))
    print("\nTOTAL %d  | ok %d  broken %d  disabled %d" % (total, ok, broken, disabled))
    print("DB:", DB_PATH)
    if broken:
        con = sqlite3.connect(DB_PATH)
        print("\n--- BROKEN ---")
        for r in con.execute("SELECT kind,name,detail FROM asset WHERE status='broken' ORDER BY kind"):
            print("  [%s] %s  %s" % (r[0], r[1], r[2]))
        con.close()

if __name__ == "__main__":
    main()
