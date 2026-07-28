#!/usr/bin/env python
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
cofounder_watch.py — Phase 0 of the real-time / ambient cofounder (decision-realtime-cofounder-2026-07-02).

AK-47 signal-dispatcher: 0 LLM tokens, stdlib only, PING-ONLY (sends nothing).
Reads the LIVE lead funnel (tg_followups.json), applies a DETERMINISTIC salience
filter (reuses the /pipeline priority rules), dedups against a file ledger so the
same event isn't re-alerted, and emits a cofounder-voice DIGEST (markdown + HTML
dashboard). High = surface now; Medium/Low = digest. No new salient events => says
so (silence is the point — no notification fatigue).

Layering later (Phase 0.5): pass HIGH events to the /cofounder LLM persona for
nuanced advice. Phase 0 uses templated cofounder-voice advice per rule = provable,
free, testable.

Usage:  python cofounder_watch.py            # normal tick
        python cofounder_watch.py --reset    # clear ledger (re-alert everything)
        python cofounder_watch.py --stdout    # also print digest to stdout
"""
import json, os, sys, hashlib, datetime
for _s in (sys.stdout, sys.stderr):           # cp1252 console guard (lint-encoding)
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

BASE = r"%IMPORTS%"
FUNNEL = os.path.join(BASE, "tg_followups.json")
OUTDIR = os.path.join(BASE, "cofounder")
LEDGER = os.path.join(OUTDIR, "cofounder_ledger.json")
DIGEST_MD = os.path.join(OUTDIR, "cofounder-digest.md")
DASH_HTML = r"%VAULT%\_Dashboards\Cofounder-Watch.html"

NOW = datetime.datetime.now()

def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _parse_dt(s):
    if not s: return None
    # accept "...(2026-06-01T19:28)" or ISO
    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", str(s))
    if not m: return None
    try:
        return datetime.datetime.fromisoformat(m.group(1))
    except Exception:
        return None

def classify(lead, top):
    """Return (salience, event_type, advice) or None. Reuses /pipeline priority order."""
    name = lead.get("lead", "?")
    replied = lead.get("replied")
    calendly_sent = lead.get("calendly_sent")
    booked = lead.get("booked") or lead.get("booking_confirmed")
    pitch_sent = lead.get("pitch_sent")
    cal_at = _parse_dt(lead.get("calendly_sent_at") or top.get("calendly_sent_at"))

    if booked:
        return None  # closed — never re-pitch
    # 1. HIGH — replied, Calendly not sent (warm NOW)
    if replied and not calendly_sent:
        return ("HIGH", "replied_no_calendly",
                f"🔥 {name} ответил — Calendly НЕ отправлен. Тёплый прямо сейчас = приоритет №1. "
                f"Действие: шли Calendly немедленно, пока не остыл. Решение: отправить · ты · сегодня.")
    # 2. MEDIUM — Calendly sent >24h ago, not booked
    if calendly_sent and not booked:
        overdue = cal_at is None or (NOW - cal_at).total_seconds() > 24*3600
        if overdue:
            return ("MEDIUM", "calendly_no_booking_24h",
                    f"⏰ {name}: Calendly отправлен, брони нет (>24ч). Лиды забывают бронировать — это правило. "
                    f"Действие: мягкий booking-nudge. Решение: пингануть · ты · сегодня.")
    # 3. LOW — pitched, no reply (awaiting / going cold)
    if pitch_sent and not replied:
        return ("LOW", "awaiting_reply",
                f"👀 {name}: питч отправлен, ответа нет. Проверь новый инбаунд; если тишина давно — "
                f"один мягкий follow-up или дропни. Решение: проверить/дропнуть · ты · 48ч.")
    return None

def main():
    if "--reset" in sys.argv:
        try: os.remove(LEDGER)
        except OSError: pass
        print("ledger reset")
    os.makedirs(OUTDIR, exist_ok=True)

    data = _load(FUNNEL, None)
    if data is None:
        print("FUNNEL MISSING:", FUNNEL); sys.exit(2)
    top = data if isinstance(data, dict) else {}
    pending = top.get("pending", data) if isinstance(top, dict) else data
    if not isinstance(pending, list):
        print("no pending[] in funnel"); sys.exit(2)

    ledger = _load(LEDGER, {})
    events, new_events = [], []
    for lead in pending:
        c = classify(lead, top)
        if not c: continue
        sal, etype, advice = c
        key = f"{lead.get('lead','?')}:{etype}"
        sig = hashlib.md5(advice.encode("utf-8")).hexdigest()[:8]
        ev = {"lead": lead.get("lead","?"), "salience": sal, "event": etype,
              "advice": advice, "key": key}
        events.append(ev)
        if ledger.get(key) != sig:          # NEW or changed => alert
            new_events.append(ev); ledger[key] = sig

    order = {"HIGH":0, "MEDIUM":1, "LOW":2}
    events.sort(key=lambda e: order[e["salience"]])
    new_events.sort(key=lambda e: order[e["salience"]])

    # --- money header (anton 2026-07-05: каждый дайджест начинается с денег) ---
    money = _load(os.path.join(OUTDIR, "money.json"), {})
    reserve = money.get("cash_personal_reserve_usd")
    cash = (money.get("cash_company_usd") or 0) + (reserve or 0)
    burn = money.get("burn_month_usd")
    earned = money.get("earned_this_month_usd")
    rw = money.get("runway_weeks")
    if rw is None and burn and reserve is not None:
        rw = round(cash / burn * 4.33)
    if rw is not None:
        flag = "🔴" if rw <= 26 else ("🟡" if rw <= 52 else "🟢")
        money_line = f"{flag} **Runway: {rw} нед** · касса ${cash:,} · burn ${burn or '?'}/мес · заработано в этом мес: ${earned or 0}"
    elif reserve is not None:
        money_line = f"🟡 **Касса ${cash:,}** · burn НЕИЗВЕСТЕН → runway не считается. Действие: Нина вписать зарплаты/подписки в money.json."
    else:
        money_line = "💰 **money.json не заполнен** — runway неизвестен. Действие: Антон+Нина вписать burn/зарплаты/резерв. Это цифра №1."

    # --- digest markdown (only NEW events = the ping; full list in dashboard) ---
    ts = NOW.strftime("%Y-%m-%d %H:%M")
    lines = [f"# 🤝 Кофаундер — сигнал ({ts})", "", money_line, ""]
    if not new_events:
        lines += ["_Тихо — новых важных событий в воронке нет. (Это хорошо: не дёргаю зря.)_"]
    else:
        counts = {}
        for e in new_events: counts[e["salience"]] = counts.get(e["salience"],0)+1
        lines += [f"**Новых сигналов: {len(new_events)}** " +
                  " · ".join(f"{k} {counts[k]}" for k in ('HIGH','MEDIUM','LOW') if k in counts), ""]
        for e in new_events:
            lines += [f"- {e['advice']}"]
    lines += ["", f"_ping-only · 0 токенов · всего активных в воронке: {len(events)} · источник tg_followups.json_"]
    digest = "\n".join(lines)
    with open(DIGEST_MD, "w", encoding="utf-8") as f:
        f.write(digest)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)

    # --- HTML dashboard (Anton works by eye) ---
    color = {"HIGH":"#e5484d","MEDIUM":"#f5a623","LOW":"#8b8b8b"}
    rows = "".join(
        f'<tr style="border-bottom:1px solid #eee"><td><b style="color:{color[e["salience"]]}">{e["salience"]}</b></td>'
        f'<td>{e["lead"]}</td><td>{e["advice"]}</td></tr>' for e in events) or \
        '<tr><td colspan=3 style="padding:20px;color:#888">Тихо — важных событий в воронке нет.</td></tr>'
    html = f"""<!doctype html><html lang=ru><meta charset=utf-8>
<title>Cofounder Watch</title><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font-family:system-ui,Segoe UI,sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#1a1a1a">
<h2>🤝 Кофаундер — наблюдение за воронкой</h2>
<p style="color:#666">{ts} · ping-only · 0 токенов · всего активных: {len(events)} · новых с прошлого тика: {len(new_events)}</p>
<table style="width:100%;border-collapse:collapse;font-size:14px"><thead>
<tr style="text-align:left;border-bottom:2px solid #333"><th>Салиентность</th><th>Лид</th><th>Совет кофаундера</th></tr></thead>
<tbody>{rows}</tbody></table>
<p style="color:#999;font-size:12px;margin-top:20px">Источник: tg_followups.json · дедуп через cofounder_ledger.json · Phase 0 (decision-realtime-cofounder-2026-07-02)</p>
</body></html>"""
    try:
        os.makedirs(os.path.dirname(DASH_HTML), exist_ok=True)
        with open(DASH_HTML, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print("dashboard write skipped:", e)

    print(f"OK · active={len(events)} · new={len(new_events)} · digest={DIGEST_MD}")
    if "--stdout" in sys.argv:
        print("\n" + digest)

if __name__ == "__main__":
    main()
