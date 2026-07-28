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
dr_registry.py v3.1 — реестр Deep Research Антона (0 токенов, stdlib only). SHARD-CUTOVER.

Каждый DR получает номер DRYY-MM-DD-<МАШИНА>-NN (у каждого компа СВОЯ очередь).

v3 (2026-07-15, мандат Антона «чини корень»): КОРЕНЬ хронических .sync-conflict на
_DR-Registry.md = несколько машин дописывали ОДИН синкаемый файл (Syncthing whole-file
LWW не мержит конкурентные записи; merge_conflicts лечил лишь ПОСЛЕ). Форевер-фикс =
single-writer протокол (рамка PROPOSAL-MAC1-2026-07-14-ne-zhdat-hab-3-role-split):
  ПИР : new/update/rescue пишут ТОЛЬКО свой шард _machine-bus/_dr/DR-registry__from-<host>.md
        (один писатель на файл => Syncthing-конфликт невозможен by design). Мастер пир НЕ пишет.
  ХАБ : единственный писатель мастера _DR-Registry.md; fold() втягивает шарды на каждой
        команде, выбирая по ID строку с САМЫМ ПРОДВИНУТЫМ статусом (см. merge_cells).
        Совместим и с 5-полевым форматом шардов peer-local движка
        (~/.claude/scripts/dr_registry.py) — оба живут, дрейфа нет.
  ЧТЕНИЕ (next/list) везде = мастер + ВСЕ шарды => пир видит свежее не дожидаясь фолда хаба.
Разрешение конкурирующих update ОДНОГО ID с разных машин: по ЖИЗНЕННОМУ ЦИКЛУ статуса
(issued<running<collected-EMPTY<collected<{dead<synthesized}), НЕ по порядку файлов —
порядок шардов больше ничего не решает. При равном статусе пустые ячейки досыпаются,
«где результат» объединяется через « · ».
v3.1 (2026-07-16): переустановлен после LWW-затирания волной ресинка 15.07 22:39
(офлайн-узел привёз старое дерево _imports — ровно тот класс, что v3 лечит) +
влит machine-aware резолв волта через _paths из параллельной правки (не потерян).
v3.2 (2026-07-22, мандат «чини корень»): КОРЕНЬ отката хаб-close = fold брал last-wins по
имени файла шарда => шард пира (from-LAPTOP1/from-MAC1) перебивал закрытие хаба
(from-HUB1 идёт раньше по алфавиту). Форевер-фикс = merge_cells по lifecycle-рангу.

Команды:
  python dr_registry.py new "<тема>" [--tool chatgpt,gemini,grok,cowork] [--gap]
  python dr_registry.py update <ID> [--status collected|collected-EMPTY|synthesized|dead|applied|parked] [--file "<путь>"] [--note "<текст>"]
  (collected-EMPTY = материал собран, но тела отчёта нет — гейт качества dr_synthesize; dr_collect продолжает искать настоящий отчёт)

v3.3 (2026-07-27, правило Антона «у каждой папки есть конец»): `synthesized` больше НЕ финиш —
отчёт написан, но система не изменилась. Финиш = один из двух, оба требуют --note:
  --status applied --note "<чем закрыто: Decision Memo / что поменяли в проде>"
  --status parked  --note "<почему не берём и что изменит решение>"
Зачем: на 27.07 из 246 разведок 184 были `synthesized`, но лишь ~20 дошли до Decision Memo.
Разницу «кормит систему / просто лежит» было не видно. Теперь видно.
  python dr_registry.py list [--today]
  python dr_registry.py next
  python dr_registry.py fold   # только хаб: шарды -> мастер (на пире печатает отказ)
