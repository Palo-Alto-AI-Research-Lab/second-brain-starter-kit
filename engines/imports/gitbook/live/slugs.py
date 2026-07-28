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
"""Карта «заголовок главы GitBook -> её slug и URL». Справочник, не процесс.

ЧТО ДЕЛАЕТ. Держит список заголовков вики ровно в том виде, в каком они там написаны, и
превращает каждый в slug, чтобы на главу можно было сослаться ссылкой. Заголовки заведены
списком намеренно: они содержат опечатки и хвосты исходника ("...Page", кавычки, двойные
точки), и slug должен строиться от РЕАЛЬНОГО заголовка, а не от того, каким он должен был бы
быть.

ВХОД: ничего, список внутри файла. ВЫХОД: соответствие заголовок->URL для других шагов.

КТО ДЁРГАЕТ: build_live.py и остальной импорт GitBook, когда проставляет ссылки.

ЧТО ЛОМАЕТСЯ. В вики переименовали или добавили главу — здесь про это не знают, и ссылка
на неё либо старая, либо отсутствует.

КАК ПОНЯТЬ. Ссылки на главы ведут в 404, или свежей главы нет в выводе вовсе.

КАК ЧИНИТЬ. Скопировать заголовок из вики ДОСЛОВНО, вместе с опечатками, и добавить в
список. Не «причёсывать» строку — от неё считается slug, и исправленный заголовок даёт
ссылку, которой нет.
"""
import re, json
BASE='https://app.gitbook.com/o/ORGIDPLACEHOLDER00000/s/SPACEIDPLACEHOLDER000/'
titles = [
"1. Who We Are","1.1 From 2015 to 2025","1.2. Traction/Highlights",
'1.3. History of AI CRM "C(H+A)RM" creation:',"1.4. The Why, The How",
"1.5. Palo Alto AI WEB-3 Research Lab",
"1.6. How Our AI Orchestration C(H+A)RM Chooses the Strongest Projects",
'1.7. Platform Functionality. Orchestration CRM "C(H+A)RM" for AI-Agents',
"1.8. Key Benefits of AI Agents","1.9. How We Make Money","1.10. Project Valuation",
"1.11. Types of Peers","1.12. AI Agents Orchestration C(H+A)RM Startup Perks",
"1.13. BACKERS + PARTNERS","1.14. TradeMarks",
'1.15. PIVOTs / "The only constant in life is CHANGES"Page',"1.16. Disclaimer",
"2. WHY AI","2.1. LLMs vs AI Agents","2.2. Key Differences Between LLMs and AI Agents",
"2.3. Energy-Efficient AI Agents Powered by Distilled LLMs",
"2.4. Swarm Orchestration: AI Agents at Scale",
"2.5. Decentralized Physical Infrastructure (DePIN) & Zero-Knowledge AI",
"3. PLATFORM FUNCTIONALITY (The Ecosystem)","3.1. Technology and Infrastructure",
"3.2. ESCROW: VC's Funds Escrow and Distribution to ProjectsPage",
"3.3. Marketplace for AI Agents","3.4. AI-Agent Creation Tools & Templates",
"3.5. AI-Agent Labor Exchange","3.6. Node Sales & Staking for AI Agents",
"3.7. Reputation System: Trust & Accountability for AI Agents",
"3.8. User Lifecycle in Our Ecosystem",
"3.9. UGC: A User-Generated Content Platform for AI Agents",
'3.10. Transitioning from "Centralized B2B SAAS" to Permissionless, Open-Source, On-Chain Autonomous',
"4. What AI Agents you can launch with us","4.1. Sentient status","4.1. DefAI = DeFi + AI Agents",
"4.2. AI Agents for Blockchain Security",'4.3. AI Agents for "NO CODE dApps"',
"4.4. Legal & Compliance AI Agents","4.5. AI Agents for ESG & Sustainability",
"4.6. More AI Agents for Web3","4.7. Our Main Competitors",
'4.8. Current Pricing for B2B Customers. "Autonomous AI Agents" as SAAS Subscription + Setup Fees',
"4.9. Autonomous Al-Agent Workflow Diagram",
"5. Tokenomics, Token Sale, Nodes sale","5.1. FAIR LAUNCH","5.2. For VCs: Token Buy",
"5.3. For VCs: Equity Sale","5.4. Designed for Tier-1 CEXs","5.5. $AAA Token Utility",
"5.6. Genesis Launch","5.6. TGE — Q3","5.7. Tokenomics","5.8. Diamond Hands Distribution Program",
"5.9. Revenue Share, Token Burning & Buyback Program","5.10. Inflation & Deflation",
"5.11. Sustainable Economy for Token Growth","5.12. Monetization",
"5.13. AI Agents as NFTs: Ownership, Privacy & Profit Sharing",
"5.14. Treasury Management in AAA C(H+A)RM",
'6. Roadmap - "This is a Way"',"6.1. 2022 - Research, Networking & Early Development",
"6.2. 2023 - Building the Foundations","6.3. 2024 - AI Launchpad Development & Product Infrastructure",
"6.4. 2025 - Official AI Launchpad & Full Ecosystem Growth",
"6.5. 2026 - Scaling, Adoption & Enterprise AI Deployment","6.6. Roadmap (Q-based)",
"6.7. Go-to-Market strategy AAA CRM",
"7. The Team, The DAO, The Roles","7.1. Сustodians \ Treasury Co-Signers","7.2. Co-founder",
"7.3. Advisor for the Laboratory","7.4. Mentor for Projects","7.5. Judge at DemoDays",
"7.6. Syndicate Member","7.7. Guidelines for Candidates Applying to Be a Member at Palo Alto Lab",
"7.8. Team",
"8. Frequently Asked Questions","8.1. Community Questions (FAQ)","8.2. Startup Questions (FAQ)",
"8.3. Investor Questions (FAQ)","8.4. Advisory Questions (FAQ)",
"9. Official Links","10. References that sparked our inspiration",
]
def slug(t):
    s=t.lower()
    s=re.sub(r"[^a-z0-9.+]+","-",s)   # keep letters/digits/dot/plus; others -> -
    s=re.sub(r"-+","-",s).strip("-")
    return s
rows=[{"n":i,"title":t,"slug":slug(t),"url":BASE+slug(t)} for i,t in enumerate(titles)]
json.dump(rows, open("urls.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("total pages:", len(rows))
for r in rows[:20]: print(r["slug"])
