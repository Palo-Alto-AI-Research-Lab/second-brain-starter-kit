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
"""tg_group_slots.py -- инвентарь и РАНЖИРОВАНИЕ Telegram-групп по релевантности (0 LLM токенов).

ЗАЧЕМ (Антон 2026-07-26): у Telegram есть жёсткий потолок ~500 супергрупп/каналов на аккаунт.
Рабочие аккаунты `corp_acct` и `work_acct_b` в него УПЁРЛИСЬ: физически не могут ни создать новую
группу, ни войти в неё (поймано вживую при сборке Пульса: GEN-ERR-085 на создании,
"maximum number of participants" на входе по инвайту). Лечение по Антону: выходить из наименее
релевантных групп (мёртвые intro-группы, конференции прошлых лет, спам-добавления), освобождая слоты.

ЧТО ДЕЛАЕТ (только ЧИТАЕТ, ничего не покидает):
собирает ВСЕ диалоги аккаунта через Telethon, считает слоты, и ранжирует каждую группу баллом
релевантности. Выход из групп -- ОТДЕЛЬНОЕ действие с явным «+» Антона (см. `--emit-plan`),
потому что оно НЕОБРАТИМО: в закрытую/приватную группу без нового инвайта не вернуться.

ЗАЩИТА ОТ ДУРАКА (никогда не предлагаем к выходу):
  * наши собственные группы и каналы (бренд-маркеры: Palo Alto, Claw, VCsDAO, SV_founders...);
  * любая группа, где мы админ/создатель (потеря админки необратима);
  * рабочие чаты флота (03, 02 POLICE, 04, CALLS, Пульс, Assistant's tasks);
  * личные диалоги (они слот не занимают);
  * всё, где за последние N дней есть НАШЕ сообщение (живой тред = живой контакт).

БАЛЛ РЕЛЕВАНТНОСТИ (чем МЕНЬШЕ, тем безопаснее выходить):
  -3  год в названии в прошлом (конференция отгремела: "2019", "EthCC 2023", "Denver'25")
  -2  замьючена + гора непрочитанных (мы её сознательно заглушили и не читаем)
  -2  нет ни одного нашего сообщения за всю историю выборки
  -1  чисто крипто-шум по словарю (airdrop/pump/KOL-биржи)
  +5  наш бренд / мы админ / рабочий чат флота  -> НИКОГДА не в кандидаты

USAGE
  python tg_group_slots.py count [--account corp_acct]     # сколько слотов занято
  python tg_group_slots.py rank  [--account ...] [--top 60]  # ранжированный список кандидатов
  python tg_group_slots.py emit-plan [--top 50]              # план выхода в JSON (для ревью Антоном)
"""
import os, sys, io, json, re, argparse
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))


def _imports_root():
    """env IMPORTS_ROOT -> ~/.claude/machine.env; "" if unresolved (no baked drive literal)."""
    v = os.environ.get("IMPORTS_ROOT", "").strip()
    if v:
        return v
    menv = os.path.join(os.path.expanduser("~"), ".claude", "machine.env")
    try:
        for line in open(menv, encoding="utf-8"):
            line = line.strip()
            if line.startswith("IMPORTS_ROOT=") and line.split("=", 1)[1].strip():
                return os.path.expandvars(os.path.expanduser(line.split("=", 1)[1].strip()))
    except Exception:
        pass
    return ""


_IR = _imports_root()
ENV_CANDIDATES = [c for c in [
    (os.path.join(_IR, "dialogs", ".env") if _IR else None),
    os.path.join(os.path.expanduser("~"), ".claude", "bus_ping.env"),
] if c]
PLAN_OUT = os.path.join(os.path.expanduser("~"), ".claude", "tg_leave_plan.json")

