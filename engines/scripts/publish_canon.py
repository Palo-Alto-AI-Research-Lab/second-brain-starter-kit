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
# publish_canon.py -- canon CLAUDE.md auto-rail for nodes OUTSIDE the claude-home Syncthing share
# (ANCHOR1/ANCHOR1 keeps an adapted Linux fork; MAC1 pairs elsewhere). Root fixed:
# "canon reached those nodes once at onboarding, then silently drifted" (found 2026-07-11:
# ANCHOR1 ran a 05.07 fork for 6 days, nobody noticed).
#
# PUBLISH: live CLAUDE.md changed -> copy into synced _transit/canon-from-hub/ + MANIFEST.json
#          + one active canon parcel in _deploy/PENDING-<node>.jsonl (deploy_check on the node
#          surfaces it; the node merges CONTENT, keeps its local header/path adaptations, then
#          writes ACK-<node>.json + deploy_apply).
# CHECK:   MANIFEST vs ACK-*.json; node behind for > GRACE days -> RED to 03; once per (node,md5)
#          -> a QUESTION to 02 POLICE via approval.py (03 drowns in heartbeat noise -- proven 07-10.07).
# 0 tokens, stdlib. Canon: reglament-raskatka-fiksov-deploy-manifest + one-system-propagate.
import argparse, os, re, sys, json, shutil, hashlib, subprocess, glob
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "_shared"))
from deploy_lib import BUS, pending_file
# HMAC signing (Anton 2026-07-16 "ДЕЛАЙ": canon parcel must be signed; receivers gate on
# canon_verify.py). Reuses the ONE fleet secret layer (fleet_hmac), not a second mechanism.
try:
    import fleet_hmac
except Exception:
    fleet_hmac = None

CLAUDE = os.path.normpath(os.path.join(HERE, "..", "CLAUDE.md"))
CHANGELOG = os.path.normpath(os.path.join(HERE, "..", "CLAUDE.CHANGELOG.md"))
# Version line in the CLAUDE.md header: "> ВЕРСИЯ: v2.1.1 · 2026-07-23 · ...".
# The gate compares this against the version recorded in MANIFEST (Anton 2026-07-23:
# md5 changed but ВЕРСИЯ not bumped -> block; auto-fill the md5 into CLAUDE.CHANGELOG.md).
VERSION_RE = re.compile(r"ВЕРСИЯ:\s*(v?\d+(?:\.\d+)*)", re.I)
_VER_TOKEN_RE = re.compile(r"v?\d+(?:\.\d+)*", re.I)
OUT = os.path.join(BUS, "_transit", "canon-from-hub")
MANIFEST = os.path.join(OUT, "MANIFEST.json")
STATE = os.path.join(HERE, "_canon_drift_state.json")
APPROVAL = os.path.join(HERE, "approval.py")
# Nodes NOT on the claude-home Syncthing share (VERIFY against LIVE REST /rest/config/folders,
# not config.xml -- the file lies; MAC1 was wrongly listed here on 2026-07-11 until
# the live check showed claude-home DOES reach it).
CANON_NODES = ["ANCHOR1"]
GRACE_DAYS = 3
# ROOT-FIX 2026-07-17 (backup canon publishers on HP17/Mac, task 8d03278c73ef): "source" used to
# be hardcoded "HUB1" -- fine while only the hub ran this script, but a backup publisher
# on another machine would then falsely claim to be the hub in its own manifest. Same env-ladder
# as machine_bus.py/fleet_manifest.py (MACHINE_KEY first, COMPUTERNAME fallback).
SOURCE = (os.environ.get("MACHINE_KEY") or os.environ.get("COMPUTERNAME") or "unknown").strip()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _now():
    return datetime.now(timezone.utc)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _rewrite_pending(node, entry):
    """Keep exactly ONE active canon-* parcel per node (drop stale canon-* lines)."""
    p = pending_file(node)
    keep = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    keep.append(line)
                    continue
                if not str(e.get("id", "")).startswith("canon-"):
                    keep.append(json.dumps(e, ensure_ascii=False))
    keep.append(json.dumps(entry, ensure_ascii=False))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".new"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(keep) + "\n")
    os.replace(tmp, p)


def _sign_canon():
    """HMAC-sig over the canonical TEXT of CLAUDE.md (CRLF-resilient). None = no secret/module."""
    if fleet_hmac is None:
        return None
    with open(CLAUDE, encoding="utf-8") as f:
        return fleet_hmac.sign_text(f.read())


