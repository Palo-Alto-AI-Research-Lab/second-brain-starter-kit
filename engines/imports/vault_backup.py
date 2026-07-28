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
"""vault_backup.py — RUN BEFORE ANY VAULT-MODIFYING OPERATION.
Commits the current vault state to git so ANY change (incl. deletions) is recoverable.
Standing rule: always `python vault_backup.py "<what I am about to do>"` first.

Recovery cheatsheet:
  git -C <vault> log --oneline                 # find the snapshot
  git -C <vault> restore --source <hash> -- <path>   # bring one file/folder back
  git -C <vault> checkout <hash> -- 06-Concepts       # bring a whole folder back
"""
import subprocess, sys, os, time, glob
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 чинит крах print() на эмодзи/кириллице в метке
except Exception: pass
try:
    from _paths import VAULT                       # portable: reads ~/.claude/machine.env
except Exception:
    VAULT = r"%VAULT%"         # HP17 fallback if _paths/machine.env unavailable
# VAULT_BACKUP_TARGET (env) — ТОЛЬКО для _test_vault_backup.py: git-песочница вместо реального
# волта (в бою переменная не выставлена -> реальный волт). Даёт /tt-ить бэкапер безопасно.
VAULT = os.environ.get("VAULT_BACKUP_TARGET") or VAULT

try:
    from brain_common import Lock                  # reuse the proven pid-aware lock (no new lock logic)
except Exception:
    class Lock:                                    # graceful: no brain_common -> backup still runs, just unguarded
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

def git(*a):
    return subprocess.run(["git", "-C", VAULT, *a], capture_output=True, text=True, encoding="utf-8", errors="ignore")

def git_w(*a):
    # WRITE-ops (add/commit/reset): параллельный Claude-флот тоже коммитит волт и может держать
    # .git/index.lock -> git падает МГНОВЕННО ("Unable to create '.../index.lock': File exists").
    # Ретраим ТОЛЬКО lock-конфликт; любая ДРУГАЯ ошибка возвращается сразу (не маскируем).
    # Основной класс-фикс = Lock ниже (2B, один бэкап за раз); git_w = вторая линия обороны
    # от НЕ-vault_backup писателей git. Окно = backoff 2+4+8с (~14с): замер 2026-07-04 —
    # `git add -A` на 128k-волте держит lock ~4.5с, цикл add+commit ~7-10с, прежние 3x2с (4с)
    # класс не перекрывали. Поймано 2x (2026-06-20, hub).
    delays = (2, 4, 8)
    r = None
    for i in range(len(delays) + 1):
        r = git(*a)
        if r.returncode == 0 or "index.lock" not in ((r.stderr or "") + (r.stdout or "")).lower():
            return r
        if i < len(delays):
            time.sleep(delays[i])
    return r


# --- reconcile-aware recoverability (2026-07-23, ROOT FIX for the recurring _originals false
# alarm — 4th recurrence 07-09/11/21/23). A staged deletion is BENIGN if its content still
# survives somewhere, so it must NOT trip the human-facing mass-delete alarm:
#   (a) a Syncthing .stversions twin exists — proves the delete arrived via SYNC (Syncthing
#       versions files it removes during a pull), not a local `rm`/bug wiping the working tree;
#   (b) the file is named in a reconcile ledger (hub-side planned move).
# git history ALSO keeps the pre-deletion blob regardless, so committing loses nothing either
# way — this classifier only decides whether to ALARM a human. 0 LLM, ledger read-only.
def _porcelain_path(line):
    # "XY <path>"  or a rename "XY <old> -> <new>"; git quotes non-ASCII paths in double quotes.
    p = line[3:].strip()
    if " -> " in p:
        p = p.split(" -> ", 1)[1]
    return p.strip().strip('"')

_LEDGER_CACHE = None
def _ledger_text():
    global _LEDGER_CACHE
    if _LEDGER_CACHE is None:
        _LEDGER_CACHE = ""
        fp = os.path.join(VAULT, "_originals", "_RECONCILE-LEDGER.md")
        try:
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                _LEDGER_CACHE = fh.read()
        except Exception:
            pass
    return _LEDGER_CACHE

