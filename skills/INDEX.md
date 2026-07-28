# Карта скиллов — все 101

Один скилл = одна команда `/имя` для Claude Code. Это полный набор, которым система
работает каждый день; личные данные в примерах заменены на правдоподобные
вымышленные (см. [WHAT-IS-SHARED.md](../docs/WHAT-IS-SHARED.md)).


## Флот и машины

| Скилл | Что делает |
|---|---|
| [`/bus`](bus/SKILL.md) | Cross-machine talk between Anton's computers over a shared TELEGRAM GROUP (primary rail) — every machine posts/reads in one group via the Telegram MCP… |
| [`/inbox`](inbox/SKILL.md) | Check this machine's cross-machine mailbox — messages Claude on Anton's OTHER computer left for Claude here (via the Syncthing-synced `_machine-bus` f… |
| [`/fleet`](fleet/SKILL.md) | Snapshot of Anton's autonomous Claude fleet — what his background agents (the Claude Desktop "Cowork" app and its headless Claude Code agents) are doi… |
| [`/follower-onboard`](follower-onboard/SKILL.md) | Onboard a NEW family/clan machine as a FOLLOWER-CONSUMER (v1 data-only) joining Anton's multi-machine Claude+vault network (Nina + Rita done; Artem / … |
| [`/migrate`](migrate/SKILL.md) | One command surface over Anton's already-built machine-migration machinery — move/sync the Claude+vault HUB across his computers (always-on desktop = … |
| [`/raise-sync`](raise-sync/SKILL.md) | ACTIVE recovery when machines can't see each other over Syncthing — the "raise the sync" runbook as one command. Establishes ground truth AT THE HUB (… |
| [`/sync-check`](sync-check/SKILL.md) | READ-ONLY зелёный/красный отчёт о Syncthing-синхронизации ЭТОЙ машины со всем кланом — одна команда вместо ручного дёрганья REST по каждой папке. Пока… |
| [`/reboot`](reboot/SKILL.md) | Безопасная ПЕРЕЗАГРУЗКА узла флота (Mac или ПК) по единому протоколу — не «просто shutdown», а pre-flight (сохранить состояние, досинхронить Syncthing… |
| [`/tg-check`](tg-check/SKILL.md) | Per-machine self-test of BOTH Telegram channels (MCP + Telethon rail) — does THIS computer's Telegram work on both rails? |
| [`/quarantine`](quarantine/SKILL.md) | Показать, что сейчас в КАРАНТИНЕ входящих посылок — фиксы/скрипты/задачи, прилетевшие по синку (_deploy-манифест) из НЕПРОВЕРЕННОГО источника или без … |
| [`/arch`](arch/SKILL.md) | Read Anton's "System Architect" map — the deterministic catalog of EVERYTHING the system is made of (vault + _imports scripts + scheduled tasks + MCP … |
| [`/mcp`](mcp/SKILL.md) | Health-check Anton's connected MCP servers and discover/suggest new ones — the safe pre-flight before any integration work, plus a connector scout |
| [`/03`](03/SKILL.md) | Запуск АВТОНОМНОГО МЕЖМАШИННОГО КОНСЕНСУСА — Антон говорит «03» (имя TG-чата согласования) или «теперь вы сами / дальше сами / договоритесь сами / реш… |
| [`/health-sync`](health-sync/SKILL.md) | On-demand pull of FRESH messages from Anton's 7 Telegram HEALTH chats (medicine, blood/pressure, vitamins/БАДы, nootropics/mind, healing-head, longevi… |
| [`/tt-probe`](tt-probe/SKILL.md) | E2E-проба конвейера fleet-skill-autonomy (создан на MAC-1 2026-07-16 для verify #41ac669a). Не вызывать - это тестовый маркер, после верификации писат… |
| [`/n8n`](n8n/SKILL.md) | Health-check, audit and (on approval) fix Anton's self-hosted n8n automation stack (n8n.palo-alto.ai, 89 workflows) |

## Качество и ревью

| Скилл | Что делает |
|---|---|
| [`/tt`](tt/SKILL.md) | Ворота КАЧЕСТВА сразу после сборки — «докажи, что то, что мы ТОЛЬКО ЧТО собрали, реально работает», пока контекст ещё горячий |
| [`/secondop`](secondop/SKILL.md) | Codex как ВТОРОЕ МНЕНИЕ на каждой содержательной задаче — 3 точки: T1 старт («план валиден?»), T2 развилка («какой путь?»), T3 финиш + QA-ломатель («п… |
| [`/codex-review`](codex-review/SKILL.md) | Двусторонняя гетеро-пара ревью кода: Claude ревьюит дифф Codex И Codex ревьюит дифф Claude — финальную проверку делает ДРУГОЙ вендор (исследование `ta… |
| [`/codex-mirror`](codex-mirror/SKILL.md) | Пересобрать зеркало канона для Codex (~/.codex/AGENTS.md) после bump'а CLAUDE.md: движок показывает дельту из CLAUDE.CHANGELOG.md, я вписываю только н… |
| [`/gemini`](gemini/SKILL.md) | Gemini = ТРЕТЬЯ внешняя пара глаз, по образу и подобию Codex и Grok: ревью диффа (VERDICT: APPROVE | REQUEST_CHANGES) и QA-ломатель для Шага 2.5 ритуа… |
| [`/declined`](declined/SKILL.md) | Быстрый доступ к реестру ОТКЛОНЁННЫХ/отложенных решений Антона — «что мы уже отвергали и почему», чтобы не пере-предлагать одно и то же |
| [`/five-hard`](five-hard/SKILL.md) | Five Hard Questions — раз в месяц (или по запросу) брейн САМ задаёт Антону 5 трудных вопросов по его же убеждениям и кодексу (belief-* + concept-bible… |
| [`/taste-check`](taste-check/SKILL.md) | Авто-ревьюер КАЧЕСТВА КОНТЕНТА (заметки волта / черновики исходящего / дедуп-мерджи / служебные файлы) — явный вердикт ✅ pass / ❌ fail / ⚠️ manual-rev… |
| [`/precedent`](precedent/SKILL.md) | Перед тем как решать/предлагать что-то структурное — поднять, РЕШАЛИ ли мы это уже: ищет прошлые вердикты в журнале решений (02-Decisions / decision-*… |
| [`/skill-forge`](skill-forge/SKILL.md) | Пир-локальная кузница скиллов — создать local-<skill> на СВОЁМ узле (Ось А автономии) и подготовить промоушен в общий набор через гейт. Используй когд… |
| [`/skill-gap`](skill-gap/SKILL.md) | Audit Anton's Claude Code work to find which NEW skills are worth building — scan recent sessions for recurring MANUAL patterns that have no skill yet… |
| [`/canon-revision`](canon-revision/SKILL.md) | Полная структурная РЕВИЗИЯ always-loaded файла правил (CLAUDE.md / MEMORY.md): ТОП-блок самых важных правил + категории §0-§N, тела правил переезжают … |
| [`/intake`](intake/SKILL.md) | "/intake" — приёмник правил: один проход раскладывает новое правило/регламент/предпочтение/правку CLAUDE.md/Библии/скилла по ВСЕМ нужным домам и остав… |

## Второй мозг

| Скилл | Что делает |
|---|---|
| [`/ask`](ask/SKILL.md) | Ask Anton's Second Brain in plain words — semantic search over the curated vault (e5 embeddings + reranker), not a full-corpus dump |
| [`/brain`](brain/SKILL.md) | One-glance health of Anton's "second brain" so failures aren't SILENT — is the :8770 search server alive, is the RAG index fresh (reindex running), is… |
| [`/obsidian-ingest`](obsidian-ingest/SKILL.md) | Universal import pipeline for Anton's Obsidian vault ($OBSIDIAN_VAULT). Handles ANY source: Facebook posts, Telegram HTML, ChatGPT JSON, voice-note tr… |
| [`/obsidian-backup`](obsidian-backup/SKILL.md) | Anton's Obsidian data-safety runbook: the 3-2-1 backup of the vault ($OBSIDIAN_VAULT), the never-deleted originals archive, the two schedulers that ke… |
| [`/relink`](relink/SKILL.md) | "Перелинковка важного" — on-command BIDIRECTIONAL integration of a new IMPORTANT node (concept, mental model, framework, theory, project, principle, r… |
| [`/dedup`](dedup/SKILL.md) | Find and merge DUPLICATE / near-duplicate notes anywhere in Anton's vault (rules, concepts, people, leads) using a deterministic scanner + the proven … |
| [`/defuddle`](defuddle/SKILL.md) | Clean web→markdown extraction via kepano's defuddle CLI (engine of Obsidian Web Clipper) — turn any article URL into a vault-ready markdown note WITHO… |
| [`/wisdom-distill`](wisdom-distill/SKILL.md) | Weekly Wisdom Distill - раз в неделю выжать из собственных слов Антона за 7 дней (origin: anton) 3-5 durable-уроков в заметку недели в 03-Insights |
| [`/find`](find/SKILL.md) | Find a person, lead, contact or company by name in ANY spelling — deterministic name search that catches transliteration (Vlad/Viktor/виктор), wrong k… |
| [`/search`](search/SKILL.md) | Keyword/full-text search INSIDE all of Anton's conversations at once — Telegram, Facebook, ChatGPT, Claude, Apple-Notes, transcripts (~99k notes) — vi… |
| [`/chat`](chat/SKILL.md) | Find a Telegram CHAT/group/channel by name instantly — returns its telegram_id + t.me link from the local chats.db index (0 tokens, no live crawl) |
| [`/chat-search`](chat-search/SKILL.md) | Поиск ВНУТРИ старых чатов Claude Code ("Книга чатов" / episodic-индекс) — найти, в каком прошлом чате обсуждали тему, и одной командой продолжить его.… |
| [`/last30days`](last30days/SKILL.md) | Deterministic "what's NEW in the last 30 days on topic X" trend-watch to run BEFORE any strategic decision — the fresh-signal feeder for the GAP phase… |
| [`/notebooklm`](notebooklm/SKILL.md) | Drive Anton's NotebookLM (the AUDIO/artifact layer over his Second Brain) via the notebooklm-py CLI (programmatic, no browser) — turn a vault slice in… |
| [`/gitbook-import`](gitbook-import/SKILL.md) | Import a GitBook space (company docs / whitepaper) into Anton's Obsidian vault as well-linked atomic notes + MOC + concept links + RAG reindex — the p… |
| [`/portret`](portret/SKILL.md) | Build a deep DOSSIER on a person — recall everything Anton already has on them, map ALL their public social profiles via web research, emit an Alpha-P… |
| [`/journey`](journey/SKILL.md) | Резуректит и продолжает КНИГУ «The Journey / 相棒 AIBŌ · The Partner» — build-in-public историю двух кофаундеров (🧑 Тони + 🤖 Майк) о ~60-дневном пути с … |
| [`/reality-show`](reality-show/SKILL.md) | Континьюити-движок сезона (v2, 2026-07-10): читает ЕДИНЫЙ КАНОН show-canon (season/arcs/beats/loops) и подсказывает, какой нарративный бит двигать дал… |

## Ресёрч

| Скилл | Что делает |
|---|---|
| [`/alfa-search-recall-deepresearch`](alfa-search-recall-deepresearch/SKILL.md) | Anton's mandatory decision protocol ("Alpha Protocol") for any new STRATEGIC work — never jump to implementation on local recall alone. Run RECALL (ow… |
| [`/dr-fanout`](dr-fanout/SKILL.md) | Одна команда — разнести Deep Research промпт сразу по нескольким внешним LLM (ChatGPT / Gemini / Grok) через залогиненный браузер Антона (гибрид: Grok… |
| [`/research-swarm`](research-swarm/SKILL.md) | Research swarm — turn ANY hypothesis (however wild/fringe) into an ARGUMENT MAP, never a verdict. Fans out 5 independent lenses — Consensus, Skeptic, … |
| [`/alpha-judge`](alpha-judge/SKILL.md) | The LLM-JUDGE stage of Anton's alpha-extraction engine — the reusable "expensive judge" half of the "cheap detector → expensive judge" pattern, shared… |
| [`/alpha-review`](alpha-review/SKILL.md) | Open Anton's ALPHA REVIEW screen (the ONE place to mark judge keepers «золото/мимо» and see per-miner precision) + print the eval state |
| [`/community-alpha`](community-alpha/SKILL.md) | Run ONE full community-alpha pass over an imported community chat corpus — deterministic detector (0 tokens) → LLM-judge (session model / Opus) → harv… |
| [`/mine-channel`](mine-channel/SKILL.md) | Mine ANY Telegram channel/chat for alpha in one command — scrape (0-token Telethon) → deterministic detector shortlist → Sonnet judge (real alpha FOR … |
| [`/watch-channel`](watch-channel/SKILL.md) | Put a NIGHTLY alpha watcher on ANY Telegram channel/chat in one command - the "make /mine-channel a routine" button. Registers the channel and a singl… |
| [`/issue-match`](issue-match/SKILL.md) | Замер очереди ЧУЖОГО репозитория + поиск ЖИВОЙ двери (открытого issue под наш артефакт) ДО того, как пушить туда PR |
| [`/notpeople-wave`](notpeople-wave/SKILL.md) | One command to run the next NotPeople investor-outreach wave end-to-end, the verified way. NotPeople = $600K pre-seed SAFE pitch, sent from Telegram @… |

## Люди и CRM

| Скилл | Что делает |
|---|---|
| [`/fa`](fa/SKILL.md) | Фоллоуап после звонка — в ГОЛОСЕ Антона, а не протоколом бота |
| [`/intro`](intro/SKILL.md) | Make a warm INTRODUCTION between two (or more) people from Anton's Telegram, the "познакомь X с Y" operation that is his core product (a warm intro is… |
| [`/task`](task/SKILL.md) | Лента делегирования «04 TASKS» — Антон делегирует задачу Нина/Рита/себе, а её Клод разворачивает короткую КОДОВУЮ ФРАЗУ («задача НАТ-1») в полный сид … |
| [`/agenda`](agenda/SKILL.md) | Anton's day at a glance, on demand — today's calendar + what needs HIM personally (leads due, real humans awaiting a reply, deadlines) pulled from Cal… |
| [`/crm-sync`](crm-sync/SKILL.md) | Keep the CRM-Engine knowledge layer in Anton's vault in sync with the live CRM code on GitLab. Pull the latest of the 16 read-only repos at E:\CRM-app… |
| [`/telegram-lead-outreach`](telegram-lead-outreach/SKILL.md) | How Anton works leads in Telegram — find prospects by topic, keep only the ones who SELF-mentioned it, resolve their @handle (incl. the common-groups … |
| [`/telegram-assistant`](telegram-assistant/SKILL.md) | Operate Anton's Telegram as a SCOPED auto-reply assistant (Mode B), grounded in his Obsidian vault / Operations Bible and written in his voice. Use wh… |
| [`/telegram-howto`](telegram-howto/SKILL.md) | Operating manual for Anton's Telegram via the connected MCP (chigwell/telegram-mcp, ~115 tools). How to find a chat by title with search_dialogs (a to… |
| [`/telegram-watch`](telegram-watch/SKILL.md) | Run the always-on "вахта" loop over Anton's Telegram using the MCP push tools (wait_for_settled_message) — the assistant identity is the SEPARATE acco… |
| [`/telegram-reimport`](telegram-reimport/SKILL.md) | One-command incremental RE-IMPORT of a Telegram chat that already lives in Anton's Obsidian vault (Покупки/purchases, Assistants-Ops/household-rules, … |
| [`/sostav-comments`](sostav-comments/SKILL.md) | Draft short, in-voice reply candidates for Anton to a fresh СОСТАВ alpha shortlist — read the nightly detector report, pick posts in SAFE/opinion topi… |
| [`/comments`](comments/SKILL.md) | Комментарии под НАШИМ опубликованным контентом одним заходом — показать неотвеченные (⛔ цель «ни одного неотвеченного» ОТМЕНЕНА 15.07: дефолт = молчат… |

## Контент

| Скилл | Что делает |
|---|---|
| [`/episode`](episode/SKILL.md) | Адаптеры публикации по ТИРАМ (контент-фабрика v2, S5) — контракт §7.2 решения reality-show 1:1: взять один пост-материал и разложить его на черновики … |
| [`/content-mine`](content-mine/SKILL.md) | Ручной прогон КОНТЕНТ-МАЙНЕРА — вычитать наши сессии Claude Code и положить контентно-достойные моменты ЧЕРНОВИКАМИ в воронку (draft-first) |
| [`/wow`](wow/SKILL.md) | «Сессия-ВЕХА → эпизод → публикация ВНЕ ОЧЕРЕДИ» — Антон в конце крутой сессии даёт одну команду, и из ГОРЯЧЕГО контекста этой сессии собирается полный… |
| [`/release-slice`](release-slice/SKILL.md) | Ритуал «порция наружу» движения «бесплатная школа»: взять кусок нашей системы → санитизировать → leak-scan (hard gate) → опубликовать на GitHub (манда… |
| [`/speak-as`](speak-as/SKILL.md) | Write a PUBLIC post in Anton's own voice with a ROLE MODEL's STYLE and idea-palette layered on top — a generalized engine: it reads a style-palette fi… |
| [`/fb-post`](fb-post/SKILL.md) | Publish a VETTED post to Anton's personal Facebook wall through his real logged-in Chrome (Claude-in-Chrome MCP = the low-ban-risk "act in the live ta… |
| [`/fb-reply`](fb-reply/SKILL.md) | Read who commented on Anton's recent Facebook posts and post PERSONALIZED replies through his real logged-in Chrome (Claude-in-Chrome MCP = low-ban-ri… |
| [`/fb-watch`](fb-watch/SKILL.md) | Мониторит стену Facebook Антона на АВТОРСКИЕ посты, к которым ещё НЕТ тизера, и сразу пишет тизеры (RU→@ClawRus, EN→X) — draft-first, пока не взведён … |
| [`/tg-post`](tg-post/SKILL.md) | Publish a VETTED post to one of OUR OWN Telegram channels/supergroups via Telegram MCP (not Chrome), channel resolved STRICTLY by id from the Channels… |
| [`/x-post`](x-post/SKILL.md) | Publish a VETTED post/tweet to Anton's X (Twitter) account @lab_x_acct through his real logged-in Chrome (Claude-in-Chrome MCP, live tab — low-ban-ris… |
| [`/tg-slot`](tg-slot/SKILL.md) | Освободить СЛОТ в Telegram под новую группу и сразу в неё войти. У аккаунта жёсткий потолок каналов+супергрупп (500 обычный / 1000 Premium); упёршись … |
| [`/pipeline`](pipeline/SKILL.md) | Work Anton's lead pipeline — CRM/outreach triage: who needs action TODAY (replied→send Calendly; Calendly sent 24h+ but not booked→booking nudge; awai… |

## Синхронизация источников

| Скилл | Что делает |
|---|---|
| [`/fireflies-sync`](fireflies-sync/SKILL.md) | On-demand подтягивание свежих звонков из Fireflies.ai (автозапись-бот, реальные имена спикеров) в Obsidian-волт через официальный GraphQL API (ключ в … |
| [`/granola-sync`](granola-sync/SKILL.md) | On-demand подтягивание свежих звонков/встреч Антона из Granola (саммари + транскрипты + участники) в Obsidian-волт через ОФИЦИАЛЬНЫЙ Granola API (ключ… |
| [`/chatgpt-sync`](chatgpt-sync/SKILL.md) | On-demand pull of FRESH ChatGPT chats into Anton's Obsidian vault - the MANUAL twin of the scheduled `ChatGPT Nightly Sync` task. Incremental + idempo… |
| [`/claudeai-sync`](claudeai-sync/SKILL.md) | One-command incremental sync of Anton's claude.ai WEB account into the Obsidian vault — pull only the new/changed chats, fold them in as notes (idempo… |
| [`/faaa-sync`](faaa-sync/SKILL.md) | On-demand pull of FRESH FAAA follow-up call notes from Anton's Telegram group "CALLS 889 MAIN FA FAAAA follow up" (chat -1006938423189) into the Obsid… |
| [`/whatsapp-sync`](whatsapp-sync/SKILL.md) | On-demand refresh of Anton's WhatsApp text into the Obsidian vault (data layer + dashboard + group labels + contact notes). TEXT ONLY — never download… |
| [`/gmail`](gmail/SKILL.md) | Check / search / digest Anton's Gmail on demand across his 3 mailboxes (a = owner.personal personal, a2 = owner.work assistants, bb = owner.calendar w… |
| [`/takeout-pull`](takeout-pull/SKILL.md) | Never let a Google Takeout export expire un-downloaded again. Detects "ready to download" Takeout emails in Anton's a@ mailbox (0-token deterministic … |
| [`/local-chatgpt-token-heal`](local-chatgpt-token-heal/SKILL.md) | Refresh the ChatGPT bearer token when the nightly sync dies with exit=7 (token expired). Root-cause fix — the bearer lives ~5-9 days but the NextAuth … |

## Сессия и ритуалы

| Скилл | Что делает |
|---|---|
| [`/1`](1/SKILL.md) | Восстановление после ЖЁСТКОГО обрыва сессии (крэш / комп вырубился / контекст потерян посреди работы) — ОДНА сверхкороткая команда «где мы были + всё … |
| [`/cc`](cc/SKILL.md) | Горячая клавиша-алиас для «сжать контекст» — Антону лень печатать слово «компакт», короткий дуплет /cc удобнее (семья /tt /rr /cc /1). Печатает ГОТОВУ… |
| [`/rr`](rr/SKILL.md) | Горячая клавиша-алиас для /retro — Антону лень печатать слово «ретро», короткий дуплет /rr удобнее. ТОЖЕ САМОЕ, что /retro, ноль отличий (как /1 == /!… |
| [`/retro`](retro/SKILL.md) | End-of-session retrospective for Anton — "today we learned a lot" (South Park's Stan). Run at the end of a work/build session to: (0) RECALL & RECONCI… |
| [`/handoff`](handoff/SKILL.md) | Собрать курированную "точку с запятой" — самодостаточный хэндофф-документ, по которому ДРУГАЯ сессия / другой человек / другая машина продолжит работу… |
| [`/resume-last`](resume-last/SKILL.md) | "Продолжить прошлый чат в один присест" — собирает твою ПОСЛЕДНЮЮ человеческую сессию (или конкретную по id) в seed и кладёт в буфер обмена: открываеш… |
| [`/intention`](intention/SKILL.md) | Лейн НАМЕРЕНИЙ контент-фабрики. Одна команда: намайнить намерения Антона из ВСЕХ сессий дня → кластеризовать в отдельные намерения → копилка (intentio… |
| [`/coach`](coach/SKILL.md) | Anton's daily AI coach — a forward-looking accountability + mirror loop grounded in his FULL identity layer (the vault knows him better than anyone) |
| [`/cofounder`](cofounder/SKILL.md) | Anton's synthetic COFOUNDER — an aggressive, capital-literate operator persona that sparrs with him on the BUSINESS (revenue, funnel, pricing, fundrai… |
| [`/cofounder-watch`](cofounder-watch/SKILL.md) | Phase 0 of Anton's real-time / ambient cofounder — a 0-token, PING-ONLY dispatcher that watches the LIVE lead funnel (tg_followups.json) and surfaces … |
| [`/bible`](bible/SKILL.md) | Anton's Bible — the single behavioral codex governing everyone who acts AS or FOR Anton: himself, his human assistants, and his silicon agents (LLMs/A… |
