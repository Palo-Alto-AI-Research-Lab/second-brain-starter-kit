#!/usr/bin/env python3
"""build_argmap_dashboard.py — render a research-swarm argument map as a self-contained HTML dashboard.

Usage:  python build_argmap_dashboard.py <map.json> <out.html>

Input JSON may be either the synthesis map object, or the full workflow return
{hypothesis, lenses:[...], map:{...}}. Stdlib only. Anton works by eye.
"""
import json
import sys
import html
from datetime import datetime

QUALITY_COLOR = {
    "strong": "#1a9850", "moderate": "#66bd63", "weak": "#fdae61",
    "theoretical": "#74add1", "none": "#bbbbbb",
}
TIER_INFO = {
    "established": (0, "#1a9850", "Хорошо воспроизводимо"),
    "emerging":    (1, "#66bd63", "Результаты есть, данных мало"),
    "speculative": (2, "#fdae61", "Гипотеза, данных почти нет"),
    "fringe":      (3, "#d73027", "Вне текущего консенсуса"),
    # off-axis: the Verifier-Calibrator abstained — not a point on established→fringe
    "insufficient": (-1, "#9aa0a6", "Данных недостаточно — воздержались от оценки"),
}
SUPPORT_COLOR = {"supported": "#1a9850", "partial": "#fdae61", "unsupported": "#d73027"}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def arg_rows(items):
    out = []
    for it in items or []:
        q = (it.get("quality") or "none").lower()
        col = QUALITY_COLOR.get(q, "#bbbbbb")
        out.append(
            f'<div class="arg"><div class="badge" style="background:{col}">{esc(q)}</div>'
            f'<div class="arg-body"><div class="pt">{esc(it.get("point"))}</div>'
            f'<div class="lens-tag">{esc(it.get("source_lens"))}</div></div></div>'
        )
    return "\n".join(out) or '<div class="empty">—</div>'


def li(items):
    return "\n".join(f"<li>{esc(x)}</li>" for x in (items or [])) or "<li class='empty'>—</li>"


def lens_cards(lenses):
    cards = []
    for l in lenses or []:
        pts = "".join(
            f'<li><span class="dir dir-{esc((p.get("direction") or "context").lower())}">'
            f'{esc(p.get("direction"))}</span> '
            f'<span class="ql" style="color:{QUALITY_COLOR.get((p.get("evidence_quality") or "none").lower(), "#999")}">'
            f'[{esc(p.get("evidence_quality"))}]</span> {esc(p.get("claim"))}</li>'
            for p in (l.get("points") or [])
        )
        cards.append(
            f'<details class="lens"><summary><b>{esc(l.get("lens"))}</b> — '
            f'{esc((l.get("stance_summary") or "")[:120])}…</summary>'
            f'<p class="ss">{esc(l.get("stance_summary"))}</p><ul class="pts">{pts}</ul>'
            f'<p class="cn">Уверенность линзы: {esc(l.get("confidence_note"))}</p></details>'
        )
    return "\n".join(cards)


def calib_box(mp):
    """Render the Verifier-Calibrator block, if present."""
    cal = mp.get("calibration")
    if not cal:
        return ""
    audits = "".join(
        f'<li><span class="ql" style="color:{SUPPORT_COLOR.get((a.get("support") or "").lower(), "#999")}">'
        f'[{esc(a.get("support"))}]</span> {esc(a.get("claim"))} — <span class="cn">{esc(a.get("note"))}</span></li>'
        for a in (cal.get("claim_audits") or [])
    ) or "<li class='empty'>—</li>"
    flags = "".join(f"<li>⚠️ {esc(f)}</li>" for f in (cal.get("flags") or [])) or "<li class='empty'>нет</li>"
    pre = mp.get("pre_calibration_tier")
    changed = ""
    if cal.get("tier_changed") and pre:
        changed = (f'<div class="noverd">🔧 Тир пересмотрен: <b>{esc(pre)}</b> → '
                   f'<b>{esc(mp.get("confidence_tier"))}</b> (по итогам аудита доказательств)</div>')
    return (
        '<div class="box" style="border-left:3px solid #b48ead">'
        '<h2>🔎 Проверка и калибровка (Verifier-Calibrator)</h2>'
        f'{changed}'
        f'<div class="cn" style="margin:6px 0 10px">{esc(cal.get("calibration_rationale"))}</div>'
        f'<b style="font-size:13px">Аудит сильнейших утверждений:</b><ul class="pts">{audits}</ul>'
        f'<b style="font-size:13px">Флаги:</b><ul class="pts">{flags}</ul>'
        '</div>'
    )


def build(data):
    mp = data.get("map", data) if isinstance(data, dict) else {}
    lenses = data.get("lenses", []) if isinstance(data, dict) else []
    hyp = mp.get("hypothesis") or data.get("hypothesis", "")
    tier = (mp.get("confidence_tier") or "speculative").lower()
    idx, tcol, tdesc = TIER_INFO.get(tier, (2, "#fdae61", ""))
    abstain = (
        '<div class="noverd" style="color:#9aa0a6">⚖️ Воздержание: данных недостаточно, '
        'чтобы поставить идею на шкалу established→fringe.</div>' if tier == "insufficient" else ""
    )

    meter = "".join(
        f'<div class="tier {"on" if i==idx else ""}" '
        f'style="{"background:"+TIER_INFO[name][1]+";color:#fff" if i==idx else ""}">{name}</div>'
        for i, name in enumerate(["established", "emerging", "speculative", "fringe"])
    )
    de = mp.get("decisive_experiment") or {}

    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Карта аргументов — {esc(hyp[:60])}</title>
