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
backfill_aliases.py — вписывает альтернативные написания в aliases: всех
лид/человеко-карточек. Хирургически: трогает ТОЛЬКО блок aliases, остальной
файл байт-в-байт. Идемпотентно (повторный запуск ничего не меняет).

  python backfill_aliases.py            # СУХОЙ прогон: считает + показывает диффы
  python backfill_aliases.py --apply    # реально пишет

Стили aliases, которые понимает: inline [..], блочный (- item), отсутствует.
"""
import os, re, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alt_spellings import alt_spellings

VAULT = r'%VAULT%'
LEADS = os.path.join(VAULT, '04-Projects', 'crypto', 'Platinum-CRM', 'leads')
PEOPLE = os.path.join(VAULT, '07-People')


def split_front(text):
    if not text.startswith('---'):
        return None, None, None
    m = re.match(r'---\r?\n(.*?\r?\n)---\r?\n?', text, re.S)
    if not m:
        return None, None, None
    return text[:m.start(1)], m.group(1), text[m.end():]  # opener, body, rest


def parse_title(body):
    m = re.search(r'^title:\s*(.+?)\s*$', body, re.M)
    return m.group(1).strip().strip('"\'') if m else ''


def parse_aliases(body):
    """Вернуть (style, items, span) — style in inline|block|none."""
    m = re.search(r'^aliases:[ \t]*\[(.*?)\][ \t]*$', body, re.M)
    if m:
        items = [x.strip().strip('"\'') for x in re.findall(r'[^,\[\]]+', m.group(1)) if x.strip()]
        return 'inline', items, (m.start(), m.end())
    m = re.search(r'^aliases:[ \t]*\r?\n((?:[ \t]*-[ \t]*.+\r?\n?)+)', body, re.M)
    if m:
        items = [re.sub(r'^[ \t]*-[ \t]*', '', l).strip().strip('"\'')
                 for l in m.group(1).splitlines() if l.strip()]
        return 'block', items, (m.start(), m.end())
    return 'none', [], None


def build(name, existing):
    alts = alt_spellings(name)
    low = {e.lower() for e in existing} | {name.lower()}
    return [a for a in alts if a.lower() not in low]


def apply_to_body(body, title, new, style, items, span):
    if style == 'inline':
        merged = items + new
        line = 'aliases: [' + ', '.join('"%s"' % x for x in merged) + ']'
        return body[:span[0]] + line + body[span[1]:]
    if style == 'block':
        add = ''.join('- %s\n' % x for x in new)
        # вставить после последнего существующего пункта
        return body[:span[1]] + add + body[span[1]:]
    # none: вставить inline-строку сразу после title:, иначе в начало
    line = 'aliases: [' + ', '.join('"%s"' % x for x in new) + ']\n'
    mt = re.search(r'^title:.*\r?\n', body, re.M)
    if mt:
        return body[:mt.end()] + line + body[mt.end():]
    return line + body


def main():
    apply = '--apply' in sys.argv
    files = (glob.glob(os.path.join(LEADS, '**', '*.md'), recursive=True) +
             [p for p in glob.glob(os.path.join(PEOPLE, '**', '*.md'), recursive=True)
              if not os.path.basename(p).startswith('_')])
    changed = skipped_noalt = skipped_done = errors = 0
    by_style = {'inline': 0, 'block': 0, 'none': 0}
    samples = []
    for path in files:
        try:
            raw = open(path, encoding='utf-8').read()
            opener, body, rest = split_front(raw)
            if body is None:
                skipped_noalt += 1
                continue
            title = parse_title(body) or os.path.splitext(os.path.basename(path))[0]
            style, items, span = parse_aliases(body)
            new = build(title, items)
            if not new:
                skipped_done += 1
                continue
            nb = apply_to_body(body, title, new, style, items, span)
            if nb == body:
                skipped_done += 1
                continue
            changed += 1
            by_style[style] += 1
            if len(samples) < 6:
                samples.append((os.path.relpath(path, VAULT), title, style, items, new))
            if apply:
                open(path, 'w', encoding='utf-8', newline='').write(opener + nb + '---\n' + rest)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print('ERR', path, e)

    print(f'\n{"=== ЗАПИСАНО ===" if apply else "=== СУХОЙ ПРОГОН (ничего не записано) ==="}')
    print(f'карточек всего:      {len(files)}')
    print(f'изменить:            {changed}  (inline {by_style["inline"]} / block {by_style["block"]} / без aliases {by_style["none"]})')
    print(f'уже заполнено/нечего добавить: {skipped_done}')
    print(f'без frontmatter:     {skipped_noalt}')
    print(f'ошибок:              {errors}')
    print('\n--- примеры ДО→ПОСЛЕ ---')
    for rel, title, style, items, new in samples:
        print(f'\n[{style}] {title}   ({rel})')
        print(f'   было aliases:  {items}')
        print(f'   добавим:       {new}')


if __name__ == '__main__':
    main()
