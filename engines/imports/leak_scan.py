#!/usr/bin/env python
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
"""leak_scan.py — deterministic pre-publication leak scanner (ONE gate for every public rail).

Closes the CLASS of formatting bypasses: numbers/handles are matched on a
NORMALIZED shadow copy of each line (spaces/dashes/dots/parens stripped), so
"+1 341 222 9178" and "-548 501 2790" match the same as compact forms.

Usage:  python leak_scan.py <dir|file> [...] [--profile freeschool|book]
        git diff --cached | python leak_scan.py --stdin --profile book
        python leak_scan.py --self-test
Exit:   0 = clean (INFO allowed), 1 = FAIL hits found, 2 = usage/path error.
Scope:  *.md *.py *.json *.txt *.yml *.yaml, skips .git/.

PROFILES (added 2026-07-27 after a real leak):
  freeschool (default, unchanged behaviour) — third-party PERSON NAMES are secret too.
  book       — the Journey / show-canon rail: person NAMES are explicitly ALLOWED
               (Anton's rule 2026-07-06: names are not secrets, generous attribution
               builds trust), but every MACHINE identifier is still blocked.
Both profiles share IDENTIFIER_WORDS + MACHINE_RULES, so a fix here fixes every rail.

Why this file grew a scrub() and a --stdin mode: on 2026-07-27 the public canon/BEATS.md
was found carrying a VPS IP, a private-network address, a hostname and two bot handles.
Two causes, both of the same class:
  1. canon_render.py copied beat bodies verbatim and had NO scrub pass at all;
  2. the /journey push gate was written as `if git diff | grep -E '...' | head -10; then`
     and `head` ALWAYS exits 0, so the gate could never block anything.
Lesson burned in: a gate returns its own honest exit code, and it scans the ARTIFACT,
not only the diff (one missed diff = a permanent leak).

Rules live below — one file, stdlib-only (AK-47).
Authorized-public tokens (CTA phone, Anton's public name) report as INFO, not FAIL.
"""
import io, os, re, sys

for _s in (sys.stdout, sys.stderr):   # cp1252 console -> force UTF-8 so non-ASCII prints don't crash
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

# --- tokens that must NEVER leave (compact digit forms; matched on normalized text)
SECRET_NUMBERS = [
    "182355026", "4074838102", "6634998361", "9095182014", "9232703764",
    "1000941603212", "1007588357707", "226258979", "5966672828",
    "9110567260", "970102884", "7179668356",
    "355388751851", "96863211225", "963308162378", "79010892080",
]
# Person names: secret ONLY on the freeschool rail. The book keeps names on purpose.
PERSON_NAMES = [
    "Нина", "Нина", "Рита", "Олег", "васильева", "Полина",
    "Арина", "Артём и алиса", "Dziatkovskii",
]
# Identifiers: secret on EVERY rail (mailboxes, hostnames).
# ⚠️ Хэндлы аккаунтов ПЕРЕЕХАЛИ в MACHINE_RULES с границей \b: подстрочный поиск ловил
# "work_acct_b" внутри публичного permalink facebook.com/OwnerProfile и давал 165 ложняков на живой
# книге (2026-07-27). Публичный профиль в ссылке на пост - не секрет; @хэндл в мессенджере - да.
IDENTIFIER_WORDS = [
    "HUB1", "LAPTOP1", "NAT1", "10.0.0.10", "owner.personal",
]
SECRET_WORDS = PERSON_NAMES + IDENTIFIER_WORDS   # kept for backwards compatibility
SECRET_REGEX = [
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{15,}"),
    re.compile(r"gho_[A-Za-z0-9]{10,}"),
    re.compile(r"xox[bp]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@(?:gmail|platinum)[A-Za-z0-9.-]*\.[a-z]{2,}", re.I),
]
# Локальные пути: секрет на free-school рельсе, но НЕ в книге — она build-in-public и открыто
# показывает устройство волта; путь не даёт доступа и не является кредом (решено 2026-07-27).
FREESCHOOL_ONLY_REGEX = [
    re.compile(r"%VAULT_ROOT%|%USERPROFILE%", re.I),
]
# --- authorized public tokens → INFO (visible, but not a failure)
ALLOW_NUMBERS = ["16213388980"]           # co-founder WA CTA (Anton-authorized, never strip)
ALLOW_WORDS = ["anton dzyatkovsky", "palo-alto-ai-research-lab",
               "a@corp_acct.fund"]   # публичный контакт Антона (стоит в START-HERE рядом с LinkedIn)

