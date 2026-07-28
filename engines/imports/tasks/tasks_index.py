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
r"""
tasks_index.py -- индексатор журнала задач v2 (декрет Антона 2026-07-04, DR26-07-04-HUB-05).

SOURCE OF TRUTH = markdown-заметки в %VAULT%\10-Tasks\task-*.md
Этот скрипт их НЕ редактирует. Он их ЧИТАЕТ и строит ПРОИЗВОДНЫЕ:
  1) витрину  _Dashboards\Task-Backlog.html  (3 зоны: несделанные / сделанные / когда-нибудь)
  2) аудит    10-Tasks\_audit\audit-latest.json  (stale / missing-evidence / WIP>3 / битые связи)

AK-47: stdlib + pyyaml, 0 токенов, ничего кроме чтения волта и записи 2 файлов.
Упрощение против DR: НЕТ отдельной SQLite-базы в v1 -- всё считается за один проход из
frontmatter. SQLite-индекс добавим Фазой 2, если понадобится внешний запрос (флаг ниже).

⚠️ SINGLE WRITER (kill-review 2026-07-17 + rollout 2026-07-26): планово этот скрипт гоняет
ТОЛЬКО Якорь (ANCHOR1, cron ночное окно). Копии на хабе/ноуте = парность кода
(one-system-propagate) + ручной fallback, если Якорь лежит. НЕ ставить в Task Scheduler,
пока Якорь жив: волт синкается, второй писатель audit-latest.json/дашборда = sync-conflict.

Запуск (Якорь, планово):  python3 $HOME/tasks-index/tasks_index.py
Запуск (хаб, вручную):   python %USERPROFILE%\.claude\scripts\tasks\tasks_index.py
Путь волта: env OBSIDIAN_VAULT -> ~/.claude/machine.env -> per-OS дефолт.
"""
import sys, json, glob, os, datetime, re, html

try:
    import yaml
except ImportError:
    print("ERR: нужен pyyaml (pip install pyyaml)"); sys.exit(2)

# UTF-8 stdout на Windows -- ТОЛЬКО при запуске скриптом (под __main__ внизу).
# На уровне модуля подмена sys.stdout клобберит stdout импортёра (найдено /tt 26.07:
# терялись буферизованные строки хоста, импортировавшего normalize_file).

def _vault():
    """OBSIDIAN_VAULT env -> ~/.claude/machine.env -> per-OS дефолты.
    Писатель: явно заданный, но битый путь = ОШИБКА, не фолбэк (Codex 26.07:
    иначе битый env тихо направляет запись в реальный волт машины)."""
    v = os.environ.get("OBSIDIAN_VAULT", "").strip().strip('"')
    if v:
        if os.path.isdir(v):
            return v
        print(f"ERR: OBSIDIAN_VAULT={v} не существует (фолбэк для писателя запрещён)")
        sys.exit(1)
    me = os.path.join(os.path.expanduser("~"), ".claude", "machine.env")
    try:
        with open(me, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OBSIDIAN_VAULT="):
                    v = line.split("=", 1)[1].strip().strip('"')
                    if v:
                        if os.path.isdir(v):
                            return v
                        print(f"ERR: machine.env OBSIDIAN_VAULT={v} не существует")
                        sys.exit(1)
    except OSError:
        pass
    for c in (r"%VAULT%",
              "$VAULT",
              os.path.expanduser("~/Obsidian/Owner-Knowledge")):
        if os.path.isdir(c):
            return c
    print("ERR: волт не найден (задай OBSIDIAN_VAULT или machine.env)"); sys.exit(1)


VAULT   = _vault()
TASKDIR = os.path.join(VAULT, "10-Tasks")
DASH    = os.path.join(VAULT, "_Dashboards", "Task-Backlog.html")
AUDITD  = os.path.join(TASKDIR, "_audit")
TODAY   = datetime.date.today()

STALE_DAYS = {"P0": 1, "P1": 7, "P2": 21, "P3": 45, "someday": 90}
UNDONE   = {"inbox", "open", "wip", "blocked"}
# Гейт схемы (kill-review 2026-07-17). Корень, который он закрывает: раньше отсутствующий
# `state` МОЛЧА подставлялся как "open" -- 20 задач 2-го поколения схемы (`status:`/`prio:`)
# две недели висели «открытыми», включая 6 закрытых, и дашборд врал. Дефолт вместо ошибки =
# слой видимости молчит. Теперь любое отклонение от канона -> schema_errors, а не тихий дефолт.
KNOWN_STATES = {"inbox", "open", "wip", "blocked", "done", "dropped", "someday", "archived"}
KNOWN_PRIOS  = {"P0", "P1", "P2", "P3"}
PRIO_ORD = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 4}
OWNER_LBL = {"anton": "🔴 Антон", "claude": "🟡 Claude", "machine": "⏳ машины", "external": "⏳ внешнее"}
TYPE_LBL  = {"business": "бизнес", "content": "контент", "infra": "инфра", "vault": "волт", "research": "ресёрч"}


