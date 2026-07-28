#!/usr/bin/env python3
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
gemini_review.py -- "Gemini проверяет Claude": ТРЕТЬЯ внешняя пара глаз, родной брат
codex_review.py (OpenAI) и grok_review.py (xAI).

WHY (anton 2026-07-27): у /tt уже есть Codex (дефолт) и Grok (вторая рельса). Gemini даёт
третьего независимого вендора с другой обучающей базой -> спасает вердикт, когда у Codex
выжжена квота, и ломает гетеро-парой то, что два других не увидели.

ДВА РЕЖИМА (тот же скрипт, разные потребители):
  review  -- ревью git-диффа, контракт как у братьев: VERDICT: APPROVE | REQUEST_CHANGES
             + отчёт review-gemini-<ts>.md.
  break   -- QA-ЛОМАТЕЛЬ для Шага 2.5 ритуала /tt: тот же break-промпт, что у Grok-рельсы;
             первая строка ответа = ACCEPT/COUNTER/BLOCK, вердикт САМ логируется в
             secondop usage.jsonl (`secondop.py log-ext --reviewer gemini`) -- ручной
             log-ext не нужен, наблюдаемость /tt получает бесплатно.
  doctor  -- жива ли рельса (CLI на PATH · ключ в store · живой ping) -- ДО того, как
             на неё понадеялся ритуал.

ДВИЖОК (⚠️ УСЛОЖНЕНИЕ, обоснованное): две headless-рельсы к одной модели.
  1) REST generativelanguage.googleapis.com -- ДЕФОЛТ, stdlib-urllib, ответ ~5-10 c.
  2) `gemini -p` (@google/gemini-cli, headless) -- `--engine cli`. ЗАМЕР 27.07: отвечает, но
     при всплеске квоты уходит в ретраи с backoff (один ping растянулся на 435 c) и падает
     с `[object Object]`; REST на том же ключе даёт 9-11 c и внятную ошибку.
Обе headless и без браузера. Дефолт выбран ЗАМЕРОМ, а не вкусом: ритуал /tt не может ждать
минуты. Дешёвая альтернатива (одна рельса) = теряем вендора, когда его рельса ляжет.

АВТОРИЗАЦИЯ: ТОЛЬКО API-ключ из secrets store (`gemini.env`), НЕ платный тир --
проект без биллинга, превышение = 429, не счёт.
⚠️ OAuth-логин CLI («вход по гуглю») для физлиц Google ОТКЛЮЧИЛ: IneligibleTierError /
UNSUPPORTED_CLIENT -> «мигрируйте в Antigravity». Не чинить его заново -- это тупик вендора.

READ-ONLY: `--approval-mode plan` (режим «только чтение») + пустой список инструментов;
Gemini только рассуждает над текстом, файлы не трогает.

Usage:
  python gemini_review.py [--repo PATH] [--range GITRANGE] [--diff PATCH] [--task TASKFILE]
                          [--out DIR] [--model M] [--timeout S] [--engine cli|rest]
  python gemini_review.py break --task <id> --context "<что собрали + что проверили>"
                          [--ritual tt] [--no-log]
  python gemini_review.py doctor
"""
import argparse, json, os, re, shutil, subprocess, sys, time
import urllib.request, urllib.error

FIRST_WORD = re.compile(r"[A-Z_]+")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, ".."))
SECONDOP = os.path.join(HERE, "secondop.py")
MAX_DIFF_CHARS = 120_000
# Порядок ЗАМЕРЕН 27.07 живьём, не угадан: Pro на бесплатном тире отдаёт квоту (429) сразу,
# каждая попытка = лишний круг -> первым идёт flash, который реально отвечает. Pro доступен
# явным --model, если Антон когда-нибудь подключит биллинг.
MODEL_CHAIN = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"]
REST_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"

REVIEW_PROMPT = """You are an INDEPENDENT senior code reviewer. The diff below was written by a
DIFFERENT AI coding agent (Anthropic Claude). Your job is to catch what it got wrong,
acting as an adversarial second pair of eyes. Be specific and grounded in the diff.

