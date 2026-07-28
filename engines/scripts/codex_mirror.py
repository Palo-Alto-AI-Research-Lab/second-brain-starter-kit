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
r"""codex_mirror.py -- one command to keep Codex's canon mirror (~/.codex/AGENTS.md) fresh.

WHY (root closed 2026-07-25): CLAUDE.md got its v2 revision on 22.07, AGENTS.md silently stayed
on the June canon for a MONTH -> Codex worked by old rules. The night watchdog
(_imports/arch/lint_agents_mirror.py) now SHOUTS when that happens; this script is the other
half -- the cheap, deterministic way to ACT on that shout without redoing the whole ritual by hand.

Division of labour (AK-47): this script moves bytes and proves things; the LLM only writes the
delta text into the mirror. Everything checkable is checked here, not remembered.

Commands
  check    what the canon says vs what the mirror says + the exact CHANGELOG delta to fold in
  backup   snapshot the current mirror into ~/.codex/_backup/ (run before editing)
  stamp    rewrite the 'MIRRORS: CLAUDE.md vX.Y.Z (date, md5) ...' header line from the live canon
  publish  gates (cap / stamp / anchors) -> copy to the codex-canon share -> md5 -> run the lint
  selftest 6 checks on synthetic files, touches nothing real

Exit: 0 = green, 1 = something must be fixed. ASCII-only stdout (Windows cp1251 consoles).
Paths come from env (skill-authoring-portable-paths); ~ fallbacks for peers.
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

HOME         = os.path.expanduser("~")
CLAUDE_DIR   = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
CODEX_DIR    = os.environ.get("CODEX_HOME") or os.path.join(HOME, ".codex")
IMPORTS_ROOT = os.environ.get("IMPORTS_ROOT") or os.path.join("E:\\", "Obsidian", "_imports")

CLAUDE_MD  = os.path.join(CLAUDE_DIR, "CLAUDE.md")
CHANGELOG  = os.path.join(CLAUDE_DIR, "CLAUDE.CHANGELOG.md")
AGENTS_MD  = os.path.join(CODEX_DIR, "AGENTS.md")
BACKUP_DIR = os.path.join(CODEX_DIR, "_backup")
SHARE_DIR  = os.path.join(IMPORTS_ROOT, "codex-canon")
LINT       = os.path.join(IMPORTS_ROOT, "arch", "lint_agents_mirror.py")

CAP = 32768  # Codex context budget for AGENTS.md; DR 29.06: a bloated file is WORSE than none
ANCHORS = ["## §%d." % i for i in range(11)] + ["### C%d." % i for i in range(1, 7)]

HEADROOM = 1024  # below this the next rule will not fit -- say so BEFORE the edit, not after

RX_CANON   = re.compile(r"ВЕРСИЯ:\s*v(\d+)\.(\d+)\.(\d+)")
RX_MIRROR  = re.compile(r"MIRRORS:\s*CLAUDE\.md\s*v(\d+)\.(\d+)\.(\d+)")
RX_STAMPH  = re.compile(r"MIRRORS:.*?md5\s+([0-9a-f]{6,32})")
RX_MIRLINE = re.compile(r"^>\s*MIRRORS:.*$", re.M)
RX_CLENTRY = re.compile(r"^(?:##\s*|\d{4}-\d{2}-\d{2}\s+)v(\d+)\.(\d+)\.(\d+)\b", re.M)


def read(path, limit=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return None


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ver(text, rx):
    m = rx.search(text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def vs(v):
    return "v%d.%d.%d" % v if v else "MISSING"


def changelog_delta(mirror_v, path=CHANGELOG):
    """Entries newer than the mirror's version -- exactly what has to be folded in."""
    text = read(path)
    if not text:
        return None, []
    marks = [(tuple(int(g) for g in m.groups()), m.start()) for m in RX_CLENTRY.finditer(text)]
    out = []
    for i, (v, start) in enumerate(marks):
        if mirror_v and v <= mirror_v:
            continue
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        out.append((v, body))
    out.sort(key=lambda x: x[0])
    return text, out


