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
"""Собирает markdown-заметки волта из выгруженных страниц GitBook (публичная вики лаборатории).

ЧТО ДЕЛАЕТ. Берёт скачанные страницы из live/pages, чистит их и раскладывает в live/md,
проставляя каждой главе (а) заголовок из CH_TITLE и (б) концепты из CH_CONCEPTS — то есть
связывает внешний документ с графом волта, а не просто конвертирует текст.

ВХОД: live/pages (выгрузка). ВЫХОД: live/md (заметки). Обе папки — промежуточные.
Соседи: slugs.py (карта заголовок→URL), gen_md.py, parse_outline.py, build_notes.py.

КТО ДЁРГАЕТ: импорт GitBook, шаг после выгрузки страниц.

ЧТО ЛОМАЕТСЯ. В вики добавили главу — её номера нет ни в CH_TITLE, ни в CH_CONCEPTS.
Заметка всё равно соберётся, но останется без заголовка и без единой концепт-связи, то
есть станет сиротой в графе. Второе: изменилась структура выгрузки, и чистка режет не то.

КАК ПОНЯТЬ. Число файлов в live/md против числа страниц в live/pages, и глазами — есть ли
у свежих заметок концепты. Заметка без концептов здесь = пропущенная строка в таблице.

КАК ЧИНИТЬ. Дописать главу в обе таблицы и пересобрать; live/md одноразовая, её удаляют и
генерируют заново, а не правят.
"""
import os, re, json, glob
PAGES=r'%IMPORTS%\gitbook\live\pages'
OUT=r'%IMPORTS%\gitbook\live\md'; os.makedirs(OUT, exist_ok=True)
URLROOT='https://app.gitbook.com/o/ORGIDPLACEHOLDER00000/s/SPACEIDPLACEHOLDER000/'
BATCH='2026-06-18'

CH_CONCEPTS={
 1:['concept-palo-alto-lab-brand','concept-charm-lifeos'],
 2:['concept-autonomous-ai-agents','concept-ai-agents','concept-ai-agent-orchestration'],
 3:['concept-ai-agent-orchestration','concept-launchpad','concept-charm-lifeos'],
 4:['concept-ai-agents','concept-autonomous-ai-agents'],
 5:['concept-aaa-token','concept-tokenomics-design'],
 6:['concept-palo-alto-lab-brand','concept-launchpad'],
 7:['concept-palo-alto-lab-brand'],
 8:['concept-launchpad','concept-charm-lifeos'],
 9:['concept-palo-alto-lab-brand'],
 10:['concept-palo-alto-lab-brand'],
}
CH_TITLE={1:'Who We Are',2:'Why AI',3:'Platform Functionality',4:'AI Agents You Can Launch',
 5:'Tokenomics, Token & Node Sale',6:'Roadmap',7:'The Team, The DAO, The Roles',
 8:'FAQ',9:'Official Links',10:'References'}

def kebab(t):
    t=re.sub(r'^\s*\d+(\.\d+)*\.?\s*','',t)  # strip leading numbering
    t=t.lower().replace('&','and').replace("'",'').replace('’','').replace('"','')
    t=re.sub(r'[^a-z0-9]+','-',t); t=re.sub(r'-+','-',t).strip('-')
    return t[:60] or 'page'

def chapter_of(title):
    m=re.match(r'\s*(\d+)', title)
    return int(m.group(1)) if m else 0

def render(body):
    out=[]
    for ln in body.split('\n'):
        s=ln.strip()
        if not s: out.append(''); continue
        if re.match(r'^\d+(\.\d+)*\.?\s+\S', s) and len(s)<90: out.append('#### '+s)
        elif s.startswith(('●','•','▪','-','✔','✓','🔥','🚀','💡')): out.append('- '+s.lstrip('●•▪-✔✓ ').strip())
        else: out.append(s)
    r='\n'.join(out); return re.sub(r'\n{3,}','\n\n',r).strip()

# load all pages in order
pages=[]
for f in sorted(glob.glob(os.path.join(PAGES,'*.txt')), key=lambda p:int(os.path.basename(p)[:2])):
    nn=int(os.path.basename(f)[:2])
    raw=open(f,encoding='utf-8').read()
    m=re.match(r'TITLE:\s*(.*?)\nURL:\s*(.*?)\n---\n(.*)', raw, re.S)
    if not m:
        title='page %d'%nn; url=URLROOT; body=raw
    else:
        title,url,body=m.group(1).strip(),m.group(2).strip(),m.group(3).strip()
    slug='pa-gitbook-%02d-%s'%(nn,kebab(title))
    pages.append({'nn':nn,'title':title,'url':url,'body':body,'slug':slug,'ch':chapter_of(title)})

# write notes with prev/next
for i,p in enumerate(pages):
    ch=p['ch']; concepts=CH_CONCEPTS.get(ch,[])
    img = len(p['body'])<160 or '[IMAGE' in p['body'] or 'PAGE NOT FOUND' in p['body']
    prev=pages[i-1]['slug'] if i>0 else None
    nxt=pages[i+1]['slug'] if i<len(pages)-1 else None
    nav=[]
    if prev: nav.append('◀ [[%s|пред.]]'%prev)
    if nxt: nav.append('[[%s|след.]] ▶'%nxt)
    navline=' · '.join(nav)
    rel='\n'.join('- [[%s]]'%c for c in concepts)
    imgnote=('\n> [!note] Визуальная страница\n> Эта страница в GitBook — в основном изображение/диаграмма; текст минимален. Смотреть оригинал: %s\n'%p['url']) if img else ''
    md=f"""---
title: "{p['title'].replace('"',chr(39))}"
type: resource
subtype: gitbook-page
gitbook_chapter: {ch}
origin: Palo Alto Research Lab (AAA / C(H+A)RM team)
source_doc: "Live GitBook (Copy of AAA GitBook)"
source_url: {p['url']}
import_batch: {BATCH}
tags: [palo-alto, gitbook, charm, aaa-token]
---

# {p['title']}

> [!info] Источник · GitBook AAA «C(H+A)RM» (гл. {ch}. {CH_TITLE.get(ch,'')})
> Живая страница: {p['url']} · Оглавление: [[_Palo-Alto-GitBook-MOC]] · {navline}
{imgnote}
{render(p['body'])}

## Связано
{rel}
- [[_Palo-Alto-GitBook-MOC]]
"""
    open(os.path.join(OUT,p['slug']+'.md'),'w',encoding='utf-8').write(md)

json.dump([{'nn':p['nn'],'ch':p['ch'],'slug':p['slug'],'title':p['title']} for p in pages],
          open(os.path.join(OUT,'_index.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('wrote', len(pages), 'notes')
# chapter counts
from collections import Counter
print('by chapter:', dict(sorted(Counter(p['ch'] for p in pages).items())))