# --- Авто-нормализатор схемы (26.07.2026, корень-фикс класса "писатели не читают шаблон") ---
# Гейт 17.07 ловил отклонения, но только кричал: за неделю флот нарожал 26 файлов 2-го/3-го
# поколения (status:/prio:/in_progress/high/seeded) -- аудит распух 0->43. Шаблон верный,
# но сессии ДРУГИХ машин пишут по памяти. Лечим класс здесь: индексатор (sole writer, Якорь)
# перед разбором ЧИНИТ известные отклонения прямо в файле, идемпотентно, CRLF-safe (байты).
# Гейт остаётся для нечинимого (реально битый YAML, неизвестные значения).
STATE_MAP = {"doing": "wip", "in_progress": "wip", "in-progress": "wip", "proposed": "open",
             "seeded": "open", "resolved": "done", "closed": "done", "todo": "open",
             "active": "wip", "waiting": "blocked"}
PRIO_MAP = {"high": "P1", "medium": "P2", "med": "P2", "normal": "P2", "low": "P3",
            "p0": "P0", "p1": "P1", "p2": "P2", "p3": "P3"}

def normalize_file(path):
    """Возвращает список применённых фиксов (пусто = не тронут). Пишет только если
    итоговый frontmatter парсится чисто."""
    raw = open(path, "rb").read()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []
    # большинство, не «хоть один»: mostly-LF файл со случайным CRLF не перекатываем в CRLF
    crlf = txt.count("\r\n") * 2 > txt.count("\n")
    body = txt.replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n", body, re.S)
    if not m:
        return []
    fm_lines = m.group(1).split("\n")
    fixes, out = [], []
    has_state = any(re.match(r"^state:", l) for l in fm_lines)
    has_prio = any(re.match(r"^priority:", l) for l in fm_lines)
    fm_parses = True
    try:
        yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        fm_parses = False
    for l in fm_lines:
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", l)
        if not km:
            out.append(l); continue
        k, v = km.group(1), km.group(2)
        vs = v.strip().strip('"').strip("'")
        if k == "status" and not has_state:
            k = "state"; has_state = True
            fixes.append("status->state")
        if k == "prio" and not has_prio:
            k = "priority"; has_prio = True
            fixes.append("prio->priority")
        if k == "state" and vs.lower() in STATE_MAP:
            v = STATE_MAP[vs.lower()]; fixes.append(f"state {vs}->{v}")
        if k == "priority" and vs.upper() not in KNOWN_PRIOS and vs.lower() in PRIO_MAP:
            v = PRIO_MAP[vs.lower()]; fixes.append(f"priority {vs}->{v}")
        # незакавыченное двоеточие в значении -> битый YAML всего frontmatter
        if (not fm_parses and ": " in v and not v.startswith(('"', "'", "[", "{"))
                and not v.startswith("#")):
            v = '"' + v.replace('"', "'") + '"'; fixes.append(f"quote {k}")
        out.append(f"{k}: {v}" if v else f"{k}:")
    if not has_prio:
        # явный P2 вместо тихого дефолта; после state, иначе первой строкой
        idx = next((i + 1 for i, l in enumerate(out) if l.startswith("state:")), 0)
        out.insert(idx, "priority: P2")
        fixes.append("priority missing->P2")
    if not fixes:
        return []
    new_fm = "\n".join(out)
    try:
        yaml.safe_load(new_fm)
    except yaml.YAMLError:
        return []  # не смогли вылечить -- не трогаем, гейт скажет
    new_body = body[:m.start(1)] + new_fm + body[m.end(1):]
    if crlf:
        new_body = new_body.replace("\n", "\r\n")
    # атомарно: temp в той же папке + os.replace (kill/гонка не оставит полфайла);
    # pid в имени -- два параллельных прогона не дерутся за один tmp (Codex 26.07)
    tmp = f"{path}.norm.{os.getpid()}.tmp"
    with open(tmp, "wb") as f:
        f.write(new_body.encode("utf-8"))
    os.replace(tmp, path)
    return fixes


