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
canon_render.py — рендер публичных ЖУРНАЛОВ-РЕЕСТРОВ канона (show-canon) в репо the-journey.

Канон (приватный волт) -> read-only проекции canon/*.md на GitHub:
  README.md · SEASON.md · CAST.md · ARCS.md · BEATS.md · LOOPS.md · RULES.md

Законы:
  - Реестры НЕ правятся руками — только перегенерация этим скриптом (иначе дрейф).
  - Ось reveal фильтрует: бит публикуется только если world_status happened/corrected
    И live_after <= today. Остальные считаются "🔒 запечатано" (интрига, без содержимого).
  - Вопрос сезона запечатан до пилота: открывается только флагом --announce-season.
  - Секрет-скан прогоняется отдельно перед push (гейт /journey ШАГ 3).

Запуск:  python canon_render.py [--today YYYY-MM-DD] [--announce-season]
Идемпотентен. 0 токенов LLM.
"""
import argparse, datetime, io, os, re, sys

# stdout/stderr utf-8 guard: this file print()s Cyrillic/emoji; without it a cp1252 console
# (Task Scheduler) raises UnicodeEncodeError. Added 2026-07-11 to clear arch encoding-lint RED.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Общий гейт секретов живёт этажом выше (_imports/leak_scan.py) — один список паттернов
# на все публичные рельсы. Импорт по пути файла, а не по cwd: скрипт зовут и из планировщика.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import leak_scan

CANON = r"%VAULT%\04-Projects\show-canon"
OUT   = r"E:\GitHub\the-journey\canon"

FOOTER = ("\n---\n*Эта страница — авто-проекция приватного канона истории "
          "(single source of truth). Руками не редактируется; пересборка: `canon_render.py`. "
          "Read-only projection of the private story canon.*\n")

# ---------- tiny frontmatter parser (stdlib only) ----------
def parse_note(path):
    txt = io.open(path, encoding="utf-8").read()
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", txt, re.S)
    if not m:
        return {}, txt
    fm_raw, body = m.group(1), m.group(2)
    fm, cur_parent = {}, None
    for line in fm_raw.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key_m = re.match(r"^\s*([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not key_m:
            continue
        key, val = key_m.group(1), key_m.group(2).strip()
        if indent == 0:
            cur_parent = None
            if val == "":
                cur_parent = key
                fm[key] = {}
                continue
        elif cur_parent is not None:
            fm[cur_parent][key] = _coerce(val)
            continue
        fm[key] = _coerce(val)
    return fm, body.strip()

def _coerce(val):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = re.findall(r'"(?:[^"\\]|\\.)*"|[^,]+', inner)
        return [p.strip().strip('"').strip() for p in parts if p.strip()]
    return val.strip('"')

# ---------- wikilink -> public link ----------
LINKMAP = [("cast-", "CAST.md"), ("arc-", "ARCS.md"), ("loop-", "LOOPS.md"),
           ("beat-", "BEATS.md"), ("rule-", "RULES.md"), ("season-", "SEASON.md")]

def pub_link(slug, public_slugs):
    slug = slug.strip()
    for pref, page in LINKMAP:
        if slug.startswith(pref):
            if slug.startswith("beat-") and slug not in public_slugs:
                return "🔒 *(запечатанный бит)*"
            return "[%s](%s#%s)" % (slug, page, slug)
    return "`%s`" % slug  # приватная волт-ссылка -> плоский текст

def render_links(text, public_slugs):
    return re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]",
                  lambda m: pub_link(m.group(1), public_slugs), text)

def clean_list(v):
    if isinstance(v, list):
        return [re.sub(r"[\[\]]", "", x).strip() for x in v]
    return []

# ---------- collectors ----------
def load_dir(sub):
    d = os.path.join(CANON, sub)
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.endswith(".md") and not f.startswith("_"):  # _TEMPLATE и служебные пропускаем
            fm, body = parse_note(os.path.join(d, f))
            fm["_slug"] = os.path.splitext(f)[0]
            out.append((fm, body))
    return out

BEAT_KINDS = ("ship", "fail", "twist", "decision", "insight", "milestone", "external", "money")
KIND_EMOJI = {"ship": "🔧", "fail": "💥", "twist": "🌀", "decision": "⚖️",
              "insight": "💡", "milestone": "🏆", "external": "📡", "money": "💸"}

def norm_beat(fm):
    """Толерантность к дрейфу схемы между сессиями (date~occurred_on, arcs~related_arcs...)."""
    fm.setdefault("occurred_on", fm.get("date", "?"))
    fm.setdefault("related_arcs", fm.get("arcs", []))
    fm.setdefault("related_cast", fm.get("cast", []))
    fm.setdefault("summary", fm.get("title", ""))
    # ЛИНТ beat_kind — автоматический сторож словаря (0 токенов):
    kind = fm.get("beat_kind")
    if not kind:
        print("⚠️  LINT: %s без beat_kind (нужен один из %s)" % (fm["_slug"], "|".join(BEAT_KINDS)))
        fm["beat_kind"] = "?"
    elif kind not in BEAT_KINDS:
        print("⚠️  LINT: %s: неизвестный beat_kind '%s' (словарь: %s)" % (fm["_slug"], kind, "|".join(BEAT_KINDS)))
    return fm

def kind_badge(fm):
    k = fm.get("beat_kind", "?")
    return "%s %s" % (KIND_EMOJI.get(k, "•"), k)

def beat_public(fm, today):
    if fm.get("world_status") not in ("happened", "corrected"):
        return False
    rv = str(fm.get("reveal", ""))
    m = re.search(r"live_after:\s*(\d{4}-\d{2}-\d{2})", rv)
    if m:
        return m.group(1) <= today
    return False  # live_hold / spoiler_until / book_hint / пусто -> запечатан

def w(path, parts):
    """Единственная точка записи публичных проекций -> здесь же скраб и гейт.

    2026-07-27: до этого дня тела битов копировались в canon/*.md ДОСЛОВНО, и в публичный
    BEATS.md уехали IP Якорьа, адрес частной сети, хостнейм и два хэндла ботов. Скраб чинит
    причину (идентификатор -> роль: «хаб», «Якорь», «адрес узла»), а гейт чинит класс: если
    после скраба осталась хоть одна находка, файл НЕ пишется и рендер падает с кодом 2.
    Сторож стоит в горлышке, через которое проходят все шесть журналов, — не рядом с ним.
    """
    text = leak_scan.scrub("\n".join(parts) + FOOTER)
    fails, _ = leak_scan.scan_text(text, profile="book")
    if fails:
        print("⛔ LEAK GATE: %s НЕ записан — %d находок после скраба:"
              % (os.path.basename(path), len(fails)))
        for tag, frag, ln in fails[:10]:
            print("   line %s [%s] %s" % (ln, tag, frag))
        raise SystemExit(2)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None)
    ap.add_argument("--announce-season", action="store_true")
    a = ap.parse_args()
    today = a.today or datetime.date.today().isoformat()

    os.makedirs(OUT, exist_ok=True)
    beats  = [(norm_beat(fm), b) for fm, b in load_dir("beats")]
    casts  = load_dir("cast")
    arcs   = load_dir("arcs")
    loops  = load_dir("loops")
    rules  = load_dir("rules")
    season_fm, season_body = parse_note(os.path.join(CANON, "season-01.md"))

    pub_beats    = [(fm, b) for fm, b in beats if beat_public(fm, today)]
    sealed_count = len(beats) - len(pub_beats)
    public_slugs = {fm["_slug"] for fm, _ in pub_beats}
    R = lambda t: render_links(t, public_slugs)

    # BEATS.md — timeline
    p = ["# 🎞 BEATS — журнал событий (таймлайн)", "",
         "Единица истории. Каждый бит = что реально случилось, с тремя осями статуса.", "",
         "| день | дата | вид | что случилось | арки | статус |", "|---|---|---|---|---|---|"]
    for fm, _ in sorted(pub_beats, key=lambda x: str(x[0].get("occurred_on", ""))):
        arcs_l = " ".join(R("[[%s]]" % s) for s in clean_list(fm.get("related_arcs")))
        p.append("| %s | %s | %s | <a id=\"%s\"></a>%s | %s | %s/%s |" % (
            fm.get("story_day", "?"), fm.get("occurred_on", "?"), kind_badge(fm), fm["_slug"],
            fm.get("summary", ""), arcs_l, fm.get("world_status", ""), fm.get("truth_mode", "")))
    for fm, body in sorted(pub_beats, key=lambda x: str(x[0].get("occurred_on", ""))):
        p += ["", "### <a id=\"%s\"></a>День %s — %s" % (fm["_slug"], fm.get("story_day", "?"), fm.get("occurred_on", "")),
              "", R(fm.get("summary", "")), "", R(body)]
        cons = clean_list(fm.get("consequences"))
        if cons:
            p += ["", "**Последствия:** " + "; ".join(cons)]
    if sealed_count:
        p += ["", "> 🔒 Ещё **%d** бит(а) запечатаны до своего reveal-времени. Спойлеров не будет." % sealed_count]
    w(os.path.join(OUT, "BEATS.md"), p)

    # CAST.md
    p = ["# 🎭 CAST — персонажи (все реальные)", ""]
    for fm, body in casts:
        p += ["## <a id=\"%s\"></a>%s" % (fm["_slug"], fm.get("name", fm["_slug"])),
              "- **Роль:** %s · **с** %s" % (fm.get("role_in_story", "?"), fm.get("first_appearance", "?")),
              "- **Хочет:** " + R(str(fm.get("desire", ""))),
              "- **Мешает:** " + R(str(fm.get("obstacle", ""))), "", R(body), ""]
    w(os.path.join(OUT, "CAST.md"), p)

    # ARCS.md
    p = ["# 🧵 ARCS — журнал сюжетных линий", ""]
    for fm, body in arcs:
        beats_l = [R("[[%s]]" % s) for s in clean_list(fm.get("beats"))]
        p += ["## <a id=\"%s\"></a>%s" % (fm["_slug"], fm.get("title", fm["_slug"])),
              "- **Ставка:** " + R(str(fm.get("stake", ""))),
              "- **Старт:** %s" % R(str(fm.get("start_state", ""))),
              "- **Куда идём:** %s" % R(str(fm.get("desired_end_state", ""))),
              "- **Сейчас:** %s · статус **%s**" % (R(str(fm.get("current_state", ""))), fm.get("status", "?")),
              "- **Пейофф:** " + R(str(fm.get("payoff_condition", ""))),
              "- **Биты:** " + (" · ".join(beats_l) if beats_l else "—"), "", R(body), ""]
    w(os.path.join(OUT, "ARCS.md"), p)

    # LOOPS.md
    p = ["# 🔓 LOOPS — открытые вопросы (клиффхэнгеры)", "",
         "Петля = честный открытый вопрос шоу. Закрывается фактом, не риторикой.", ""]
    for fm, body in loops:
        badge = "🟢 OPEN" if fm.get("status") == "open" else "✅ CLOSED"
        p += ["## <a id=\"%s\"></a>%s %s" % (fm["_slug"], badge, R(str(fm.get("question", fm["_slug"])))),
              "- **Открыт битом:** " + R(str(fm.get("opened_by", "—"))),
              "- **Лучший ответ сейчас:** " + R(str(fm.get("current_best_answer", "—"))),
              "- **Закроется когда:** " + R(str(fm.get("close_condition", "—"))), "", R(body), ""]
    w(os.path.join(OUT, "LOOPS.md"), p)

    # RULES.md
    p = ["# 📜 RULES — инварианты шоу", ""]
    for fm, body in rules:
        p += ["## <a id=\"%s\"></a>%s" % (fm["_slug"], fm["_slug"]),
              "> **%s**" % R(str(fm.get("invariant", ""))),
              "", R(body), ""]
    w(os.path.join(OUT, "RULES.md"), p)

    # SEASON.md
    # Сезон объявлен = персистентное состояние канона (season-01.md frontmatter: season_announced),
    # а не одноразовый CLI-флаг: иначе любой рендер без --announce-season запечатывал вопрос обратно
    # (регрессия ловилась 2026-07-25: пилот вышел 11.07, а рендер дня перезапечатал SEASON.md).
    # split("#") — наш парсер frontmatter наивный и оставляет inline-комментарий в значении
    _sa = str(season_fm.get("season_announced", "")).split("#")[0].strip().lower()
    announced = a.announce_season or _sa not in ("", "none", "false", "no", "0")
    p = ["# 🎬 SEASON 1 — %s" % season_fm.get("title", "Сезон 1"), ""]
    if announced:
        p += ["## Вопрос сезона", "**%s**" % season_fm.get("season_question", ""), ""]
    else:
        p += ["## Вопрос сезона", "🔒 **Запечатан до пилотного эпизода.** Скоро объявим — подпишись и жди.", ""]
    p += ["## Премиса", R(str(season_fm.get("premise", ""))), "",
          "## Стандарт честности", "> %s" % season_fm.get("truth_standard", ""), "",
          "- **Story day:** %s · live as of %s" % (season_fm.get("current_story_day", "?"), season_fm.get("live_as_of", "?")),
          "- **Активные арки:** " + " · ".join(R("[[%s]]" % s) for s in clean_list(season_fm.get("active_arcs"))),
          "- **Открытые петли:** " + " · ".join(R("[[%s]]" % s) for s in clean_list(season_fm.get("open_loops"))),
          "- **Каст:** " + " · ".join(R("[[%s]]" % s) for s in clean_list(season_fm.get("cast_main"))), "",
          "## Табло (дельты, не абсолюты)"]
    sb = season_fm.get("scoreboard", {})
    if isinstance(sb, dict):
        for k, v in sb.items():
            p.append("- `%s`: %s" % (k, v))
    w(os.path.join(OUT, "SEASON.md"), p)

    # README.md — карта
    p = ["# 🗺 CANON — публичная карта истории The Journey", "",
         "Это **реестры-проекции** нашего единого канона истории (story bible). Книга-главы,",
         "живые посты и dev-log рассказывают одни и те же факты разными голосами — а факты живут здесь.", "",
         "| Журнал | Что внутри |", "|---|---|",
         "| [SEASON.md](SEASON.md) | сезон: вопрос, премиса, табло |",
         "| [CAST.md](CAST.md) | персонажи (все реальные) |",
         "| [ARCS.md](ARCS.md) | многосерийные сюжетные линии |",
         "| [BEATS.md](BEATS.md) | таймлайн событий (единица истории) |",
         "| [LOOPS.md](LOOPS.md) | открытые вопросы-клиффхэнгеры |",
         "| [RULES.md](RULES.md) | инварианты (честность и т.д.) |", "",
         "**Как всё связано:** сезон ставит вопрос → арки ведут к ответу → биты (события) двигают арки →",
         "петли держат открытые вопросы → главы книги (`0*-*/`) и посты рендерятся из битов.", "",
         "🔒 Часть битов запечатана до своего времени (ось reveal) — интрига без вранья.",
         "", "Старт чтения: [../00-prologue.md](../00-prologue.md)"]
    w(os.path.join(OUT, "README.md"), p)

    print("RENDERED canon/ -> %s" % OUT)
    print("beats: %d public / %d sealed · cast %d · arcs %d · loops %d · rules %d · today=%s · season_announced=%s"
          % (len(pub_beats), sealed_count, len(casts), len(arcs), len(loops), len(rules), today, announced))

if __name__ == "__main__":
    main()
