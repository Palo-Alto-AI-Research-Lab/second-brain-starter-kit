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
"""Concept + tag routing for Pokupki knowledge notes (weighted bilingual keyword
   map; product-domain beats process-domain). DETECT mode unless APPLY=1.
   Honors 'keyword OK for rough first pass'; validated by LLM QA sample after."""
import re, os, json
from collections import Counter, defaultdict
from pathlib import Path

VAULT = Path(r"E:/Obsidian/Owner-Knowledge")
OUT = Path(r"E:/Obsidian/_imports")
POSTS = VAULT / "01-Conversations/Telegram/Pokupki/posts"
APPLY = os.environ.get("APPLY") == "1"

# concept -> (weight, tag, [keyword substrings, lowercased])
DOMAINS = {
 "concept-construction-renovation": (3, "construction", [
   "бетон","цемент"," sika","sikadur","sikatop","sikalastic","sika ","грунтовк","праймер",
   "извест","кругляк","бревн","арматур","стекловолокн","стержен","стержн","гидроизоляц",
   "штукатур","пеноплас","гофр","koster","mapei","foamjet","кладк","кирпич","плитк","клей",
   "герметик","шпатлев","шпаклев","смол","эпоксид","битум","рубероид","утеплит","изоляц",
   "гипсокартон","саморез","дюбел","обезжир","пластификатор","крыш","фасад","мансард","velux",
   "leroy","леруа","строит","ремонт","раствор","скоб","сетк","профнастил","арматурн"]),
 "concept-garden-landscaping": (3, "garden", [
   "растен","виноград","ковыл","девичий","саженц","семен","газон","кустар","ландшафт",
   "мульч","торф","удобрен","рассад","клумб","теплиц","полив","ирригац","грядк","дерев",
   "цвет","декоратив","хвойн","туя","самшит"]),
 "concept-home-goods": (3, "home-goods", [
   "холодильник","морозил","стиральн","посудомо","духов","варочн","плита","микроволнов",
   "бойлер","водонагрев","кондиционер","обогреват","нагреват","унитаз","биде","смеситель",
   "раковин","ванна","душ","мебел","диван","кровать","матрас","шкаф","коврик","ковер",
   "лампа","светильник","светодиод","люстра","штор","пылесос","керхер","бесперебойник",
   " ups","ибп","eaton","ellipse","термосифон","солнечн","samsung","посуд","контейнер",
   "пакет","humydry","самокат","scooter","утюг","чайник","фен ","полк","вешалк","зеркал",
   "стекл","насос","матрац","одеял","подушк","полотенц","жалюзи","карниз"]),
 "concept-cars": (3, "cars", [
   "аккумулятор","автомобил","машин","колес","болт","шин ","шины","мерс","mercedes","lexus",
   "лексус","моторн масл","v class","vito","гараж","автодом","кемпер","velosiped","велосипед"]),
 "concept-parenting": (3, "kids", [
   "лего","lego","игрушк","игр для дет","детск","ребен","ребён","школ","танц","конструктор",
   "mindstorms","карточн","раскраск","самокат для"]),
 "concept-groceries-food": (3, "groceries", [
   "молок","milk","продукт","celeiro","целейр","glovo","глово","вино ","шампан","espumante",
   "сыр","чеснок","бакале","овощ","фрукт","мясо","кофе","чай ","масло оливк","специ","соус",
   "хлеб","крупа","орех"]),
 "concept-travel-logistics": (3, "travel", [
   "билет","рейс","перелет","авиа","отел","аренд жил","rental","виза","casevacanza",
   "hometogo","skyscanner","kayak","google flight","транзит","поездк","бронир","booking",
   "чемодан","багаж","airbnb"]),
 "concept-tech-tools": (3, "electronics", [
   "кабель","hdmi","зарядн устр","зарядк","ноутбук","монитор"," audio","телевизор","роутер",
   "чат gpt","чатгпт","chatgpt","наушник","флешк","ssd","камер","датчик","gps","адаптер",
   "повербанк","зарядное"]),
 "concept-personal-finance": (2, "finance", [
   "оплат","карт ","банк","инвойс","invoice","налог"," ндс","страхов","возврат средств",
   "претензи","рефанд","реквизит"]),
}
PROC = ("concept-procurement-vendors", 1, "procurement", [
   "trello","доставк","отгруз","апрув","поставщик","контрагент","amazon","ebay","aliexpress",
   "worten","заказ","выкуп","Игорь","валери","склад","посылк","курьер"," dhl","отправ","счет"])

def route(text):
    t = " " + text.lower() + " "
    scores = Counter(); hits = defaultdict(list)
    for concept, (w, tag, kws) in DOMAINS.items():
        for kw in kws:
            if kw in t:
                scores[concept] += w; hits[concept].append(kw.strip())
    # procurement only as weak signal
    pc, pw, ptag, pkws = PROC
    for kw in pkws:
        if kw in t:
            scores[pc] += pw; hits[pc].append(kw.strip())
    if not scores:
        return None, []
    best = max(scores, key=lambda c: scores[c])
    # if best is procurement but a product domain also scored, prefer product
    prod = {c: s for c, s in scores.items() if c != pc}
    if best == pc and prod:
        best = max(prod, key=lambda c: prod[c])
    return best, hits[best][:4]

TAG_OF = {c: v[1] for c, v in DOMAINS.items()}; TAG_OF[PROC[0]] = PROC[2]

rows_by_id = {r["id"]: r for r in (json.loads(l) for l in (OUT / "pokupki-archive.jsonl").read_text(encoding="utf-8").splitlines())}

def post_fields(txt):
    fm, _, rest = txt.partition("\n---\n")
    body = re.split(r"\n## Контекст", rest)[0]
    mid = re.search(r"(?m)^msg_id:\s*(\d+)", fm)
    rep = re.search(r"(?m)^reply_to:\s*(\d+)", fm)
    return body, (int(mid.group(1)) if mid else None), (int(rep.group(1)) if rep else None)

dist = Counter(); unrouted = []
applied = 0
for p in POSTS.glob("*.md"):
    txt = p.read_text(encoding="utf-8")
    body, mid, rep = post_fields(txt)
    rt = " " + (rows_by_id[rep]["text"] if rep in rows_by_id else "")   # inherit parent domain
    concept, kws = route(body + rt)
    if concept is None:
        dist["(unrouted)"] += 1
        if len(unrouted) < 25: unrouted.append(p.stem)
        concept_final = "concept-procurement-vendors"  # fallback bucket
        tag = "procurement"
    else:
        dist[concept] += 1
        concept_final = concept; tag = TAG_OF[concept]
    if APPLY:
        new = re.sub(r"(?m)^concept:\s*$", f'concept: "[[{concept_final}]]"', txt, count=1)
        # merge tag into tags list
        def add_tag(m):
            inner = m.group(1)
            adds = [tag] + ([t.strip() for t in kws] if concept else [])
            for a in adds:
                if a and a not in inner:
                    inner = inner + ", " + a
            return "tags: [" + inner + "]"
        new = re.sub(r"tags: \[([^\]]*)\]", add_tag, new, count=1)
        if new != txt:
            p.write_text(new, encoding="utf-8"); applied += 1

(OUT / "pokupki-concept-dist.txt").write_text(
    "\n".join(f"{c}: {n}" for c, n in dist.most_common()) +
    "\n\nUNROUTED SAMPLES:\n" + "\n".join(unrouted), encoding="utf-8")
print("APPLY", APPLY, "applied", applied)
for c, n in dist.most_common():
    print(f"  {n:5d}  {c}")