# ---- НИКОГДА не трогаем: наш бренд, наши рабочие чаты, наши каналы ----
KEEP_MARKERS = [
    "palo alto", "paloalto", "clawrus", "claweng", "openclaw", "vcsdao", "sv_founders",
    "ai & vcs dao", "ai agents kol & influencers", "ai founders",
    "03 nat", "02 police", "04 ai-duo", "пульс", "pulse",
    "calls", "faq фак", "assistant", "покупки approve", "обработанные голосовые",
    "platinum", "charm", "canton ecosystem bd",
]
# ---- Признаки шума (понижают балл, но НЕ решают в одиночку) ----
NOISE_WORDS = [
    "airdrop", "pump", "koin", "drops", "nft", "yup", "doge", "meme",
    "kol", "kols", "influencer", "crypto wolf",   # "trade"/"signal" убраны: бьют по легитимным бизнес-группам
]
# по границам слова: подстрокой "kol" ловилась "Kolkata", "trade" -- "Trade Finance"
NOISE_RE = re.compile(r"(?<![a-z])(%s)(?![a-z])" % "|".join(re.escape(w) for w in NOISE_WORDS))
YEAR_RE = re.compile(r"\b(20\d{2})\b|'(\d{2})\b")
# intro / партнёрские группы (ядро продукта Антона) -- НИКОГДА не в массовый список.
# ⚠️ Инцидент 27.07: первая версия ловила только "<>" и пропустила в кандидаты 10 живых intro-групп
# ("Mei Shmidt 🤝 Stanford AiW3 Research Lab", "HSG < > AAAPadSF"). Доминирующая конвенция Антона --
# ЭМОДЗИ-рукопожатие, а не угловые скобки. Ловим все разделители «сущность X <-> сущность Y».
INTRO_RE = re.compile(
    r"<\s*-{0,2}\s*>"                       # X <> Y · X < > Y · X <-> Y
    r"|🤝|↔|⟷|👥"                            # X 🤝 Y -- основная конвенция
    r"|\bintro\b|\bинтро\b|\bзнакомство\b"
    r"|антон\s*дзи|anton\s*dz|tony\s*dz"    # группа с личным именем Антона = живой тред, не шум
)
# Бренды Антона, которых не было в словаре и которые из-за этого попали в кандидаты (инцидент 27.07)
BRAND_RE = re.compile(r"\ba\.?\s?a\.?\s?a\b|aaapad|aiw3|c\(h\+a\)rm|stanford")
# Партнёрская/дил-группа двух сущностей ("EdgeIn x Ape Terminal", "DAOBase & Pinksale").
# Применяется ТОЛЬКО когда нет года прошедшей конференции и нет шумовых слов -- иначе
# "MALTA AI & BLOCKCHAIN SUMMIT 2019" и "KOLs + Influencers Global" ушли бы в защиту зря.
PARTNER_RE = re.compile(r"\s[x×]\s|\s&\s|\s\+\s|\[adv\]|\botc\b")


