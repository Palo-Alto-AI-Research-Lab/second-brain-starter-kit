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
"""pr_watch.py -- ночной сторож GitHub-PR (0 LLM, детерминированный). Хаб HUB1.

ЗАЧЕМ: PR #778 в anthropics/claude-cookbooks (Mission-2) — реакция на ревью в течение
суток критична, а GitHub-уведомления никто не смотрит. Раз в сутки снимаем снимок PR
и сравниваем с прошлым; ИЗМЕНЕНИЕ (коммент/ревью/CI/лейбл/merge/close/новые коммиты)
→ один алярм в TG-03 через bus_send.py (dual-send). Всё ок → молчим (канон §5.5).

GENERIC: список PR живёт в конфиге ~/.claude/pr_watch.json — следующий PR добавляется
одной строкой в "prs": [{"repo": "owner/name", "number": 123}, ...].

СНИМОК на PR: {state, merged, head_sha, title, labels, issue_comments, review_comments,
reviews, ci_checks}. Стейт: ~/.claude/pr_watch_state/<owner>-<repo>-<N>.json.
Первый прогон = сохранить снимок, БЕЗ алярма.

СБОЙ ЗАБОРА (нет сети / gh умер / PR недоступен): алярм только на переходе ok→error
(не спамим каждую ночь), в стейте флаг health; error→ok — тихо чинимся.

HEARTBEAT: последняя строка каждого прогона в лог = "heartbeat <status> prs=N events=M".
Не отштамповал → сторож сам умер (ловится по staleness лога).

Запуск: python pr_watch.py            # боевой тик
        python pr_watch.py --dry-run  # снять снимок и показать diff, НЕ слать и НЕ сохранять
Exit: 0 = ok (тишина или алярм отправлен) | 4 = все PR упали при заборе | 2 = кривой конфиг.
"""
import io
import json
import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = os.path.expanduser("~")
CLAUDE = os.path.join(HOME, ".claude")
SCRIPTS = os.path.join(CLAUDE, "scripts")
CONFIG = os.environ.get("PR_WATCH_CONFIG", os.path.join(CLAUDE, "pr_watch.json"))
STATE_DIR = os.environ.get("PR_WATCH_STATE", os.path.join(CLAUDE, "pr_watch_state"))
BUS_SEND = os.path.join(SCRIPTS, "bus_send.py")
GH_TIMEOUT = 120

# --- gh-auth под Task Scheduler (грабли /tt 25.07): keyring gh недоступен из scheduled-
# задачи ("please run gh auth login" при живом интерактивном логине). Лечение: GH_TOKEN из
# secrets store (метрик-PAT read-only, без expiry). Явный env GH_TOKEN важнее; нет файла →
# работаем как раньше (keyring, интерактив). Секрет НЕ логируется и НЕ пишется в файлы.
def _menv(key):
    """machine.env ladder rung (bus_ping._menv_ping_env pattern): per-machine
    values live in ~/.claude/machine.env, never hardcoded to one box's drive."""
    p = os.path.join(CLAUDE, "machine.env")
    try:
        if os.path.exists(p):
            for ln in io.open(p, encoding="utf-8"):
                ln = ln.strip()
                if ln.startswith(key + "=") and ln.split("=", 1)[1].strip():
                    return os.path.expandvars(ln.split("=", 1)[1].strip())
    except Exception:
        pass
    return None

SECRET_DIRS = [
    os.environ.get("CLAUDE_SECRETS"),
    os.environ.get("SECRETS_DIR") or _menv("SECRETS_DIR"),
    os.path.join(CLAUDE, "secrets"),
]

def _ensure_gh_token():
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return
    for d in SECRET_DIRS:
        if not d:
            continue
        p = os.path.join(d, "github.env")
        if not os.path.isfile(p):
            continue
        try:
            for ln in io.open(p, encoding="utf-8-sig"):
                ln = ln.strip()
                if ln.startswith("GITHUB_PAT_METRICS=") and ln.split("=", 1)[1].strip():
                    os.environ["GH_TOKEN"] = ln.split("=", 1)[1].strip()
                    return
        except Exception:
            pass