"""
import argparse
import datetime
import glob
import os
import re
import shutil
import sys

# Портируемость: _paths (machine.env) -> env CLAUDE_VAULT_ROOT -> E:\ (Windows) -> ~/Obsidian.
try:
    from _paths import VAULT as _PV          # machine-aware: reads ~/.claude/machine.env (hub/Mac/Якорёк)
    VAULT = str(_PV)
except Exception:
    _WIN_VAULT = r"%VAULT%"
    VAULT = (os.environ.get("CLAUDE_VAULT_ROOT")
             or (_WIN_VAULT if os.path.isdir(_WIN_VAULT) else os.path.expanduser("~/Obsidian/Owner-Knowledge")))
if os.environ.get("CLAUDE_VAULT_ROOT"):      # явный env всегда главнее (нужно тестам и нестандартным узлам)
    VAULT = os.environ["CLAUDE_VAULT_ROOT"]
BUS = os.environ.get("MACHINE_BUS_DIR") or os.path.join(VAULT, "_machine-bus")
REGISTRY = os.path.join(VAULT, "_DR-Registry.md")
SHARD_DIR = os.path.join(BUS, "_dr")
CONFLICT_ARCHIVE = os.path.join(VAULT, "_sync-conflict-archive")
HUB_HOSTNAME = "HUB1"
# ID: DR26-07-16-HUB-01-2146 (v4, с часами-минутами выдачи; anton 2026-07-16: время делает ID
# независимым от чужого счётчика — ручная нумерация больше не коллидит), DR26-07-03-ZB-11 (v2),
# DR26-07-03-10 (v1, до 2026-07-03 22:40). Хвост -HHMM опционален: все три формата валидны.
ROW_RE = re.compile(r"^\|\s*(DR\d{2}-\d{2}-\d{2}-(?:[A-Z0-9]+-)?\d{2,}(?:-\d{4})?)\s*\|")
BARE_RE = re.compile(r"^(DR\d{2}-\d{2}-\d{2}-(?:[A-Z0-9]+-)?\d{2,}(?:-\d{4})?)\s*\|")  # шард peer-local (без ведущего |)

MACHINE_CODES = {
    "HUB1": "HUB",      # десктоп-хаб Palo Alto
    "LAPTOP1": "ZB",     # ноут LAPTOP1 Антона
    "NAT1": "NAT",            # комп Нина
    # фикс класса 2026-07-16 (коллизии DR26-07-14/07-07-MAC1-01): без записи авто-код
    # Мака Антона = "MACB" = код Мака Рита -> люди нумеровали MAC1 вручную мимо счётчика
    "MAC1": "MAC1", # MacBook Антона (MACHINE_KEY=MAC1)
    "ANCHOR1": "ANCHOR1",     # Якорь VPS (оффлайн-фолбэк; истина = fleet_nodes.json)
}

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def hostname():
    return (os.environ.get("MACHINE_KEY") or os.environ.get("COMPUTERNAME")
            or os.uname().nodename)


def is_hub():
    return hostname().upper() == HUB_HOSTNAME


def _registry_codes():
    """fleet_nodes.json = single source of truth (root-fix FLEE 2026-07-18); {} офлайн-фолбэк."""
    try:
        import sys as _s, os as _o
        for p in (_o.path.expanduser("~/.claude/scripts"), _o.path.expanduser("~/.claude/scripts/_shared")):
            if p not in _s.path:
                _s.path.insert(0, p)
        import fleet_nodes
        return {str(k).upper(): v for k, v in fleet_nodes.codes().items()}
    except Exception:
        return {}


def machine_code():
    host = hostname().upper()
    codes = dict(MACHINE_CODES)
    codes.update(_registry_codes())
    if host in codes:
        return codes[host]
    # незнакомая машина: первые 4 буквенно-цифровых символа hostname — само-регистрация без правки скрипта
    return re.sub(r"[^A-Z0-9]", "", host)[:4] or "UNKN"


def shard_path():
    return os.path.join(SHARD_DIR, f"DR-registry__from-{hostname()}.md")


def today_prefix():
    d = datetime.date.today()
    return f"DR{d:%y-%m-%d}-{machine_code()}"


# ---------- парсинг строк (мастер-формат И 5-полевый шард peer-local) ----------
def parse_row(line):
    """-> (id, [id,date,topic,tool,status,files]) или None. Понимает оба формата."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.startswith("|"):
        m = ROW_RE.match(s)
        if not m:
            return None
        cells = [c.strip() for c in s.strip("|").split("|")]
    else:
        m = BARE_RE.match(s)
        if not m:
            return None
        cells = [c.strip() for c in s.split("|")]
        if len(cells) == 5:                      # peer-local: ID|date|theme|status|where -> вставить tool
            cells = [cells[0], cells[1], cells[2], "—", cells[3], cells[4]]
    cells = (cells + ["—"] * 6)[:6]
    return cells[0], cells