Review for, in priority order:
1. CORRECTNESS bugs (logic errors, off-by-one, wrong conditions, broken edge cases,
   null/empty/overflow, race conditions, resource leaks).
2. SECURITY (injection, unsafe input, secret handling, auth/permission gaps).
3. BREAKAGE (does it break existing behavior, contracts, or callers?).
4. SIMPLIFICATION / reuse (clearly over-complex code that should be simpler).

Rules:
- Only report issues you can justify from the diff. No vague "consider maybe".
- For each finding: file:line (best effort) - severity [HIGH/MED/LOW] - what's wrong - the fix.
- If the change is clean, say so plainly. Do not invent problems.
- Review only. Do not attempt to edit, write, or run anything.

End with exactly one VERDICT line:
VERDICT: APPROVE   (no blocking issues)
or
VERDICT: REQUEST_CHANGES   (1+ MED/HIGH issues)

Output clean Markdown. Start with a one-line summary, then findings, then the VERDICT line.
"""

# Тот же контракт, что у Grok-рельсы (secondop.GROK_BREAK_PROMPT): первая строка = вердикт.
BREAK_PROMPT = """\
Ты — внешний QA-ломатель (second opinion) в нашем ритуале приёмки /tt. Другой ИИ только что
собрал/поправил артефакт и уже прогнал свои проверки. Твоя работа — попробовать его СЛОМАТЬ.

Задача: {task}

Что собрали и что уже проверено:
{context}

Ищи то, что автор не видит сам: краевые случаи и кривой ввод; отсутствующие зависимости;
Windows-грабли путей (C:/E:, пробелы, кодировки); тихие сбои (exit 0 при нуле работы);
гонки при параллельном запуске; устаревшие предположения; «работает у автора, умрёт у соседа».

