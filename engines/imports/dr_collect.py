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
dr_collect.py — ночной СБОРЩИК + СТОРОЖ Deep Research отчётов (0 токенов, stdlib).

СБОРЩИК: для каждого DR в реестре со статусом issued/running ищет отчёт в уже
импортированных ночным синком чатах (ChatGPT / Claude-AI / _cowork-inbox) по
DR-ID в заголовке ИЛИ теле заметки (ChatGPT переименовывает чаты — тело надёжнее:
наш промпт с ID лежит первым сообщением). Найдено → копия verbatim в
_originals\\deep-research\\<ID>-<slug>-<vendor>.md + статус collected.
Дедуп трёхслойный: (1) ночной импорт идемпотентен по conversation_id;
(2) имя целевого файла детерминировано по ID+vendor — существует=скип;
(3) реестр = гроссбух, путь уже вписан=скип. Дублей не бывает по построению.

СТОРОЖ: (a) DR старше N часов в issued/running; (b) файлы-сироты в
_originals\\deep-research без строки реестра; (c) импортированные чаты, похожие
на DR (в названии "deep research"), но БЕЗ номера. Есть находки → пост в TG-03
(bus_ping --post), нет — молчит (silent-if-green).

Usage:
  python dr_collect.py                  # collect + watch, отчёт в stdout
  python dr_collect.py --post-alerts    # + красные находки в TG-03
  python dr_collect.py --stale-hours 0  # порог зависших (умолч. 48)
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

# dead-man's-switch: общий хелпер (URL живёт только в нём, синкается на все машины)
WATCHDOG_HELPER = os.path.join(os.path.expanduser("~"), ".claude", "scripts", "watchdog_ping.py")