RECOVER_FRESH_DAYS = 30   # a .stversions twin proves BENIGN churn only if RECENT: a year-old
# stale version must NOT clear a fresh accidental mass-delete (Gemini break #1). Sync churn is
# always versioned "today" (twin timestamp = when Syncthing applied the delete here), so 30 days
# is a wide safety margin over the ~15-min backup cadence while defeating stale-version masking.

def _twin_is_fresh(path):
    # Syncthing twin name: <stem>~YYYYMMDD-HHMMSS<ext>. Judge by the embedded version timestamp
    # (local time, as Syncthing writes it); fall back to file mtime if the name is unparseable.
    import re
    m = re.search(r"~(\d{8}-\d{6})", os.path.basename(path))
    now = time.time()
    # bounded window: 0..RECOVER_FRESH_DAYS in the PAST, with 1-day future grace for clock skew.
    # A far-FUTURE stamp (e.g. ~20990101 from a broken clock) must NOT read as "fresh" via a
    # negative age — that would mask loss forever (Gemini break v2 #1).
    def _fresh(age):
        return -86400 <= age <= RECOVER_FRESH_DAYS * 86400
    if m:
        try:
            ts = time.mktime(time.strptime(m.group(1), "%Y%m%d-%H%M%S"))
            return _fresh(now - ts)
        except Exception:
            pass
    try:
        return _fresh(now - os.path.getmtime(path))
    except OSError:
        return False

def _ledger_has(frag, led):
    # frag (relpath под _originals/) должен встретиться в леджере как ЦЕЛЫЙ путь-токен, а НЕ как
    # суффикс внутри более длинного имени. Голое `frag in led` даёт ложный recoverable и МАСКИРУЕТ
    # реальную потерю: удаляем `note.md`, а в леджере где-то есть `bignote.md` -> совпало ->
    # массовое удаление не блокируется (Codex T3 #1 residual, Gemini break #1, 2026-07-27).
    # Требуем разделители по обе стороны совпадения (леджер обрамляет пути ` `/пробелами/newline).
    BND = " \t\r\n`\"'|"
    for cand in (frag, frag.replace(os.sep, "/"), frag.replace(os.sep, "\\")):
        start = 0
        while True:
            i = led.find(cand, start)
            if i < 0:
                break
            before = led[i - 1] if i > 0 else "\n"
            after = led[i + len(cand)] if i + len(cand) < len(led) else "\n"
            if before in BND and after in BND:
                return True
            start = i + 1
    return False

def _recoverable(relpath):
    rel = relpath.replace("/", os.sep).lstrip(os.sep)
    d, base = os.path.split(rel)
    stem, ext = os.path.splitext(base)
    # (a) a RECENT .stversions twin. glob.escape the WHOLE dir+stem+ext so metachars in real
    # folder names ("Archive [2024]") are literal, not a glob char-class (Gemini break #3).
    base_dir = os.path.join(VAULT, ".stversions", d)
    pat = os.path.join(glob.escape(base_dir), glob.escape(stem) + "~*" + glob.escape(ext))
    if any(_twin_is_fresh(t) for t in glob.glob(pat)):
        return True
    # (b) reconcile-ledger membership — match the path RELATIVE TO _originals/, NOT the bare
    # basename (Codex T3 #1: bare basename false-matches an unrelated same-named file in another
    # folder, masking a real loss). The ledger only tracks _originals/ moves, so gate on that.
    if rel.startswith("_originals" + os.sep):
        frag = rel[len("_originals" + os.sep):]
        if frag and _ledger_has(frag, _ledger_text()):
            return True
    return False

if not os.path.isdir(os.path.join(VAULT, ".git")):
    print("NO_GIT_REPO — initialize git in the vault first."); sys.exit(1)

# --- аргументы: флаги + свободный текст-метка ---
_args = sys.argv[1:]
force   = "--force" in _args
_labels = [a for a in _args if not a.startswith("--")]
label = _labels[0] if _labels else "pre-intervention"