def fmt_row(cells):
    return "| " + " | ".join(cells[:6]) + " |"


def read_file_lines(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def read_lines():
    # back-compat shim: dr_collect/dr_ingest_downloads/dr_synthesize зовут read_lines() (v3 переименовал в read_file_lines)
    return read_file_lines(REGISTRY)


def all_ids(lines):
    # back-compat shim: dr_ingest_downloads.all_ids(read_lines()); восстановлен из pre-gate v2
    return [m.group(1) for m in (ROW_RE.match(l) for l in lines) if m]


def shard_files():
    return sorted(glob.glob(os.path.join(SHARD_DIR, "DR-registry__from-*.md")))


# ---------- lifecycle-монотонный мерж (корень-фикс 2026-07-22) ----------
# Раньше merged_rows брал last-wins по ПОРЯДКУ ФАЙЛОВ (мастер, потом шарды по алфавиту).
# Итог: шард пира с алфавитно-поздним именем (from-LAPTOP1) перебивал закрытие хабом
# (from-HUB1 идёт раньше) — хаб В ПРИНЦИПЕ не мог авторитетно закрыть чужой DR,
# статус откатывался на collected/running после fold. Форевер-фикс: порядок шардов НЕ
# решает — выигрывает строка с САМЫМ ПРОДВИНУТЫМ статусом по жизненному циклу.
# collected-EMPTY = пустышка (материал есть, тела отчёта нет) — НИЖЕ collected: она ждёт
# настоящего отчёта и не должна перебивать collected/synthesized. Терминалы сверху;
# synthesized > dead (реальный синтез бьёт «заброшено», иначе тухлый шард обнулил бы
# счётчик synthesized). Неизвестный статус = 0 (любой известный его перебьёт).
_STATUS_RANK = {
    "issued": 1,
    "running": 2,
    "collected-empty": 3,
    "collected": 4,
    "dead": 5,
    "synthesized": 6,
    "parked": 7,
    "applied": 8,
}

# Статусы, на которых разведка ЗАКРЫТА (правило Антона 27.07: у каждой папки есть конец —
# либо «сделали вот это», либо честно «решили не делать, потому что»).
# `synthesized` ФИНАЛЬНЫМ НЕ СЧИТАЕТСЯ: отчёт написан, но состояние системы не изменилось.
TERMINAL_STATUSES = ("applied", "parked", "dead")


def status_rank(status):
    return _STATUS_RANK.get((status or "").strip().lower(), 0)


def _union_files(a, b):
    """Объединить непустые сегменты «где результат» через « · » (как cmd_update), без дублей."""
    segs = []
    for v in (a, b):
        for part in (v or "").split(" · "):
            part = part.strip()
            if part and part not in ("—", "") and part not in segs:
                segs.append(part)
    return " · ".join(segs) if segs else "—"


def merge_cells(a, b):
    """Слить две строки одного ID: статус = самый продвинутый; непустые ячейки не теряем;
    «где результат» объединяется. Порядок шардов теперь не решает ничего.
    Осознанные ограничения монотонности (не баги, а суть подхода — мандат «монотонный статус»):
      • downgrade невозможен, пока ХОТЬ ОДИН источник держит статус выше (напр. dead НЕ
        перебьёт synthesized; running→issued внутри шарда игнорируется) — это и защищает
        счётчик synthesized от обнуления тухлым шардом. Нужен явный откат = убрать
        высокостатусную строку из ВСЕХ шардов, иначе fold её вернёт.
      • тема/заметки (idx2): при равном статусе берём БОЛЕЕ аннотированную (длиннее) —
        покрывает частый случай накопительных «(note)»; расходящиеся заметки разных машин
        по одному ID редки (single-writer шард копит их у одного писателя)."""
    hi, lo = (a, b) if status_rank(a[4]) >= status_rank(b[4]) else (b, a)
    out = list(hi)
    for i in (1, 3):                        # date, tool — досыпать из проигравшей, если у hi пусто
        if out[i] in ("—", "") and lo[i] not in ("—", ""):
            out[i] = lo[i]
    # тема/заметки: не терять накопленные «(note)» — берём более длинную непустую
    if lo[2] not in ("—", "") and len(lo[2]) > len(out[2] if out[2] not in ("—", "") else ""):
        out[2] = lo[2]
    out[5] = _union_files(hi[5], lo[5])     # где результат — объединяем всегда
    return out


def merged_rows():
    """Мастер + все шарды, мерж по ID с ВЫБОРОМ САМОГО ПРОДВИНУТОГО СТАТУСА (не last-wins
    по порядку файлов). -> (order:list[id], rows:dict[id]->cells)."""
    order, rows = [], {}
    for src in [REGISTRY] + shard_files():
        for l in read_file_lines(src):
            pr = parse_row(l)
            if not pr:
                continue
            rid, cells = pr
            if rid not in rows:
                order.append(rid)
                rows[rid] = cells
            else:
                rows[rid] = merge_cells(rows[rid], cells)
    return order, rows


# ---------- запись: пир -> шард; хаб -> мастер ----------
SHARD_HEADER = (
    "# DR-шард узла {key} (single-writer: пишет ТОЛЬКО эта машина; хаб фолдит в _DR-Registry.md)\n"
    "# Формат: | ID | дата | тема | tool | статус | где результат |  (повторная строка ID = обновление)\n\n"
)


def append_shard(row_line):
    os.makedirs(SHARD_DIR, exist_ok=True)
    p = shard_path()
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(SHARD_HEADER.format(key=hostname()))
    with open(p, "a", encoding="utf-8") as f:
        f.write(row_line + "\n")


def fold():
    """Только хаб: втянуть шарды в мастер (преамбула мастера сохраняется). Идемпотентно."""
    if not is_hub():
        return 0
    lines = read_file_lines(REGISTRY)
    preamble = []
    for l in lines:
        if ROW_RE.match(l):
            break
        preamble.append(l)
    order, rows = merged_rows()
    body = [fmt_row(rows[rid]) for rid in order]
    with open(REGISTRY, "w", encoding="utf-8") as f:
        f.write("\n".join(preamble + body) + "\n")
    return len(order)


def merge_conflicts():
    """Syncthing-конфликт мастера: спасти недостающие DR-строки. v3: спасённое пишется
    в МОЙ шард (пир) / мастер (хаб) — пир мастера не трогает. Копии -> архив."""
    conflicts = glob.glob(os.path.join(VAULT, "_DR-Registry*sync-conflict*"))
    if not conflicts:
        return
    _, rows = merged_rows()
    known = set(rows)
    total = 0
    for path in conflicts:
        try:
            rescued = []
            for l in read_file_lines(path):     # utf-8-sig внутри: BOM от PowerShell не ломает парс
                pr = parse_row(l)
                if pr and pr[0] not in known:
                    rescued.append(fmt_row(pr[1]))
                    known.add(pr[0])
            # порядок важен: сначала дописать строки, только потом убирать копию — иначе тихая потеря
            if rescued:
                if is_hub():
                    with open(REGISTRY, "a", encoding="utf-8") as f:
                        f.write("\n".join(rescued) + "\n")
                else:
                    for r in rescued:
                        append_shard(r)
                total += len(rescued)
            os.makedirs(CONFLICT_ARCHIVE, exist_ok=True)
            shutil.move(path, os.path.join(CONFLICT_ARCHIVE, os.path.basename(path)))
        except OSError:
            pass  # файл занят/едет по синку — заберём в следующий раз
    if total:
        print(f"(само-лечение: спасено {total} строк из sync-conflict копий)", file=sys.stderr)


def next_seq(rows, gap=False):
    prefix = today_prefix()  # считаем ТОЛЬКО свою машину — чужие очереди не мешают
    # v4: хвост -HHMM не путать с NN — сек всегда группа перед опциональным временем
    seq_re = re.compile(re.escape(prefix) + r"-(\d{2,})(?:-\d{4})?$")
    seqs = [int(m.group(1)) for m in (seq_re.match(i) for i in rows) if m]
    base = max(seqs) if seqs else 0
    return base + (10 if gap else 1)


def cmd_new(args):
    merge_conflicts()
    if is_hub():
        fold()
    _, rows = merged_rows()
    # v4 (anton 2026-07-16): -HHMM время выдачи. NN страхует пачку в одну минуту,
    # HHMM страхует ручную нумерацию (не нужно знать чужой счётчик — часы локальны).
    dr_id = f"{today_prefix()}-{next_seq(rows, args.gap):02d}-{datetime.datetime.now():%H%M}"
    date = datetime.date.today().isoformat()
    tool = args.tool or "—"
    row = fmt_row([dr_id, date, args.topic, tool, "issued", "—"])
    if is_hub():
        with open(REGISTRY, "a", encoding="utf-8") as f:
            f.write(row + "\n")
    else:
        append_shard(row)
    print(dr_id)


def cmd_update(args):
    merge_conflicts()
    if is_hub():
        fold()
    _, rows = merged_rows()
    if args.id not in rows:
        sys.exit(f"ID {args.id} не найден (мастер + шарды)")
    cells = list(rows[args.id])
    if args.status:
        # Гейт правила «конец у каждой папки»: applied/parked обязаны нести причину.
        # applied — чем именно закрыто (Decision Memo / что поменяли); parked — почему не берём.
        if args.status in ("applied", "parked") and not (args.note or args.file):
            sys.exit(
                f"status={args.status} требует объяснения: добавь --note \"<чем закрыто / почему не берём>\"\n"
                f"  applied → что реально изменилось (Decision Memo, правка в проде, новая рутина)\n"
                f"  parked  → почему решили не делать (и что изменит решение)"
            )
        cells[4] = args.status
    if args.file:
        cells[5] = args.file if cells[5] in ("—", "") else cells[5] + " · " + args.file
    if args.note:
        cells[2] = cells[2] + f" ({args.note})"
    row = fmt_row(cells)
    if is_hub():
        lines = read_file_lines(REGISTRY)
        hit = None
        for n, l in enumerate(lines):
            m = ROW_RE.match(l)
            if m and m.group(1) == args.id:
                hit = n
        if hit is None:                          # ID жил только в шарде — доехал через fold ниже
            lines.append(row)
        else:
            lines[hit] = row
        with open(REGISTRY, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        fold()
    else:
        append_shard(row)                        # повторная строка ID = обновление (фолд возьмёт последнюю)
    print(row)


def cmd_list(args):
    merge_conflicts()
    order, rows = merged_rows()
    if args.today:
        day = f"DR{datetime.date.today():%y-%m-%d}-"
        order = [i for i in order if i.startswith(day)]
    print("\n".join(fmt_row(rows[i]) for i in order) if order else "(пусто)")


def cmd_next(args):
    merge_conflicts()
    _, rows = merged_rows()
    print(f"{today_prefix()}-{next_seq(rows):02d}-{datetime.datetime.now():%H%M}")


def cmd_fold(args):
    if not is_hub():
        print(f"fold пишет мастер — это делает только хаб ({HUB_HOSTNAME}); эта машина = {hostname()}")
        return
    merge_conflicts()
    n = fold()
    print(f"FOLD OK: мастер = {n} строк (шарды втянуты, по самому продвинутому статусу)")


def main():
    p = argparse.ArgumentParser(description="Реестр Deep Research (v3.1 shard-cutover)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new")
    n.add_argument("topic")
    n.add_argument("--tool", default="")
    n.add_argument("--gap", action="store_true", help="не уверен в счётчике дня → +10")
    n.set_defaults(fn=cmd_new)

    u = sub.add_parser("update")
    u.add_argument("id")
    u.add_argument("--status", choices=["issued", "running", "collected", "collected-EMPTY",
                                        "synthesized", "dead", "applied", "parked"])
    u.add_argument("--file", default="")
    u.add_argument("--note", default="")
    u.set_defaults(fn=cmd_update)

    l = sub.add_parser("list")
    l.add_argument("--today", action="store_true")
    l.set_defaults(fn=cmd_list)

    x = sub.add_parser("next")
    x.set_defaults(fn=cmd_next)

    f = sub.add_parser("fold")
    f.set_defaults(fn=cmd_fold)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