def watchdog_ping(source, every_min=1440):
    """'Я отработал' → n8n-сторож. Пропущенная ночь → крик в чат-03. Fire-and-forget."""
    try:
        subprocess.run([sys.executable, WATCHDOG_HELPER, source, str(every_min)],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dr_registry  # REGISTRY, ROW_RE, read_lines, merge_conflicts

try:
    from _paths import VAULT   # machine-aware: reads ~/.claude/machine.env (hub/Mac/Якорёк)
except Exception:
    VAULT = r"%VAULT%"   # HP17/Windows fallback
# _originals и _cowork-inbox — сиблинги волта (%VAULT_ROOT%\... на хабе); derive относительно
# волта, чтобы путь резолвился на любой ОС, а не только на Windows-хабе.
_OBS = os.path.dirname(VAULT)
SOURCES = {  # vendor -> папка импортированных заметок
    "chatgpt": os.path.join(VAULT, "01-Conversations", "ChatGPT", "conversations"),
    "claude": os.path.join(VAULT, "01-Conversations", "Claude-AI", "conversations"),
    "cowork": os.path.join(_OBS, "_cowork-inbox"),
}
DEST = os.path.join(_OBS, "_originals", "deep-research")
BUS_PING = os.path.join(os.path.expanduser("~"), ".claude", "scripts", "bus_ping.py")
ID_RE = re.compile(r"DR\d{2}-\d{2}-\d{2}-(?:[A-Z0-9]+-)?\d{2,}(?:-\d{4})?")  # v4: опц. хвост -HHMM (2026-07-16)
BODY_HEAD = 6000  # ID ищем в первых N символах (промпт = первое сообщение)
# ChatGPT Deep Research: тело отчёта живёт в кросс-доменном sandbox-iframe и НЕ попадает
# ни в API, ни в официальный экспорт (см. skills/dr-fanout §3). Импортированный чат такого DR =
# наш промпт + kickoff-JSON, без ответа. Раньше collect() считал его отчётом (ID матчится же!)
# → collected → synthesize выжимал "выводы" из самого промпта → ложное synthesized
# (прецедент DR26-07-01-ZB-01..05, 2026-07-14). Гейт ниже режет класс на входе.
KICKOFF_MARK = "/Deep Research App/start"
KICKOFF_MIN_ANSWER_WORDS = 120  # меньше этого содержательного текста ассистента = эхо

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def read_head(path, n=BODY_HEAD):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def is_kickoff_echo(path):
    """True = чат содержит только запуск Deep Research (промпт + kickoff-JSON), тела отчёта нет.
    Детерминированно: маркер kickoff есть И после выреза code-fence'ов в секциях ассистента
    (**ChatGPT:** ...) почти нет слов. Настоящий отчёт в чате = тысячи слов → False."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            txt = f.read(200_000)
    except OSError:
        return False
    if KICKOFF_MARK not in txt:
        return False
    body = re.sub(r"```.*?```", "", txt, flags=re.S)  # kickoff-JSON живёт в fence'ах
    answer = " ".join(re.split(r"\*\*ChatGPT:\*\*", body)[1:])  # только секции ассистента
    return len(answer.split()) < KICKOFF_MIN_ANSWER_WORDS


def registry_rows():
    dr_registry.merge_conflicts()
    rows = []
    for line in dr_registry.read_lines():
        m = dr_registry.ROW_RE.match(line)
        if m:
            cells = [c.strip() for c in line.split("|")][1:7]  # id,date,topic,tool,status,files
            rows.append(cells)
    return rows


def update_row(dr_id, status=None, add_file=None):
    lines = dr_registry.read_lines()
    for n, l in enumerate(lines):
        m = dr_registry.ROW_RE.match(l)
        if m and m.group(1) == dr_id:
            cells = [c.strip() for c in l.split("|")]
            if status:
                cells[5] = status
            if add_file:
                cells[6] = add_file if cells[6] in ("—", "") else cells[6] + " · " + add_file
            lines[n] = "| " + " | ".join(cells[1:7]) + " |"
            with open(dr_registry.REGISTRY, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True
    return False


def collect():
    """Вернёт (collected: list[str], kickoffs: list[str], notes_scanned: int)."""
    os.makedirs(DEST, exist_ok=True)
    # collected-EMPTY = гейт качества dr_synthesize признал материал пустым (нет тела отчёта)
    # → продолжаем искать НАСТОЯЩИЙ отчёт; новый файл найден → статус снова collected → ресинтез
    pending = [r for r in registry_rows() if r[4] in ("issued", "running", "collected-EMPTY")]
    if not pending:
        return [], [], 0
    collected, kickoffs, scanned = [], [], 0
    for vendor, folder in SOURCES.items():
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if not fn.endswith(".md"):
                continue
            scanned += 1
            src_path = os.path.join(folder, fn)
            head = read_head(src_path)
            found = set(ID_RE.findall(head))
            echo = None  # лениво, 1 раз на файл
            for row in pending:
                dr_id = row[0]
                if dr_id not in found:
                    continue
                if echo is None:
                    echo = is_kickoff_echo(src_path)
                if echo:
                    # отчёт готов у вендора, но тело не выгружается → НЕ collected, статус
                    # остаётся issued; человек жмёт Export→Markdown (полоса Downloads подберёт)
                    kickoffs.append(f"{dr_id}: kickoff-эхо без тела ({vendor}/{fn}) → нужен Export→Markdown")
                    continue
                slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", fn[:-3])[:40]
                target = os.path.join(DEST, f"{dr_id}-{slug}-{vendor}.md")
                if os.path.basename(target) in row[5]:
                    continue  # уже собран (гроссбух)
                if not os.path.exists(target):
                    shutil.copy2(os.path.join(folder, fn), target)
                update_row(dr_id, status="collected", add_file=target)
                row[4], row[5] = "collected", row[5] + " " + os.path.basename(target)
                collected.append(f"{dr_id} ← {vendor}/{fn}")
    return collected, kickoffs, scanned


def watch(stale_hours):
    """Вернёт список проблемных строк (пусто = всё зелёное)."""
    problems = []
    today = datetime.date.today()
    known_ids, all_files = set(), []
    for r in registry_rows():
        known_ids.add(r[0])
        all_files.append(r[5])
        if r[4] in ("issued", "running", "collected-EMPTY"):
            try:
                age_h = (today - datetime.date.fromisoformat(r[1])).days * 24
            except ValueError:
                continue
            if age_h >= stale_hours:
                mark = "🕳️ пустышка ждёт настоящего отчёта" if r[4] == "collected-EMPTY" else "⏳ завис"
                problems.append(f"{mark} {r[0]} ({r[4]} {age_h}ч): {r[2][:60]}")
    all_files = " ".join(all_files)  # покрытие: на файл указывает хоть одна строка реестра
    if os.path.isdir(DEST):
        for fn in os.listdir(DEST):
            m = ID_RE.match(fn)
            if (m and m.group(0) in known_ids) or fn in all_files:
                continue
            problems.append(f"👻 сирота без строки реестра: _originals\\deep-research\\{fn}")
    for vendor, folder in SOURCES.items():
        if vendor == "cowork" or not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if not fn.endswith(".md"):
                continue
            head = read_head(os.path.join(folder, fn), 1200)
            tm = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M)
            title = tm.group(1) if tm else fn
            if re.search(r"deep.?research|дипрес[её]рч", title, re.I) and not ID_RE.search(head) \
                    and fn not in all_files:
                problems.append(f"🔢 DR без номера: {vendor}/{fn}")
    return problems


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--post-alerts", action="store_true", help="красные находки → TG-03")
    p.add_argument("--stale-hours", type=int, default=48)
    args = p.parse_args()

    # ПОЛОСА 2: подмести сырые DR-файлы, скачанные в Downloads (мимо чат-импорта),
    # и зарегистрировать любые сироты в DEST. Отдельным процессом — сбой здесь не валит сторожа.
    ingest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dr_ingest_downloads.py")
    if os.path.exists(ingest):
        try:
            r = subprocess.run([sys.executable, ingest, "--apply"],
                               capture_output=True, text=True, timeout=300,
                               encoding="utf-8", errors="replace")
            tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
            print("DR-INGEST(Downloads):", tail[0])
        except (OSError, subprocess.SubprocessError) as e:
            print(f"DR-INGEST(Downloads): пропущено ({e})")

    got, kickoffs, scanned = collect()
    problems = watch(args.stale_hours)
    # kickoff-эхо = actionable-проблема (человек жмёт Export→Markdown), дедуп от повторов за файл
    problems.extend("🖨️ " + k for k in sorted(set(kickoffs)))

    print(f"DR-COLLECT: собрано {len(got)}, просканировано заметок {scanned}")
    for g in got:
        print("  ✅", g)
    if problems:
        print(f"DR-WATCH: {len(problems)} проблем")
        for pr in problems:
            print("  ", pr)
        if args.post_alerts:
            text = "🕵️ DR-сторож: " + f"{len(problems)} проблем · " + " ; ".join(problems[:5])
            subprocess.run([sys.executable, BUS_PING, "--post", text], timeout=90)
    else:
        print("DR-WATCH: чисто ✅")

    watchdog_ping("dr-collect-nightly", every_min=1440)  # dead-man's-switch: пропущенная ночь → крик


if __name__ == "__main__":
    main()
