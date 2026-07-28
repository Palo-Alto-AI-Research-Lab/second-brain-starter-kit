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
"""issue_match.py -- ЗАМЕР очереди чужого репо + поиск ЖИВОЙ двери (issue) ДО пуша PR.

ЗАЧЕМ: правило [[cold-pr-into-silent-queue]] (Антон, замер 25.07.2026): холодный PR в глухую
очередь = шум, не вклад. Замер очереди -- ПЕРВЫЙ шаг, до написания кода. До этого скрипта
замер делался руками в каждой сессии заново (18 сессий за неделю 21-27.07).

0 LLM, 0 токенов -- только `gh` (уже авторизован) + арифметика. Ничего не пушит, не пишет
в репо, не комментит: READ-ONLY. Решение о PR всё равно принимает человек.

ЧТО МЕРИТ (всё -- живьём, ничего из головы):
  A. ОЧЕРЕДЬ: сколько открытых PR (точный счёт через search, не обрезанный лимитом),
     медиана возраста (по выборке новейших), доля PR без единого комментария,
     как выглядят реальные мержи (медиана часов до мержа + доля "смержено в день подачи"
     = признак договорённости ДО PR).
  B. МЫ ТАМ: сколько наших PR открыто и сколько из них холодные (0 комментариев).
  C. ДВЕРИ: открытые issue с активностью за последние N дней; если задан --artifact --
     отфильтрованные по ключевым словам (title + labels + body). Наши собственные issue
     считаются отдельно: своя дверь -- не приглашение.
  D. ВЕРДИКТ: 🟢 живая дверь (входим через issue) / 🟡 очередь ок, но двери нет
     (открыть issue и ждать) / 🔴 глухая очередь (не пушить).

ЗАПУСК:
  python issue_match.py anthropics/claude-cookbooks
  python issue_match.py anthropics/claude-cookbooks --artifact "search agent, adversarial verify"
  python issue_match.py --all                      # по всем репо из конфига
  python issue_match.py --init                     # собрать конфиг из НАШЕЙ истории PR
  python issue_match.py <repo> --json              # машинный вывод

КОНФИГ: ~/.claude/issue_match.json {"repos": [...], "live_days": 30}. Нет конфига -> --all
сам выведет список репо из наших PR (тот же путь, что --init).

EXIT: 0 = замер сделан | 2 = кривые аргументы/конфиг | 4 = gh недоступен или все заборы упали.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".claude" / "issue_match.json"
GH_TIMEOUT = 60

# Пороги вердикта (менять здесь, а не по месту вызова)
STALE_MEDIAN_DAYS = 30.0     # медиана возраста открытых PR выше -> очередь глухая
WARM_MEDIAN_DAYS = 14.0      # ниже -> очередь живая
SILENT_SHARE_RED = 0.70      # доля PR без комментариев выше -> глухая
SILENT_SHARE_OK = 0.50       # ниже -> терпимо
DEFAULT_LIVE_DAYS = 30       # issue считается живым, если обновлялся за столько дней
PR_SAMPLE = 100              # сколько новейших открытых PR берём для медианы возраста
MERGED_SAMPLE = 30           # сколько последних мержей смотрим на паттерн
ISSUE_SAMPLE = 60            # сколько открытых issue тянем


def _out(s: str = "") -> None:
    print(s)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_bot(actor: dict | None) -> bool:
    """Бот или человек. gh отдаёт is_bot; у app-аккаунтов логин вида 'dependabot[bot]'."""
    a = actor or {}
    login = (a.get("login") or "").lower()
    return bool(a.get("is_bot")) or login.endswith("[bot]") or login in {
        "github-actions", "dependabot", "stale", "codecov", "renovate"}


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def gh(args: list[str]) -> tuple[int, str, str]:
    """Вызов gh. Возвращает (rc, stdout, stderr). Не бросает -- решает вызывающий."""
    try:
        p = subprocess.run(["gh"] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=GH_TIMEOUT)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "gh не найден в PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"gh не ответил за {GH_TIMEOUT}с"


def gh_json(args: list[str], default):
    rc, out, err = gh(args)
    if rc != 0 or not out:
        return default, err or f"gh rc={rc}"
    try:
        return json.loads(out), None
    except json.JSONDecodeError as e:
        return default, f"нечитаемый JSON от gh: {e}"


def search_count(query: str) -> tuple[int | None, str | None]:
    """Точный счёт через search API (не обрезан лимитом list)."""
    data, err = gh_json(["api", f"search/issues?q={query}&per_page=1"], None)
    if err or not isinstance(data, dict):
        return None, err or "нет ответа search"
    return data.get("total_count"), None


def me() -> str | None:
    rc, out, _ = gh(["api", "user", "--jq", ".login"])
    return out if rc == 0 and out else None


def measure_queue(repo: str, login: str | None) -> dict:
    """A + B: здоровье очереди и наше присутствие в ней."""
    q = {"repo": repo, "errors": []}

    open_prs, err = search_count(f"repo:{repo}+is:pr+is:open")
    if err:
        q["errors"].append(f"счёт открытых PR: {err}")
    q["open_prs"] = open_prs

    silent, err = search_count(f"repo:{repo}+is:pr+is:open+comments:0")
    if err:
        q["errors"].append(f"счёт молчаливых PR: {err}")
    q["open_prs_zero_comment"] = silent
    q["silent_share"] = (silent / open_prs) if (open_prs and silent is not None) else None

    # медиана возраста -- по выборке новейших открытых PR
    prs, err = gh_json(["pr", "list", "--repo", repo, "--state", "open",
                        "--limit", str(PR_SAMPLE), "--json", "number,createdAt"], [])
    if err:
        q["errors"].append(f"список открытых PR: {err}")
    ages = [(now_utc() - parse_ts(p.get("createdAt"))).total_seconds() / 86400
            for p in prs if parse_ts(p.get("createdAt"))]
    q["age_sample"] = len(ages)
    q["age_sample_is_partial"] = bool(open_prs and len(ages) < open_prs)
    q["median_age_days"] = round(statistics.median(ages), 1) if ages else None

    # паттерн реальных мержей
    merged, err = gh_json(["pr", "list", "--repo", repo, "--state", "merged",
                           "--limit", str(MERGED_SAMPLE),
                           "--json", "number,createdAt,mergedAt,author"], [])
    if err:
        q["errors"].append(f"список мержей: {err}")
    hrs, same_day, authors = [], 0, {}
    for p in merged:
        c, m = parse_ts(p.get("createdAt")), parse_ts(p.get("mergedAt"))
        if c and m:
            h = (m - c).total_seconds() / 3600
            hrs.append(h)
            if h <= 24:
                same_day += 1
        a = (p.get("author") or {}).get("login")
        if a and not is_bot(p.get("author")):
            authors[a] = authors.get(a, 0) + 1
    # Разовый автор = вероятный "чужак с улицы". Если таких мержей нет, репо мержит
    # только своих, и здоровая медиана ничего нам не обещает (находка Grok 27.07).
    q["drive_by_merges"] = sum(1 for a, n in authors.items() if n == 1)
    q["merged_sample"] = len(hrs)
    q["median_merge_hours"] = round(statistics.median(hrs), 1) if hrs else None
    q["same_day_merge_share"] = (same_day / len(hrs)) if hrs else None
    q["distinct_merge_authors"] = len(authors)
    q["merges_from_regulars_only"] = bool(hrs) and q["drive_by_merges"] == 0

    # наше присутствие
    if login:
        ours, _ = search_count(f"repo:{repo}+is:pr+is:open+author:{login}")
        cold, _ = search_count(f"repo:{repo}+is:pr+is:open+author:{login}+comments:0")
        merged_ours, _ = search_count(f"repo:{repo}+is:pr+is:merged+author:{login}")
        q["our_open_prs"] = ours
        q["our_cold_prs"] = cold
        q["our_merged_prs"] = merged_ours
    return q


def find_doors(repo: str, keywords: list[str], live_days: int, login: str | None) -> dict:
    """C: открытые issue, живые по updatedAt, с матчингом по ключевым словам."""
    res = {"errors": [], "live": [], "ours": [], "checked": 0, "keywords": keywords,
           "fetch_ok": False, "open_total": None, "sample_partial": False}
    issues, err = gh_json(["issue", "list", "--repo", repo, "--state", "open",
                           "--limit", str(ISSUE_SAMPLE),
                           "--json", "number,title,body,createdAt,updatedAt,labels,comments,author,url"], [])
    if err:
        # ВАЖНО: забор упал -> "дверей нет" НЕ доказано. Вердикт обязан стать UNKNOWN,
        # иначе инструмент соврёт человеку удобным ему ответом "не пушить".
        res["errors"].append(f"список issue: {err}")
        return res
    res["fetch_ok"] = True
    res["checked"] = len(issues)
    total, terr = search_count(f"repo:{repo}+is:issue+is:open")
    res["open_total"] = total
    if total is not None and total > len(issues):
        # дверь может лежать ЗА выборкой -> "не нашли" != "нет"
        res["sample_partial"] = True
    elif terr:
        res["errors"].append(f"счёт открытых issue: {terr}")
    for it in issues:
        # ЖИВОСТЬ = человеческая активность, не updatedAt: тот дёргают боты и лейблы,
        # а бот-"bump" на брошенном тикете выглядел бы как живая дверь (нашёл Grok 27.07).
        comments = it.get("comments") or []
        human_c = [c for c in comments if not is_bot((c or {}).get("author"))]
        last_human = parse_ts(human_c[-1].get("createdAt")) if human_c else None
        created = parse_ts(it.get("createdAt"))
        author_human = not is_bot(it.get("author"))
        cands = []
        if last_human:
            cands.append((now_utc() - last_human).total_seconds() / 86400)
        if created and author_human:
            cands.append((now_utc() - created).total_seconds() / 86400)
        if not cands:
            continue  # ни человеческого комментария, ни человека-автора = не дверь
        human_days = min(cands)
        if human_days > live_days:
            continue
        upd = parse_ts(it.get("updatedAt"))
        age_days = (now_utc() - upd).total_seconds() / 86400 if upd else human_days

        # ГДЕ совпало важно: заголовок/метка = по теме, одно общее слово в теле = совпадение
        # ни о чём (`auth`, `fix`, `token` встречаются везде) -- тоже находка Grok.
        strong_hay = " ".join([it.get("title") or "",
                               " ".join((lb.get("name") or "") for lb in (it.get("labels") or []))]).lower()
        weak_hay = (it.get("body") or "").lower()
        strong = [k for k in keywords if k and k in strong_hay]
        weak = [k for k in keywords if k and k not in strong_hay and k in weak_hay]
        hits = strong + weak
        if keywords and not hits:
            continue
        rec = {
            "number": it.get("number"),
            "title": (it.get("title") or "").strip(),
            "url": it.get("url"),
            "updated_days_ago": round(age_days, 1),
            "human_days_ago": round(human_days, 1),
            "comments": len(comments),
            "human_comments": len(human_c),
            "last_human_by": (human_c[-1].get("author") or {}).get("login") if human_c else None,
            "labels": [lb.get("name") for lb in (it.get("labels") or [])],
            "author": (it.get("author") or {}).get("login"),
            "hits": hits,
            "strong_hits": strong,
            "weak_hits": weak,
        }
        if login and rec["author"] == login:
            res["ours"].append(rec)
        else:
            res["live"].append(rec)
    res["live"].sort(key=lambda r: (-len(r["hits"]), r["updated_days_ago"]))
    res["ours"].sort(key=lambda r: r["updated_days_ago"])
    return res


def verdict(q: dict, doors: dict) -> tuple[str, list[str]]:
    """D: вердикт + причины. Живая ЧУЖАЯ дверь бьёт даже забитую очередь
    (так вошёл единственный замеченный PR #787 через issue #619)."""
    why = []
    share, med = q.get("silent_share"), q.get("median_age_days")

    # Забор issue упал -> про двери мы НИЧЕГО не знаем. Молчать и выдать RED = соврать.
    if not doors.get("fetch_ok"):
        return "UNKNOWN", ["issue не забрались (" + "; ".join(doors.get("errors") or ["причина не названа"]) + ")",
                           "про двери вывода НЕТ -- это не 'дверей нет', это 'не замерено'"]

    if share is not None:
        why.append(f"{share:.0%} открытых PR без единого комментария")
    if med is not None:
        why.append(f"медиана возраста открытых PR {med:.0f} дн")

    queue_red = (share is not None and share >= SILENT_SHARE_RED) or \
                (med is not None and med > STALE_MEDIAN_DAYS)
    queue_green = (share is not None and share < SILENT_SHARE_OK) and \
                  (med is not None and med <= WARM_MEDIAN_DAYS)

    if q.get("merges_from_regulars_only"):
        why.append("среди последних мержей НЕТ ни одного разового автора -- "
                   "репо мержит только своих, чужаку сюда трудно")

    if doors.get("live") and doors.get("keywords"):
        top = doors["live"][0]
        # Совпадение только общим словом в ТЕЛЕ issue -- это не тема, это коллизия.
        solid = bool(top.get("strong_hits")) or len(top.get("weak_hits") or []) >= 2
        where = "в заголовке/метках" if top.get("strong_hits") else "только в теле"
        if not solid:
            why.insert(0, f"issue #{top['number']} совпало {where} одним словом "
                          f"('{', '.join(top.get('weak_hits') or [])}') -- похоже на "
                          f"случайное совпадение, а не на нашу тему")
            return "YELLOW", why
        why.insert(0, f"есть живое чужое issue #{top['number']} по нашей теме "
                      f"(совпало {where}: {', '.join(top['hits'])}; человеческая "
                      f"активность {top['human_days_ago']:.0f} дн назад)")
        return "GREEN", why
    if doors.get("sample_partial") and not doors.get("live"):
        # выборка обрезана и в ней ничего -> "двери нет" не доказано
        why.insert(0, f"совпадений нет в выборке {doors.get('checked')} из "
                      f"{doors.get('open_total')} открытых issue -- дверь может быть за выборкой")
        return "UNKNOWN", why
    if doors.get("live") and not doors.get("keywords"):
        # Ключевых слов не дали -- совпадение НЕ проверялось. Свежее issue != наша дверь.
        why.insert(0, f"живых issue {len(doors['live'])}, но --artifact не задан: "
                      f"совпадение с нашим артефактом НЕ проверялось")
        return "YELLOW", why
    if queue_red:
        why.insert(0, "подходящего живого issue нет")
        return "RED", why
    if queue_green:
        why.insert(0, "подходящего живого issue нет, но очередь читают")
        return "YELLOW", why
    why.insert(0, "подходящего живого issue нет")
    return "YELLOW" if med is not None and med <= STALE_MEDIAN_DAYS else "RED", why


BADGE = {"GREEN": "🟢 ЖИВАЯ ДВЕРЬ", "YELLOW": "🟡 ДВЕРИ НЕТ", "RED": "🔴 ГЛУХАЯ ОЧЕРЕДЬ",
         "UNKNOWN": "⚪ НЕ ЗАМЕРЕНО"}
ADVICE = {
    "GREEN": "Входим через issue: сперва комментарий по делу в найденный тред, PR -- ссылкой на него.",
    "YELLOW": "PR не пушим. Открываем СВОЁ issue с предложением и ждём ответа мейнтейнера.",
    "RED": "Не пушим ничего холодного. Либо греем уже лежащие PR (привязать к issue), либо мимо.",
    "UNKNOWN": "Решение не принимаем на этих данных. Перезапусти замер; молчание забора -- не ответ.",
}
ADVICE_NO_KW = ("Дай --artifact \"ключевые, слова\" -- без них список выше это просто свежие "
                "issue, а не наши двери. Вердикт 🟢 без фильтра не выдаётся намеренно.")


def fmt_num(v, suffix=""):
    return "н/д" if v is None else f"{v}{suffix}"


def report(q: dict, doors: dict, v: str, why: list[str], draft: bool) -> None:
    repo = q["repo"]
    _out("=" * 68)
    _out(f"  {repo}")
    _out("=" * 68)
    _out()
    _out("ОЧЕРЕДЬ")
    # выборка = НОВЕЙШИЕ PR, они моложе среднего -> настоящая медиана не ниже показанной
    partial = " (оценка СНИЗУ: выборка из новейших)" if q.get("age_sample_is_partial") else ""
    _out(f"  открытых PR ............... {fmt_num(q.get('open_prs'))}")
    _out(f"  медиана возраста .......... {fmt_num(q.get('median_age_days'), ' дн')}"
         f"{partial}  [выборка {q.get('age_sample')}]")
    share = q.get("silent_share")
    _out(f"  без единого комментария ... {fmt_num(q.get('open_prs_zero_comment'))}"
         f"{'' if share is None else f' ({share:.0%})'}")
    sd = q.get("same_day_merge_share")
    _out(f"  мержи (последние {q.get('merged_sample')}) ..... медиана "
         f"{fmt_num(q.get('median_merge_hours'), ' ч')}"
         f"{'' if sd is None else f', в день подачи {sd:.0%}'}"
         f", разных авторов {q.get('distinct_merge_authors')}"
         f", из них разовых («с улицы») {q.get('drive_by_merges')}")
    if q.get("merges_from_regulars_only"):
        _out("    ^ ни одного разового автора = мержат только своих; здоровая медиана "
             "тут ничего чужаку не обещает")
    if sd is not None and sd >= 0.6:
        _out("    ^ большинство мержей в сутки = договорённость БЫЛА до PR, не 'быстро мёржат'")
    _out()
    if q.get("our_open_prs") is not None:
        _out("МЫ ТАМ")
        _out(f"  наших открытых PR ......... {fmt_num(q.get('our_open_prs'))}"
             f" (холодных, без реакции: {fmt_num(q.get('our_cold_prs'))})")
        _out(f"  наших смержено ............ {fmt_num(q.get('our_merged_prs'))}")
        _out()
    _out(f"ДВЕРИ (issue, живые = обновлялись за {doors.get('live_days')} дн"
         f"{', фильтр: ' + ', '.join(doors['keywords']) if doors.get('keywords') else ', без фильтра'})")
    if doors.get("live"):
        for r in doors["live"][:8]:
            hit = f"  ← совпало: {', '.join(r['hits'])}" if r["hits"] else ""
            _out(f"  #{r['number']:<5} {r['title'][:62]}")
            if r.get("last_human_by"):
                live_sig = (f"человек писал {r['human_days_ago']:.0f} дн назад "
                            f"(@{r['last_human_by']})")
            else:
                live_sig = (f"живых ответов НЕТ, но issue открыл человек "
                            f"{r['human_days_ago']:.0f} дн назад")
            bots = r["comments"] - r["human_comments"]
            botnote = f" · из {r['comments']} комм ботовых {bots}" if bots else ""
            _out(f"         {live_sig}{botnote} · автор @{r['author']}{hit}")
            _out(f"         {r['url']}")
    else:
        _out("  подходящих чужих issue не нашлось")
    if doors.get("sample_partial"):
        _out(f"  ⚠ смотрели {doors.get('checked')} из {doors.get('open_total')} открытых issue "
             f"-- 'не нашли' здесь НЕ значит 'нет'")
    if doors.get("ours"):
        _out(f"  (наших собственных issue тут {len(doors['ours'])}: "
             f"{', '.join('#' + str(r['number']) for r in doors['ours'][:5])}"
             f" -- своя дверь не считается приглашением)")
    _out(f"  просмотрено открытых issue: {doors.get('checked')}")
    _out()
    _out(f"ВЕРДИКТ: {BADGE[v]}")
    for w in why:
        _out(f"  · {w}")
    _out(f"  → {ADVICE[v]}")
    if not doors.get("keywords"):
        _out(f"  → {ADVICE_NO_KW}")
    for e in (q.get("errors") or []) + (doors.get("errors") or []):
        _out(f"  ⚠ не замерено: {e}")
    _out()
    if draft and v == "GREEN" and doors.get("live"):
        top = doors["live"][0]
        _out("-" * 68)
        _out(f"ЧЕРНОВИК ВХОДА (комментарий в #{top['number']}, правь под себя):")
        _out("-" * 68)
        _out(f"  Hi -- I have a working implementation that covers this.")
        _out(f"  Short summary: <что делает, 1-2 строки>.")
        _out(f"  Happy to open a PR against this issue if that's useful --")
        _out(f"  should it live in <путь в репо>?")
        _out()
        _out(f"  Тред: {top['url']}")
        _out()


def load_config() -> dict:
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            _out(f"⚠ конфиг {CONFIG} нечитаем ({e}) -- игнорирую")
    return {}


def derive_repos(login: str | None) -> list[str]:
    """Список репо = туда, куда мы уже подавали PR (свои репо не считаем)."""
    if not login:
        return []
    data, err = gh_json(["api", f"search/issues?q=is:pr+author:{login}&per_page=100"], None)
    if err or not isinstance(data, dict):
        return []
    seen = {}
    for it in data.get("items", []):
        url = it.get("repository_url") or ""
        r = re.sub(r".*/repos/", "", url)
        if r and not r.lower().startswith(login.lower() + "/"):
            seen[r] = seen.get(r, 0) + 1
    return [r for r, _ in sorted(seen.items(), key=lambda kv: -kv[1])]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(
        prog="issue_match.py",
        description="Замер очереди чужого репо + поиск живой двери (issue) ДО пуша PR. READ-ONLY.")
    ap.add_argument("repo", nargs="?", help="owner/name, например anthropics/claude-cookbooks")
    ap.add_argument("--all", action="store_true", help="пройти по всем репо из конфига")
    ap.add_argument("--init", action="store_true",
                    help="собрать конфиг из нашей истории PR и выйти")
    ap.add_argument("--artifact", default="",
                    help="ключевые слова артефакта через запятую -- фильтр issue")
    ap.add_argument("--live-days", type=int, default=None,
                    help=f"issue живой, если обновлялся за N дней (дефолт {DEFAULT_LIVE_DAYS})")
    ap.add_argument("--json", action="store_true", dest="as_json", help="машинный вывод")
    ap.add_argument("--no-draft", action="store_true", help="не печатать черновик входа")
    a = ap.parse_args()

    rc, _, err = gh(["--version"])
    if rc != 0:
        _out(f"❌ gh недоступен: {err}")
        return 4

    login = me()
    cfg = load_config()
    live_days = a.live_days or cfg.get("live_days") or DEFAULT_LIVE_DAYS
    keywords = [k.strip().lower() for k in a.artifact.split(",") if k.strip()]

    if a.init:
        repos = derive_repos(login)
        if not repos:
            _out("❌ не вывел ни одного репо (нет наших PR или gh молчит)")
            return 4
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"repos": repos, "live_days": live_days},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        _out(f"✅ конфиг записан: {CONFIG}")
        for r in repos:
            _out(f"   · {r}")
        return 0

    if a.all:
        repos = cfg.get("repos") or derive_repos(login)
        if not repos:
            _out("❌ пусто: ни конфига, ни наших PR. Укажи репо явно.")
            return 2
    elif a.repo:
        repos = [a.repo]
    else:
        ap.print_usage()
        _out("нужен <owner/repo>, либо --all, либо --init")
        return 2

    bad = [r for r in repos if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", r)]
    if bad:
        _out(f"❌ не похоже на owner/repo: {', '.join(bad)}")
        return 2

    results, failures = [], 0
    for repo in repos:
        q = measure_queue(repo, login)
        if q.get("open_prs") is None and q.get("median_age_days") is None:
            failures += 1
            _out(f"⚠ {repo}: замер не удался -- {'; '.join(q['errors']) or 'нет данных'}")
            continue
        doors = find_doors(repo, keywords, live_days, login)
        doors["live_days"] = live_days
        v, why = verdict(q, doors)
        results.append({"repo": repo, "queue": q, "doors": doors,
                        "verdict": v, "why": why})
        if not a.as_json:
            report(q, doors, v, why, draft=not a.no_draft)

    if a.as_json:
        _out(json.dumps({"measured_at": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "login": login, "results": results},
                        ensure_ascii=False, indent=2))
    elif len(results) > 1:
        _out("=" * 68)
        _out("  ИТОГ")
        _out("=" * 68)
        order = {"GREEN": 0, "YELLOW": 1, "RED": 2, "UNKNOWN": 3}
        for r in sorted(results, key=lambda x: order.get(x["verdict"], 9)):
            door = (f" → #{r['doors']['live'][0]['number']}" if r["doors"].get("live") else "")
            _out(f"  {BADGE[r['verdict']]:<18} {r['repo']}{door}")
        _out()

    if not results:
        return 4
    if failures:
        _out(f"⚠ репо не замерено: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
