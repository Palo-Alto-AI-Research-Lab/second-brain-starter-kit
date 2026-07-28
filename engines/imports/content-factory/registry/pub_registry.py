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
r"""pub_registry.py — ЕДИНЫЙ РЕЕСТР ИСХОДЯЩИХ ПУБЛИКАЦИЙ (content-factory).

WHY (Anton 2026-07-10): «у нас должен быть реестр постов на публикацию... реестр =
порядок». Аналог реестра исходящих сообщений лидам, но для контента. До него факт
публикации жил враздробь (publish_state.json / fb_teaser_ledger / priority.json), а
ОЧЕРЕДИ и ЛИМИТОВ не было нигде → риск: 129 заготовок и соблазн заспамить площадки.

Это НЕ публикатор. Публикуют существующие рельсы (content_publish.py, /fb-post, git
push, руки). Реестр = бухгалтерия и светофор вокруг них:
  QUEUE  — что стоит в очереди на какую площадку (draft-first, ждёт «+» Антона);
  POSTED — что реально ушло (когда, куда, URL) = журнал фактов;
  NEXT   — что МОЖНО постить прямо сейчас, не нарушая безопасные лимиты
           (registry/limits.json: per_day / per_week / min_gap / paused / глобальная
           «одна новая история наружу в день» — петля вместо ковра).

Файлы (рядом, в registry/):
  pub_ledger.jsonl — append-only события {event: queued|posted|skipped, ...}
  limits.json      — безопасные лимиты (правится руками)
  PUB-REGISTRY.md  — человекочитаемое зеркало (генерится командой render)

Команды:
  queue  --id <story-id> --platform <p> --title "..." [--tier t] [--earliest ISO]
         [--source episode:slug|post:id] [--needs-plus]
  posted --id <story-id> --platform <p> [--url U] [--when ISO] [--title "..."]
  skip   --id <story-id> --platform <p> --reason "..."
  next   [--platform p]      что можно постить сейчас (светофор по лимитам)
  status                     сводка: очередь/факты/расход лимитов
  render                     перегнать PUB-REGISTRY.md
  seed-priority              разовый импорт исторических постов из priority.json

Дисциплина: publish-рельсы ОБЯЗАНЫ звать `posted` после успешной публикации.
Draft-first не ослабляется: queue ≠ разрешение постить; наружу — по «+» Антона.
ASCII-safe prints (Windows cp1252). Stdlib only.
"""
import os, sys, io, json, argparse, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CF = os.path.dirname(HERE)                       # ...\content-factory
LEDGER = os.path.join(HERE, "pub_ledger.jsonl")
LIMITS = os.path.join(HERE, "limits.json")
VIEW = os.path.join(HERE, "PUB-REGISTRY.md")
PRIORITY = os.path.join(CF, "priority.json")

OUTWARD = {"fb_wall", "tg_clawrus", "x_en", "vcru", "habr", "reddit_claudeai", "github"}
# github наружу, но каноничные реестры/dev-log не «новая история» — глобальный
# сторилимит считает только сторителлинг-площадки:
STORY_PLATFORMS = {"fb_wall", "tg_clawrus", "x_en", "vcru", "habr", "reddit_claudeai"}


def now_iso():
    return datetime.datetime.now().isoformat(timespec="minutes")


def load_limits():
    with io.open(LIMITS, encoding="utf-8") as f:
        return json.load(f)


def load_events():
    ev = []
    if os.path.exists(LEDGER):
        for ln in io.open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    ev.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    return ev


def append_event(e):
    e["at"] = e.get("at") or now_iso()
    with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


def state(events):
    """Свёртка событий: очередь (queued без posted/skip) + факты (posted)."""
    queued, posted = {}, []
    for e in events:
        key = (e.get("id"), e.get("platform"))
        if e.get("event") == "queued":
            queued[key] = e
        elif e.get("event") == "posted":
            posted.append(e)
            queued.pop(key, None)
        elif e.get("event") == "skipped":
            queued.pop(key, None)
    return list(queued.values()), posted


def _parse(dtiso):
    try:
        return datetime.datetime.fromisoformat(str(dtiso)[:16])
    except ValueError:
        return None


def usage_counts(posted, platform, now):
    day = week = 0
    last = None
    for e in posted:
        if e.get("platform") != platform:
            continue
        t = _parse(e.get("at"))
        if not t:
            continue
        if (now - t).days < 7:
            week += 1
        if t.date() == now.date():
            day += 1
        if last is None or t > last:
            last = t
    return day, week, last


def stories_today(posted, now):
    return len({e.get("id") for e in posted
                if e.get("platform") in STORY_PLATFORMS
                and _parse(e.get("at")) and _parse(e["at"]).date() == now.date()})


