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
"""Organize the 319 Platinum-CRM tags into a taxonomy note + flag merge candidates."""
import json, io, re
EXP=r"C:$HOME/!CLAUDE-HP17 May26/crm_export"
OUT=r"E:/Obsidian/Owner-Knowledge/04-Projects/crypto/Platinum-CRM/_Platinum-CRM-Tag-Taxonomy.md"
tags=json.load(io.open(EXP+"/crm_tags.json",encoding="utf-8"))  # [[tag,count],...]

# ordered (regex, category) — first match wins
RULES=[
 (r"Not investor|мимо кассы|irrelevant|ХЗ/Unknown|spam|cпам|SCAM|Скам|Toxic|Токсик|banned|удалил|no lead in group|Лида нет|Массовая группа|DO NOT TOUCH|Not Succe|не бомж|проект бомж|мелкая сошка|не могу отправить|не инвестировал|not interested|не заинтересован|DOES NOT NEED|NOT invest|Ordinary|Лид из \"Состав\"", "🚫 Дисквалификация / шум"),
 (r"МЕМ|Не мем|Мем обработан", "🎭 Мем"),
 (r"INTRO from us|allocation was proposed|Мяч|фидбек|Promises|Договорились меняться|Deal flow|Дилфлоу|принимает решения|профакаплен|Endorsement|подана заявка|need ping|пингануть|^ping\d|пинг\d|Запросили|Получили", "📈 Пайплайн / статус сделки"),
 (r"pitch|offer|OFFER|newsletter|Linkedin|blurb|happy_new_year|CHARM|FUNDRAISE MALIKA|Auto send|People newsletter|autoping|MALIKA|VLAD", "✉️ Кампании (рассылки/питчи)"),
 (r"Lead.?s? .*Vlad|Лид из|FB Lead|from Vlad|SKIP from", "🌱 Источник лида"),
 (r"VIP|Personal contact|Персональный|IRL|Stanford|Стенфорд|Davos|Давос|Collective call|ANTON ONLY|Karina/Alina", "⭐ VIP / личное"),
 (r"Наш |Наша |синтетик|retagging|CRM_Client|^CRM/|РУЧНОЙ|Тестовые|TEST|Сотрудник|employee|рабочая группа|Auto send|added to otc channel|Paid messaging", "⚙️ Внутреннее / операционка"),
 (r"EUROPE|Europe|APAC|Asia|Азиат|North America|Hong Kong|Гонконг|Dubai|Singapore|California|Paris|India|Индус|CHINA|KOREA|JAPAN|СНГ|AFRICA|Latin America|MiddleEAST|Vietnam|^GB$|USA|Лид — |EUROPE|Европеец|Нигериец", "🌍 География"),
 (r"INVESTOR|VC|Angel|Ангел|инвестир|инвестal|активно инвест|^GP/|^LP/|give grants|Grants|Гранты|YZi|fundraise helper|поднять бабла|Match Makers|Коннекторы|Vertical Agnostic|invest in kol|kol rounds|backers|бекеры|Market Maker|Маркет Мейкер", "💰 Инвестор (квалификация)"),
 (r"привлекли \$|привлекли |TGE in|токен уже|залищен|нужны инвесторы|нужны ланчпады|нужны листинг|need projects|needs investors|needs launchpad|fundraising|привлекают|crowdfunding|Краудфандинг", "🎯 Фандрейз-стадия проекта"),
 (r"Founder|Фаундер|Developer|Разработчик|Advisor|Адвайзер|Mentor|Ambassador|Event organizer|Организатор|Researcher|Исследователь|Lawyer|Юрист|designer|Дизайн|Consulting|Консульт|Community management|Менеджер групп|KOL|Influencer|Speaker|Спикер|Journalist|Журналист|Scout|Скаут|Interviewer|Contractor|Подрядчик|^HR$|recruitment|hiring|Co-?founder|Кофаундер|Ко-[Фф]аундер|Venture Studio|Venture Builder|Repeated founder|Data Scientist|Data analy|Анализ данных|Computer Scientist|Учёный|Аналитик|Analytics|Match", "👤 Роль / тип контакта"),
 (r"DeFi|GameFi|Gamefi|Геймфи|GameDev|Геймдев|NFT|^AI|ИИ|Ai|RWA|Infra|Инфраструктур|DAO|ДАО|Wallet|Кошел|Exchange|Биржа|CEX|DEX|Layer|Лэер|^Zk|Зикей|zK|SocialFi|Социальные|Metaverse|Метавселенная|Fintech|Финтех|Healthcare|Здоровье|Медицин|Blockchain|Блокчейн|Ton|Тон|Aptos|Sui|Суй|Move|Мув|Protocol|Протокол|Marketplace|Маркетплейс|web3|web2|веб3|веб2|Mining|Майнинг|Trading|Трейдинг|Listing|Листинг|OTC|otc|gambl|Гемблинг|казино|беттинг|ставки|Music|музык|Art|Искусств|Sport|Спорт|Education|Образование|EdTech|Real estate|Недвижим|Proptech|Construction|Fashion|Мода|Media|Медийн|Cybersecurity|Кибербез|Audit|Аудит|SAAS|SaaS|B2C|e-commerce|Escrow|tax|налог|Validator|Валидатор|Aggregator|Агрегатор|Ecosystem|Экосистем|dev tools|тулз|mobile|Мобильн|bot/|бот|Telegram|Whatsapp|Twitter|youtube|ютуб|TikTok|Instagram|Socialfi|Liquidity|ликвидн|price|Цена|Traffic|Трафик|Траффик|Trafic|Bank|Банк|банки|Finance|Финансы|Крипта|Крипто|Cloud|Storage|Хранени|VR|Виртуальн|ML|Машинн|Layer|RWA|Реальные|Sustainab|устойчив|ECO|ЭКО|Longevity|Лонгевити|Healthcare|Mining|Майнинг|Incubator|Инкубатор|Accelerator|Акселератор|Launchpad|Ланчпад|Listing|Hackathon|хакатон|Grants|Lead.*traffic|трафик|Indexing|Индексир|lead generation|Creative tech|native speaker|Crypto tax", "🏷️ Сектор / вертикаль"),
 (r"Gatekeeper|Noah|Cheesus|Sidus|Marnotaur|qdao|NFT Stars|BTCNEXT|gotbit|Binance|SpaceSwap|Кар|@", "🔑 Гейткиперы / персоны / группы"),
]
import collections
cat=collections.OrderedDict()
order=["🚫 Дисквалификация / шум","🎭 Мем","📈 Пайплайн / статус сделки","✉️ Кампании (рассылки/питчи)",
 "🌱 Источник лида","⭐ VIP / личное","⚙️ Внутреннее / операционка","🌍 География",
 "💰 Инвестор (квалификация)","🎯 Фандрейз-стадия проекта","👤 Роль / тип контакта",
 "🏷️ Сектор / вертикаль","🔑 Гейткиперы / персоны / группы","❓ Прочее"]