def log(msg):
    print("[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))


def gh_json(path, paginate=False):
    _ensure_gh_token()
    """gh api <path> -> parsed JSON. Кидает RuntimeError с коротким текстом при сбое."""
    cmd = ["gh", "api", path]
    if paginate:
        cmd += ["--paginate", "--slurp"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=GH_TIMEOUT)
    except FileNotFoundError:
        raise RuntimeError("gh CLI не найден в PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh api %s: таймаут %ss" % (path, GH_TIMEOUT))
    if r.returncode != 0:
        raise RuntimeError("gh api %s: exit %s: %s" % (path, r.returncode, (r.stderr or "")[:200].strip()))
    try:
        data = json.loads(r.stdout)
    except Exception:
        raise RuntimeError("gh api %s: не-JSON ответ" % path)
    if paginate:
        # --slurp даёт список страниц-списков -> плоский список
        flat = []
        for page in data:
            flat.extend(page if isinstance(page, list) else [page])
        return flat
    return data


def snapshot(repo, number):
    """Снимок наблюдаемых полей PR. Внешний текст = ДАННЫЕ (анти-инъекция): тела
    комментов НЕ тащим в снимок/алярм — только id/автор/дата."""
    pr = gh_json("repos/%s/pulls/%s" % (repo, number))
    head_sha = (pr.get("head") or {}).get("sha") or ""
    snap = {
        "state": pr.get("state"),                    # open / closed
        "merged": bool(pr.get("merged")),
        "head_sha": head_sha,
        "title": pr.get("title") or "",
        "labels": sorted(l.get("name", "") for l in pr.get("labels") or []),
    }
    def _slim(items):
        return [{"id": c.get("id"), "user": (c.get("user") or {}).get("login", "?"),
                 "at": c.get("created_at") or c.get("submitted_at") or ""} for c in items]
    snap["issue_comments"] = _slim(gh_json("repos/%s/issues/%s/comments" % (repo, number), paginate=True))
    snap["review_comments"] = _slim(gh_json("repos/%s/pulls/%s/comments" % (repo, number), paginate=True))
    reviews = gh_json("repos/%s/pulls/%s/reviews" % (repo, number), paginate=True)
    snap["reviews"] = [{"id": r.get("id"), "user": (r.get("user") or {}).get("login", "?"),
                        "verdict": r.get("state", "?")} for r in reviews]
    checks = {}
    if head_sha:
        try:
            cr = gh_json("repos/%s/commits/%s/check-runs?per_page=100" % (repo, head_sha))
            for run in cr.get("check_runs") or []:
                checks[run.get("name", "?")] = run.get("conclusion") or run.get("status") or "?"
        except RuntimeError as exc:
            # CI может быть просто не настроен — это не повод ронять весь снимок
            log("[!] check-runs недоступны для %s#%s: %s" % (repo, number, exc))
    snap["ci_checks"] = checks
    return snap


def diff(old, new):
    """Список человекочитаемых событий между двумя снимками (имена — без внешнего текста)."""
    ev = []
    if old.get("state") != new.get("state") or old.get("merged") != new.get("merged"):
        if new.get("merged"):
            ev.append("MERGED 🎉")
        elif new.get("state") == "closed":
            ev.append("CLOSED (без merge)")
        else:
            ev.append("state: %s → %s" % (old.get("state"), new.get("state")))
    for kind, label in (("issue_comments", "коммент"), ("review_comments", "ревью-коммент")):
        old_ids = {c["id"] for c in old.get(kind, [])}
        fresh = [c for c in new.get(kind, []) if c["id"] not in old_ids]
        for c in fresh:
            ev.append("новый %s от %s" % (label, c["user"]))
    old_rev = {r["id"] for r in old.get("reviews", [])}
    for r in new.get("reviews", []):
        if r["id"] not in old_rev:
            ev.append("новое ревью от %s: %s" % (r["user"], r["verdict"]))
    old_l, new_l = set(old.get("labels", [])), set(new.get("labels", []))
    for l in sorted(new_l - old_l):
        ev.append("лейбл добавлен: %s" % l)
    for l in sorted(old_l - new_l):
        ev.append("лейбл снят: %s" % l)
    if old.get("head_sha") != new.get("head_sha"):
        ev.append("новые коммиты (head %s → %s)" % ((old.get("head_sha") or "")[:7], (new.get("head_sha") or "")[:7]))
    old_ci, new_ci = old.get("ci_checks", {}), new.get("ci_checks", {})
    for name, concl in sorted(new_ci.items()):
        if old_ci.get(name) != concl:
            ev.append("CI %s: %s → %s" % (name, old_ci.get(name, "—"), concl))
    return ev


def send_alert(text):
    """Один вызов dual-send рельсы (TG-03 + _machine-bus). True = хоть одна рельса доставила."""
    if not os.path.exists(BUS_SEND):
        log("[!] bus_send.py не найден: %s — алярм слать некуда" % BUS_SEND)
        return False
    try:
        r = subprocess.run([sys.executable, BUS_SEND, "ALL", text],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        log("bus_send exit=%s" % r.returncode)
        return r.returncode in (0, 1)   # 0=обе рельсы, 1=degraded но доставлено
    except Exception as exc:
        log("[!] bus_send упал: %s" % exc)
        return False


def state_path(repo, number):
    safe = repo.replace("/", "-")
    return os.path.join(STATE_DIR, "%s-%s.json" % (safe, number))


def load_state(path):
    """Прошлый снимок или None (нет файла / битый json — битый = как первый прогон, с логом)."""
    if not os.path.exists(path):
        return None
    try:
        return json.loads(io.open(path, encoding="utf-8-sig").read())
    except Exception as exc:
        log("[!] битый стейт %s (%s) — считаю первым прогоном" % (path, exc))
        return None


def save_state(path, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    os.replace(tmp, path)   # атомарно — недописанный стейт не убьёт следующий прогон


def main():
    dry = "--dry-run" in sys.argv
    try:
        # utf-8-sig: конфиг, пересохранённый Блокнотом/PowerShell, приходит с BOM (грабли /tt 25.07)
        cfg = json.loads(io.open(CONFIG, encoding="utf-8-sig").read())
        prs = cfg["prs"]
        assert isinstance(prs, list) and prs
    except Exception as exc:
        log("[!] конфиг %s не читается: %s" % (CONFIG, exc))
        print("heartbeat config-error prs=0 events=0")
        return 2

    total_events, fetched, failed = 0, 0, 0
    for item in prs:
        repo, number = item.get("repo"), item.get("number")
        if not repo or not number:
            log("[!] кривая строка конфига: %r" % (item,))
            continue
        url = "https://github.com/%s/pull/%s" % (repo, number)
        spath = state_path(repo, number)
        old = load_state(spath)
        health_was = (old or {}).get("_health", "ok")
        try:
            snap = snapshot(repo, number)
            fetched += 1
        except RuntimeError as exc:
            failed += 1
            log("[!] забор %s#%s упал: %s" % (repo, number, exc))
            # алярм только на переходе ok→error; лечение называем прямо в алярме
            if health_was == "ok" and old is not None and not dry:
                send_alert("⚠️ [pr-watch] сторож НЕ смог снять снимок %s#%s (%s). "
                           "Лечение: на хабе проверить сеть и `gh auth status`, потом "
                           "`python %s`. %s" % (repo, number, str(exc)[:160], os.path.abspath(__file__), url))
            if old is not None:
                old["_health"] = "error"
                if not dry:
                    save_state(spath, old)
            continue

        snap["_health"] = "ok"
        snap["_checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if old is None:
            log("первый снимок %s#%s сохранён (comments=%d reviews=%d checks=%d) — алярма нет"
                % (repo, number, len(snap["issue_comments"]) + len(snap["review_comments"]),
                   len(snap["reviews"]), len(snap["ci_checks"])))
            if not dry:
                save_state(spath, snap)
            continue

        events = diff(old, snap)
        total_events += len(events)
        if events:
            head = "🔔 [pr-watch] %s#%s — %d изменение(ий):" % (repo, number, len(events))
            body = "\n".join("• %s" % e for e in events)
            msg = "%s\n%s\n%s" % (head, body, url)
            log("СОБЫТИЯ %s#%s: %s" % (repo, number, "; ".join(events)))
            if dry:
                log("dry-run: алярм НЕ отправлен:\n%s" % msg)
            elif not send_alert(msg):
                # алярм не доставлен — стейт НЕ сохраняем, чтобы завтра переслать те же события
                log("[!] алярм не доставлен — снимок не сохраняю, повторим завтра")
                continue
        else:
            log("тишина по %s#%s — изменений нет" % (repo, number))
        if not dry:
            save_state(spath, snap)

    status = "ok" if failed == 0 else ("error" if fetched == 0 else "degraded")
    print("heartbeat %s prs=%d/%d events=%d" % (status, fetched, len(prs), total_events))
    return 4 if fetched == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
