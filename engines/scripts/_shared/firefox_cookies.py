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
firefox_cookies.py  --  Флотовый хелпер: извлечение session-куки из Firefox.

ЗАЧЕМ: Chrome 127+/Edge шифруют куки App-Bound Encryption (ABE) — внешний процесс
не может их прочитать. Chrome 146 (апр-2026) добавил DBSC: сессии, созданные В CHROME
на Windows, привязаны к TPM и extract-нутые куки сервер отклонит. Firefox НЕ делает ни
ABE, ни DBSC → его сессии не device-bound, куки лежат в открытой cookies.sqlite и
извлекаются тривиально. Поэтому Firefox = наш "браузер-робот" для API-клиентов
(notebooklm-py, fb-*, x-post, telegram-web). Канон: DR26-07-16-HUB-01,
02-Decisions/decision-2026-07-16-browser-automation-layer.md.

AK-47: одна функция read_cookies() + CLI. Никаких зависимостей кроме stdlib.
Безопасность: копируем БД перед чтением (обход lock + WAL/SHM), значения куки
(секрет) в stdout по умолчанию НЕ печатаем (только --export пишет их в файл).
"""
import argparse
import configparser
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Firefox sameSite (int) -> Playwright/Chromium строка
_SAMESITE = {0: "None", 1: "Lax", 2: "Strict"}


def firefox_root() -> Path:
    """Корень профилей Firefox (Windows / macOS / Linux)."""
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "Mozilla" / "Firefox"
    home = Path.home()
    mac = home / "Library" / "Application Support" / "Firefox"
    return mac if mac.exists() else (home / ".mozilla" / "firefox")


def find_profile(name: str | None = None) -> Path:
    """
    Путь к профилю Firefox.
    name=None  -> дефолтный (Default=1 / default-release из profiles.ini)
    name="..." -> по имени секции Name= или по имени папки.
    Можно также передать в name абсолютный путь к папке профиля.
    """
    if name and Path(name).is_dir():
        return Path(name)
    root = firefox_root()
    ini = root / "profiles.ini"
    if not ini.exists():
        raise FileNotFoundError(f"profiles.ini не найден: {ini}")
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    profiles = []  # (Name, Path, IsRelative, LegacyDefault)
    for sec in cp.sections():
        if not sec.startswith("Profile"):
            continue
        g = cp[sec]
        profiles.append((
            g.get("Name", ""),
            g.get("Path", ""),
            g.getboolean("IsRelative", fallback=True),
            g.get("Default", "0") == "1",
        ))
    if not profiles:
        raise RuntimeError("В profiles.ini нет ни одного профиля")

    def resolve(pth: str, rel: bool) -> Path:
        return (root / pth) if rel else Path(pth)

    def has_cookies(p: Path) -> bool:
        return (p / "cookies.sqlite").exists()

    if name:
        for nm, pth, rel, _ in profiles:
            if nm == name or Path(pth).name == name or pth == name:
                return resolve(pth, rel)
        raise KeyError(f"Профиль '{name}' не найден. Есть: {[p[0] for p in profiles]}")

    # Порядок детекта (грабля: [Install*] Default= = профиль, который Firefox РЕАЛЬНО
    # запускает; он важнее legacy [ProfileN] Default=1, который может висеть на пустом
    # неиспользуемом профиле без cookies.sqlite):
    candidates = []
    # 1) install-default (Default=<path> в секции [Install...])
    for sec in cp.sections():
        if sec.startswith("Install"):
            d = cp[sec].get("Default", "")
            if d:
                candidates.append(resolve(d, True))
    # 2) legacy Default=1
    candidates += [resolve(p, r) for nm, p, r, dflt in profiles if dflt]
    # 3) *.default-release
    candidates += [resolve(p, r) for nm, p, r, _ in profiles if p.endswith("default-release")]
    # 4) любой профиль с cookies.sqlite
    candidates += [resolve(p, r) for nm, p, r, _ in profiles]

    for c in candidates:
        if has_cookies(c):
            return c
    # ничего с куками не нашли — вернём первого кандидата (пусть read_cookies даст явную ошибку)
    return candidates[0] if candidates else resolve(profiles[0][1], profiles[0][2])


def read_cookies(profile: Path, domain: str | None = None) -> list[dict]:
    """
    Читает куки из cookies.sqlite профиля. Копирует БД (+ -wal/-shm) в temp,
    чтобы обойти блокировку живого Firefox и WAL-неполноту. Возвращает список
    dict в формате, совместимом с Playwright storage_state cookies.
    """
    src = Path(profile) / "cookies.sqlite"
    if not src.exists():
        raise FileNotFoundError(f"нет cookies.sqlite: {src}")
    tmpdir = Path(tempfile.mkdtemp(prefix="ffcookies_"))
    try:
        dst = tmpdir / "cookies.sqlite"
        shutil.copy2(src, dst)
        for ext in ("-wal", "-shm"):
            s = src.with_name(src.name + ext)
            if s.exists():
                shutil.copy2(s, tmpdir / (dst.name + ext))
        con = sqlite3.connect(f"file:{dst.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        q = ("SELECT host, path, name, value, expiry, isSecure, isHttpOnly, sameSite "
             "FROM moz_cookies")
        params = ()
        if domain:
            q += " WHERE host LIKE ?"
            params = (f"%{domain}%",)
        rows = con.execute(q, params).fetchall()
        con.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    out = []
    for r in rows:
        host = r["host"]
        out.append({
            "name": r["name"],
            "value": r["value"],
            "domain": host,
            "path": r["path"] or "/",
            "expires": float(r["expiry"]) if r["expiry"] else -1,
            "httpOnly": bool(r["isHttpOnly"]),
            "secure": bool(r["isSecure"]),
            "sameSite": _SAMESITE.get(r["sameSite"], "Lax"),
        })
    return out


def to_storage_state(cookies: list[dict]) -> dict:
    """Обёртка в Playwright storage_state (cookies + пустой origins)."""
    return {"cookies": cookies, "origins": []}


def _cli():
    ap = argparse.ArgumentParser(description="Извлечение куки из Firefox (fleet helper).")
    ap.add_argument("--profile", help="имя профиля (Name=) / папка / абс.путь; по умолчанию дефолтный")
    ap.add_argument("--domain", help="фильтр по подстроке хоста, напр. google.com")
    ap.add_argument("--count", action="store_true", help="только СЧЁТЧИКИ и ИМЕНА (без значений — безопасно)")
    ap.add_argument("--export", metavar="PATH", help="записать storage_state JSON (со значениями!) в файл-секрет")
    args = ap.parse_args()

    prof = find_profile(args.profile)
    cookies = read_cookies(prof, args.domain)
    print(f"profile: {prof}", file=sys.stderr)
    print(f"cookies: {len(cookies)}" + (f" (domain~{args.domain})" if args.domain else ""), file=sys.stderr)

    if args.export:
        import json
        p = Path(args.export)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(to_storage_state(cookies), ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        print(f"WROTE storage_state -> {p} (это СЕКРЕТ, храни в secrets\\)", file=sys.stderr)
        return
    # безопасный дефолт: имена+хосты, без значений
    seen = {}
    for c in cookies:
        seen.setdefault(c["name"], set()).add(c["domain"])
    for nm in sorted(seen):
        print(f"  {nm}: {len(seen[nm])} host(s)")
    print(f"[{len(cookies)} cookies, {len(seen)} distinct names — значения скрыты; --export пишет их в файл]", file=sys.stderr)


if __name__ == "__main__":
    _cli()
