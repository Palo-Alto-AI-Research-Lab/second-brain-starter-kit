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
"""Integrate 2539 ChatGPT notes into the concept layer cheaply, using their
existing frontmatter (no per-note LLM). Adds provenance, a topic->concept link
(guaranteed connection), and converts frontmatter concepts into body wikilinks
(top ones resolve to existing bridge/concept notes)."""
import re, glob, os
from pathlib import Path
import yaml

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
CGPT = VAULT / "01-Conversations/ChatGPT"
CONCEPTS = VAULT / "06-Concepts"
MARK = "## Концепты и сущности"

# topic -> primary concept (umbrella). NEW umbrellas created as stubs below.
TOPIC = {
 "01-AI-Tech":"concept-ai-agents","02-Crypto-Web3":"concept-blockchain",
 "03-Biohacking":"concept-biohacking-nutrition","04-Translation":"concept-language-learning",
 "05-Medicine":"concept-medicine-health","06-Cars":"concept-cars",
 "08-Family-Kids":"concept-parenting","11-Portugal":"concept-place-livability",
 "12-Construction":"concept-construction-renovation","13-General-Tech":"concept-tech-tools",
 "14-Business-Finance":"concept-startup-fundraising","15-Personal-Growth":"concept-life-observations",
 "16-Travel":"concept-place-livability","17-Home-Life":"concept-life-observations",
 "18-Games-Entertainment":"concept-tap-to-earn-games",
}
NEW_UMBRELLA = {
 "concept-language-learning":"Изучение языков",
 "concept-medicine-health":"Медицина и здоровье",
 "concept-cars":"Автомобили",
 "concept-construction-renovation":"Стройка и ремонт",
 "concept-tech-tools":"Технические инструменты",
}

existing_files = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(str(VAULT/'**/*.md'),recursive=True)}

def translit_slug(s):
    M={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',' ':'-'}
    s=s.lower(); o=[]
    for c in s: o.append(M.get(c, c if (c.isalnum() and c.isascii()) else '-'))
    return re.sub(r'-+','-',''.join(o)).strip('-')

def resolve_concept(term):
    """map a free-text concept to an existing note name if possible."""
    t=term.strip()
    if not t: return None
    if t in existing_files: return t                 # exact (e.g. bridge note 'CGM')
    cs="concept-"+translit_slug(t)
    if cs in existing_files: return cs               # concept-<slug>
    return t                                          # leave as-is (may be ghost)

stats=Counter=__import__('collections').Counter()
n=0
for f in glob.glob(str(CGPT/'**/*.md'),recursive=True):
    t=open(f,encoding='utf-8',errors='ignore').read()
    m=re.match(r'^(---\n)(.*?)(\n---\n)(.*)$',t,re.DOTALL)
    if not m: continue
    h,fmtext,e,body=m.groups()
    try: d=yaml.safe_load(fmtext) or {}
    except Exception: d={}
    topic=str(d.get('topic') or '')
    tc=TOPIC.get(topic)
    # provenance
    if not re.search(r'^origin:',fmtext,re.M):
        fmtext+="\norigin: mixed"
    if not re.search(r'^authored_by:',fmtext,re.M):
        fmtext+="\nauthored_by: hybrid"
    # topic concept link
    if tc and not re.search(r'^concept:',fmtext,re.M):
        fmtext+=f'\nconcept: "[[{tc}]]"'
    # body entity section (idempotent)
    if MARK not in body:
        cons=[resolve_concept(str(c)) for c in (d.get('concepts') or [])] if isinstance(d.get('concepts'),list) else []
        cons=[c for c in cons if c]
        links=[]
        if tc: links.append(f"- Тема: [[{tc}]]")
        for c in dict.fromkeys(cons):
            links.append(f"- [[{c}]]")
        if links:
            body=body.rstrip()+"\n\n"+MARK+"\n"+"\n".join(links)+"\n"
    open(f,'w',encoding='utf-8').write(h+fmtext+e+body)
    n+=1
    if tc: stats[tc]+=1

# create new umbrella concept stubs
for slug,title in NEW_UMBRELLA.items():
    p=CONCEPTS/f"{slug}.md"
    if p.exists(): continue
    p.write_text("\n".join(["---",f'title: "{title}"',"type: concept","status: stub","authored_by: hybrid",
        "origin: mixed","created_by: obsidian-ingest","created: 2026-05-28","tags: [concept, chatgpt-derived]","---","",
        f"# {title}","","## Определение",
        f"_Зонтичный концепт для ChatGPT-заметок темы. Объединяет заметки категории. Требует доработки._","",
        "## See Also","- [[_Telegram-MOC]]",""]),encoding="utf-8")

print("integrated ChatGPT notes:",n)
print("topic->concept distribution:",dict(stats.most_common()))