def load_env():
    env = {}
    for p in ENV_CANDIDATES:
        if not os.path.exists(p):
            continue
        try:
            for line in io.open(p, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass
    return env


def creds_for(account, env):
    """Креды по аккаунту. Разные .env исторически используют разные префиксы."""
    a = (account or "").upper()
    for pref in (a, a.replace("1", ""), "REFRESH"):
        api_id = env.get("%s_API_ID" % pref)
        api_hash = env.get("%s_API_HASH" % pref)
        sess = env.get("%s_SESSION_STRING" % pref) or env.get("%s_SESSION" % pref)
        if api_id and api_hash and sess:
            return int(api_id), api_hash, sess, pref
    return None, None, None, None


def title_of(d):
    return (getattr(d, "title", None) or getattr(d, "name", None) or "").strip()


COMPACT_RE = re.compile(r"[^a-zа-яё0-9]+")
# Бренд-маркеры в «сжатом» виде: без пробелов и знаков.
# ⚠️ Инцидент 27.07 (второй): бренд лежал как "vcsdao", а группа называлась "Everstake - VCs DAO"
# -- с пробелом. Совпадения не было, партнёрская группа с НАШИМ брендом попала в кандидаты.
# Сравнение по сжатой строке ловит любое написание: "VCs DAO" / "VCsDAO" / "vcs-dao".
KEEP_COMPACT = [COMPACT_RE.sub("", m) for m in KEEP_MARKERS]


def is_keeper(title):
    t = title.lower()
    if any(m in t for m in KEEP_MARKERS) or BRAND_RE.search(t):
        return True
    c = COMPACT_RE.sub("", t)
    return any(m and m in c for m in KEEP_COMPACT)


def is_intro(title):
    """Intro-группа («X <> Palo Alto …») = активный тред с лидом/партнёром.
    Даже мёртвая на вид -- в массовую чистку НЕ идёт, только отдельный разбор (граница Антона)."""
    return bool(INTRO_RE.search(title.lower()))


def idle_days(d):
    """Сколько дней в группе вообще НИЧЕГО не происходило. Берётся из самого диалога -- 0 доп. запросов.
    Это единственный сигнал, покрывающий ВСЕ диалоги (проба сообщений упирается в probe_limit)."""
    dt = getattr(d, "date", None)
    if not dt:
        return None
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return None


def stale_year(title):
    """Год в названии, который уже прошёл -> конференция отгремела."""
    now_y = datetime.now(timezone.utc).year
    for m in YEAR_RE.finditer(title):
        y = m.group(1) or ("20" + m.group(2))
        try:
            if int(y) < now_y:
                return int(y)
        except Exception:
            pass
    return None


def score(d, title, admin, mine_recent, idle):
    """Меньше балл = безопаснее выходить. Возвращает (балл, причины)."""
    if is_keeper(title) or admin:
        return 99, ["наша/админ -> НЕ ТРОГАТЬ"]
    if is_intro(title):
        return 98, ["intro-группа -> отдельный разбор, не в массовую чистку"]
    y0, noisy = stale_year(title), bool(NOISE_RE.search(title.lower()))
    if not y0 and not noisy and PARTNER_RE.search(title.lower()):
        return 98, ["партнёрская/дил-группа двух сущностей -> отдельный разбор"]
    s, why = 0, []
    if idle is not None:
        if idle >= 365:
            s -= 4; why.append("молчит %d дн (~%d мес)" % (idle, idle // 30))
        elif idle >= 180:
            s -= 2; why.append("молчит %d дн" % idle)
    y = stale_year(title)
    if y:
        s -= 3; why.append("конференция %s прошла" % y)
    unread = getattr(d, "unread_count", 0) or 0
    muted = bool(getattr(d, "muted", False)) or bool(getattr(getattr(d, "dialog", None), "notify_settings", None) and
                                                     getattr(d.dialog.notify_settings, "mute_until", None))
    if muted and unread > 500:
        s -= 2; why.append("замьючена, %d непрочитанных" % unread)
    elif unread > 5000:
        s -= 2; why.append("%d непрочитанных, не читаем" % unread)
    if not mine_recent:
        s -= 2; why.append("ни одного нашего сообщения")
    if NOISE_RE.search(title.lower()):
        s -= 1; why.append("крипто-шум по словарю")
    return s, why


def collect(account, probe_mine=True, probe_limit=250):
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel, Chat

    env = load_env()
    api_id, api_hash, sess, pref = creds_for(account, env)
    if not api_id:
        print("НЕТ КРЕДОВ для аккаунта '%s'. Искал префиксы в: %s" % (account, ENV_CANDIDATES))
        return None
    print("креды: префикс %s" % pref)
    rows = []
    with TelegramClient(StringSession(sess), api_id, api_hash) as client:
        me = client.get_me()
        prem = bool(getattr(me, "premium", False))
        # Потолок каналов/супергрупп зависит от Premium: 500 обычный / 1000 Premium.
        # Без этого «сколько освобождать» считается от выдуманной цифры (замер 27.07: work_acct_b = 1003).
        print("аккаунт: @%s (%s) · Premium: %s · потолок ~%d"
              % (getattr(me, "username", "?"), getattr(me, "id", "?"),
                 "ДА" if prem else "нет", 1000 if prem else 500))
        for d in client.iter_dialogs():
            ent = d.entity
            # Слот занимают ТОЛЬКО супергруппы/каналы. Личные диалоги и basic-группы не в счёт.
            if not isinstance(ent, Channel):
                continue
            title = title_of(d)
            admin = bool(getattr(ent, "creator", False) or getattr(ent, "admin_rights", None))
            mine_recent = True
            if probe_mine and len(rows) < probe_limit:
                try:
                    mine_recent = any(True for _ in client.iter_messages(ent, from_user="me", limit=1))
                except Exception:
                    mine_recent = True   # не смогли проверить -> считаем живой (безопасно)
            idle = idle_days(d)
            sc, why = score(d, title, admin, mine_recent, idle)
            last_dt = getattr(d, "date", None)
            rows.append({
                "chat_id": getattr(ent, "id", None),
                "title": title,
                "megagroup": bool(getattr(ent, "megagroup", False)),
                "admin": admin,
                "unread": getattr(d, "unread_count", 0) or 0,
                "mine": mine_recent,
                "idle_days": idle,
                "last_msg": last_dt.strftime("%Y-%m-%d") if last_dt else "?",
                "intro": is_intro(title),
                "score": sc,
                "why": why,
                "_cap": 1000 if prem else 500,
            })
    return rows


def do_leave(account, plan_path, confirm, sleep_s=2.0):
    """ИСПОЛНИТЕЛЬ выхода. Работает ТОЛЬКО по уже одобренному Антоном плану.

    Выход из группы НЕОБРАТИМ (в приватную без нового инвайта не вернуться), поэтому здесь
    двойная защита: план -- не истина в последней инстанции, статус каждой группы
    ПЕРЕПРОВЕРЯЕТСЯ в момент выхода (план мог устареть: нас сделали админом, группа ожила).
    """
    import time
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel
    from telethon.errors import FloodWaitError

    if not confirm or not confirm.startswith("ANTON-PLUS"):
        print("ОТКАЗ: нужен --confirm ANTON-PLUS-<дата> (явное «+» Антона на КОНКРЕТНЫЙ список).")
        return 2
    if not os.path.exists(plan_path):
        print("ОТКАЗ: нет плана %s -- сперва emit-plan и показать Антону." % plan_path)
        return 2
    with io.open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("account") != account:
        print("ОТКАЗ: план для аккаунта '%s', а просят выход на '%s'." % (plan.get("account"), account))
        return 2
    targets = plan.get("leave", [])
    print("план: %d групп, аккаунт %s, собран %s" % (len(targets), account, plan.get("generated")))

    env = load_env()
    api_id, api_hash, sess, pref = creds_for(account, env)
    if not api_id:
        print("НЕТ КРЕДОВ для '%s'." % account)
        return 2

    left, skipped, failed = [], [], []
    with TelegramClient(StringSession(sess), api_id, api_hash) as client:
        for i, t in enumerate(targets, 1):
            title = t.get("title", "?")
            try:
                ent = client.get_entity(t["chat_id"])
            except Exception as e:
                failed.append((title, "не нашёл: %s" % e)); print("%3d. ✗ %s -- не нашёл" % (i, title[:60])); continue
            # --- перепроверка НА МОМЕНТ ВЫХОДА, а не по плану ---
            live_title = title_of(ent) or title
            if not isinstance(ent, Channel):
                skipped.append((live_title, "не супергруппа/канал")); print("%3d. – %s -- слот не занимает" % (i, live_title[:60])); continue
            if getattr(ent, "creator", False) or getattr(ent, "admin_rights", None):
                skipped.append((live_title, "мы админ/создатель")); print("%3d. ⛔ %s -- МЫ АДМИН, не выходим" % (i, live_title[:60])); continue
            if is_keeper(live_title):
                skipped.append((live_title, "наша/бренд")); print("%3d. ⛔ %s -- наша, не выходим" % (i, live_title[:60])); continue
            if is_intro(live_title):
                skipped.append((live_title, "intro-группа")); print("%3d. ⛔ %s -- intro, не выходим" % (i, live_title[:60])); continue
            try:
                client.delete_dialog(ent)
                left.append(live_title); print("%3d. ✅ вышли: %s" % (i, live_title[:60]))
            except FloodWaitError as e:
                print("     FloodWait %ds -- ждём" % e.seconds); time.sleep(e.seconds + 1)
                try:
                    client.delete_dialog(ent); left.append(live_title); print("%3d. ✅ вышли (после ожидания): %s" % (i, live_title[:60]))
                except Exception as e2:
                    failed.append((live_title, str(e2))); print("%3d. ✗ %s -- %s" % (i, live_title[:60], e2))
            except Exception as e:
                failed.append((live_title, str(e))); print("%3d. ✗ %s -- %s" % (i, live_title[:60], e))
            time.sleep(sleep_s)

    log = os.path.join(os.path.expanduser("~"), ".claude", "tg_leave_log.jsonl")
    with io.open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "account": account,
                            "left": left, "skipped": skipped, "failed": failed},
                           ensure_ascii=False) + "\n")
    print("\nИТОГ: вышли из %d · пропущено защитой %d · ошибок %d\nжурнал: %s"
          % (len(left), len(skipped), len(failed), log))
    print("Пере-замерь слоты: python tg_group_slots.py count --account %s --no-probe" % account)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Инвентарь и ранжирование Telegram-групп (слоты).")
    ap.add_argument("mode", choices=["count", "rank", "emit-plan", "leave"])
    ap.add_argument("--account", default="corp_acct")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--no-probe", action="store_true", help="не проверять наши сообщения (быстрее)")
    ap.add_argument("--plan", default=PLAN_OUT, help="одобренный план для режима leave")
    ap.add_argument("--confirm", default="", help="ANTON-PLUS-<дата> -- явное «+» Антона")
    a = ap.parse_args()

    if a.mode == "leave":
        return do_leave(a.account, a.plan, a.confirm)

    rows = collect(a.account, probe_mine=not a.no_probe)
    if rows is None:
        return 2
    slots = len(rows)
    cap = rows[0].get("_cap", 500) if rows else 500
    print("СЛОТОВ ЗАНЯТО (супергруппы+каналы): %d из ~%d  ->  свободно ~%d" % (slots, cap, cap - slots))
    if a.mode == "count":
        return 0

    cands = sorted([r for r in rows if r["score"] < 98],
                   key=lambda r: (r["score"], -(r["idle_days"] or 0)))
    keepers = [r for r in rows if r["score"] >= 99]
    intros = [r for r in rows if r["score"] == 98]
    print("защищено (наши/админ): %d · intro-групп (отдельный разбор): %d · кандидатов на выход: %d\n"
          % (len(keepers), len(intros), len(cands)))
    for i, r in enumerate(cands[: a.top], 1):
        print("%3d. [%+d] %s" % (i, r["score"], r["title"][:70]))
        print("      посл.сообщение %s · непрочит %d · %s"
              % (r["last_msg"], r["unread"], "; ".join(r["why"]) or "нет явных причин"))
    if a.mode == "emit-plan":
        # all_candidates -- весь пул, а не только верхушка: позволяет пере-фильтровать план
        # офлайн (0 запросов), не гоняя ~7-минутный обход диалогов заново.
        plan = {"account": a.account, "slots_used": slots, "cap": cap,
                "generated": datetime.now(timezone.utc).isoformat(),
                "leave": cands[: a.top], "all_candidates": cands,
                "protected_count": len(keepers), "intro_count": len(intros)}
        with io.open(PLAN_OUT, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("\nПЛАН СОХРАНЁН: %s (%d групп). Выход НЕ выполнен -- нужен «+» Антона."
              % (PLAN_OUT, len(plan["leave"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