def normalize_all():
    fixed = {}
    for path in glob.glob(os.path.join(TASKDIR, "task-*.md")):
        fx = normalize_file(path)
        if fx:
            fixed[os.path.basename(path)] = fx
    return fixed


def parse_date(v):
    if not v:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v).strip()[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def load_tasks():
    tasks, errors = [], []
    for path in glob.glob(os.path.join(TASKDIR, "task-*.md")):
        try:
            with open(path, encoding="utf-8") as f:
                txt = f.read()
        except OSError as e:
            errors.append(f"{os.path.basename(path)}: не читается ({e})"); continue
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.S)
        if not m:
            errors.append(f"{os.path.basename(path)}: нет frontmatter"); continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            errors.append(f"{os.path.basename(path)}: битый YAML ({e})"); continue
        if not isinstance(fm, dict):
            errors.append(f"{os.path.basename(path)}: frontmatter не словарь ({type(fm).__name__})"); continue
        fm["_file"] = os.path.basename(path)
        fm["_id"] = str(fm.get("id") or os.path.splitext(fm["_file"])[0])
        # --- гейт схемы: ругаться, а не подставлять дефолт ---
        nm = fm["_file"]
        if fm.get("state") is None:
            if fm.get("status") is not None:
                errors.append(f"{nm}: поле `status` вместо `state` (2-е поколение схемы) -- "
                              f"задача считалась бы открытой независимо от status={fm.get('status')!r}")
            else:
                errors.append(f"{nm}: нет поля `state` -- задача считалась бы открытой молча")
        elif str(fm.get("state")).strip().lower() not in KNOWN_STATES:
            errors.append(f"{nm}: неканоничный state={fm.get('state')!r} (канон: {sorted(KNOWN_STATES)})")
        if fm.get("priority") is None:
            src = "`prio`" if fm.get("prio") is not None else "ничего"
            errors.append(f"{nm}: нет поля `priority` (есть {src}) -- молча стало бы P2")
        elif str(fm.get("priority")).strip().upper() not in KNOWN_PRIOS:
            errors.append(f"{nm}: неканоничный priority={fm.get('priority')!r} (канон: P0..P3)")

        fm["state"] = str(fm.get("state", "open")).strip().lower()
        fm["priority"] = str(fm.get("priority", "P2")).strip().upper()
        fm["type"] = str(fm.get("type", "")).strip().lower()
        fm["owner"] = str(fm.get("owner", "claude")).strip().lower()
        created = parse_date(fm.get("created_at"))
        touched = parse_date(fm.get("touched_at")) or created
        fm["_age"] = (TODAY - touched).days if touched else None
        thr = STALE_DAYS.get("someday" if fm["state"] == "someday" else fm["priority"])
        fm["_stale"] = bool(fm["_age"] is not None and thr is not None and fm["_age"] > thr)
        ev = fm.get("evidence") or []
        fm["_has_ev"] = bool(ev if isinstance(ev, list) else str(ev).strip())
        # Критерий «сделано». Нет его -> задачу нельзя закрыть, она копится вечно
        # (так 71 legacy-заглушка из tasks.db держала 7 из 8 P0). Считаем только для живых.
        body = txt[m.end():]
        fm["_has_acc"] = ("## Acceptance" in body) or ("- [ ]" in body)
        tasks.append(fm)
    return tasks, errors