def can_post(platform, limits, posted, now):
    """-> (ok:bool, reason:str)."""
    cfg = limits.get(platform)
    if not cfg:
        return False, "unknown platform (add to limits.json)"
    if cfg.get("paused"):
        return False, "PAUSED: " + str(cfg.get("note", ""))[:60]
    day, week, last = usage_counts(posted, platform, now)
    if day >= cfg.get("per_day", 1):
        return False, "day limit %d/%d" % (day, cfg.get("per_day", 1))
    if week >= cfg.get("per_week", 7):
        return False, "week limit %d/%d" % (week, cfg.get("per_week", 7))
    gap = cfg.get("min_gap_min", 0)
    if last and gap and (now - last).total_seconds() < gap * 60:
        wait = int(gap - (now - last).total_seconds() / 60)
        return False, "min-gap: wait ~%d min" % max(wait, 1)
    return True, "ok (today %d/%d, week %d/%d)" % (day, cfg.get("per_day", 1), week, cfg.get("per_week", 7))


def cmd_queue(a):
    e = append_event({"event": "queued", "id": a.id, "platform": a.platform,
                      "title": a.title or "", "tier": a.tier or "",
                      "source": a.source or "", "earliest": a.earliest or "",
                      "needs_plus": bool(a.needs_plus)})
    print("QUEUED %s -> %s%s" % (a.id, a.platform, " [needs +]" if a.needs_plus else ""))


def writeback_funnel(story_id, platform, url, when):
    """Закрыть петлю: факт публикации -> status=done в реестре воронки (posts.jsonl).

    Без этого шага метрика канона «опубликовано/актив >= 80%» НЕВЫЧИСЛИМА: до
    2026-07-27 факт публикации умирал здесь, и недельный отчёт печатал «н/д».
    Мягкий шаг: воронка не обязана знать про эту публикацию (эпизод мог родиться
    мимо неё) - тогда просто молчим, публикацию починит `reconcile-published`.
    Никогда не роняет публикатор: любая ошибка здесь - предупреждение, не сбой.
    """
    if not str(story_id).startswith("episode:"):
        return
    slug = str(story_id)[len("episode:"):]
    try:
        sys.path.insert(0, CF)
        import voice_triage as vt
        box = {"n": 0}
        def _wb(recs):                    # под замком: публикатор — ВТОРОЙ писатель файла
            hit = [r for r in recs if r.get("slug") == slug]
            for r in hit:
                vt._apply_published(r, when or "", platform or "", url or "", "pub_registry")
            box["n"] = len(hit)
        vt.mutate_posts(_wb)
        if box["n"]:
            print("  (воронка: %d запись(ей) -> status=done)" % box["n"])
        else:
            print("  (воронка: записи со slug '%s' нет - привяжи `voice_triage.py "
                  "link-episode --id <post-id> --slug %s`)" % (slug, slug))
    except Exception as exc:
        print("  WARN write-back в воронку не удался: %s" % str(exc)[:100])


def cmd_posted(a):
    when = a.when or now_iso()
    append_event({"event": "posted", "id": a.id, "platform": a.platform,
                  "url": a.url or "", "title": a.title or "", "at": when})
    print("POSTED %s -> %s %s" % (a.id, a.platform, a.url or ""))
    writeback_funnel(a.id, a.platform, a.url or "", when)
    cmd_render(a, quiet=True)


def cmd_skip(a):
    append_event({"event": "skipped", "id": a.id, "platform": a.platform,
                  "reason": a.reason or ""})
    print("SKIPPED %s -> %s (%s)" % (a.id, a.platform, (a.reason or "")[:60]))


def cmd_next(a):
    limits = load_limits()
    queued, posted = state(load_events())
    now = datetime.datetime.now()
    glob = limits.get("_global", {})
    story_cap = glob.get("max_new_stories_outward_per_day", 1)
    used_stories = stories_today(posted, now)
    story_ids_today = {e.get("id") for e in posted
                       if e.get("platform") in STORY_PLATFORMS
                       and _parse(e.get("at")) and _parse(e["at"]).date() == now.date()}
    if a.platform:
        queued = [q for q in queued if q.get("platform") == a.platform]
    queued.sort(key=lambda q: q.get("at", ""))
    go, hold = [], []
    for q in queued:
        p = q.get("platform")
        ok, why = can_post(p, limits, posted, now)
        if ok and q.get("earliest"):
            t = _parse(q["earliest"])
            if t and t > now:
                ok, why = False, "earliest %s" % q["earliest"]
        # глобальная петля: новая история наружу — если сегодня ещё есть слот,
        # ИЛИ это продолжение уже вышедшей сегодня истории (та же id = одна волна)
        if ok and p in STORY_PLATFORMS and q.get("id") not in story_ids_today \
                and used_stories >= story_cap:
            ok, why = False, "story/day cap %d used (петля вместо ковра)" % story_cap
        if ok and q.get("needs_plus"):
            why += " · ЖДЁТ «+» Антона (Tier-2)"
        (go if ok else hold).append((q, why))
    print("NOW %s · stories today %d/%d" % (now.strftime("%Y-%m-%d %H:%M"), used_stories, story_cap))
    print("--- CAN POST NOW (%d) ---" % len(go))
    for q, why in go:
        t = (q.get("title") or "")[:58].encode("ascii", "replace").decode()
        print("  %-12s %-22s %s | %s" % (q.get("platform"), q.get("id"), why, t))
    print("--- HOLD (%d) ---" % len(hold))
    for q, why in hold[:25]:
        print("  %-12s %-22s %s" % (q.get("platform"), q.get("id"), why))