def cmd_check(a):
    canon, mirror = read(CLAUDE_MD), read(AGENTS_MD)
    if canon is None:
        print("FAIL: no CLAUDE.md at %s" % CLAUDE_MD); return 1
    cv = ver(canon[:4000], RX_CANON)
    if not os.path.isdir(CODEX_DIR):
        print("SKIP: no ~/.codex on this node -- nothing to mirror (green)"); return 0
    if mirror is None:
        print("FAIL: no AGENTS.md at %s -- bootstrap from %s" % (AGENTS_MD, SHARE_DIR)); return 1
    mv = ver(mirror[:4000], RX_MIRROR)

    size = os.path.getsize(AGENTS_MD)
    print("canon  CLAUDE.md %s  (%d b, md5 %s)" % (vs(cv), os.path.getsize(CLAUDE_MD), md5(CLAUDE_MD)[:8]))
    print("mirror AGENTS.md %s  (%d b / cap %d, %+d)" % (vs(mv), size, CAP, CAP - size))
    if CAP - size < HEADROOM:
        print("WARN: headroom %d b < %d -- the next rule fits only in exchange for trimming a fat"
              " paragraph in the SAME section; if it does not, the mirror needs a full revision." % (CAP - size, HEADROOM))
    if not cv or not mv:
        print("VERDICT: REBUILD -- version stamp missing on one side"); return 1

    if cv[:2] != mv[:2]:
        verdict, rc = "REBUILD (mirror lags by MAJOR.MINOR -- Codex is on OLD rules)", 1
    elif cv[2] != mv[2]:
        verdict, rc = "OK, PATCH lag only -- green by design; refresh stamp when convenient", 0
    else:
        verdict, rc = "OK -- mirror matches canon", 0
    print("VERDICT: %s" % verdict)

    _, delta = changelog_delta(mv)
    if delta:
        print("\n--- CHANGELOG delta (%d entr%s to fold into the mirror) ---"
              % (len(delta), "y" if len(delta) == 1 else "ies"))
        for v, body in delta:
            print("\n[%s]\n%s" % (vs(v), body))
    elif rc == 1:
        print("\nNOTE: no CHANGELOG entries newer than the mirror -- diff CLAUDE.md by hand.")
    return rc


def cmd_backup(a):
    if not os.path.exists(AGENTS_MD):
        print("FAIL: nothing to back up"); return 1
    os.makedirs(BACKUP_DIR, exist_ok=True)
    mv = ver(read(AGENTS_MD, 4000), RX_MIRROR)
    dst = os.path.join(BACKUP_DIR, "AGENTS.md.pre-%s-%s" % (
        ("v%d.%d.%d" % mv) if mv else "unstamped", datetime.now().strftime("%Y%m%d-%H%M")))
    shutil.copy2(AGENTS_MD, dst)
    print("backup: %s (%d b)" % (dst, os.path.getsize(dst)))
    return 0