# --- machine identifiers: (kind, regex, scrub replacement = a ROLE, not "***").
# Public text must stay readable after scrubbing, so we swap in what the thing IS.
MACHINE_RULES = [
    ("hostname-hub",    r"(?i)HUB1",                      "хаб"),
    ("hostname-laptop", r"(?i)LAPTOP1[A-Za-z0-9-]*",               "ноутбук"),
    ("hostname-anchor", r"(?i)ANCHOR1",                       "Якорь"),
    ("hostname-peer",   r"(?i)NAT1[A-Za-z0-9-]*",               "машина коллеги"),
    ("hostname-mac",    r"(?i)MacBook-(?:Anton|Rita)",          "Mac"),
    # аккаунты и ящики: сканируются словарём IDENTIFIER_WORDS, но скрабить их обязан
    # тот же слой, иначе рендер вечно падает на гейте и «чинится» руками (было 2026-07-27)
    ("acct-service",    r"(?i)\b@?(?:corp_acct\d*|bbplatinum[a-z]*)\b", "служебный аккаунт"),
    ("acct-work",       r"(?i)\b@?(?:work_acct_b|work_acct_a|personal_acct)\b",   "рабочий аккаунт"),
    ("acct-peer",       r"(?i)\b@?(?:teammate_r|teammate_n)\b",      "личный аккаунт"),
    ("mailbox",         r"[A-Za-z0-9._%+-]+@(?:gmail|platinum)[A-Za-z0-9.-]*\.[a-z]{2,}", "почтовый ящик"),
    # ⚠️ НЕ блокируем слово "Tailscale": это публичный продукт, и обсуждать его в DR-отчётах
    # не утечка. Секрет = НАШ адрес в нём (100.x.x.x ловится ip-правилом) и наш tailnet-хост.
    # Широкое правило дало 18 ложняков на живой книге 2026-07-27 -> вечно-красный гейт,
    # который перестают читать. Гейт ловит идентификаторы, не темы.
    ("tailnet-host",    r"(?i)\b[a-z0-9-]+\.ts\.net\b",            "адрес частной сети"),
    ("device-id",       r"\b[A-Z0-9]{7}-[A-Z0-9]{7}-[A-Z0-9]{7}[A-Z0-9-]*", "<device-id>"),
    ("tg-chat-id",      r"-100\d{6,}|(?<![\d.])-\d{9,}\b",         "<chat-id>"),
    # Положительный user-id идёт без минуса, поэтому правилом выше не ловился и уехал в
    # публичный артефакт («своя сессия @… id 7303193973», найдено глазами 2026-07-27).
    # Голое 10-значное число ловить нельзя (ложняки), поэтому якорим по слову-контексту.
    ("tg-user-id",      r"(?i)\b(?:user_?id|chat_?id|peer_?id|id)[\s:=]+\d{8,}", "id <tg-id>"),
    ("bot-handle",      r"@[A-Za-z0-9_]{2,}_?bot\b",               "служебный бот"),
    ("our-domain",      r"\b(?:[a-z0-9-]+\.)*palo-alto\.ai\b",     "наш сайт"),
    ("infra-domain",    r"\b(?:[a-z0-9-]+\.)*star-alliance\.io\b", "наш сервис"),
    ("hoster-acct",     r"btcnext[a-z]*|\b1685279\b",              "аккаунт хостера"),
    ("api-key-name",    r"N8N_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY", "<key-var>"),
    # Только реальный ПУТЬ к стору (backslash или файл с расширением), а не слово "secrets"
    # в перечислении папок: "skills/secrets/engines" — это не утечка (ложняк 2026-07-27).
    ("secrets-path",    r"secrets\\[A-Za-z0-9_.-]+|secrets/[A-Za-z0-9_-]+\.(?:env|json|md|txt)", "локальный секрет-стор"),
]
MACHINE_COMPILED = [(k, re.compile(p), r) for k, p, r in MACHINE_RULES]