Формат ответа — СТРОГО:
Первая строка — ровно одно слово: ACCEPT (реальных проблем не нашёл) ИЛИ COUNTER (нашёл
проблемы, надо чинить) ИЛИ BLOCK (критично, выпускать нельзя).
Дальше — нумерованный список конкретных сценариев поломки с шагами воспроизведения, без воды.
"""


# ---------------------------------------------------------------- ключ и окружение
def _menv(key):
    """Пер-машинное значение из ~/.claude/machine.env (канон §10.3: не хардкодим C:/E:)."""
    p = os.path.join(os.path.expanduser("~"), ".claude", "machine.env")
    try:
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line.startswith(key + "=") and line.split("=", 1)[1].strip():
                    return os.path.expandvars(line.split("=", 1)[1].strip())
    except Exception:
        pass
    return None


def api_key():
    """env -> secrets store. Ключ НИКОГДА не печатается и не уезжает в лог/чат."""
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k.strip()
    sdir = os.environ.get("SECRETS_DIR") or _menv("SECRETS_DIR")
    if sdir:
        p = os.path.join(sdir, "gemini.env")
        try:
            for line in open(p, encoding="utf-8"):
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return ""


def _quota_error(text):
    low = (text or "").lower()
    return ("429" in low or "quota" in low or "rate limit" in low
            or "resource_exhausted" in low or "exhausted" in low)


# ---------------------------------------------------------------- две рельсы к модели
def ask_cli(prompt, model, timeout, cwd):
    """Рельса 1: официальный CLI headless. Read-only: --approval-mode plan."""
    exe = shutil.which("gemini") or shutil.which("gemini.cmd")
    if not exe:
        return None, "gemini CLI не на PATH (npm i -g @google/gemini-cli)"
    env = dict(os.environ)
    env["GEMINI_API_KEY"] = api_key()
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"   # иначе CLI просит доверить папку интерактивно
    try:
        proc = subprocess.run([exe, "-p", prompt, "-m", model, "--approval-mode", "plan",
                               "-o", "text"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return None, "gemini CLI timeout %ds" % timeout
    except OSError as e:
        return None, "gemini CLI не запустился: %s" % e
    out = (proc.stdout or "").strip()
    if out:
        return out, None
    # Косметический шум CLI («true color», «ripgrep») уезжал в вердикт ВМЕСТО настоящей
    # причины -- оператор читал «нет true color» там, где был битый ключ (находка /tt 27.07).
    noise = ("true color", "ripgrep", "warning:")
    lines = [l for l in (proc.stderr or "").splitlines()
             if l.strip() and not any(n in l.lower() for n in noise)]
    return None, ("\n".join(lines).strip()[:400] or "CLI вернул пустой ответ без диагностики")


def ask_rest(prompt, model, timeout):
    """Рельса 2: прямой REST на stdlib -- работает, когда CLI лёг."""
    key = api_key()
    if not key:
        return None, "нет GEMINI_API_KEY (env или secrets/gemini.env)"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(REST_URL % (model, key), data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])
    except Exception as e:
        return None, str(e)[:300]
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        return None, "ответ без текста: %s" % json.dumps(data)[:300]
    return (text, None) if text else (None, "пустой ответ модели")


def _fatal_error(text):
    """Ошибки, при которых перебирать модели и рельсы бессмысленно -- лечение одно и то же."""
    low = (text or "").lower()
    return "api_key_invalid" in low or "api key not valid" in low or "permission_denied" in low


def ask(prompt, model, timeout, engine="rest", cwd=None):
    """Спросить Gemini: выбранная рельса -> при квоте спуск по MODEL_CHAIN -> фолбэк-рельса.
    Возвращает (text, model_used, engine_used, err). Ошибку возвращаем ПЕРВУЮ содержательную
    (она про причину), а не последнюю (последняя -- шум упавшего фолбэка)."""
    cwd = cwd or os.getcwd()
    chain = [model] + [m for m in MODEL_CHAIN if m != model] if model else list(MODEL_CHAIN)
    rails = [engine] + [e for e in ("rest", "cli") if e != engine]
    errs = []
    for rail in rails:
        for m in chain:
            text, err = (ask_cli(prompt, m, timeout, cwd) if rail == "cli"
                         else ask_rest(prompt, m, timeout))
            if text:
                return text, m, rail, None
            err = err or "?"
            errs.append("%s/%s: %s" % (rail, m, err.replace("\n", " ")[:200]))
            if _fatal_error(err):
                return None, None, None, errs[0]   # битый ключ -> не жечь время на перебор
            if not _quota_error(err):
                break   # не квота -> другая модель не поможет, меняем рельсу
            sys.stderr.write("[gemini] %s на %s: квота -> следующая модель\n" % (rail, m))
    # Один ключ на весь флот: три узла, стрельнувшие одновременно, выжигают короткое окно
    # и ВСЕ трое остаются без второго глаза (Grok VERIFY #2, 28.07). Бак у Google минутный,
    # поэтому одна выдержанная пауза дешевле, чем потерянный вердикт. Ровно одна.
    if errs and _quota_error(errs[0]) and not os.environ.get("GEMINI_NO_RETRY"):
        wait = _retry_delay(errs[0])
        sys.stderr.write("[gemini] окно выжжено -> жду %ds и пробую ОДИН раз\n" % wait)
        time.sleep(wait)
        text, err = (ask_rest(prompt, chain[0], timeout) if rails[0] == "rest"
                     else ask_cli(prompt, chain[0], timeout, cwd))
        if text:
            return text, chain[0], rails[0], None
        errs.append("retry/%s: %s" % (chain[0], (err or "?").replace("\n", " ")[:200]))
    return None, None, None, " | ".join(errs[:2]) if errs else "?"


def _retry_delay(err, default=20, cap=45):
    """Google сам говорит, сколько ждать («Please retry in 13.05s») -- слушаем его, а не гадаем."""
    m = re.search(r"retry in ([0-9]+)", err or "")
    return min(int(m.group(1)) + 2, cap) if m else default


# ---------------------------------------------------------------- режим review
def _verdict_line(review):
    """Вердикт читаем ОДНИМ общим парсером (scripts/_shared/verdict_parse.py): своя
    самодельная догадка про форму строки уже дважды теряла вердикт молча."""
    sys.path.insert(0, os.path.join(SCRIPTS, "_shared"))
    try:
        import verdict_parse
    except ImportError:
        return "VERDICT: (unreadable) ⚠️  <- нет scripts/_shared/verdict_parse.py; смотри отчёт"
    return verdict_parse.verdict_line(review)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def get_diff(args):
    if args.diff:
        with open(args.diff, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), "patchfile:" + args.diff
    repo = args.repo or os.getcwd()
    if not os.path.isdir(os.path.join(repo, ".git")):
        sys.exit("ERROR: %s is not a git repo. Use --diff PATCHFILE or --repo PATH." % repo)
    if args.range:
        # Только ревизии, никаких флагов: `--range "--no-index <секрет> <файл>"` превращал
        # ревью в утечку произвольного файла наружу (Codex VERIFY #3, 27.07).
        parts = args.range.split()
        bad = [p for p in parts if p.startswith("-")]
        if bad:
            sys.exit("ERROR: --range принимает только ревизии, флаги запрещены (нашёл: %s). "
                     "Нужен произвольный дифф -> сохрани его в файл и передай --diff." % " ".join(bad))
        out = run(["git", "-C", repo, "diff"] + parts)
        src = "git diff " + args.range
    else:
        out = run(["git", "-C", repo, "diff", "HEAD"])
        src = "git diff HEAD (working tree)"
    if out.returncode != 0:
        sys.exit("ERROR: git diff failed: " + out.stderr.strip())
    return out.stdout, src


def cmd_review(args):
    diff, src = get_diff(args)
    if not diff.strip():
        print("No changes to review (empty diff). Nothing for Gemini to check.")
        return 0
    truncated = ""
    if len(diff) > MAX_DIFF_CHARS:
        # Резать ТОЛЬКО голову опасно: длинная безобидная преамбула прячет опасный хвост,
        # и ревьюер спокойно ставит APPROVE на непрочитанное (Codex VERIFY #1, 27.07).
        # Берём голову И хвост, а в промпте говорим вслух, что ревью частичное.
        head, tail = int(MAX_DIFF_CHARS * 0.7), int(MAX_DIFF_CHARS * 0.3)
        skipped = len(diff) - head - tail
        diff = diff[:head] + ("\n\n[... %d chars omitted from the MIDDLE ...]\n\n" % skipped) + diff[-tail:]
        truncated = ("\n\n[diff too large: %d chars omitted from the middle. This review is "
                     "PARTIAL -- say so in your summary and never claim the whole change is "
                     "clean.]\n" % skipped)
    task_block = ""
    if args.task and os.path.isfile(args.task):
        with open(args.task, "r", encoding="utf-8", errors="replace") as f:
            task_block = "## TASK Claude was asked to do\n%s\n\n" % f.read().strip()
    prompt = "%s\n%s## DIFF (Claude's change), source: %s\n```diff\n%s\n```%s\n" % (
        REVIEW_PROMPT, task_block, src, diff, truncated)

    repo = args.repo if os.path.isdir(args.repo or "") else os.getcwd()
    t0 = time.time()
    review, model, rail, err = ask(prompt, args.model, args.timeout, args.engine, cwd=repo)
    dt = int(time.time() - t0)
    if not review:
        sys.exit("ERROR: gemini review failed (%ds): %s" % (dt, err))

    out_dir = args.out or repo
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(out_dir, "review-gemini-%s.md" % ts)
    header = ("# Gemini review of Claude's change\n- when: %s\n- source: %s\n"
              "- reviewer: %s via %s (read-only)\n- took: %ds\n\n" % (ts, src, model, rail, dt))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + review + "\n")
    print("OK - review saved: %s" % out_path)
    print(_verdict_line(review))
    return 0


# ---------------------------------------------------------------- режим break (/tt Шаг 2.5)
def _first_verdict(text):
    """Первая строка = вердикт. Невидимые символы (BOM/zero-width) едут с копипастой и
    молча съедали настоящий вердикт (грабли Grok 21.07) -- чистим до сравнения."""
    head = (text or "").strip()
    for cp in (0xFEFF, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F):
        head = head.replace(chr(cp), "")
    line = head.strip().splitlines()[0].strip() if head.strip() else ""
    line = line.lstrip("#*> ").strip()
    m = FIRST_WORD.match(line.upper())
    return m.group(0) if m else line[:40]


def cmd_break(args):
    if not args.task or not args.context:
        sys.exit("ERROR: break требует --task и --context")
    prompt = BREAK_PROMPT.format(task=args.task, context=args.context)
    t0 = time.time()
    text, model, rail, err = ask(prompt, args.model, args.timeout, args.engine)
    dt = int(time.time() - t0)
    if not text:
        # Сбой рельсы = ЯВНЫЙ скип, не тихий зелёный: /tt обязан упасть в ⚠️ PARTIAL.
        print("⚠️ GEMINI НЕ ОТВЕТИЛ (%s) -- вердикт не получен, ✅ ставить нельзя." % (err or "?")[:160])
        _log_secondop(args, verdict="", note="rail failed: %s" % (err or "?")[:120], skip=True)
        return 3
    verdict = _first_verdict(text)
    print("[GEMINI-BREAK %s · %s via %s · %ds]" % (args.task, model, rail, dt))
    print(text)
    print("\n--- вердикт первой строкой: %s ---" % verdict)
    logged = True
    if not args.no_log:
        logged = _log_secondop(args, verdict=verdict,
                               note="gemini %s/%s: %s" % (model, rail, text.strip().replace("\n", " ")[:150]))
        if not logged:
            # Слой видимости молчит -> ритуал ослеп, хотя вердикт получен. Тихий exit 0 тут
            # означал бы «проверено» при пустом леджере (Codex VERIFY #2, 27.07).
            print("⚠️ ВЕРДИКТ НЕ ЗАПИСАН в secondop usage.jsonl -- дайджест /tt этого прогона "
                  "НЕ УВИДИТ. Считать проверку незалогированной: почини лог или впиши вручную "
                  "(secondop.py log-ext --reviewer gemini ...).")
    if verdict not in ("ACCEPT", "COUNTER", "BLOCK"):
        return 3
    return 0 if logged else 3


def _log_secondop(args, verdict, note, skip=False):
    """Наблюдаемость /tt: пишем в тот же usage.jsonl, что Codex и Grok -- дайджест
    (secondop.py digest) видит все три рельсы. Возвращает True/False: НЕ записалось =
    вызывающий обязан сказать это вслух, а не выйти зелёным."""
    if not os.path.exists(SECONDOP):
        sys.stderr.write("[gemini] secondop.py не найден -- вердикт не залогирован\n")
        return False
    if skip:
        cmd = [sys.executable, SECONDOP, "log-skip", "--task", args.task,
               "--ritual", args.ritual or "tt", "--reason", note[:180]]
    else:
        cmd = [sys.executable, SECONDOP, "log-ext", "--reviewer", "gemini",
               "--task", args.task, "--ritual", args.ritual or "tt",
               "--verdict", verdict, "--note", note[:180]]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        sys.stderr.write("[gemini] secondop log: %s\n" % ((p.stdout or p.stderr or "").strip()[:200]))
        return p.returncode == 0
    except Exception as e:
        sys.stderr.write("[gemini] лог в secondop не прошёл: %s\n" % str(e)[:160])
        return False


# ---------------------------------------------------------------- режим doctor
def cmd_doctor(args):
    """Жива ли рельса? Зелёное = МОЛЧАЩИЙ ok, красное = имя больного + лечение."""
    ok = True
    exe = shutil.which("gemini") or shutil.which("gemini.cmd")
    print("CLI на PATH: %s" % (exe if exe else "НЕТ ⛔ -> npm i -g @google/gemini-cli"))
    ok &= bool(exe)
    key = api_key()
    print("API-ключ: %s" % ("есть (%d симв.) ✅" % len(key) if key
                            else "НЕТ ⛔ -> secrets/gemini.env, строка GEMINI_API_KEY="))
    ok &= bool(key)
    # Слой видимости проверяем ДО боя: на Якорье стоял secondop.py без `log-ext`, и вердикт
    # Gemini молча не попадал в журнал -- зелёный doctor это не ловил (Grok VERIFY #3, 28.07).
    sink = "НЕТ ⛔ -> нет secondop.py, вердикт писать некуда"
    if os.path.exists(SECONDOP):
        try:
            has = "log-ext" in open(SECONDOP, encoding="utf-8", errors="replace").read()
        except Exception:
            has = False
        sink = ("`log-ext` есть ✅" if has else
                "secondop.py СТАРЫЙ (нет `log-ext`) ⛔ -> вердикты потеряются молча; "
                "подтяни версию с хаба")
        ok &= has
    else:
        ok = False
    print("журнал вердиктов: %s" % sink)
    auth = os.path.join(os.path.expanduser("~"), ".gemini", "settings.json")
    sel = ""
    try:
        sel = json.load(open(auth, encoding="utf-8")).get("security", {}).get("auth", {}).get("selectedType", "")
    except Exception:
        pass
    print("~/.gemini/settings.json auth: %s" % (
        sel + (" ✅" if sel == "gemini-api-key"
               else " ⚠️ (oauth-personal для физлиц Google отключил -> ставь gemini-api-key)")
        if sel else "не задан ⚠️ -> security.auth.selectedType=gemini-api-key"))
    t0 = time.time()
    text, model, rail, err = ask("Reply with exactly one word: PONG", args.model,
                                 args.timeout or 90, args.engine)
    dt = int(time.time() - t0)
    if text and "PONG" in text.upper():
        print("живой ping: %s via %s за %ds ✅" % (model, rail, dt))
    else:
        ok = False
        print("живой ping: ⛔ %s (%ds) -> проверь ключ/сеть; лечение: gemini_review.py doctor "
              "--engine rest" % ((err or text or "?")[:200], dt))
    print("ИТОГ: %s" % ("рельса Gemini ЖИВА ✅" if ok else "рельса Gemini НЕ ГОТОВА ⛔"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("mode", nargs="?", default="review", choices=["review", "break", "doctor"])
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--range", default="")
    ap.add_argument("--diff", default="")
    ap.add_argument("--task", default="")
    ap.add_argument("--context", default="")
    ap.add_argument("--ritual", default="tt")
    ap.add_argument("--out", default="")
    ap.add_argument("--model", default="", help="по умолчанию цепочка: " + " -> ".join(MODEL_CHAIN))
    ap.add_argument("--engine", default="rest", choices=["rest", "cli"],
                    help="rest = прямой headless-вызов (дефолт, ~10 c); cli = @google/gemini-cli (медленнее)")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--no-log", action="store_true", help="break: не писать вердикт в secondop usage.jsonl")
    args = ap.parse_args()
    if args.mode == "doctor":
        return cmd_doctor(args)
    if args.mode == "break":
        return cmd_break(args)
    return cmd_review(args)


if __name__ == "__main__":
    sys.exit(main())