<style>
:root{{--bg:#0f1115;--card:#191c23;--txt:#e8eaed;--mut:#9aa0a6;--line:#2a2e37;--for:#1a9850;--against:#d73027}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt);padding:24px}}
.wrap{{max-width:1100px;margin:0 auto}}
h1{{font-size:21px;margin:0 0 4px}} .sub{{color:var(--mut);font-size:13px;margin-bottom:18px}}
.hyp{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:18px}}
.hyp .label{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.5px}}
.hyp .h{{font-size:18px;margin-top:4px}}
.meter{{display:flex;gap:6px;margin:14px 0}}
.tier{{flex:1;text-align:center;padding:8px 4px;border-radius:8px;background:#23262e;color:var(--mut);font-size:13px;border:1px solid var(--line)}}
.tier.on{{font-weight:700}}
.tdesc{{color:var(--mut);font-size:13px;margin-top:-4px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}}
@media(max-width:760px){{.cols{{grid-template-columns:1fr}}}}
.col{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}
.col h2{{font-size:15px;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid}}
.col.for h2{{border-color:var(--for);color:#6fd39a}} .col.against h2{{border-color:var(--against);color:#f08a80}}
.arg{{display:flex;gap:10px;margin-bottom:10px;align-items:flex-start}}
.badge{{flex:none;font-size:11px;color:#08130c;padding:2px 7px;border-radius:6px;font-weight:700;margin-top:2px;min-width:64px;text-align:center}}
.arg-body .pt{{font-size:14px}} .lens-tag{{color:var(--mut);font-size:11px;margin-top:2px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:760px){{.grid2{{grid-template-columns:1fr}}}}
.box{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}}
.box h2{{font-size:15px;margin:0 0 10px}}
.exp{{background:linear-gradient(135deg,#13243a,#0f1115);border:1px solid #2d4a6b}}
.exp .why{{color:var(--mut);font-size:13px;margin-top:6px}}
ul{{margin:6px 0;padding-left:20px}} li{{margin:4px 0}}
.empty{{color:var(--mut)}}
.lens{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin-bottom:8px}}
.lens summary{{cursor:pointer}} .ss{{color:var(--txt);font-size:13px}} .cn{{color:var(--mut);font-size:12px}}
.pts{{font-size:13px}} .dir{{font-size:11px;padding:1px 5px;border-radius:4px}}
.dir-for{{background:#143b27;color:#6fd39a}} .dir-against{{background:#3b1414;color:#f08a80}} .dir-context{{background:#23262e;color:var(--mut)}}
.summary-box{{background:var(--card);border-left:3px solid #74add1;border-radius:8px;padding:14px 16px;margin-bottom:18px;font-size:15px}}
.foot{{color:var(--mut);font-size:12px;text-align:center;margin-top:24px}}
.noverd{{color:#f0c674;font-size:13px;margin-top:8px}}
</style></head><body><div class="wrap">
<h1>🧭 Карта аргументов</h1>
<div class="sub">Research swarm · 5 линз · расследование, а не приговор · эпистемическая нейтральность</div>

<div class="hyp"><div class="label">Гипотеза</div><div class="h">{esc(hyp)}</div>
<div class="meter">{meter}</div>
<div class="tdesc">Степень уверенности: <b style="color:{tcol}">{esc(tier)}</b> — {esc(tdesc)}. {esc(mp.get("confidence_rationale"))}</div>
{abstain}
</div>

<div class="summary-box">{esc(mp.get("map_summary"))}
<div class="noverd">⚖️ {esc(mp.get("verdict") or "Вердикта нет — см. степень уверенности и открытые вопросы.")}</div></div>

{calib_box(mp)}

<div class="cols">
<div class="col for"><h2>✅ Аргументы ЗА</h2>{arg_rows(mp.get("for_arguments"))}</div>
<div class="col against"><h2>❌ Аргументы ПРОТИВ</h2>{arg_rows(mp.get("against_arguments"))}</div>
</div>

<div class="box exp"><h2>🔬 Самый дешёвый решающий эксперимент</h2>
<div>{esc(de.get("description"))}</div>
<div class="why">Почему решающий: {esc(de.get("why_decisive"))}{(" · Ориентировочная цена: " + esc(de.get("rough_cost"))) if de.get("rough_cost") else ""}</div></div>

<div class="grid2">
<div class="box"><h2>📜 Исторические аналоги</h2><ul>{li(mp.get("historical_analogs"))}</ul></div>
<div class="box"><h2>❓ Открытые вопросы</h2><ul>{li(mp.get("open_questions"))}</ul></div>
</div>

<div class="box"><h2>🔍 Линзы роя (детали)</h2>{lens_cards(lenses)}</div>

<div class="foot">Сгенерировано {esc(datetime.now().strftime("%Y-%m-%d %H:%M"))} · skill research-swarm · канон: protocol-epistemic-neutrality-fringe-research</div>
</div></body></html>"""


def main():
    if len(sys.argv) < 3:
        print("usage: build_argmap_dashboard.py <map.json> <out.html>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    out = build(data)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    print(f"OK -> {sys.argv[2]} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