def cmd_stamp(a):
    canon, mirror = read(CLAUDE_MD), read(AGENTS_MD)
    if canon is None or mirror is None:
        print("FAIL: canon or mirror unreadable"); return 1
    cv = ver(canon[:4000], RX_CANON)
    if not cv:
        print("FAIL: CLAUDE.md carries no 'ВЕРСИЯ: vX.Y.Z' -- versioning canon broken"); return 1
    if not RX_MIRLINE.search(mirror):
        print("FAIL: no '> MIRRORS: ...' line in AGENTS.md -- add it manually once"); return 1
    line = "> MIRRORS: CLAUDE.md %s (%s, md5 %s) · зеркало собрано %s хабом %s" % (
        vs(cv), datetime.now().strftime("%Y-%m-%d"), md5(CLAUDE_MD)[:8],
        datetime.now().strftime("%Y-%m-%d"), os.environ.get("MACHINE_HOST") or os.environ.get("COMPUTERNAME", "?"))
    new, n = RX_MIRLINE.subn(lambda m: line, mirror, count=1)
    if n != 1:
        print("FAIL: stamp line replace count = %d" % n); return 1
    with open(AGENTS_MD, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("stamped: %s" % line)
    return 0


def gates(path):
    """Deterministic publish gates. Returns (ok, lines)."""
    out, ok = [], True
    text = read(path)
    size = os.path.getsize(path)
    out.append("  size      %d b / cap %d  -> %s" % (size, CAP, "OK" if size <= CAP else "FAIL"))
    ok &= size <= CAP
    cv = ver(read(CLAUDE_MD, 4000) or "", RX_CANON)
    mv = ver(text[:4000], RX_MIRROR)
    same = bool(cv and mv and cv[:2] == mv[:2])
    out.append("  stamp     mirror %s vs canon %s -> %s" % (vs(mv), vs(cv), "OK" if same else "FAIL"))
    ok &= same
    missing = [x for x in ANCHORS if x not in text]
    out.append("  anchors   %d/%d present -> %s%s" % (len(ANCHORS) - len(missing), len(ANCHORS),
               "OK" if not missing else "FAIL: ", ", ".join(missing)))
    ok &= not missing
    # Codex T3 break #2: the canon can move between `stamp` and `publish` (a parallel /intake
    # session appends to CLAUDE.md) -> the stamp would claim a version whose body it never saw.
    sm = RX_STAMPH.search(text[:4000])
    live = md5(CLAUDE_MD)[:8] if os.path.exists(CLAUDE_MD) else None
    if sm and live:
        fresh = sm.group(1).startswith(live[:len(sm.group(1))]) or live.startswith(sm.group(1))
        out.append("  canon-md5 stamp %s vs live %s -> %s" % (sm.group(1), live,
                   "OK" if fresh else "FAIL: canon moved after stamping -- re-run `stamp`"))
        ok &= fresh
    return ok, out


def cmd_publish(a):
    if not os.path.exists(AGENTS_MD):
        print("FAIL: no mirror to publish"); return 1
    print("gates:")
    ok, lines = gates(AGENTS_MD)
    print("\n".join(lines))
    if not ok:
        print("PUBLISH BLOCKED -- fix the FAILs above (nothing was copied)"); return 1
    if a.dry_run:
        print("dry-run: gates pass, share copy and lint skipped"); return 0

    dst = os.path.join(SHARE_DIR, "AGENTS.md")
    try:  # Codex T3 break #3: E: may be absent on this node / share unwritable
        os.makedirs(SHARE_DIR, exist_ok=True)
        shutil.copy2(AGENTS_MD, dst)
    except OSError as e:
        print("FAIL: share %s unreachable (%s) -- local Codex is updated, the FLEET copy is NOT."
              " Re-run publish when the drive is back." % (SHARE_DIR, e.__class__.__name__))
        return 1
    src_h, dst_h = md5(AGENTS_MD), md5(dst)
    print("share:    %s  md5 %s %s %s" % (dst, src_h[:8], "==" if src_h == dst_h else "!=", dst_h[:8]))
    if src_h != dst_h:
        print("PUBLISH FAILED -- share copy differs"); return 1

    if os.path.exists(LINT):
        r = subprocess.run([sys.executable, LINT], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print("lint:     %s (exit %d)" % ((r.stdout or "").strip().splitlines()[-1:] or [""], r.returncode))
        if r.returncode != 0:
            print("PUBLISH DONE but the night watchdog still flags it -- read %s"
                  % os.path.join(IMPORTS_ROOT, "arch", "_lint_agents_mirror.txt"))
            return 1
    else:
        print("lint:     SKIP (no %s on this node)" % LINT)
    print("PUBLISH OK -- Codex on this node and the share are on the current canon")
    return 0


def cmd_selftest(a):
    """6 checks on synthetic files; the real mirror is never touched."""
    global CLAUDE_MD, AGENTS_MD, CHANGELOG
    tmp = tempfile.mkdtemp(prefix="codexmirror_")
    keep = (CLAUDE_MD, AGENTS_MD, CHANGELOG)
    passed = failed = 0

    def chk(name, cond):
        nonlocal passed, failed
        print("  %s %s" % ("PASS" if cond else "FAIL", name))
        if cond: passed += 1
        else: failed += 1

    def write(p, s):
        with open(p, "w", encoding="utf-8") as f: f.write(s)
        return p

    try:
        body = "\n".join(ANCHORS) + "\n"
        CLAUDE_MD = write(os.path.join(tmp, "CLAUDE.md"), "> ВЕРСИЯ: v2.3.0 · 2026-07-26\n")
        live8 = md5(CLAUDE_MD)[:8]
        CHANGELOG = write(os.path.join(tmp, "CHANGELOG.md"),
                          "## v2.3.0 · 2026-07-26\n- new rule X\n\n## v2.2.1 · 2026-07-25\n- old rule\n")

        AGENTS_MD = write(os.path.join(tmp, "fresh.md"), "> MIRRORS: CLAUDE.md v2.3.0 (x, md5 y)\n" + body)
        chk("gates pass on a fresh, in-cap, fully-anchored mirror", gates(AGENTS_MD)[0])

        AGENTS_MD = write(os.path.join(tmp, "stale.md"), "> MIRRORS: CLAUDE.md v2.2.1 (x, md5 y)\n" + body)
        chk("MINOR-stale mirror is BLOCKED", not gates(AGENTS_MD)[0])

        AGENTS_MD = write(os.path.join(tmp, "nostamp.md"), body)
        chk("unstamped mirror is BLOCKED", not gates(AGENTS_MD)[0])

        AGENTS_MD = write(os.path.join(tmp, "short.md"),
                          "> MIRRORS: CLAUDE.md v2.3.0 (x, md5 y)\n" + "\n".join(ANCHORS[:-1]) + "\n")
        chk("mirror missing the C6 anchor is BLOCKED (a lost block = silent hole)", not gates(AGENTS_MD)[0])

        AGENTS_MD = write(os.path.join(tmp, "fat.md"),
                          "> MIRRORS: CLAUDE.md v2.3.0 (x, md5 y)\n" + body + "x" * CAP)
        chk("over-cap mirror is BLOCKED", not gates(AGENTS_MD)[0])

        _, delta = changelog_delta((2, 2, 1), CHANGELOG)
        chk("changelog delta returns exactly the newer entry",
            len(delta) == 1 and delta[0][0] == (2, 3, 0) and "new rule X" in delta[0][1])

        # Codex T3 break #2: right version, stale md5 = the canon moved after stamping
        AGENTS_MD = write(os.path.join(tmp, "moved.md"),
                          "> MIRRORS: CLAUDE.md v2.3.0 (2026-07-26, md5 deadbeef)\n" + body)
        chk("stamp of the right version but a STALE canon md5 is BLOCKED", not gates(AGENTS_MD)[0])

        AGENTS_MD = write(os.path.join(tmp, "matching.md"),
                          "> MIRRORS: CLAUDE.md v2.3.0 (2026-07-26, md5 %s)\n" % live8 + body)
        chk("same version + matching canon md5 passes", gates(AGENTS_MD)[0])
    finally:
        CLAUDE_MD, AGENTS_MD, CHANGELOG = keep
        shutil.rmtree(tmp, ignore_errors=True)

    print("selftest: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="Keep ~/.codex/AGENTS.md (Codex canon mirror) in sync with CLAUDE.md.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", help="canon vs mirror + CHANGELOG delta to fold in (default)")
    sub.add_parser("backup", help="snapshot the mirror into ~/.codex/_backup/")
    sub.add_parser("stamp", help="rewrite the MIRRORS header line from the live canon")
    p = sub.add_parser("publish", help="gates -> share copy -> md5 -> night lint")
    p.add_argument("--dry-run", action="store_true", help="gates only, copy nothing")
    sub.add_parser("selftest", help="6 synthetic checks, touches nothing real")
    a = ap.parse_args()
    return {"backup": cmd_backup, "stamp": cmd_stamp, "publish": cmd_publish,
            "selftest": cmd_selftest}.get(a.cmd, cmd_check)(a)


if __name__ == "__main__":
    sys.exit(main())
