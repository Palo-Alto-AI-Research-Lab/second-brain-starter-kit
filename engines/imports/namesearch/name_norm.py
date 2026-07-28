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
name_norm.py — общий «мозг» умного поиска имён/слов для волта Антона.

Лечит ТРИ болезни написания одного имени:
  1) транслит      Vlad / Viktor / виктор
  2) не та раскладка   dbrnjh  == «виктор», набранное в EN-раскладке
  3) опечатки      висктор / dbcrjhr   (ловится нечётким сравнением)

Идея: любое имя приводим к набору «фонетических отпечатков» (latin).
Все Викторы получают отпечаток "viktor" -> находятся вместе.
Только stdlib. Открой файл и почини молотком — таблицы прямо тут.
"""

# --- 1. Раскладка: английская буква -> русская (ЙЦУКЕН), нижний регистр ---
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
EN2RU = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
    'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
    'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о',
    'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
    'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь',
    ',': 'б', '.': 'ю',
}
RU2EN = {v: k for k, v in EN2RU.items()}

# --- 2. Транслит: русская буква -> латиница ---
RU2LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}

CYR = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
LAT = set('abcdefghijklmnopqrstuvwxyz')


def _has_cyr(s):
    return any(ch in CYR for ch in s)


def en_layout_to_ru(s):
    """'dbrnjh' -> 'виктор' (как будто набрали по-русски в EN-раскладке)."""
    return ''.join(EN2RU.get(ch, ch) for ch in s.lower())


def ru_layout_to_en(s):
    """'мшлещк' -> 'viktor' (русские буквы, набранные в RU-раскладке вместо EN)."""
    return ''.join(RU2EN.get(ch, ch) for ch in s.lower())


def translit(s):
    """Кириллица -> латиница. Латиница остаётся как есть."""
    return ''.join(RU2LAT.get(ch, ch) for ch in s.lower())


def _phonetic(latin):
    """Латинская строка -> грубый фонетический ключ (Vlad и Viktor сходятся)."""
    s = latin.lower()
    for a, b in (('ph', 'f'), ('sch', 's'), ('sh', 's'), ('ch', 'c'),
                 ('zh', 'z'), ('kh', 'h'), ('ya', 'a'), ('yu', 'u'),
                 ('ye', 'e'), ('ck', 'k')):
        s = s.replace(a, b)
    trans = {'c': 'k', 'q': 'k', 'x': 'k', 'w': 'v', 'y': 'i', 'j': 'i'}
    s = ''.join(trans.get(ch, ch) for ch in s)
    s = s.replace('h', '')                      # немое h
    s = ''.join(ch for ch in s if ch in LAT)    # только буквы
    out = []                                     # схлопнуть дубли подряд
    for ch in s:
        if not out or out[-1] != ch:
            out.append(ch)
    return ''.join(out)


def keys(name):
    """
    Имя (в любом написании) -> множество фонетических ключей.
    Берём само имя + его «раскладочную» расшифровку, оба транслитерируем.
    """
    name = (name or '').strip()
    if not name:
        return set()
    forms = set()
    base = name.lstrip('@')
    forms.add(base)
    if _has_cyr(base):
        forms.add(translit(base))
    else:
        # чисто латиница: вдруг это кириллица в EN-раскладке (dbrnjh)
        cyr = en_layout_to_ru(base)
        if _has_cyr(cyr):
            forms.add(translit(cyr))
    out = set()
    for f in forms:
        k = _phonetic(translit(f))
        if len(k) >= 2:
            out.add(k)
    return out


def tokens(name):
    """Разбить имя на слова (имя + фамилия + ник) для пословного индекса."""
    import re
    name = (name or '').replace('@', ' ')
    parts = re.split(r'[\s\-_.,/|()]+', name)
    return [p for p in parts if p]


def lev(a, b):
    """Расстояние Левенштейна (сколько правок), на чистом stdlib."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def fuzzy_thr(k):
    """Сколько опечаток прощаем ключу длины len(k). Короткие — строже."""
    n = len(k)
    if n < 4:
        return 0
    if n < 7:
        return 1
    return 2


if __name__ == '__main__':
    # быстрый самотест: всё про Виктора должно дать один ключ
    import sys
    samples = ['виктор', 'Vlad', 'Viktor', 'dbrnjh', 'ВИКТОР', '@lead_vk']
    for s in samples:
        print(f'{s:14} -> {sorted(keys(s))}')
    # опечатки — через нечёткое сравнение к "viktor"
    for s in ['висктор', 'viktr', 'vicktor']:
        kk = sorted(keys(s))
        d = min((lev(k, 'viktor') for k in kk), default=99)
        print(f'{s:14} -> {kk}  dist→viktor={d}')
