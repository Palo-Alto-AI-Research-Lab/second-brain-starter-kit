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
r"""alpha_review_server.py — the ONE screen where Anton says "это золото / это мимо".

The alpha-extraction engine has 10 deterministic detectors -> a shared LLM-judge ->
10 separate `<miner>-judged-latest.md` reports. This was the MISSING last mile: a
single surface that gathers every judge KEEPER across all miners, lets Anton mark each
✅ золото / ❌ мимо / ⏭ потом with one click, and computes the eval the Deep Research
demanded — per-miner PRECISION (did the judge surface real value?) so the engine can be
tuned by evidence, not vibes.

Pure stdlib (http.server + sqlite3), same house style as ask_server.py / search_server.py.
Additive only: reads the judged .md files (read-only, via alpha_harvest) and stores Anton's
verdicts in its OWN alpha_review.db.verdicts table. Touches NO detector, ledger, or vault note.

  python alpha_review_server.py            # auto-harvest, serve http://127.0.0.1:8772
  python alpha_review_server.py --port 8780
  python alpha_review_server.py --no-harvest   # skip the startup re-harvest

Token-cheap: 0 LLM calls. The expensive judging already happened upstream.
"""
import sys, os, json, sqlite3
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alpha_harvest as ah
try:
    import alpha_security_lens as asl   # 2nd lens: provenance/security (additive, read-only)
except Exception:
    asl = None

DB = ah.DB
PORT = 8772
VAULT = "Owner-Knowledge"            # Obsidian vault name for obsidian:// deep-links
HOME_QUEUE = os.path.join(ah.CAND, "home-queue-latest.md")
# eval-loop: the precision fix each judge ALREADY named in its report — surfaced as a
# 💡 hint when a miner's precision is low (≥3 judged & <50%). Static map (AK-47, no ML).
SUGGESTIONS = {
    "novelty": "резать reference-карточки (undated foreign-medical) — фильтр `_is_low_value_for_novelty` уже в novelty_scan; поднять порог.",
    "bets": "OSINT-файлы о третьих лицах + ретроспектива постфактум (date_recorded>deadline) + цитаты третьих лиц → 🗑 на стадии детектора.",
    "openq": "Detector B (эвристика из чат-логов) шумная — фильтровать сервисные фрагменты Claude (вопрос-к-Антону ≠ вопрос Антона).",
    "contradictions": "dedup-vs-home гейт (уже в /alpha-judge) + ловить belief↔BEHAVIOR, не belief↔belief.",
    "stance": "dedup-vs-home vs `insight-contradictions` — отсекать уточнения, держать только датированный сдвиг А→Б.",
    "identity": "dedup-vs-home vs `_Self-Bible-MOC` (110 кандидатов часто рестейтят 117 правил).",
    "recurring": "со-частотность служебных слов — поднять порог dist_years × dist_notes.",
    "bridge": "случайные со-упоминания — поднять порог pair_rarity (держать неочевидные мосты).",
    "leadsignal": "raw score обманчив — взвешивать recency инбаунда > объём; убирать уже-в-воронке.",
    "orphan": "стабы/path-not-found → 🗑; держать только дозревшие заметки с маркерами.",
}
# friendly labels + the home note each miner feeds (shown on the card)
MINER_LABEL = {
    "bets": "🎯 Забытые ставки", "contradictions": "⚔️ Противоречия",
    "stance": "🔄 Смена взглядов", "bridge": "🌉 Кросс-домен мосты",
    "recurring": "🔁 Повторяющиеся убеждения", "leadsignal": "📇 Лид-сигналы",
    "novelty": "✨ Новизна", "identity": "🪞 Идентичность",
    "openq": "❓ Открытые вопросы", "orphan": "🧩 Осиротевшие инсайты",
    "lobster": "🦞 LobsterDAO (community)",
    "sostav": "🔒 СОСТАВ (private)",
}
ORDER = ["lobster", "sostav", "contradictions", "stance", "bridge", "recurring",
         "novelty", "identity", "openq", "leadsignal", "orphan", "bets"]

