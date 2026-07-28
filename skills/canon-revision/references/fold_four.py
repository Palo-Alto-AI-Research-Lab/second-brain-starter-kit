# -*- coding: utf-8 -*-
"""Structural fold of 4 mechanics-heavy sections in live CLAUDE.md (trigger+essence+pointer)."""
import os, hashlib

P = os.path.expanduser(r"~\.claude\CLAUDE.md")
raw = open(P, "rb").read()
nl = "\r\n" if b"\r\n" in raw else "\n"
text = raw.decode("utf-8-sig").replace("\r\n", "\n")

FOLDS = {
"### §7.7 Координация перед правкой sensitive/общего; крупная работа → табличка ON AIR":
"Перед правкой sensitive/общего (always-loaded CLAUDE.md/MEMORY.md, standing память, Библия, конфиг `~/.claude`, общие БД, синк-узлы `concept-*`/`person-*`) — two-tier: (1) скан параллельных сессий (`onair.py check --zone` + `_active-sessions` + `/inbox` + свежие `*.sync-conflict`); (2) чисто → lease TTL~15мин → правка → propagate+verify [[one-system-propagate]]; (3) коллизия → НЕ править параллельно: договориться в 03 / разделить, тупик → tie-break/QQQ. КРУПНАЯ структурная работа → сперва табличка `onair.py declare --zone <из onair zones> --mode exclusive|collab|fyi`; чек и мид-сессию; свою закрывать `onair close` (/retro закрывает хвосты); мелкие правки не декларируем (alert-fatigue). ⚠️ Тот-же-комп опаснее (нет sync-conflict-страховки, тихий clobber); БД → SQLite-транзакции/WAL, не lease. Канон: память `onair-board` + `reglament-koordinatsiya-sessiy-pered-pravkoy-sensitive-failov` + `02-Decisions\\decision-2026-07-05-onair-work-declaration-board` + [[coordinate-sessions-before-sensitive-edit]], [[consensus-active-session-marking]]; сестра [[prescan-coordination-before-outbound]].",

"### §7.8 Межмашинный консенсус: триггер «03» + свои машины Антона = равные пиры":
"«03»/«003» (не путать с «02» = эскалация К Антону) или «договоритесь сами / найдите консенсус» (любой регистр; скилл `/03`) = мандат: пиры-Claude сами договариваются и сами исполняют, без Антона-курьера. Анонсируй-и-иди: «🤝 иду согласовывать…» + сразу `consensus.py propose`; сперва консенсус (propose→counter→accept→commit + VERIFY ≥2), потом действие. Свои машины (хаб · ноут · Якорь-VPS · MAC1) = равные пиры: обратимое Tier-0/1 исполняется по согласию, одобрения хаба не ждём. Антона будим ровно на 2 воротах: (1) Tier-2 → QQQ; (2) тупик за round-cap → tie-break Якорьа (Якорь = координатор+хранилище истины+tie-break; мёртв/не способен → QQQ; leader-down >70мин → арбитр-на-тик хаб). ⚠️ Не путать с [[machine-governance-leader-follower]] (ЧУЖИЕ машины семьи) и с §9.2 (субагенты/человеко-сессии). Канон: `reglament-trigger-03-avtonomnyy-konsensus-mashin` + [[multi-machine-auto-consensus]] (движок `~/.claude/scripts/consensus.py`), [[own-fleet-peer-equality]], [[vps-anchor-node]].",

"### §3.1 Нужен ОК Антона, а он не у терминала → пиши в 02, он жмёт `+`/`QQQ`":
"Упёрся в «нужен ОК» (Tier-2 / делать-не-делать), Антон не у терминала → не жду молча: аск ТОЛЬКО через `~/.claude/scripts/approval.py ask` (от руки в чат — тонут) в «02 POLICE» (TG `-6491142604`; канал стерилен — только вопросы Антону, гейт `lint_approval_routing.py`). Да = `+`/`QQQ`/`да`; нет = `NO`/`НЕТ`/`СТОП` → ACK «✅ принял #id»; молчание → `approval.py due` перепинг → escalate; бэклог >24ч не воскрешаем. ⭐ Типизация (anton 14.07): A внутреннее/флот-обратимое · B наш контент в наши каналы · C короткое исходящее 3-м лицам по делу — решаю САМ как кофаундер (журнал approvals.db, отчёт постфактум), в 02 НЕ шлю; в 02 только D «нужны руки Антона» (2FA/UAC/пароль; формулировка = клик-путь) и E серьёзное (деньги · невозвратное удаление · секреты 3-м лицам · юр.обязательства · масс-рассылка · новый пир); сомнение C-vs-E → E. Подписанты: Антон + Рита + Нина (сила = ответ с их аккаунта). Канон: `reglament-distancionnoe-odobrenie-qqq` (+ §Поправка 14.07) + [[remote-approval-qqq]] (конверт, id каналов, multi-approver, форензика).",

"### §9.2 Параллельность — три этажа: субагенты · человеко-сессии · выгрузка дрифта":
"Помнить про агентов обязан я, на каждой задаче (расширение RECALL). ① СУБАГЕНТЫ в сессии [[multi-agent-offer-reflex]]: ответили дёшево (SQL/grep/RAG) → без агентов; Решение·Сравнение·Анализ·Синтез, где независимые линзы материально улучшат → авто-запуск ~2 Sonnet read-only (advocate↔skeptic + синтез) с объявлением строкой «🤝 Запускаю…»; оффер+спрос (`+`) при записи/отправке · ≥3 агентах/долго/дорого · стратегически-необратимом (→ R+DR) · деньги/секреты/Tier-2. ② ДЕКОМПОЗИЦИЯ на человеко-сессии [[decompose-into-parallel-sessions]]: слабо-связанные куски (не дерутся за файлы · не влезает в окно) → предлагаю сам + paste-ready сиды (Outcome·Контекст·Scope·Deliverable·DoD·не-цели·эскалация), доставка чипом `spawn_task`; потолок ~3 пишущих + 2 ревью; больше/ретраи/кросс-чек → `ultracode`/Workflow; связанные сессии → роли [[multi-agent-role-discipline]] + lease. ③ ДРИФТ [[goal-drift-offload-to-seed-sessions]]: мелочь ≤2мин обратимая → сам по пути; блокирует главную → тут; остальное → сорняк чипом в соседнюю сессию + «⛳ возвращаемся к <цели>»; выданный сид = моя эстафета (журнал `10-Tasks/task-*.md`, на чекине карта «сиды → чего добились»); пожары (данные/безопасность/синк) — не сорняки, чиню сразу; /retro сам делает дрифт-аудит (потолок ~5 чипов). Границы: не пере-дроблю [[ak47-simplicity]]; грунт Sonnet; Tier-2 в силе. Канон: `reglament-proaktivno-predlagay-agentov`, `reglament-dekompozitsiya-zadachi-na-parallelnye-sessii`, `reglament-drift-ot-glavnoy-tseli-sornyaki-v-sosednie-sessii`.",
}