def _read_version(path=None):
    """(version, date) from the CLAUDE.md header ВЕРСИЯ line, or (None, None) if absent.
    version keeps its 'v' prefix (e.g. 'v2.1.1'); the header format is a soft contract, so a
    missing line WARNS rather than bricking canon delivery (AK-47: never block the fleet on a
    header typo -- only block the clear violation 'md5 changed but version not bumped').
    CLAUDE is resolved at CALL time (not a def-time default) so a test/caller that rebinds the
    module path is honoured -- a def-time default silently pins the original path (/tt 2026-07-23)."""
    path = path or CLAUDE
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(4000)  # ВЕРСИЯ lives in the first lines
    except Exception:
        return None, None
    m = VERSION_RE.search(head)
    if not m:
        return None, None
    ver = m.group(1)
    dm = re.search(r"·\s*(\d{4}-\d{2}-\d{2})", head[m.end():m.end() + 60])
    return ver, (dm.group(1) if dm else None)


def _norm_ver(s):
    """First vX.Y.Z token in a string, lowercased without 'v' -> '2.1.1'. None if none."""
    if not s:
        return None
    m = _VER_TOKEN_RE.search(s)
    return m.group(0).lstrip("vV") if m else None


def _update_changelog(version, date_str, md5hex):
    """Ensure CLAUDE.CHANGELOG.md carries a row for `version` with the real published md5.
      - placeholder md5 cell (empty / pending / — / tbd) -> filled with md5[:8];
      - a DIFFERENT real hash already in the cell -> WARN, do NOT overwrite (preserves the
        audit trail of a version that shipped twice with different content);
      - no row for this version -> append one after the last table row.
    Returns a short status string for the caller to print."""
    if not version:
        return "no version -> changelog untouched"
    short = md5hex[:8]
    want = _norm_ver(version)
    try:
        with open(CHANGELOG, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "changelog file absent (%s)" % CHANGELOG
    last_row = -1
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4 or _norm_ver(cells[0]) is None:
            continue  # header / separator / non-version row
        last_row = i
        if _norm_ver(cells[0]) != want:
            continue
        cur_cell = cells[2]
        if short in cur_cell.lower():
            return "changelog row for %s already has md5 %s" % (version, short)
        if re.search(r"[0-9a-f]{6,}", cur_cell.lower()):  # a real, different hash sits there
            return ("⚠️ changelog: row %s already lists md5 '%s' != published %s -> ВЕРСИЯ likely "
                    "not bumped for a content change; left as-is for audit" % (version, cur_cell, short))
        cells[2] = short  # placeholder -> fill
        lines[i] = "| " + " | ".join(cells) + " |\n"
        with open(CHANGELOG, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)
        return "changelog: filled md5 %s into existing row %s" % (short, version)
    # no matching version row -> append after the last table row
    row = "| %s | %s | %s | (авто: опубликовано publish_canon) |\n" % (
        version, date_str or _now().strftime("%Y-%m-%d"), short)
    ins = last_row + 1 if last_row >= 0 else len(lines)
    lines[ins:ins] = [row]
    with open(CHANGELOG, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    return "changelog: appended row %s (md5 %s)" % (version, short)


def publish(dry=False):
    live = md5(CLAUDE)
    man = _load(MANIFEST, {})
    version, vdate = _read_version()
    man_ver = man.get("version")
    changed = man.get("md5") != live
    # VERSION GATE (Anton 2026-07-23): a content change MUST bump the ВЕРСИЯ line. If the file
    # changed but its version equals the version we last published, the edit shipped unversioned
    # -> BLOCK before writing anything. A missing header line only WARNS (never brick the fleet).
    if version is None:
        print("⚠️ publish: no ВЕРСИЯ line in CLAUDE.md header -> version gate + changelog skipped for this run")
    elif changed and man_ver and _norm_ver(version) == _norm_ver(man_ver):
        print("🔴 publish BLOCKED: CLAUDE.md content changed (md5 %s -> %s) but ВЕРСИЯ still %s "
              "(same as last published). Bump the header (MAJOR=ревизия · MINOR=правило · PATCH=микро) "
              "+ add a CLAUDE.CHANGELOG.md row, then re-run." % (
                  (man.get("md5") or "none")[:8], live[:8], version))
        return False
    if man.get("md5") == live and man.get("sig") and man_ver == version:
        print("publish: up-to-date (md5 %s, %s, signed)" % (live[:8], version or "no-ver"))
        return False
    if man.get("md5") == live:
        print("publish: content up-to-date but manifest stale (sig/version) -> re-publishing")
    if dry:
        try:
            sig = _sign_canon()
        except Exception:
            sig = None
        print("publish-DRY: would publish md5 %s (%d bytes, %s, %s) -> canon-from-hub + PENDING for %s; nothing written"
              % (live[:8], os.path.getsize(CLAUDE), version or "no-ver",
                 "signed" if sig else "UNSIGNED", ", ".join(CANON_NODES)))
        return True
    os.makedirs(OUT, exist_ok=True)
    # atomic tmp->replace (Codex T3 2026-07-21): hub AND laptop both run this on a schedule, so
    # concurrent publishers are real; a direct write could leave a node reading a half-copied file.
    # pid-unique tmp names: hub + laptop can publish concurrently, and a SHARED "CLAUDE.md.new"
    # lets one publisher's copy2 race the other's os.replace (Codex T3-BREAK #1, 2026-07-23).
    tag = ".new-%d" % os.getpid()
    dst = os.path.join(OUT, "CLAUDE.md")
    shutil.copy2(CLAUDE, dst + tag)
    os.replace(dst + tag, dst)
    sig = _sign_canon()
    if not sig:
        print("🔴 publish: NO FLEET SECRET on hub -> parcel goes out UNSIGNED; receivers will HOLD it. Fix ~/.claude/secrets/fleet_hmac.env")
        try:
            import bus_ping
            bus_ping.post("🔴 canon publish: хаб НЕ смог подписать канон (нет fleet-секрета) — узлы обязаны держать посылку в HELD")
        except Exception:
            pass
    man = {"md5": live, "version": version, "bytes": os.path.getsize(CLAUDE),
           "published_utc": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "source": SOURCE,
           "sig": sig, "sig_alg": "HMAC-SHA256 fleet_hmac v1 over canonical CLAUDE.md text"}
    with open(MANIFEST + tag, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    os.replace(MANIFEST + tag, MANIFEST)
    print("changelog:", _update_changelog(version, vdate, live))
    for node in CANON_NODES:
        _rewrite_pending(node, {
            "id": "canon-%s" % live[:8],
            "title": "Canon CLAUDE.md %s (hub) — СНАЧАЛА verify-гейт, потом влей СОДЕРЖАНИЕ в свой локальный канон; свою шапку/пути-адаптацию сохраняй; md5-равенство НЕ требуется" % live[:8],
            "apply": ("STEP 1 (gate): python3 ~/.claude/scripts/_shared/canon_verify.py %s/_transit/canon-from-hub ; "
                      "exit!=0 -> НЕ применять, посылку в HELD, алерт в 03. "
                      "STEP 2: read %s/_transit/canon-from-hub/CLAUDE.md -> merge -> write ACK-<node>.json {applied_md5:'%s'} рядом"
                      % (BUS.replace("\\", "/"), BUS.replace("\\", "/"), live)),
            "verify": "canon_verify.py exit 0 (VALID) зафиксирован ДО merge",
        })
    print("publish: OK md5 %s (%s) -> canon-from-hub + PENDING for %s"
          % (live[:8], "signed" if sig else "UNSIGNED", ", ".join(CANON_NODES)))
    return True


_TS_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%S",
               "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _parse_ts(s):
    """Tolerant UTC parse of the varied ACK timestamps ('...:04Z', '...12:05Z' seconds-less,
    ISO). None if unparseable."""
    if not s:
        return None
    s = str(s).strip().replace("+00:00", "").rstrip("Z") + ("Z" if str(s).strip().endswith("Z") else "")
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(str(s).strip(), fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _ack_files():
    return glob.glob(os.path.join(OUT, "ACK-*.json"))


def _load_ack_for(node):
    """ACK-<node>.json matched CASE-INSENSITIVELY (CANON_NODES lists 'ANCHOR1' but the file
    is 'ACK-ANCHOR1.json' -- the old exact-match missed it and read the node as un-ACKed)."""
    nl = node.lower()
    for p in _ack_files():
        if os.path.basename(p)[len("ACK-"):-len(".json")].lower() == nl:
            return _load(p, {})
    return {}


def _all_ack_nodes():
    """Every node the watchdog must verify: the hardcoded CANON_NODES PLUS every node that has
    ever written an ACK-*.json (case-deduped, real ACK spelling wins). Root-fix 2026-07-23: the
    old check watched ONLY CANON_NODES, so the hub (HUB1) sat 6 days behind unseen."""
    seen = {}
    for n in CANON_NODES:
        seen[n.lower()] = n
    for p in _ack_files():
        n = os.path.basename(p)[len("ACK-"):-len(".json")]
        seen[n.lower()] = n  # ACK-file spelling is the machine's own canonical spelling
    return [seen[k] for k in sorted(seen)]


def _escalate_02(node, days, cur):
    q = ("Канон CLAUDE.md на узле %s отстаёт от хаба %d дн. (нет ACK на %s). "
         "Пнуть узел / разобраться? + = да, займись · NO = осознанно оставляем" % (node, days, cur[:8]))
    if os.environ.get("CANON_DRIFT_DRYRUN"):
        print("ESCALATE-DRYRUN (02):", q)
        return True
    try:
        r = subprocess.run([sys.executable, APPROVAL, "ask", q], capture_output=True, timeout=60)
        ask_text = json.loads(r.stdout.decode("utf-8"))["ask_text"]
        import bus_ping
        bus_ping.post_police(ask_text)
        print("ESCALATED to 02 (node %s)" % node)
        return True
    except Exception as e:
        print("escalation failed:", e)
        return False


def check():
    # ROOT-FIX 2026-07-23 (Anton; memory watchdog-must-verify-the-item): the OLD check measured
    # the age of the CURRENT PUBLICATION, so every fresh publish reset the clock to 0 and a node
    # that stopped ACKing days ago never went RED (hub + Якорь sat 6 days behind, nobody screamed).
    # The watchdog must measure the ELEMENT it guards -> per-node age of that node's LAST ACK.
    # A node whose applied_md5 != current AND whose last ACK is older than GRACE = RED, regardless
    # of how recently the hub re-published.
    man = _load(MANIFEST, {})
    if not man:
        print("check: no manifest yet (run publish first)")
        return 0
    cur = man["md5"]
    if not man.get("sig"):
        print("⚠️ check: manifest UNSIGNED — узлы держат канон в HELD; прогони publish на машине с fleet-секретом")
    pub = _parse_ts(man.get("published_utc")) or _now()
    st = _load(STATE, {})
    st.setdefault("escalated", {})
    st.setdefault("behind_since", {})   # nodes that never ACKed -> first time we saw them behind
    red = 0
    for node in _all_ack_nodes():
        ack = _load_ack_for(node)
        if ack.get("applied_md5") == cur:
            print("GREEN %s: ack %s @ %s" % (node, cur[:8], ack.get("at") or ack.get("applied_utc", "?")))
            st["behind_since"].pop(node, None)
            continue
        # node is behind current canon. Clock = age since it LAST confirmed anything.
        # A node self-reports its ACK time, so a FUTURE timestamp (bogus / clock-skew) must NOT be
        # trusted -- it would make age negative and buy the node permanent WAIT, silently
        # suppressing the very drift alarm we are fixing (Codex T3-BREAK #3, 2026-07-23). A future
        # 'at' is treated as no usable ACK time -> falls through to the started-now clock below.
        ack_ts = _parse_ts(ack.get("at") or ack.get("applied_utc"))
        if ack_ts and ack_ts > _now():
            ack_ts = None
        if ack_ts:
            since, src = ack_ts, "last ACK (%s @ %s)" % ((ack.get("applied_md5") or "none")[:8],
                                                          ack.get("at") or ack.get("applied_utc"))
        else:
            # never ACKed at all: stamp first-sighting so the clock starts, fall back to publish time
            first = st["behind_since"].get(node)
            if not first:
                first = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
                st["behind_since"][node] = first
            since, src = (_parse_ts(first) or pub), "no ACK ever (since %s)" % first
        age_days = (_now() - since).total_seconds() / 86400.0
        if age_days < GRACE_DAYS:
            print("WAIT %s: behind %s, %.1f/%d days [%s]" % (node, cur[:8], age_days, GRACE_DAYS, src))
            continue
        red += 1
        idays = int(age_days)
        print("RED %s: canon drift, no ACK on %s for %.1f days [%s]" % (node, cur[:8], age_days, src))
        if not os.environ.get("CANON_DRIFT_DRYRUN"):
            try:
                import bus_ping
                bus_ping.post("⚠️ canon-drift: узел %s без ACK на канон %s уже %d дн. (%s)"
                              % (node, cur[:8], idays, src))
            except Exception as e:
                print("03 ping failed:", e)
        if st["escalated"].get(node) != cur:
            if _escalate_02(node, idays, cur):
                st["escalated"][node] = cur
    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(st, f, ensure_ascii=False)
    return 1 if red else 0


def main():
    # argparse (root-fix 2026-07-21): the old hand-rolled parser silently ignored anything it
    # didn't know -- `--help` fell through and PUBLISHED canon for real. Now --help exits 0 and
    # an unknown flag exits 2, both before any write.
    ap = argparse.ArgumentParser(
        prog="publish_canon.py",
        description="Canon CLAUDE.md publisher. No args = publish (if changed) + drift check "
                    "(current default behavior, used by the scheduled routine).")
    ap.add_argument("--dry", action="store_true",
                    help="show what WOULD be published (md5, size, nodes) and exit; writes nothing, no drift check")
    ap.add_argument("--check", action="store_true",
                    help="drift check only (MANIFEST vs ACK-*), no publish")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.dry:
        publish(dry=True)
        return 0
    publish()
    return check()


if __name__ == "__main__":
    sys.exit(main())