for c in order: cat[c]=[]
def categorize(t):
    for rx,c in RULES:
        if re.search(rx,t,re.I): return c
    return "❓ Прочее"
for t,n in tags: cat[categorize(t)].append((t,n))

# merge candidates: normalize (drop RU half after /, lowercase, strip emoji/space)
def norm(t):
    t=re.split(r"[/\-]",t)[0]
    t=re.sub(r"[^a-zа-я0-9]","",t.lower())
    return t
groups=collections.defaultdict(list)
for t,n in tags: groups[norm(t)].append((t,n))
dups=[v for k,v in groups.items() if len(v)>1 and k]

md=["---","title: \"Platinum CRM — таксономия тегов\"","type: reference","context: platinum-crm",
    "tags: [platinum-crm, taxonomy, crm-tags]","origin: mixed","authored_by: hybrid","---","",
    "# Platinum CRM — таксономия тегов","",
    f"_319 рабочих тегов CRM ({sum(n for _,n in tags):,} применений) сгруппированы по смыслу. Источник: `crm_entities_export.csv`. См. [[_Platinum-CRM-MOC]]._".replace(","," "),""]
for c in order:
    items=sorted(cat[c],key=lambda x:-x[1])
    if not items: continue
    md.append(f"## {c}  ·  {len(items)} тегов / {sum(n for _,n in items):,} исп.".replace(","," "))
    md.append("")
    for t,n in items:
        md.append(f"- **{t}** — {n:,}".replace(","," "))
    md.append("")
md.append("## 🔧 Кандидаты на слияние (дубли/опечатки)")
md.append("")
md.append("_Один смысл, разное написание — свести к одному канону:_")
md.append("")
for g in sorted(dups,key=lambda v:-sum(n for _,n in v)):
    parts=" + ".join(f"`{t}` ({n})" for t,n in sorted(g,key=lambda x:-x[1]))
    md.append(f"- {parts}")
io.open(OUT,"w",encoding="utf-8").write("\n".join(md))
print("taxonomy written:",OUT)
print("category sizes:",{c:len(cat[c]) for c in order if cat[c]})
print("merge-candidate groups:",len(dups))
