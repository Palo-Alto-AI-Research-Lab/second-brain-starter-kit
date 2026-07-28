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
name_index.py — строит names.db: отпечаток имени -> карточка.

Источники (по умолчанию):
  * лиды Platinum CRM   04-Projects/crypto/Platinum-CRM/leads/**.md
  * люди                07-People/**.md
Флаг --vault: дополнительно индексирует ЗАГОЛОВКИ всех заметок волта
  (чтобы «важные слова» искались по всему хранилищу, п.2).

Запуск:
  python name_index.py            # CRM + люди
  python name_index.py --vault    # + заголовки всего волта
Идемпотентно: каждый раз пересоздаёт names.db с нуля (быстро).
"""
import os, re, sys, sqlite3, glob
sys.stdout.reconfigure(encoding='utf-8')          # виндовая консоль -> UTF-8
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_norm import keys, tokens

VAULT = r'%VAULT%'
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'names.db')

LEADS = os.path.join(VAULT, '04-Projects', 'crypto', 'Platinum-CRM', 'leads')
PEOPLE = os.path.join(VAULT, '07-People')
CONTACTS_DB = r'%IMPORTS%\apple-contacts\contacts.db'

FM = re.compile(r'^---\s*\n(.*?)\n---', re.S)


def front(text):
    """Очень лёгкий парсер frontmatter: title / aliases / handles."""
    m = FM.match(text)
    d = {'title': '', 'aliases': [], 'handles': []}
    if not m:
        return d
    for line in m.group(1).splitlines():
        mm = re.match(r'(title|aliases|handles)\s*:\s*(.*)', line)
        if not mm:
            continue
        k, v = mm.group(1), mm.group(2).strip()
        if k == 'title':
            d['title'] = v.strip('"\' ')
        else:
            # ["@a","@b"]  или  @a, @b
            d[k] = [p.strip().strip('"\'') for p in re.findall(r'[^\[\]\s,"\']+', v)]
    return d


def pretty(stem):
    """igor-kononov -> 'Igor Kononov' (для показа, если нет title)."""
    return re.sub(r'-\d+$', '', stem).replace('-', ' ').replace('_', ' ').title()


def name_strings(path, with_front=True):
    """Все строки-имена карточки: title, aliases, handles, slug."""
    stem = os.path.splitext(os.path.basename(path))[0]
    out = {pretty(stem), stem}
    display = pretty(stem)
    if with_front:
        try:
            with open(path, encoding='utf-8') as f:
                head = f.read(4000)
            d = front(head)
            if d['title']:
                out.add(d['title'])
                display = d['title']
            for h in d['aliases'] + d['handles']:
                out.add(h)
        except Exception:
            pass
    return display, {s for s in out if s}


def index_files(cur, files, kind, with_front=True):
    n = 0
    for path in files:
        rel = os.path.relpath(path, VAULT)
        display, strings = name_strings(path, with_front)
        # ключи: по полному имени И по каждому слову (имя/фамилия/ник)
        seen = set()
        for s in strings:
            cand = [s] + tokens(s)
            for c in cand:
                for k in keys(c):
                    if (k, rel) in seen:
                        continue
                    seen.add((k, rel))
                    cur.execute('INSERT INTO nkeys(key,tok,path) VALUES(?,?,?)',
                                (k, c.lower(), rel))
        cur.execute('INSERT INTO entries(path,kind,display) VALUES(?,?,?)',
                    (rel, kind, display))
        n += 1
    return n


def index_contacts(cur):
    """Apple-контакты из contacts.db: ВСЕ 12.5k, у кого есть карточка — привязать к ней."""
    if not os.path.exists(CONTACTS_DB):
        print('  contacts.db не найден — пропускаю')
        return 0
    import sqlite3
    cc = sqlite3.connect(CONTACTS_DB)
    matched = {cid: note for cid, note in
               cc.execute('SELECT contact_id, vault_note FROM vault_matches WHERE vault_note IS NOT NULL')}
    socials = {}
    for cid, uname in cc.execute('SELECT contact_id, username FROM social'):
        socials.setdefault(cid, []).append(uname or '')
    n = 0
    for cid, display, first, middle, last, nick, org in cc.execute(
            'SELECT id, display, first, middle, last, nickname, org FROM contacts'):
        strings = {display or '', f'{first or ""} {last or ""}'.strip(),
                   nick or '', f'{first or ""} {middle or ""} {last or ""}'.strip()}
        for u in socials.get(cid, []):
            strings.add(u)
        strings = {s for s in strings if s}
        if not strings:
            continue
        target = matched.get(cid)                 # уже есть карточка?
        path = target if target else f'apple:{cid}'
        seen = set()
        any_key = False
        for s in strings:
            for c in [s] + tokens(s):
                for k in keys(c):
                    if (k, path) in seen:
                        continue
                    seen.add((k, path))
                    any_key = True
                    cur.execute('INSERT INTO nkeys(key,tok,path) VALUES(?,?,?)',
                                (k, c.lower(), path))
        if not any_key:                            # имя было только из цифр/символов
            continue
        disp = display or f'{first or ""} {last or ""}'.strip() or nick
        if org:
            disp = f'{disp} · {org}'
        # OR IGNORE: если path = существующая карточка, не перетираем её kind
        cur.execute('INSERT OR IGNORE INTO entries(path,kind,display) VALUES(?,?,?)',
                    (path, 'contact', disp[:80]))
        if not target:
            n += 1
    cc.close()
    return n


ARCHIVE_DB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'leads.db'))

def _real_name(nm):
    nm = (nm or '').strip()
    if len(nm) < 3:
        return False
    if not re.search(r'[A-Za-zА-Яа-я]', nm):     # must contain a letter
        return False
    if re.search(r'\d{2}[.\-/]\d', nm):           # looks like a date -> junk
        return False
    return True

def index_archive_contacts(cur):
    """GDrive-архив контактов (leads.db → archive_contacts): индексируем ТОЛЬКО
    досягаемых (tg/email/linkedin) с настоящим именем, чтобы /find по имени находил
    архивных людей. path=archive:{id} (указатель в archive_contacts, как apple:{cid})."""
    if not os.path.exists(ARCHIVE_DB):
        print('  leads.db не найден — архив пропущен'); return 0
    ac = sqlite3.connect(ARCHIVE_DB)
    try:
        rows = list(ac.execute(
            "SELECT id,name,tg_norm,em_norm,li_norm,source_sheet,year FROM archive_contacts"))
    except Exception:
        print('  archive_contacts нет — пропуск'); ac.close(); return 0
    n = 0
    for cid, nm, tgn, emn, lin, ss, yr in rows:
        if not (tgn or emn or lin):               # только досягаемые
            continue
        if not _real_name(nm):                    # /find = поиск по ИМЕНИ
            continue
        path = f'archive:{cid}'
        strings = {nm}
        if tgn:
            strings.add('@' + tgn)
        seen = set(); any_key = False
        for s in strings:
            for c in [s] + tokens(s):
                for k in keys(c):
                    if (k, path) in seen:
                        continue
                    seen.add((k, path)); any_key = True
                    cur.execute('INSERT INTO nkeys(key,tok,path) VALUES(?,?,?)', (k, c.lower(), path))
        if not any_key:
            continue
        tag = []
        if tgn: tag.append('@' + tgn)
        if ss:  tag.append(ss[:24])
        disp = (f"{nm} · " + ' · '.join(tag))[:90] if tag else nm[:90]
        cur.execute('INSERT OR IGNORE INTO entries(path,kind,display) VALUES(?,?,?)',
                    (path, 'archive', disp))
        n += 1
    ac.close(); return n

def main():
    do_vault = '--vault' in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript('''
        DROP TABLE IF EXISTS nkeys;
        DROP TABLE IF EXISTS entries;
        CREATE TABLE nkeys(key TEXT, tok TEXT, path TEXT);
        CREATE TABLE entries(path TEXT PRIMARY KEY, kind TEXT, display TEXT);
    ''')

    COMPANIES = os.path.join(PEOPLE, 'Companies')
    leads = glob.glob(os.path.join(LEADS, '**', '*.md'), recursive=True)
    companies = [p for p in glob.glob(os.path.join(COMPANIES, '*.md'))
                 if not os.path.basename(p).startswith('_')]
    people = [p for p in glob.glob(os.path.join(PEOPLE, '**', '*.md'), recursive=True)
              if not os.path.basename(p).startswith('_')
              and os.path.dirname(p) != COMPANIES]
    nl = index_files(cur, leads, 'lead')
    print(f'  лиды:  {nl}')
    np = index_files(cur, people, 'person')
    print(f'  люди:  {np}')
    ncomp = index_files(cur, companies, 'company')
    print(f'  компании:  {ncomp}')
    nc = index_contacts(cur)
    print(f'  Apple-контакты (без карточки): {nc}')
    na = index_archive_contacts(cur)
    print(f'  GDrive-архив контактов: {na}')

    nv = 0
    if do_vault:
        # только заголовки/имена файлов всего волта (без frontmatter — быстро)
        already = set(leads) | set(people) | set(companies)
        allmd = [p for p in glob.glob(os.path.join(VAULT, '**', '*.md'), recursive=True)
                 if p not in already and not os.path.basename(p).startswith('_')]
        nv = index_files(cur, allmd, 'note', with_front=False)
        print(f'  заметки волта: {nv}')

    cur.execute('CREATE INDEX ix_key ON nkeys(key)')
    con.commit()
    cur.execute('SELECT COUNT(*) FROM nkeys')
    rows = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT key) FROM nkeys')
    dk = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM entries')
    total = cur.fetchone()[0]
    con.close()
    print(f'\nИтого: {total} записей ({nl} лид/{np} люди/{ncomp} компаний/{nc} apple/'
          f'{nv} заметки), {rows} ключ-строк, {dk} уникальных отпечатков')
    print(f'БД: {DB}')


if __name__ == '__main__':
    main()