def as_list(v):
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def esc(s):
    return html.escape(str(s))


def links_html(items):
    out = []
    for it in as_list(items):
        s = str(it).strip().strip("[]")
        if s:
            out.append(f"<span class=lnk>{esc(s)}</span>")
    return " ".join(out)


def card(t):
    cls = "t" + (" stale" if t["_stale"] else "")
    prio = t["priority"]
    owner = OWNER_LBL.get(t["owner"], t["owner"])
    typ = TYPE_LBL.get(t["type"], t["type"])
    age = f"{t['_age']}д" if t["_age"] is not None else "?"
    bits = [f"<span class='pill p{prio}'>{esc(prio)}</span>"]
    if typ:
        bits.append(f"<span class=pill>{esc(typ)}</span>")
    bits.append(f"<span class=pill>{esc(owner)}</span>")
    bits.append(f"<span class=age>⏳{age}</span>")
    if t["_stale"]:
        bits.append("<span class='pill warn'>протухает</span>")
    meta = ""
    bf = links_html(t.get("born_from"))
    if bf:
        meta += f"<div class=rel>← из: {bf}</div>"
    bb = links_html(t.get("blocked_by"))
    if bb:
        meta += f"<div class=rel>⛔ ждёт: {bb}</div>"
    bl = links_html(t.get("blocks"))
    if bl:
        meta += f"<div class=rel>→ блокирует: {bl}</div>"
    if t["state"] == "done":
        ev = links_html(t.get("evidence")) or (esc(t.get("outcome")) if t.get("outcome") else "")
        if ev:
            meta += f"<div class=rel ok>✅ {ev}</div>"
        elif not t["_has_ev"]:
            meta += "<div class=rel warn2>⚠ закрыто без доказательства</div>"
    return (f"<div class='{cls}'><span class=id>{esc(t['_id'])}</span> "
            f"<b>{esc(t.get('title',''))}</b><div class=tags>{''.join(bits)}</div>{meta}</div>")


def sort_key(t):
    return (PRIO_ORD.get(t["priority"], 4), -(t["_age"] or 0))