# --- single-backup lock (2B): parallel Claude sessions each call vault_backup; without this
# they collide on .git/index.lock during a long `git add -A` (esp. a huge one-time changeset),
# one gets interrupted -> commit returns nonzero -> the OLD code mislabeled it "corrupt".
# Lock (reused from brain_common: pid-aware, auto-clears stale) lets only ONE backup touch git
# at a time. A colliding backup exits 0 (busy_exit_code=0, BENIGN): the running backup is mid
# add+commit, so it captures this session's changes too — nothing is lost, no index.lock race.
with Lock(name="vault_backup", busy_exit_code=0, max_age_min=30):  # backup = секунды; лок >30мин = крэш+recycled-PID -> reclaim, иначе каждый след. бэкап молча skip'ит (T9)
    git("config", "core.longpaths", "true")   # иначе длинный путь (GDrive-импорт) валит `add` целиком
    _add = git_w("add", "-A")
    if _add.returncode != 0:
        print("WARN: `git add -A` FAILED (rc=%d) — снимок может быть НЕПОЛНЫМ:" % _add.returncode)
        for _ln in (_add.stderr or "").strip().splitlines()[:4]:
            print("  ", _ln)
        print("  -> почини путь-нарушитель (core.longpaths / укороти имя), затем повтори.")
    # quotePath=false: без него git C-эскейпит не-ASCII пути (кириллица/DR-имена в _originals)
    # в "\NNN\NNN..." -> _porcelain_path отдаёт искажённый путь -> _recoverable не находит ни
    # .stversions-твин, ни строку леджера -> ЛОЖНЫЙ BLOCK на benign churn ровно там, где фикс и
    # задуман (не-ASCII _originals — главный источник reconcile-удалений). Gemini break #2 (2026-07-27).
    st = git("-c", "core.quotePath=false", "status", "--porcelain")
    lines = [l for l in st.stdout.splitlines() if l.strip()]
    changed = len(lines)

    # --- mass-delete tripwire: быстро, из git (без обхода 128k файлов на медленном E:) ---
    # Блокирует коммит, если на удаление помечено >= DELETE_BLOCK файлов — как glob-delete
    # 2026-06-06 (111 concept-нот). Косметику (битый YAML и пр.) тут НЕ трогаем — её ловит
    # полный vault_doctor.py. Намеренную массовую чистку (дедуп) проводи с --force.
    DELETE_BLOCK = 50
    _dels = [l for l in lines if l[:1] == "D"]
    deleted = len(_dels)
    if deleted >= DELETE_BLOCK and not force:
        # ROOT FIX 2026-07-23: alarm ONLY on deletions with NO surviving copy. A .stversions
        # twin or ledger entry = benign propagated sync churn (nightly originals_reconcile /
        # leaked-md cleanup), which used to burn a peer session on EVERY run. See _recoverable().
        _unexplained = [l for l in _dels if not _recoverable(_porcelain_path(l))]
        _recov = deleted - len(_unexplained)
        if len(_unexplained) >= DELETE_BLOCK:
            print("BLOCKED: %d files staged for DELETION (>= %d); %d WITHOUT a recoverable copy - possible mass-delete." % (deleted, DELETE_BLOCK, len(_unexplained)))
            # RCA 2026-07-16 (GDrive-Sheets 739): голое "BLOCKED" без контекста породило 3
            # расходящихся задачи про одну ренейм-волну. adds ~= deletes -> скорее rename/dedup.
            added = len([l for l in lines if l[:1] == "A"])
            import collections
            _top = collections.Counter(
                "/".join(_porcelain_path(l).split("/")[:3]) for l in _unexplained).most_common(3)
            for _folder, _n in _top:
                print("  UNEXPLAINED deletions in: %-60s %d" % (_folder, _n))
            print("  staged ADDS alongside: %d %s" % (
                added, "(adds ~= deletes -> likely an import RENAME/DEDUP wave, not data loss;"
                       " check the folder for the new names before assuming deletion)" if
                       added >= deleted * 0.8 else ""))
            print("  -> review:  git -C \"%s\" status   |   intended? re-run with --force." % VAULT)
            git_w("reset")
            sys.exit(2)
        # all-but-<DELETE_BLOCK deletions are recoverable -> benign churn, do NOT alarm a human.
        print("NOTE: %d deletions staged; %d recoverable (.stversions/ledger), %d unexplained (< %d) — benign sync churn, committing." % (
            deleted, _recov, len(_unexplained), DELETE_BLOCK))
        # SECOND tripwire (root fix pt.2, 2026-07-23): vault_precommit_guard.py runs as the git
        # pre-commit HOOK with its OWN binary mass-delete block. vault_backup has already VETTED
        # these deletions as recoverable, so authorize the hook to pass them — mirrors the
        # VAULT_CANON_OK=1 handoff below. Without this, the hook re-blocked at commit time and the
        # false alarm survived even after THIS tripwire cleared it (caught by live /tt on 51 real
        # deletions). The hook still guards un-vetted DIRECT `git commit` (env unset there).
        os.environ["VAULT_MASSDEL_OK"] = "1"

    # --- canon advisory (any-LLM guardrails, 2026-06-29): the pre-commit guard blocks DIRECT
    # `git commit` touching canon files; the BACKUP must never break (it captures reality for
    # rollback), so here we only DETECT + SCREAM, then commit with VAULT_CANON_OK=1.
    # Canon list lives in ONE place: vault_precommit_guard.CANON_FILES.
    try:
        from vault_precommit_guard import CANON_FILES as _CANON
    except Exception:
        _CANON = ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]
    _canon_hits = [l for l in lines if any(c in l for c in _CANON)]
    if _canon_hits:
        print("!!! CANON FILES CHANGED ON DISK (snapshot proceeds, Anton must review/revert):")
        for _l in _canon_hits[:6]:
            print("   ", _l.strip())
        os.environ["VAULT_CANON_OK"] = "1"

    # Per-person git identity (P4, shared-machine attribution): resolve who this commit is
    # attributed to -- explicit VAULT_GIT_AUTHOR_* env > operator-at-keyboard (CLAUDE_OPERATOR /
    # ~/.claude/operator.txt -> GIT_OPERATOR_<op> in machine.env) > repo git config default.
    # Logic in git_author.py (synced to all machines); per-machine operator table in machine.env.
    # Proven by _test_git_author.py. try/except: a machine without git_author.py still backs up.
    try:
        from git_author import resolve_git_author
        _an, _ae = resolve_git_author()
    except Exception:
        _an = os.environ.get("VAULT_GIT_AUTHOR_NAME")
        _ae = os.environ.get("VAULT_GIT_AUTHOR_EMAIL")
    _author = []
    if _an: _author += ["-c", "user.name=%s" % _an]
    if _ae: _author += ["-c", "user.email=%s" % _ae]
    r = git_w(*_author, "commit", "-m", "backup: %s" % label)
    out = (r.stdout + r.stderr)
    if "nothing to commit" in out.lower():
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        print("HEAD", head, "— NO_CHANGES (already clean snapshot)")
    elif r.returncode != 0:
        # LOUD but HONEST failure (1A): report git's REAL error, never GUESS "corrupt".
        # A broken HEAD used to fall through to the "committed" branch and LIE the snapshot
        # was saved (hid a 2-day gap on PaloAlto-Desktop, 2026-06-21) -> we fail loud now.
        # But blaming EVERY nonzero rc on "bad HEAD/ref" was ALSO a lie: the usual cause is a
        # parallel/interrupted backup holding index.lock (concurrency), not corruption.
        print("BACKUP FAILED (git commit rc=%d) — snapshot NOT saved:" % r.returncode)
        for _ln in out.strip().splitlines()[:6]:
            print("  ", _ln)
        if "index.lock" in out.lower():
            print("  -> a parallel backup holds .git/index.lock (or one was interrupted) —")
            print("     this is a CONCURRENCY collision, NOT corruption. Re-run in a moment.")
        else:
            print("  -> if this repeats, check repo health: git -C \"%s\" fsck --full" % VAULT)
        sys.exit(3)
    else:
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        print("HEAD", head, "— committed", changed, "changes:", label)