# plain-Russian, ELI5: what THIS KIND of card is + what золото/мимо means here.
# Shown as a header box above each miner group so Anton never decides blind.
MINER_EXPLAIN = {
    "bridge": ("Неожиданная СВЯЗЬ между двумя твоими темами (формат «тема1 × тема2 — идея»).",
               "если связь настоящая и тебе интересно про это подумать",
               "если это просто случайно совпавшие слова"),
    "openq": ("ВОПРОС, который ты где-то задал и не закрыл.",
              "если вопрос живой и ты хочешь на него ответ",
              "если уже неактуально или давно решено"),
    "identity": ("Твой личный ПРИНЦИП/правило о самом себе (иногда записан латиницей).",
                 "если это точно про тебя — в твой личный кодекс",
                 "если это не твоё или сформулировано неточно"),
    "stance": ("Тема, по которой твоё мнение ПОМЕНЯЛОСЬ (было так → стало иначе).",
               "если ты правда передумал и это важно помнить",
               "если мнение не менялось или это выдумка"),
    "contradictions": ("Место, где ты как будто сам себе ПРОТИВОРЕЧИШЬ.",
                       "если противоречие реальное и интересно подумать",
                       "если никакого противоречия на деле нет"),
    "recurring": ("Слово/тема, которая всплывает в твоих заметках ГОДАМИ.",
                  "если это правда твоя стержневая тема",
                  "если это просто частое слово, а не тема"),
    "novelty": ("Редкая, НЕОБЫЧНАЯ идея из твоих заметок.",
                "если свежо и стоит развить",
                "если ничего нового в этом нет"),
    "leadsignal": ("Человек — возможный тёплый КОНТАКТ/лид.",
                   "если стоит написать ему или поднять карточку",
                   "если сейчас не актуально"),
    "orphan": ("Заметка, которая висит ОДНА, без связей с другими.",
               "если ценная — вплести её в общую сеть заметок",
               "если пусть висит или это мусор"),
    "promptdesign": ("Инструмент/гайд про AI, найденный в Telegram-канале «Силиконовый Мешок».",
                     "если нам это полезно и стоит взять в дело",
                     "если не наше или у нас уже есть лучше"),
    "promptchat": ("Инструмент/гайд про AI из чата-обсуждения «Силиконового Мешка».",
                   "если нам это полезно и стоит взять в дело",
                   "если не наше или у нас уже есть лучше"),
    "lobster": ("Находка из крипто-сообщества LobsterDAO.",
                "если это реальная альфа/возможность",
                "если шум"),
    "sostav": ("Находка из закрытого клуба предпринимателей СОСТАВ (приватно).",
               "если ценно (контакт/сделка/интел)",
               "если шум"),
    "bets": ("Прогноз/ставка, которую ты когда-то сделал и забыл проверить.",
             "если стоит вспомнить и проверить — сбылось ли",
             "если это не твоя ставка / ерунда"),
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_eli5(con):
    con.execute("""CREATE TABLE IF NOT EXISTS item_eli5(
        item_hash TEXT PRIMARY KEY, what TEXT, pick TEXT)""")


def load_state():
    con = sqlite3.connect(DB)
    ah.ensure_db(con)
    _ensure_eli5(con)
    verdicts = {r[0]: {"v": r[1], "ts": r[2], "note": (r[3] or "")}
                for r in con.execute("SELECT item_hash, anton_verdict, ts, note FROM verdicts")}
    eli5 = {r[0]: {"what": r[1], "pick": r[2]}
            for r in con.execute("SELECT item_hash, what, pick FROM item_eli5")}
    _ensure_promo(con)
    promoted = {r[0] for r in con.execute("SELECT item_hash FROM promotions")}
    items = []
    for r in con.execute("""SELECT item_hash, miner, home, title, source,
                            judge_verdict, reason, raw, first_seen FROM items"""):
        ih = r[0]
        e = eli5.get(ih, {})
        # 2nd lens = quarantine prism (provenance/security) — additive, never changes the value verdict
        sec = {"risk": "low", "status": "clear", "provenance": "", "tier2": [], "note": ""}
        if asl is not None:
            try:
                sec = asl.assess({"miner": r[1], "title": r[3], "reason": r[6], "raw": r[7]})
            except Exception:
                pass
        items.append({
            "hash": ih, "miner": r[1], "home": r[2], "title": r[3], "source": r[4],
            "judge": r[5], "reason": r[6], "raw": r[7],
            "sec_risk": sec["risk"], "sec_status": sec.get("status", "clear"),
            "sec_prov": sec.get("provenance", ""),
            "sec_tier2": sec.get("tier2", []), "sec_note": sec.get("note", ""),
            "batch": (r[8] or "")[:10],   # nightly-batch day the item first appeared
            "anton": verdicts.get(ih, {}).get("v", ""),
            "promoted": ih in promoted,
            "what": e.get("what", ""), "pick": e.get("pick", ""),
            # mine = a verdict I pre-marked as co-founder (Anton reviews these)
            "mine": verdicts.get(ih, {}).get("note", "").startswith("claude-cofounder"),
            # unseen = my pre-mark that Anton has NOT re-clicked yet (still at the
            # 01:00 night-batch ts; any Anton click bumps ts past the cutoff -> drops out)
            "unseen": (verdicts.get(ih, {}).get("note", "").startswith("claude-cofounder")
                       and verdicts.get(ih, {}).get("ts", "") < "2026-07-04T12:00"),
        })
    con.close()
    # newest batch first inside each (miner, judge) group — stable two-pass sort
    items.sort(key=lambda x: x["batch"], reverse=True)
    items.sort(key=lambda x: (ORDER.index(x["miner"]) if x["miner"] in ORDER else 99,
                              x["judge"] != "ok"))
    return items


def eval_metrics(items):
    by = {}
    for it in items:
        m = it["miner"]
        d = by.setdefault(m, {"miner": m, "label": MINER_LABEL.get(m, m),
                              "surfaced": 0, "gold": 0, "miss": 0, "pending": 0})
        d["surfaced"] += 1
        if it["anton"] == "gold":
            d["gold"] += 1
        elif it["anton"] == "miss":
            d["miss"] += 1
        else:
            d["pending"] += 1
    rows = []
    for m in ORDER:
        if m in by:
            d = by[m]
            judged = d["gold"] + d["miss"]
            d["precision"] = round(d["gold"] / judged, 2) if judged else None
            # eval-loop: low precision with enough evidence -> surface the judge's named fix
            d["suggestText"] = SUGGESTIONS.get(m, "")
            d["suggest"] = (d["suggestText"] if (d["precision"] is not None
                            and judged >= 3 and d["precision"] < 0.5) else "")
            rows.append(d)
    tot_g = sum(d["gold"] for d in rows)
    tot_m = sum(d["miss"] for d in rows)
    total = {"surfaced": sum(d["surfaced"] for d in rows), "gold": tot_g, "miss": tot_m,
             "pending": sum(d["pending"] for d in rows),
             "precision": round(tot_g / (tot_g + tot_m), 2) if (tot_g + tot_m) else None}
    return rows, total


def set_verdict(item_hash, verdict):
    con = sqlite3.connect(DB)
    ah.ensure_db(con)
    miner = con.execute("SELECT miner FROM items WHERE item_hash=?", (item_hash,)).fetchone()
    miner = miner[0] if miner else ""
    if verdict == "clear":
        con.execute("DELETE FROM verdicts WHERE item_hash=?", (item_hash,))
    else:
        con.execute("""INSERT INTO verdicts(item_hash, miner, anton_verdict, note, ts)
            VALUES(?,?,?,?,?) ON CONFLICT(item_hash) DO UPDATE SET
            anton_verdict=excluded.anton_verdict, ts=excluded.ts""",
            (item_hash, miner, verdict, "", _now()))
    con.commit()
    con.close()


def _ensure_promo(con):
    con.execute("""CREATE TABLE IF NOT EXISTS promotions(
        item_hash TEXT PRIMARY KEY, miner TEXT, home TEXT,
        title TEXT, source TEXT, reason TEXT, ts TEXT)""")


def toggle_promote(item_hash):
    """Queue (or un-queue) a gold item for promotion to its home note. Does NOT write
    the vault — only records intent + regenerates the human-readable draft queue file.
    The actual curated-note append stays behind backup -> ДО→ПОСЛЕ -> approve (Tier-2).

    QUARANTINE-PRISM boundary (DR26-07-14-HUB-01 #1+#5): an idea the prism marks 'hold'
    (gate-weakening / injection signature / external carrier payload) MUST NOT enter the
    home-note queue — home notes sync fleet-wide, so promoting poison = writing it into
    shared knowledge. Un-queue is always allowed. Returns {'queued':bool} or {'blocked':True}."""
    con = sqlite3.connect(DB)
    ah.ensure_db(con)
    _ensure_promo(con)
    row = con.execute("""SELECT miner, home, title, source, reason, raw FROM items
                         WHERE item_hash=?""", (item_hash,)).fetchone()
    if not row:
        con.close()
        return {"queued": False}
    already = con.execute("SELECT 1 FROM promotions WHERE item_hash=?", (item_hash,)).fetchone()
    # Only GATE a NEW queue action; always permit removing something already queued.
    if not already and asl is not None:
        try:
            verdict = asl.assess({"miner": row[0], "title": row[2], "reason": row[4], "raw": row[5]})
            if verdict.get("status") == "hold":
                con.close()
                return {"blocked": True, "reason": verdict.get("note", "prism hard-hold")}
        except Exception:
            pass
    exists = already
    if exists:
        con.execute("DELETE FROM promotions WHERE item_hash=?", (item_hash,))
        queued = False
    else:
        con.execute("""INSERT INTO promotions(item_hash, miner, home, title, source, reason, ts)
                       VALUES(?,?,?,?,?,?,?)""",
                    (item_hash, row[0], row[1], row[2], row[3], row[4], _now()))
        queued = True
    con.commit()
    _write_queue(con)
    con.close()
    return {"queued": queued}


def promoted_set():
    con = sqlite3.connect(DB)
    _ensure_promo(con)
    s = {r[0] for r in con.execute("SELECT item_hash FROM promotions")}
    con.close()
    return s


def _write_queue(con):
    """Regenerate the draft queue file, grouped by home note. This file IS the draft —
    when Anton says 'перенеси очередь в дома', the agent does the backup+ДО→ПОСЛЕ append."""
    rows = con.execute("""SELECT p.home, p.miner, p.title, p.source, p.reason, i.reason, i.raw
                          FROM promotions p LEFT JOIN items i ON i.item_hash=p.item_hash
                          ORDER BY p.home, p.miner""").fetchall()
    lines = ["# 🅰️→🏠 Очередь на добавление в home-заметки (ЧЕРНОВИК)",
             "",
             "_Антон пометил эти кипперы как ЗОЛОТО→в дом на экране отбора (alpha_review_server)._",
             "_Это НЕ запись в волт — это список на ручной перенос через `vault_backup` + ДО→ПОСЛЕ._",
             "_Триггер переноса: «перенеси очередь в дома» / `/alpha-judge` step-5._",
             "_🛡️ Карантин-призма: строки с ⛔ HOLD — НЕ переносить в дом до проверки происхождения (дом синкается на флот)._", ""]
    if not rows:
        lines.append("_(очередь пуста)_")
    cur_home = None
    for home, miner, title, source, reason, ireason, iraw in rows:
        if home != cur_home:
            cur_home = home
            lines += ["", f"## → {home}", ""]
        src = f" · 🔗 [[{source}]]" if source else ""
        rsn = f"\n  - _{reason}_" if reason else ""
        hold = ""
        if asl is not None:
            try:
                v = asl.assess({"miner": miner, "title": title, "reason": ireason or reason, "raw": iraw or ""})
                if v.get("status") == "hold":
                    hold = f"\n  - ⛔ **HOLD (карантин-призма):** _{v.get('note','')}_"
            except Exception:
                pass
        lines.append(f"- **[{miner}]** {title}{src}{rsn}{hold}")
    with open(HOME_QUEUE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


PAGE = r"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Альфа — экран отбора золота</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;
--acc:#5b9bff;--gold:#ffc107;--miss:#ff6b8b;--ok:#37d399;--part:#ffb454;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:22px;margin:0 0 3px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
.evalbar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
.ev{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:8px 11px;font-size:12px;min-width:120px}
.ev b{font-size:13px}.ev .pr{float:right;font-variant-numeric:tabular-nums;font-weight:700}
.ev .pr.hi{color:var(--ok)}.ev .pr.lo{color:var(--miss)}.ev .pr.na{color:var(--mut)}
.ev .ln{color:var(--mut);font-size:11px;margin-top:3px}
.ev .sg{color:var(--part);font-size:10.5px;margin-top:5px;line-height:1.35;border-top:1px dashed var(--line);padding-top:4px}
.toolbar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:6px 0 16px}
.chip{font-size:12.5px;color:var(--mut);background:#11141a;border:1px solid var(--line);
border-radius:20px;padding:5px 12px;cursor:pointer;user-select:none}
.chip.on{border-color:var(--acc);color:#fff;background:#16263f}
.chip.unseen{font-size:14px;font-weight:700;color:#1a1206;background:#f0b330;
border-color:#f0b330;padding:7px 16px;box-shadow:0 0 0 2px rgba(240,179,48,.25)}
.chip.unseen.on{color:#1a1206;background:#ffcf5c;border-color:#ffcf5c}
.tot{margin-left:auto;color:var(--mut);font-size:12.5px}
button.rh{background:var(--acc);color:#fff;border:0;border-radius:9px;padding:6px 13px;font-size:12.5px;cursor:pointer}
.grp{margin:18px 0 6px;font-size:14px;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);padding-bottom:5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:12px 15px;margin-bottom:10px}
.card.gold{border-color:var(--gold);background:#1d1a10}
.card.miss{opacity:.55}
.card .top{display:flex;align-items:flex-start;gap:9px;flex-wrap:wrap}
.card .t{font-weight:600;font-size:15px;flex:1;min-width:60%}
.badge{font-size:10.5px;border-radius:5px;padding:1px 7px;white-space:nowrap}
.badge.ok{color:#0c0f14;background:var(--ok)}.badge.partial{color:#0c0f14;background:var(--part)}
.badge.d{color:#9aa4b2;background:#232a38}.badge.d.nw{color:#0c0f14;background:#7dd3fc;font-weight:600}
.badge.mine{color:#0c0f14;background:#c9a0ff;font-weight:600}
.badge.sec-high{color:#0c0f14;background:#ff6b8b;font-weight:700}
.badge.sec-review{color:#0c0f14;background:#ffb454;font-weight:600}
.secnote{margin-top:7px;font-size:12.5px;border-radius:8px;padding:7px 11px;line-height:1.45}
.secnote.sec-high{color:#ffd7de;background:#2a1216;border:1px solid #5a2330}
.secnote.sec-review{color:#ffe6c2;background:#241a0e;border:1px solid #4a3517}
.src{font-size:12px;color:var(--acc);margin-top:4px;word-break:break-all}
.rsn{font-size:12px;color:#8b94a3;margin-top:5px;font-style:italic}
.explain{background:#12202e;border:1px solid #23384a;border-left:4px solid var(--acc);
border-radius:9px;padding:9px 13px;margin:2px 0 12px;font-size:14px;line-height:1.55}
.explain b{color:#dbe8f7}
.crit{margin-top:6px;font-size:13.5px;color:#c3cdd9}
.gg{color:var(--gold);font-weight:700}.mm{color:var(--miss);font-weight:700}
.mt{font-size:11.5px;color:#6b7688;margin-top:5px;font-family:ui-monospace,Consolas,monospace}
.pick{font-size:13px;color:#e7c86b;margin-top:6px}
.acts{display:flex;gap:7px;margin-top:9px;align-items:center}
.acts button{border:1px solid var(--line);background:#11141a;color:var(--ink);border-radius:8px;
padding:5px 12px;font-size:13px;cursor:pointer}
.acts button.g.on{background:var(--gold);color:#0c0f14;border-color:var(--gold);font-weight:700}
.acts button.m.on{background:var(--miss);color:#0c0f14;border-color:var(--miss);font-weight:700}
.acts button.s.on{background:#333;border-color:#444}
.acts button.h{border-color:#3a4658;color:#bcd}
.acts button.h.on{background:#1f3a2a;border-color:var(--ok);color:#bdf0d2;font-weight:700}
.acts .more{margin-left:auto;color:var(--mut);font-size:12px;cursor:pointer;background:none;border:0}
.raw{display:none;white-space:pre-wrap;font:12px/1.45 ui-monospace,Consolas,monospace;
color:#aab3c0;background:#0c0f14;border:1px solid var(--line);border-radius:8px;padding:9px;margin-top:8px}
.empty{color:var(--mut);text-align:center;padding:40px}
</style></head><body><div class="wrap">
<h1>🅰️ Альфа — экран отбора золота</h1>
<div class="sub">Все кипперы 10 майнеров в одном месте. Жми <b>золото</b> / <b>мимо</b> — это и есть eval точности судьи. 0 токенов, ничего не уходит в LLM. Вердикты пишутся в alpha_review.db (волт не трогается).</div>
<div class="evalbar" id="evalbar"></div>
<div class="toolbar" id="toolbar"></div>
<div id="list"></div>
</div><script>
let DATA=__DATA__;
const MINER_ORDER=__ORDER__, MINER_LABEL=__LABEL__, MINER_EXPLAIN=__EXPLAIN__;
let filter=null, onlyPending=false, onlyMine=false, onlyUnseen=false, onlySec=false;
const $=s=>document.querySelector(s);
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

function renderEval(){
  const ev=DATA.eval, t=DATA.total;
  let h=`<div class="ev"><b>ИТОГО</b><span class="pr ${t.precision==null?'na':(t.precision>=.6?'hi':'lo')}">${t.precision==null?'—':Math.round(t.precision*100)+'%'}</span>`+
        `<div class="ln">${t.surfaced} всплыло · ✅${t.gold} ❌${t.miss} · ${t.pending} ждут</div></div>`;
  ev.forEach(d=>{
    const cl=d.precision==null?'na':(d.precision>=.6?'hi':'lo');
    const sg=d.suggest?`<div class="sg">💡 ${esc(d.suggest)}</div>`:'';
    h+=`<div class="ev"><b>${esc(d.label)}</b><span class="pr ${cl}">${d.precision==null?'—':Math.round(d.precision*100)+'%'}</span>`+
       `<div class="ln">${d.surfaced} · ✅${d.gold} ❌${d.miss} · ${d.pending} ждут</div>${sg}</div>`;
  });
  $('#evalbar').innerHTML=h;
}
function renderToolbar(){
  const nunseen=DATA.items.filter(x=>x.unseen).length;
  let h=`<div class="chip unseen ${onlyUnseen?'on':''}" onclick="togU()">⏳ ещё не смотрел ${nunseen}</div>`;
  h+=`<div class="chip ${filter==null?'on':''}" onclick="setF(null)">все</div>`;
  MINER_ORDER.forEach(m=>{const n=DATA.items.filter(x=>x.miner===m).length; if(!n)return;
    h+=`<div class="chip ${filter===m?'on':''}" onclick="setF('${m}')">${esc(MINER_LABEL[m]||m)} ${n}</div>`;});
  h+=`<div class="chip ${onlyPending?'on':''}" onclick="togP()">⏳ только неоценённые</div>`;
  const nmine=DATA.items.filter(x=>x.mine).length;
  h+=`<div class="chip ${onlyMine?'on':''}" onclick="togM()">🤖 предложения Клода ${nmine}</div>`;
  const nsec=DATA.items.filter(x=>x.sec_risk&&x.sec_risk!=='low').length;
  if(nsec) h+=`<div class="chip ${onlySec?'on':''}" onclick="togS()">🛡️ проверить безопасность ${nsec}</div>`;
  h+=`<button class="rh" onclick="reharvest()">🔄 пере-собрать</button>`;
  const done=DATA.items.filter(x=>x.anton==='gold'||x.anton==='miss').length;
  h+=`<span class="tot">${done}/${DATA.items.length} оценено</span>`;
  $('#toolbar').innerHTML=h;
}
function renderList(){
  const NEWEST_BATCH=DATA.items.reduce((m,x)=>(x.batch||'')>m?x.batch:m,'');
  let its=DATA.items.slice();
  if(filter) its=its.filter(x=>x.miner===filter);
  if(onlyPending) its=its.filter(x=>x.anton!=='gold'&&x.anton!=='miss');
  if(onlyMine) its=its.filter(x=>x.mine);
  if(onlySec) its=its.filter(x=>x.sec_risk&&x.sec_risk!=='low');
  if(onlyUnseen) its=its.filter(x=>x.unseen);
  if(!its.length){$('#list').innerHTML='<div class="empty">Пусто — либо всё оценено, либо снять фильтр.</div>';return;}
  let h='', lastM=null;
  its.forEach(it=>{
    if(it.miner!==lastM){lastM=it.miner;
      const ex=MINER_EXPLAIN[it.miner];
      const exbox=ex?`<div class="explain"><b>📂 Что это за находки:</b> ${esc(ex[0])}<div class="crit"><span class="gg">🟡 ЖМИ ЗОЛОТО</span> — ${esc(ex[1])}.<br><span class="mm">🔴 ЖМИ МИМО</span> — ${esc(ex[2])}.</div></div>`:'';
      h+=`<div class="grp">${esc(MINER_LABEL[it.miner]||it.miner)} → дом: ${esc(it.home||'')}</div>${exbox}`;}
    const cardcl=it.anton==='gold'?'gold':(it.anton==='miss'?'miss':'');
    // obsidian:// deep-link: orphan's note is its TITLE (source=folder); others use source
    const tgt=(it.miner==='orphan'||!it.source||it.source.includes('/'))?it.title:it.source;
    const src=it.source?`<div class="src">🔗 <a href="obsidian://open?vault=__VAULT__&file=${encodeURIComponent(tgt)}">${esc(it.source||it.title)}</a></div>`:'';
    const rsn=it.reason?`<div class="rsn">${esc(it.reason)}</div>`:'';
    const promo=it.anton==='gold'?`<button class="h ${it.promoted?'on':''}" onclick="promote('${it.hash}')">${it.promoted?'✓ в очереди →дом':'→ в дом'}</button>`:'';
    const nb=it.batch===NEWEST_BATCH;
    const bd=it.batch?`<span class="badge d${nb?' nw':''}">${nb?'🆕 ':''}${it.batch.slice(8,10)}.${it.batch.slice(5,7)}</span>`:'';
    // NEW: lead with the plain-Russian sentence; demote the cryptic machine title.
    const headline=it.what?esc(it.what):esc(it.title);
    const mt=it.what?`<div class="mt">🏷 ${esc(it.title)}</div>`:'';
    const pick=it.pick?`<div class="pick">👉 ${esc(it.pick)}</div>`:'';
    h+=`<div class="card ${cardcl}" id="c_${it.hash}">
      <div class="top"><div class="t">${headline}</div>${bd}
      ${it.mine?'<span class="badge mine">🤖 Клод</span>':''}
      ${it.sec_risk&&it.sec_risk!=='low'?`<span class="badge sec-${it.sec_risk}">🛡️ ${it.sec_risk==='high'?'риск':'проверь'}</span>`:''}
      <span class="badge ${it.judge}">${it.judge==='ok'?'✅ судья: OK':'🟡 судья: PARTIAL'}</span></div>
      ${mt}${pick}
      ${it.sec_note?`<div class="secnote sec-${it.sec_risk}">🛡️ ${esc(it.sec_note)}</div>`:''}
      ${src}${rsn}
      <div class="acts">
        <button class="g ${it.anton==='gold'?'on':''}" onclick="vote('${it.hash}','gold')">золото</button>
        <button class="m ${it.anton==='miss'?'on':''}" onclick="vote('${it.hash}','miss')">мимо</button>
        <button class="s ${it.anton==='skip'?'on':''}" onclick="vote('${it.hash}','skip')">потом</button>
        ${promo}
        <button class="more" onclick="tg('${it.hash}')">показать сырой блок</button>
      </div>
      <div class="raw" id="r_${it.hash}">${esc(it.raw)}</div></div>`;
  });
  $('#list').innerHTML=h;
}
function render(){renderEval();renderToolbar();renderList();}
function setF(m){filter=m;render();}
function togP(){onlyPending=!onlyPending;render();}
function togM(){onlyMine=!onlyMine;render();}
function togS(){onlySec=!onlySec;render();}
function togU(){onlyUnseen=!onlyUnseen;if(onlyUnseen){onlyMine=false;onlyPending=false;filter=null;}render();}
function tg(h){const e=$('#r_'+h);e.style.display=e.style.display==='block'?'none':'block';}
async function vote(hash,v){
  const it=DATA.items.find(x=>x.hash===hash);
  const nv=(it.anton===v)?'clear':v;   // click same again = clear
  await fetch('/api/verdict',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({hash,verdict:nv})});
  it.anton=(nv==='clear')?'':nv;
  if(it.anton!=='gold'&&it.promoted){   // un-gold -> drop it from the home queue too
    await fetch('/api/promote',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({hash})}); it.promoted=false;
  }
  recomputeEval();render();
}
async function promote(hash){
  const it=DATA.items.find(x=>x.hash===hash);
  const r=await fetch('/api/promote',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({hash})}); const j=await r.json();
  if(j.blocked){alert('🛡️ Карантин-призма НЕ пускает эту идею в дом:\n\n'+(j.reason||'hard-hold')+'\n\nДом-заметки синкаются на весь флот — отравленную идею туда писать нельзя.');return;}
  it.promoted=j.queued; render();
}
function recomputeEval(){
  const by={};DATA.items.forEach(it=>{const d=by[it.miner]||(by[it.miner]={surfaced:0,gold:0,miss:0,pending:0});
    d.surfaced++; it.anton==='gold'?d.gold++:it.anton==='miss'?d.miss++:d.pending++;});
  DATA.eval.forEach(d=>{const x=by[d.miner];if(!x)return;Object.assign(d,x);
    const j=d.gold+d.miss; d.precision=j?Math.round(d.gold/j*100)/100:null;
    d.suggest=(d.precision!=null&&j>=3&&d.precision<0.5)?(d.suggestText||''):'';});
  const g=DATA.eval.reduce((a,d)=>a+d.gold,0),m=DATA.eval.reduce((a,d)=>a+d.miss,0);
  DATA.total={surfaced:DATA.items.length,gold:g,miss:m,
    pending:DATA.items.filter(x=>x.anton!=='gold'&&x.anton!=='miss').length,
    precision:(g+m)?Math.round(g/(g+m)*100)/100:null};
}
async function reharvest(){
  $('#toolbar').innerHTML='<span class="tot">пере-собираю…</span>';
  const r=await fetch('/api/reharvest',{method:'POST'});DATA=await r.json();render();
}
render();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _payload(self):
        items = load_state()
        ev, total = eval_metrics(items)
        return {"items": items, "eval": ev, "total": total}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            data = self._payload()
            page = (PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
                        .replace("__ORDER__", json.dumps(ORDER))
                        .replace("__LABEL__", json.dumps(MINER_LABEL, ensure_ascii=False))
                        .replace("__EXPLAIN__", json.dumps(MINER_EXPLAIN, ensure_ascii=False))
                        .replace("__VAULT__", VAULT))
            self._send(200, page)
            return
        if u.path == "/api/items":
            self._send(200, json.dumps(self._payload(), ensure_ascii=False),
                       "application/json; charset=utf-8")
            return
        self._send(404, "not found")

    def do_POST(self):
        u = urlparse(self.path)
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln) if ln else b""
        if u.path == "/api/verdict":
            try:
                d = json.loads(raw or "{}")
                set_verdict(d["hash"], d.get("verdict", "skip"))
                self._send(200, json.dumps({"ok": True}), "application/json")
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)[:200]}), "application/json")
            return
        if u.path == "/api/promote":
            try:
                d = json.loads(raw or "{}")
                res = toggle_promote(d["hash"])
                self._send(200, json.dumps({"ok": True, **res}), "application/json")
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)[:200]}), "application/json")
            return
        if u.path == "/api/reharvest":
            try:
                ah.harvest(quiet=True)
                self._send(200, json.dumps(self._payload(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:200]}), "application/json")
            return
        self._send(404, "not found")


def main():
    global PORT
    if "--port" in sys.argv:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])
    if "--no-harvest" not in sys.argv:
        print("harvesting judge keepers ...")
        ah.harvest(quiet=True)
    n = len(load_state())
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"\n  🅰️  Alpha review screen ready  ->  http://127.0.0.1:{PORT}")
    print(f"     {n} keeper-items across the miners · Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("bye")


if __name__ == "__main__":
    main()