def build_html(tasks, errors):
    undone = sorted([t for t in tasks if t["state"] in UNDONE], key=sort_key)
    done = sorted([t for t in tasks if t["state"] == "done"],
                  key=lambda t: (t["_age"] if t["_age"] is not None else 9999))
    someday = sorted([t for t in tasks if t["state"] == "someday"], key=sort_key)
    wip = [t for t in tasks if t["state"] == "wip"]
    no_ev = [t for t in done if not t["_has_ev"]]
    stale = [t for t in undone if t["_stale"]]

    def sec(title, items, empty="— пусто —"):
        body = "".join(card(t) for t in items) if items else f"<p class=empty>{empty}</p>"
        return f"<h2>{title} <span class=cnt>{len(items)}</span></h2>{body}"

    kpis = "".join(f"<span class=kpi><b>{n}</b> {lbl}</span>" for n, lbl in [
        (len(undone), "несделанных"), (len(wip), "в работе"), (len(stale), "⏳протухают"),
        (len(done), "сделано"), (len(someday), "когда-нибудь"), (len(no_ev), "⚠без доказательства")])
    warn = ""
    if len(wip) > 3:
        warn += f"<div class=banner>⚠ WIP={len(wip)} (лимит 3) — слишком много в работе одновременно</div>"
    if errors:
        warn += "<div class=banner>⚠ проблемы схемы: " + "; ".join(esc(e) for e in errors) + "</div>"

    style = """<style>
body{font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:22px;background:#faf9f7;color:#222;max-width:1000px}
h1{font-size:21px}h2{margin-top:26px;border-bottom:2px solid #eee;padding-bottom:5px;font-size:16px}
.cnt{color:#999;font-size:13px;font-weight:normal}
.kpi{display:inline-block;background:#fff;border:1px solid #e4e2de;border-radius:8px;padding:7px 13px;margin:4px 7px 4px 0}
.t{background:#fff;border:1px solid #e4e2de;border-radius:9px;padding:9px 13px;margin:7px 0}
.t.stale{border-left:4px solid #e8a33d}
.id{color:#aaa;font-size:11px}.tags{margin-top:5px}
.pill{display:inline-block;font-size:11px;background:#eef0f2;border-radius:5px;padding:1px 7px;margin-right:5px}
.pill.pP0{background:#d32f2f;color:#fff}.pill.pP1{background:#f57c00;color:#fff}
.pill.pP2{background:#e3ecf5}.pill.pP3{background:#eee;color:#888}
.pill.warn{background:#fff3e0;color:#b26a00}.age{font-size:11px;color:#999}
.rel{font-size:12px;color:#666;margin-top:3px}.rel .lnk{color:#3a6ea5}
.rel.ok{color:#2e7d32}.rel.warn2{color:#d32f2f}
.empty{color:#bbb;font-style:italic}
.banner{background:#fff3e0;border:1px solid #e8a33d;border-radius:8px;padding:8px 12px;margin:8px 0;color:#8a5a00}
footer{margin-top:30px;color:#aaa;font-size:12px}
</style>"""
    return (f"<!doctype html><meta charset=utf-8><title>Журнал задач</title>{style}"
            f"<h1>📋 Журнал задач — {TODAY.isoformat()}</h1>"
            f"<div>{kpis}</div>{warn}"
            f"{sec('📋 Несделанные', undone, 'всё закрыто 🎉')}"
            f"{sec('✅ Журнал сделанных', done)}"
            f"{sec('🗄 Когда-нибудь', someday)}"
            f"<footer>source of truth = 10-Tasks\\task-*.md · генерит tasks_index.py · "
            f"правило: reglament-zhurnal-zadach-sdelannye-i-nesdelannye-s-perelinkovkoy</footer>")


def main():
    if not os.path.isdir(TASKDIR):
        print(f"ERR: нет папки {TASKDIR}"); sys.exit(1)
    fixed = normalize_all()
    if fixed:
        print(f"🩹 нормализовано {len(fixed)} файлов:")
        for f, fx in sorted(fixed.items()):
            print(f"    {f}: {', '.join(fx)}")
    tasks, errors = load_tasks()
    os.makedirs(os.path.dirname(DASH), exist_ok=True)
    os.makedirs(AUDITD, exist_ok=True)
    with open(DASH, "w", encoding="utf-8") as f:
        f.write(build_html(tasks, errors))
    undone = [t for t in tasks if t["state"] in UNDONE]
    audit = {
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total": len(tasks), "undone": len(undone),
        "wip": sum(t["state"] == "wip" for t in tasks),
        "done": sum(t["state"] == "done" for t in tasks),
        "someday": sum(t["state"] == "someday" for t in tasks),
        "stale": [t["_id"] for t in undone if t["_stale"]],
        "done_no_evidence": [t["_id"] for t in tasks if t["state"] == "done" and not t["_has_ev"]],
        "no_acceptance": [t["_id"] for t in undone if not t.get("_has_acc")],
        "schema_errors": errors,
    }
    # атомарно: читатели (SessionStart-хук на пирах) не должны видеть полфайла
    ap = os.path.join(AUDITD, "audit-latest.json")
    tmp = f"{ap}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ap)
    print(f"OK: {len(tasks)} задач -> {DASH}")
    print(f"    несделанных={audit['undone']} wip={audit['wip']} done={audit['done']} "
          f"someday={audit['someday']} протухает={len(audit['stale'])} "
          f"без-доказательства={len(audit['done_no_evidence'])} "
          f"без-критерия-сделано={len(audit['no_acceptance'])}")
    if errors:
        print("    ⚠ схема:", "; ".join(errors))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