def cmd_status(a):
    limits = load_limits()
    queued, posted = state(load_events())
    now = datetime.datetime.now()
    print("QUEUED %d · POSTED total %d · stories today %d/%d"
          % (len(queued), len(posted), stories_today(posted, now),
             limits.get("_global", {}).get("max_new_stories_outward_per_day", 1)))
    for p, cfg in sorted(limits.items()):
        if p.startswith("_"):
            continue
        day, week, last = usage_counts(posted, p, now)
        nq = sum(1 for q in queued if q.get("platform") == p)
        flag = "PAUSED" if cfg.get("paused") else ("day %d/%d wk %d/%d" % (day, cfg.get("per_day", 1), week, cfg.get("per_week", 7)))
        print("  %-16s queue=%-3d %s" % (p, nq, flag))


def cmd_render(a, quiet=False):
    limits = load_limits()
    queued, posted = state(load_events())
    now = datetime.datetime.now()
    L = ["# PUB-REGISTRY — реестр исходящих публикаций (зеркало, генерится pub_registry.py)",
         "", "_Обновлено: %s · Очередь: %d · Опубликовано всего: %d. Файл не править руками._"
         % (now.strftime("%Y-%m-%d %H:%M"), len(queued), len(posted)), "",
         "## Очередь (draft-first; наружу — по «+» Антона)", "",
         "| story-id | площадка | тир | заголовок | earliest | + |", "|---|---|---|---|---|---|"]
    for q in sorted(queued, key=lambda x: x.get("at", "")):
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            q.get("id"), q.get("platform"), q.get("tier", ""),
            (q.get("title") or "").replace("|", "/")[:70],
            q.get("earliest", ""), "ждёт+" if q.get("needs_plus") else ""))
    if len(queued) == 0:
        L.append("| — | | | | | |")
    L += ["", "## Опубликовано (журнал фактов)", "",
          "| когда | story-id | площадка | URL |", "|---|---|---|---|"]
    for e in sorted(posted, key=lambda x: x.get("at", ""), reverse=True)[:100]:
        L.append("| %s | %s | %s | %s |" % (e.get("at", ""), e.get("id"),
                                            e.get("platform"), e.get("url", "")))
    io.open(VIEW, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    if not quiet:
        print("RENDERED", VIEW)


def cmd_seed_priority(a):
    """Импорт исторических wow-постов (priority.json, status=posted) как факты.
    Идемпотентно: (id, platform) уже в журнале -> пропуск. Площадка тех постов =
    tg_clawrus/fb (шли волной через фабрику) — пишем консервативно chat03_preview,
    если точная площадка неизвестна, чтобы НЕ съедать лимиты наружных площадок."""
    if not os.path.exists(PRIORITY):
        print("no priority.json"); return
    have = {(e.get("id"), e.get("platform")) for e in load_events() if e.get("event") == "posted"}
    n = 0
    for rec in json.load(io.open(PRIORITY, encoding="utf-8")):
        if rec.get("status") != "posted":
            continue
        key = ("episode:" + rec.get("slug", ""), "chat03_preview")
        if key in have:
            continue
        append_event({"event": "posted", "id": key[0], "platform": key[1],
                      "title": rec.get("title", ""), "url": "",
                      "at": (rec.get("date", "") + "T12:00")})
        n += 1
    print("SEEDED %d historical posted events (as chat03_preview)" % n)
    cmd_render(a, quiet=True)


def main():
    ap = argparse.ArgumentParser(description="content-factory publication registry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue")
    for opt, req in (("id", True), ("platform", True), ("title", False), ("tier", False),
                     ("earliest", False), ("source", False)):
        q.add_argument("--" + opt, required=req)
    q.add_argument("--needs-plus", action="store_true")
    q.set_defaults(f=cmd_queue)
    p = sub.add_parser("posted")
    for opt, req in (("id", True), ("platform", True), ("url", False), ("when", False), ("title", False)):
        p.add_argument("--" + opt, required=req)
    p.set_defaults(f=cmd_posted)
    s = sub.add_parser("skip")
    for opt, req in (("id", True), ("platform", True), ("reason", False)):
        s.add_argument("--" + opt, required=req)
    s.set_defaults(f=cmd_skip)
    n = sub.add_parser("next"); n.add_argument("--platform"); n.set_defaults(f=cmd_next)
    sub.add_parser("status").set_defaults(f=cmd_status)
    sub.add_parser("render").set_defaults(f=cmd_render)
    sub.add_parser("seed-priority").set_defaults(f=cmd_seed_priority)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
