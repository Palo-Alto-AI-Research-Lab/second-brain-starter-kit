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
alt_spellings.py — ЧИТАЕМЫЕ альтернативные написания имени для поля в карточке.
Целое имя в ОДНОМ алфавите за раз (не смешиваем), без раскладочного мусора.

  Sergey Davydov  -> Сергей Давыдов, Sergei Davydov
  Виктория Елена  -> Viktoria Elena
"""
import os, sys, re, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_norm import translit, _has_cyr

# латиница -> кириллица (упорядочено: длинные сочетания первыми)
L2R_MULTI = [('shch', 'щ'), ('sch', 'щ'), ('sh', 'ш'), ('ch', 'ч'), ('zh', 'ж'),
             ('kh', 'х'), ('ts', 'ц'), ('yo', 'ё'), ('iy', 'ий'), ('ey', 'ей'),
             ('ay', 'ай'), ('oy', 'ой'), ('uy', 'уй'), ('ya', 'я'), ('yu', 'ю'),
             ('ye', 'е'), ('ia', 'ия'), ('ph', 'ф'), ('ck', 'к'), ('ee', 'и'),
             ('ou', 'у'), ('th', 'т')]
L2R = {'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е', 'z': 'з',
       'i': 'и', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п',
       'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'к',
       'y': 'ы', 'w': 'в', 'x': 'кс', 'q': 'к', 'j': 'дж'}

# частые развилки транслита (применяются к латинской форме целиком)
LAT_VARIANTS = [(r'ks', 'x'), (r'iy\b', 'y'), (r'ii\b', 'y'), (r'ey\b', 'ei'),
                (r'yi\b', 'y'), (r'ya', 'ia'), (r'yu', 'iu')]


def _word_l2r(w):
    s = w.lower()
    for a, b in L2R_MULTI:
        s = s.replace(a, b)
    if s.endswith('y'):
        s = s[:-1] + ('й' if s[:-1] and s[:-1][-1] in 'аеиоуыэюя' else 'ий')
    out = ''.join(L2R.get(ch, ch) for ch in s)
    return out.capitalize()


def _to_latin(name):
    return ' '.join((translit(w).capitalize() if _has_cyr(w) else w)
                    for w in name.split())


def _to_cyr(name):
    return ' '.join((_word_l2r(w) if not _has_cyr(w) else w)
                    for w in name.split())


def _lat_variants(lat):
    out = {lat}
    low = lat.lower()
    for pat, repl in LAT_VARIANTS:
        v = re.sub(pat, repl, low)
        if v and v != low:
            out.add(v.title())
    return out


# --- «уверенно славянское имя?» — чтобы иностранцам НЕ лепить кириллицу (вариант 1) ---
RU_FIRST = set('''sergey sergei viktor Vlad aleksandr alexander aleksandra alexandra
ivan dmitry dmitrii dmitriy andrey andrei mikhail mihail nikolay nikolai vladimir
anton pavel roman denis maxim maksim konstantin oleg igor kirill artem artyom artiom
evgeny evgenii evgeniy alexey aleksey yuri yury yuriy vadim vasily vasiliy boris gleb
stanislav stas vyacheslav valery valeriy ruslan timur german arseny arseniy fedor
Alina elena yelena olga Nina Nina nataliya maria mariya marya irina ekaterina
katerina tatiana tatyana svetlana daria darya dasha viktoria victoria ksenia kseniya
polina sofia sofya alina marina galina vera nadezhda lyudmila oksana yulia julia
nina raisa zinaida valentina lidia lidiya alla angelina veronika kristina karina
mikhailo bogdan taras ostap petro mykola oleksandr oleksiy volodymyr'''.split())
RU_SUFFIX = ('ov', 'ova', 'ev', 'eva', 'iev', 'ieva', 'yev', 'yeva', 'in', 'ina',
             'yn', 'yna', 'sky', 'skiy', 'skii', 'skaya', 'ski', 'tsky', 'tskaya',
             'enko', 'chenko', 'uk', 'yuk', 'chuk', 'ich', 'ovich', 'evich', 'ovna',
             'evna', 'shvili', 'dze', 'yan', 'ko', 'iy', 'ij')


def looks_slavic(name):
    toks = [t.lower() for t in re.split(r'[\s\-]+', name) if t]
    if not toks:
        return False
    if _has_cyr(name):
        return True
    if toks[0] in RU_FIRST:
        return True
    # суффикс фамилии проверяем только на ПОСЛЕДНЕМ слове (иначе Albin/Martin → ложно)
    return toks[-1].endswith(RU_SUFFIX) and len(toks[-1]) >= 5 and len(toks) >= 2


def alt_spellings(name, max_n=5):
    """Имя -> читаемые альтернативы. Кириллицу даём латинским именам ТОЛЬКО если славянское."""
    name = (name or '').strip()
    if not name or any(ch.isdigit() for ch in name):
        return []
    forms = set()
    if _has_cyr(name):
        forms.add(_to_latin(name))                 # кириллица -> латиница (всегда полезно)
        forms |= _lat_variants(_to_latin(name))
    elif looks_slavic(name):                       # латинское И славянское: и кириллица, и развилки
        forms.add(_to_cyr(name))
        forms |= _lat_variants(name)
    # иностранное латинское имя -> ничего (нет осмысленных альтернатив; опечатки ловит поиск)
    orig_l = name.lower()
    res = sorted({f.strip() for f in forms if f.strip() and f.lower() != orig_l},
                 key=lambda s: (len(s), s))
    return res[:max_n]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    tests = sys.argv[1:] or ['Sergey Davydov', 'Viktoria Elena', 'Виктория Елена',
                             'Konstantin Sedura', 'Glory Lucas', 'Abhishek Mahto',
                             'John Smith', 'Jun Hasegawa']
    for t in tests:
        print(f'{t:20} -> {alt_spellings(t)}')