lines = text.split("\n")
# index sections by header line
idx = {}
for i, l in enumerate(lines):
    if l.startswith("### ") or l.startswith("## "):
        idx[l.strip()] = i

out_lines = lines[:]
for hdr, newbody in FOLDS.items():
    if hdr not in idx: raise SystemExit("HEADER NOT FOUND: " + hdr)

# rebuild by walking
result = []
i = 0
folded = 0
while i < len(lines):
    l = lines[i]
    result.append(l)
    if l.strip() in FOLDS:
        # skip old body until next header (## or ###) or EOF
        j = i + 1
        while j < len(lines) and not (lines[j].startswith("### ") or lines[j].startswith("## ")):
            j += 1
        result.append(FOLDS[l.strip()])
        result.append("")
        i = j
        folded += 1
        continue
    i += 1

if folded != len(FOLDS): raise SystemExit("folded %d of %d" % (folded, len(FOLDS)))
new_text = "\n".join(result)
while "\n\n\n" in new_text: new_text = new_text.replace("\n\n\n", "\n\n")
data = new_text.rstrip("\n").encode("utf-8") + nl.encode()
data = new_text.rstrip("\n").replace("\n", nl).encode("utf-8") + nl.encode()
open(P, "wb").write(data)
print("folded:", folded, "| bytes:", len(data), "| KiB: %.1f" % (len(data)/1024))
print("md5:", hashlib.md5(data).hexdigest())