# IPv4 needs a value check: "2026.07.26.1" is a version, not an address.
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
IP_ALLOW = {"0.0.0.0", "127.0.0.1", "255.255.255.255", "8.8.8.8", "1.2.3.4"}
# IPv6: наш VPS отвечает и по нему, а правило было только под v4 (нашёл внешний ревьюер
# Codex 2026-07-27 — «попробуй [2001:db8::1]»; проверено: не ловилось). Требуем 2+ групп
# и хотя бы одно "::" или 4+ групп, чтобы не ловить обычный текст с двоеточиями.
# Кандидаты ловим широко, а РЕШАЕТ стандартный парсер адресов — regex-гадание про IPv6
# ломалось на "[2001:db8::1]" и молча пропускало адрес (Codex T3, 2026-07-27).
IPV6 = re.compile(r"(?<![\w:])[0-9A-Fa-f:]{4,45}(?![\w])")
IPV6_ALLOW = {"::1", "::"}


def _is_ipv6(s):
    import ipaddress
    if ":" not in s or s.count(":") < 2:
        return False
    try:
        return isinstance(ipaddress.ip_address(s.strip("[]")), ipaddress.IPv6Address)
    except ValueError:
        return False

EXT = {".md", ".py", ".json", ".txt", ".yml", ".yaml"}
NORM = re.compile(r"[\s\-\.\(\) ]+")


def _real_ip(m):
    return all(int(g) <= 255 for g in m.groups()) and m.group(0) not in IP_ALLOW


def scan_text(text, profile="freeschool"):
    """-> (fails, infos); each item = (tag, fragment, lineno). Empty fails = clean."""
    words = IDENTIFIER_WORDS if profile == "book" else SECRET_WORDS
    fails, infos = [], []

    def add(tag, frag, n, matched):
        """Авторизованный публичный токен -> INFO, не FAIL. Проверка ОБЩАЯ для всех правил:
        раньше она жила только в словарной ветке, поэтому публичный контакт Антона в
        START-HERE.md всё равно валил гейт (поймано 2026-07-27)."""
        if any(a in matched.lower() for a in ALLOW_WORDS):
            infos.append(("allowed:" + matched[:40], frag, n))
        else:
            fails.append((tag, frag, n))

    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        norm = NORM.sub("", line)
        for num in ALLOW_NUMBERS:
            if num in norm:
                infos.append(("allowed-number:" + num, line.strip()[:80], n))
        for num in SECRET_NUMBERS:
            if num in norm:
                add("number:" + num, line.strip()[:80], n, num)
        for w in words:
            if w in low and not any(a in low for a in ALLOW_WORDS):
                add("word:" + w, line.strip()[:80], n, w)
        rx_set = SECRET_REGEX if profile == "book" else SECRET_REGEX + FREESCHOOL_ONLY_REGEX
        for rx in rx_set:
            m = rx.search(line)
            if m:
                add("regex:" + m.group(0)[:30], line.strip()[:80], n, m.group(0))
        for kind, rx, _ in MACHINE_COMPILED:
            m = rx.search(line)
            if m:
                add("%s:%s" % (kind, m.group(0)[:30]), line.strip()[:80], n, m.group(0))
        for m in IPV4.finditer(line):
            if _real_ip(m):
                add("ip:" + m.group(0), line.strip()[:80], n, m.group(0))
        for m in IPV6.finditer(line):
            if _is_ipv6(m.group(0)) and m.group(0) not in IPV6_ALLOW:
                add("ipv6:" + m.group(0), line.strip()[:80], n, m.group(0))
    return fails, infos


def scrub(text):
    """Replace machine identifiers with their ROLE. Person names are never touched.
    Use before writing any public projection; then re-scan (scrub is not a substitute
    for the gate - it is what makes the gate passable without losing the story)."""
    def _keep(m):
        return any(a in m.group(0).lower() for a in ALLOW_WORDS)
    for _, rx, repl in MACHINE_COMPILED:
        text = rx.sub(lambda m: m.group(0) if _keep(m) else repl, text)
    text = IPV6.sub(lambda m: "адрес узла" if _is_ipv6(m.group(0))
                    and m.group(0) not in IPV6_ALLOW else m.group(0), text)
    return IPV4.sub(lambda m: "адрес узла" if _real_ip(m) and not _keep(m) else m.group(0), text)


def scan_file(path, profile="freeschool"):
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return [("READ-ERROR", str(e), 0)], []
    return scan_text(text, profile)


