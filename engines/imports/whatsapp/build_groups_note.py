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
"""Generate the WhatsApp Groups vault note from the DB (labeled active groups)."""
import sqlite3, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"%IMPORTS%\whatsapp\whatsapp_train.db"
NOTE = r"%VAULT%\01-Conversations\WhatsApp\_WhatsApp-Groups.md"

CAT_RU = {
    "household-community": "🏠 Быт и сообщество",
    "family-personal": "👨‍👩‍👧 Семья / личное",
    "services-vendors": "🔧 Подрядчики / услуги",
    "project-windmill": "🌬️ Парк-мельница",
    "work-business": "💼 Работа / бизнес",
    "longevity-health": "🧬 Долголетие / здоровье",
    "crypto-web3": "🪙 Крипто / Web3",
    "other": "📦 Прочее",
}
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
groups = [dict(r) for r in con.execute(
    "SELECT * FROM chats WHERE is_group=1 AND named=2 ORDER BY category, n_mine DESC")]
numeric = con.execute("SELECT COUNT(*) FROM chats WHERE is_group=1 AND named=0").fetchone()[0]
con.close()

by_cat = {}
for g in groups:
    by_cat.setdefault(g["category"], []).append(g)

lines = []
lines.append("---")
lines.append('title: "WhatsApp — группы (активные, размечены по содержимому)"')
lines.append('aliases: ["WhatsApp Groups", "Группы WhatsApp"]')
lines.append("date: 2026-06-15")
lines.append("type: whatsapp-index")
lines.append("source: whatsapp")
lines.append("tags: [whatsapp, groups, index, second-brain]")
lines.append("---")
lines.append("")
lines.append("# 📱 WhatsApp — группы")
lines.append("")
lines.append(f"Активных групп (где Антон пишет): **{len(groups)}** · ещё **{numeric}** пассивных "
             "групп остались номерами (низкая активность).")
lines.append("")
lines.append("> ✎ = **название выведено из содержимого** (живой мост не отдаёт реальный subject групп; "
             "реальные подтянутся после патча сервера на следующем прогоне). Не путать с официальным названием чата.")
lines.append("")
for cat in sorted(by_cat, key=lambda c: -len(by_cat[c])):
    lines.append(f"## {CAT_RU.get(cat, cat)} ({len(by_cat[cat])})")
    lines.append("")
    lines.append("| Группа (✎) | Мои | Всего | Период | Уверен. | О чём |")
    lines.append("|---|--:|--:|---|---|---|")
    for g in by_cat[cat]:
        one = (g.get("one_line") or "").replace("|", "/").replace("\n", " ")
        lines.append(f"| ✎ {g['name']} | {g['n_mine']} | {g['n']} | {g['first']}→{g['last']} "
                     f"| {g.get('conf','')} | {one} |")
    lines.append("")
lines.append("---")
lines.append("Данные: `whatsapp_train.db` · дашборд: [[WhatsApp-Dashboard]] · хаб: [[_WhatsApp-MOC]]")
lines.append("")

os.makedirs(os.path.dirname(NOTE), exist_ok=True)
open(NOTE, "w", encoding="utf-8").write("\n".join(lines))
print(f"wrote {NOTE} : {len(groups)} groups in {len(by_cat)} categories")
