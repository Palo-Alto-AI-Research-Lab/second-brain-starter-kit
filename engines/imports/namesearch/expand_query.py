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
expand_query.py — расширяет ЛЮБОЕ важное слово во все написания.
Это «мост» от умного отпечатка к обычному поиску по волту и к RAG (brain_ask).

  python expand_query.py виктор
     -> виктор viktor Vlad wiktor ...          (все читаемые варианты)

  python expand_query.py dbrnjh --grep
     -> прогоняет ripgrep по волту по всем вариантам (что есть в волте)

  python expand_query.py виктор --line
     -> одной строкой, чтобы скормить в brain_ask:
        python brain_ask.py "$(python expand_query.py виктор --line)"

Зачем: эмбеддинги (RAG) НЕ понимают «dbrnjh». Поэтому сначала разворачиваем
слово в нормальные написания, а уже их ищем точным поиском / отдаём в RAG.
"""
import os, re, sys, subprocess
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_norm import en_layout_to_ru, ru_layout_to_en, translit, _has_cyr, RU2LAT

VAULT = r'%VAULT%'

# латиница -> кириллица (приблизительно, для grep по русским заметкам)
LAT2RU_MULTI = [('sch', 'щ'), ('sh', 'ш'), ('ch', 'ч'), ('zh', 'ж'),
                ('yu', 'ю'), ('ya', 'я'), ('kh', 'х'), ('ye', 'е')]
LAT2RU = {'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е', 'z': 'з',
          'i': 'и', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п',
          'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'к',
          'y': 'ы', 'j': 'й', 'w': 'в', 'x': 'кс', 'q': 'к'}


def lat_to_ru(s):
    s = s.lower()
    for a, b in LAT2RU_MULTI:
        s = s.replace(a, b)
    return ''.join(LAT2RU.get(ch, ch) for ch in s)


def variants(word):
    """Множество читаемых написаний одного слова (для глаз, grep и RAG)."""
    word = (word or '').strip().lstrip('@')
    v = {word}
    if _has_cyr(word):
        v.add(translit(word))                 # виктор -> viktor
        v.add(ru_layout_to_en(word))          # на случай RU-раскладки
    else:
        cyr = en_layout_to_ru(word)           # dbrnjh -> виктор
        if _has_cyr(cyr):
            v.add(cyr)
            v.add(translit(cyr))              # -> viktor
        v.add(lat_to_ru(word))                # viktor -> виктор
    # ещё латинский слой от любой кириллицы внутри
    more = set()
    for x in v:
        if _has_cyr(x):
            more.add(translit(x))
    v |= more
    return sorted({x for x in v if len(x) >= 2})


def grep(words):
    """ripgrep по волту по всем вариантам (если rg есть в PATH)."""
    pat = '|'.join(re.escape(w) for w in words)
    try:
        out = subprocess.run(['rg', '-i', '-l', '--', pat, VAULT],
                             capture_output=True, text=True, encoding='utf-8')
        files = [l for l in out.stdout.splitlines() if l]
        print(f'\nripgrep по [{pat}] — файлов: {len(files)}')
        for f in files[:60]:
            print('  ' + os.path.relpath(f, VAULT))
        if len(files) > 60:
            print(f'  … ещё {len(files)-60}')
    except FileNotFoundError:
        print('rg (ripgrep) не найден в PATH — используй find_name.py или поставь rg')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('использование: python expand_query.py <слово> [--grep] [--line]')
        return
    word = ' '.join(args)
    v = variants(word)
    if '--line' in sys.argv:
        print(' '.join(v))
        return
    print('варианты:', ' '.join(v))
    if '--grep' in sys.argv:
        grep(v)


if __name__ == '__main__':
    main()