def _self_test():
    """The gate must catch what actually leaked on 2026-07-27 and stay quiet on safe text."""
    must_catch = ["ssh 167.233.122.145", "узел 100.122.143.5", "host ANCHOR1",
                  "@fleet_wake_bot пингует", "хост HUB1", "чат -1008317706981",
                  "ssh ANCHOR1.tail1234.ts.net", "ключ sk-abcdefghijklmnopqrst",
                  "ssh [2001:db8::1] порт 22",        # IPv6 — дыру нашёл Codex T3 2026-07-27
                  "своя сессия id 7303193973"]        # положительный tg user-id
    # Tailscale/Syncthing как ПРОДУКТЫ обсуждать можно: гейт ловит идентификаторы, не темы.
    must_pass_book = ["версия 2026.07.26.1", "счёт 15/15 ссылок", "Нина решила сама",
                      "Дмитрий Глеб ответил", "loopback 127.0.0.1", "5 из 5 за 48 секунд",
                      "поставили Tailscale на все машины", "Syncthing держит один волт"]
    bad = 0
    for s in must_catch:
        f, _ = scan_text(s, "book")
        if not f:
            print("  MISS:", s); bad += 1
    for s in must_pass_book:
        f, _ = scan_text(s, "book")
        if f:
            print("  FALSE POSITIVE (book):", s, f[0][0]); bad += 1
    # freeschool profile must still block person names (backwards compatibility)
    if not scan_text("Нина решила сама", "freeschool")[0]:
        print("  REGRESSION: freeschool stopped blocking person names"); bad += 1
    sample = "хост HUB1 по адресу 167.233.122.145 пингует @fleet_wake_bot"
    scrubbed = scrub(sample)
    if scan_text(scrubbed, "book")[0]:
        print("  SCRUB LEFT A HIT:", scrubbed); bad += 1
    print("  scrub sample -> %s" % scrubbed)
    print("SELF-TEST: %s (%d problems)" % ("PASS" if not bad else "FAIL", bad))
    return 1 if bad else 0


def main(argv):
    args = list(argv[1:])
    profile = "freeschool"
    if "--profile" in args:
        i = args.index("--profile")
        profile = args[i + 1] if i + 1 < len(args) else "freeschool"
        del args[i:i + 2]
    if "--self-test" in args:
        return _self_test()
    if "--stdin" in args:
        data = io.open(sys.stdin.fileno(), encoding="utf-8", errors="replace").read()
        if "--diff" in args:
            # Unified diff: судим ТОЛЬКО добавляемые строки. Без этого гейт ловит сам себя
            # на удалении утечки и блокирует её же зачистку (поймано 2026-07-27).
            # И помни: diff-скан слеп к тому, что уже лежит в файле, — он ДОПОЛНЕНИЕ
            # к скану артефактов (`leak_scan.py <dir>`), а не замена ему.
            data = "\n".join(ln[1:] for ln in data.splitlines()
                             if ln.startswith("+") and not ln.startswith("+++"))
        fails, infos = scan_text(data, profile)
        for tag, frag, ln in fails:
            print("FAIL <stdin>:%d  [%s]  %s" % (ln, tag, frag))
        print("--- leak_scan[%s]: stdin FAIL=%d -> %s"
              % (profile, len(fails), "BLOCKED" if fails else "CLEAN"))
        return 1 if fails else 0
    if not args:
        print(__doc__); return 2
    total_fail, total_info, files = 0, 0, 0
    for root_arg in args:
        if not os.path.exists(root_arg):
            print("ERR path not found: %s" % root_arg); return 2
        targets = []
        if os.path.isfile(root_arg):
            targets = [root_arg]
        else:
            for root, dirs, names in os.walk(root_arg):
                dirs[:] = [d for d in dirs if d not in (".git", ".stversions", ".stfolder", "__pycache__")]
                targets += [os.path.join(root, n) for n in names
                            if os.path.splitext(n)[1].lower() in EXT]
        for p in targets:
            files += 1
            fails, infos = scan_file(p, profile)
            for tag, frag, ln in fails:
                print("FAIL %s:%d  [%s]  %s" % (p, ln, tag, frag))
                total_fail += 1
            for tag, frag, ln in infos:
                print("INFO %s:%d  [%s]" % (p, ln, tag))
                total_info += 1
    print("--- leak_scan[%s]: files=%d FAIL=%d INFO=%d -> %s"
          % (profile, files, total_fail, total_info, "BLOCKED" if total_fail else "CLEAN"))
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
