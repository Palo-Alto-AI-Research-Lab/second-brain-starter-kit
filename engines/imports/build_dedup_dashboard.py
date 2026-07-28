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
r"""build_dedup_dashboard.py — /dedup review screen (visual).

Runs the deterministic dedup_scan.py (read-only), parses its cluster report and
renders a self-contained HTML "review before merge" screen: candidate duplicate
clusters grouped by theme, similarity-scored, with the keep/supersede guidance.
It MERGES NOTHING — merging stays the manual supersede-not-delete step in /dedup.

  python build_dedup_dashboard.py     # runs scan -> _Dashboards\Dedup-Dashboard.html
"""
import subprocess, re, html, datetime, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"   # HP17 fallback
try:
    from _paths import VAULT
except Exception:
    VAULT = r"%VAULT%"   # HP17 fallback

SCAN = str(Path(IMPORTS) / "dedup_scan.py")
REPORT = Path(IMPORTS) / "dedup_report.txt"
OUT = Path(VAULT) / "_Dashboards" / "Dedup-Dashboard.html"
NOW = datetime.datetime.now()
PY = sys.executable

def run_scan():
    try:
        subprocess.run([PY, SCAN], capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    except Exception as e:
        print("scan failed (using existing report):", str(e)[:80])

RULE_RE = re.compile(r"\[([^|]*)\|([^|]*)\|([^\]]*)\]\s*(.+)")

def parse():
    txt = REPORT.read_text(encoding="utf-8", errors="replace") if REPORT.exists() else ""
    active = 0
    m = re.search(r"ACTIVE full-text rules:\s*(\d+)", txt)
    if m:
        active = int(m.group(1))
    themes = []          # [{theme, clusters:[{sim,k,rules:[{date,origin,msg,fn,stmt}]}]}]
    cur_theme = None
    cur_cluster = None
    cur_rule = None
    for line in txt.splitlines():
        if line.startswith("#### "):
            mt = re.match(r"#### (.+?) \((\d+) active\) — (\d+) cluster", line)
            cur_theme = {"theme": mt.group(1) if mt else line[5:], "clusters": []}
            themes.append(cur_theme)
            cur_cluster = None
        elif "--- cluster" in line:
            ms = re.search(r"max sim ([\d.]+|\?),\s*(\d+) rules", line)
            cur_cluster = {"sim": ms.group(1) if ms else "?", "k": int(ms.group(2)) if ms else 0, "rules": []}
            if cur_theme is not None:
                cur_theme["clusters"].append(cur_cluster)
            cur_rule = None
        elif line.strip().startswith("[") and cur_cluster is not None:
            mr = RULE_RE.search(line.strip())
            if mr:
                cur_rule = {"date": mr.group(1).strip(), "origin": mr.group(2).strip(),
                            "msg": mr.group(3).strip(), "fn": mr.group(4).strip(), "stmt": ""}
                cur_cluster["rules"].append(cur_rule)
        elif line.startswith("       ") and cur_rule is not None:
            cur_rule["stmt"] = (cur_rule["stmt"] + " " + line.strip()).strip()
    n_clusters = sum(len(t["clusters"]) for t in themes)
    return active, themes, n_clusters

def sim_color(sim):
    try:
        v = float(sim)
    except Exception:
        return "--mut"
    if v >= 0.7:
        return "--acc4"   # very likely dup
    if v >= 0.55:
        return "--acc3"
    return "--acc"        # complementary / review

def main():
    run_scan()
    active, themes, n_clusters = parse()
    themes = [t for t in themes if t["clusters"]]
    # sort clusters within theme by sim desc
    for t in themes:
        t["clusters"].sort(key=lambda c: (-(float(c["sim"]) if c["sim"] not in ("?", "") else 0)))
    n_dup_themes = len(themes)
    n_rules_in_clusters = sum(len(c["rules"]) for t in themes for c in t["clusters"])

    kpis = [
        (active, "активных правил просканировано"),
        (n_clusters, "кластеров-кандидатов"),
        (n_rules_in_clusters, "правил в кластерах"),
        (n_dup_themes, "тем с повторами"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="n">{n}</div><div class="l">{html.escape(l)}</div></div>'
                       for n, l in kpis)

    blocks = []
    for t in themes:
        cl_html = []
        for c in t["clusters"]:
            col = sim_color(c["sim"])
            rules = c["rules"]
            # newest = keep candidate (rules already date-sorted ascending in report -> last is newest)
            newest_fn = rules[-1]["fn"] if rules else ""
            rh = []
            for r in rules:
                keep = (r["fn"] == newest_fn)
                badge = '<span class="keep">оставить (новее)</span>' if keep else '<span class="sup">→ superseded</span>'
                origin = html.escape(r["origin"])
                ob = f'<span class="origin">{origin}</span>' if origin else ""
                rh.append(
                    f'<div class="rule {"k" if keep else ""}">'
                    f'<div class="rmeta">{html.escape(r["date"])} {ob} '
                    f'<span class="fn">{html.escape(r["fn"])}</span> {badge}</div>'
                    f'<div class="stmt">{html.escape(r["stmt"][:240])}</div></div>')
            cl_html.append(
                f'<div class="cluster" style="border-left-color:var({col})">'
                f'<div class="ch"><span class="sim">sim {html.escape(str(c["sim"]))}</span>'
                f'<span class="cn">{c["k"]} правила</span></div>'
                f'{"".join(rh)}</div>')
        blocks.append(
            f'<div class="theme"><h3>{html.escape(t["theme"])}</h3>'
            f'<div class="clusters">{"".join(cl_html)}</div></div>')

    body = "".join(blocks) or '<div class="empty">🎉 Дублей не найдено — чисто.</div>'
    gen = NOW.strftime("%Y-%m-%d %H:%M")
    doc = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Дубли заметок — дашборд</title>
<style>
:root{{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;
--acc:#5b9bff;--acc2:#37d399;--acc3:#ffb454;--acc4:#ff6b8b;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
header{{padding:26px 28px 6px}} h1{{margin:0 0 4px;font-size:23px}}
.sub{{color:var(--mut);font-size:13px}} .wrap{{padding:14px 28px 60px;max-width:1180px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:14px 0 18px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.kpi .n{{font-size:26px;font-weight:700}} .kpi .l{{color:var(--mut);font-size:12px;margin-top:2px}}
.theme{{margin:0 0 20px}} .theme h3{{font-size:16px;margin:0 0 10px;color:#cdd6e2}}
.clusters{{display:flex;flex-direction:column;gap:12px}}
.cluster{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:12px;padding:12px 14px}}
.ch{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
.sim{{font-weight:700;font-size:13px}} .cn{{color:var(--mut);font-size:12px}}
.rule{{padding:8px 10px;border:1px solid var(--line);border-radius:9px;margin-bottom:7px;background:#11141a}}
.rule.k{{border-color:#1f3a2a;background:#101a14}}
.rmeta{{font-size:11.5px;color:var(--mut);margin-bottom:3px}}
.fn{{color:#aab6c6;font-family:Consolas,monospace}}
.origin{{background:#222834;border-radius:5px;padding:0 6px;font-size:10.5px}}
.keep{{color:#bdf0d2;border:1px solid #1f3a2a;border-radius:5px;padding:0 6px;font-size:10.5px}}
.sup{{color:#ffb0c0;border:1px solid #4a2330;border-radius:5px;padding:0 6px;font-size:10.5px}}
.stmt{{font-size:12.5px;color:#cdd6e2}}
.empty{{color:var(--mut);text-align:center;padding:40px;font-size:15px}}
.note{{background:#1c1207;border:1px solid #4a3413;color:#f4d6a6;border-radius:12px;padding:10px 16px;font-size:12.5px;margin:0 0 14px}}
</style></head><body>
<header><h1>🧹 Дубли заметок — экран обзора перед склейкой</h1>
<div class="sub">Сканер: dedup_scan.py (Operations reglament-*) · {gen} · Claude Code</div></header>
<div class="wrap">
<div class="note">👁️ Только показ кандидатов. Склейка — вручную через /dedup по правилу <b>supersede, НЕ delete</b>: новее бьёт старое, ничего не удаляется. Комплементарные (разные адресаты/грани) — НЕ склеивать.</div>
<div class="kpis">{kpi_html}</div>
{body}
</div></body></html>'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"OK dedup: active={active} clusters={n_clusters} themes={n_dup_themes} -> {OUT}")

if __name__ == "__main__":
    main()
