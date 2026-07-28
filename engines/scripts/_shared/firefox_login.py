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
firefox_login.py -- Флотовый launcher выделенного Firefox-профиля автоматизации
(Playwright persistent context). Модель "живём в браузере": один раз логинишься
руками (2FA/капчу проходит человек), дальше профиль на диске живёт и переиспользуется
без релогина, пока сессия не протухнет.

Профили лежат в D:\AutomationBrowsers\Firefox\<service> (Windows-хаб). Это ИЗОЛИРОВАННЫЙ
от повседневного Firefox Антона профиль — не смешиваем.

⚠️ НЕ для fb-post/x-post/fb-reply: те УЖЕ используют живую залогиненную вкладку Chrome
через Claude-in-Chrome MCP — осознанный anti-ban выбор (действуем как человек в реальном
сеансе Антона), не headless-автоматизацию. Playwright Firefox дал бы МЕНЬШЕ защиты от
бана, не больше. Этот launcher — для сервисов БЕЗ live-tab опции: будущий headless API-клиент
или сайт, куда Chrome-MCP не дотягивается (напр. telegram-web без нативного MCP).

⚠️ ЗНАЙ (проверено 2026-07-16, хаб HUB1): Playwright-Firefox на ХАБЕ сейчас
НЕ запускается — `spawn UNKNOWN` / SxS «mozglue v1.0.0.0 could not be found» (ОС-уровень,
не битый файл; чистая перекачка 116MB не лечит). Это НЕ мешает firefox_cookies.py (тот
только читает cookies.sqlite с диска, Playwright не стартует). Если этот launcher нужен на
хабе — сперва починить SxS ОС (sfc/DISM/endpoint-policy, админ). На других узлах проверить
запуск отдельно. Канон: decision-2026-07-16-browser-automation-layer.md § A/B-эксперимент.

Канон: DR26-07-16-HUB-01, 02-Decisions/decision-2026-07-16-browser-automation-layer.md.
Пара к firefox_cookies.py (тот читает СИСТЕМНЫЙ Firefox-профиль; этот заводит ОТДЕЛЬНЫЙ).

Использование:
  python firefox_login.py --profile google-main --url https://accounts.google.com/   # первичный логин (headed)
  python firefox_login.py --profile google-main --url https://notebooklm.google.com/ --headless   # рабочий заход
  python firefox_login.py --profile google-main --export-state E:\...\secrets\google-main.state.json
"""
import argparse
import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("AUTOMATION_BROWSERS", r"D:\AutomationBrowsers")) / "Firefox"


def profile_dir(name: str) -> Path:
    p = Path(name)
    if p.is_absolute():
        return p
    return DEFAULT_ROOT / name


def main():
    ap = argparse.ArgumentParser(description="Firefox persistent-context launcher (fleet).")
    ap.add_argument("--profile", required=True, help="имя профиля (папка в D:\\AutomationBrowsers\\Firefox) или абс.путь")
    ap.add_argument("--url", default="about:blank", help="куда открыть")
    ap.add_argument("--headless", action="store_true", help="без окна (рабочий заход; для логина НЕ ставить)")
    ap.add_argument("--wait", action="store_true", help="ждать Enter (первичный ручной логин)")
    ap.add_argument("--export-state", metavar="PATH", help="сохранить storage_state JSON (секрет!) после захода")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright не установлен: pip install playwright && playwright install firefox")

    pdir = profile_dir(args.profile)
    pdir.mkdir(parents=True, exist_ok=True)
    print(f"profile dir: {pdir}", file=sys.stderr)

    with sync_playwright() as p:
        ctx = p.firefox.launch_persistent_context(user_data_dir=str(pdir), headless=args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(args.url)
        print(f"opened: {args.url}", file=sys.stderr)
        if args.wait or (not args.headless and args.url != "about:blank"):
            try:
                input(">>> Залогинься/проверь в окне, потом Enter для сохранения и выхода... ")
            except EOFError:
                pass
        if args.export_state:
            sp = Path(args.export_state)
            sp.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(sp))
            try:
                os.chmod(sp, 0o600)
            except Exception:
                pass
            print(f"WROTE storage_state -> {sp} (СЕКРЕТ, храни в secrets\\)", file=sys.stderr)
        ctx.close()


if __name__ == "__main__":
    main()
