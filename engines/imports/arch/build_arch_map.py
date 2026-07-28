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
build_arch_map.py -- System Architect: VISUAL architecture map (interactive HTML).
Reads system.db (assets + edges) and renders a self-contained, CDN-free SVG map:
banded layout  ROBOTS (tasks) -> CODE (scripts/pipelines) -> DATA (dbs) -> FACES (dashboards/skills),
edges = real dependencies. Hover = details; legend toggles kinds. Deterministic, 0 tokens.
Output: %VAULT%\\_Dashboards\\System-Architecture-Map.html
"""
import os, sqlite3, html, math

IMPORTS = r"%IMPORTS%"
VAULT   = r"%VAULT%"
DB      = os.path.join(IMPORTS, "arch", "system.db")
OUT     = os.path.join(VAULT, "_Dashboards", "System-Architecture-Map.html")

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
assets = {r["asset_id"]: dict(r) for r in con.execute("SELECT * FROM asset")}
edges  = [dict(r) for r in con.execute("SELECT * FROM edge")]
meta   = {r["key"]: r["val"] for r in con.execute("SELECT * FROM meta")} \
         if con.execute("SELECT name FROM sqlite_master WHERE name='meta'").fetchone() else {}
con.close()

# keep only asset<->asset edges (drop synthetic wrapper:* sources for the visual)
edges = [e for e in edges if e["src"] in assets and e["dst"] in assets]

# bands (rows). kind -> band index + color
BAND = {
    "scheduled_task": (0, "#e67e22", "Роботы (задачи)"),
    "import_pipeline": (1, "#3498db", "Пайплайны"),
    "script":          (1, "#5dade2", "Скрипты"),
    "sqlite_db":       (2, "#2ecc71", "Данные (SQLite)"),
    "dashboard":       (3, "#9b59b6", "Дашборды"),
    "skill":           (3, "#e84393", "Скиллы"),
    "mcp_server":      (2, "#1abc9c", "MCP"),
}
BAND_LABELS = ["РОБОТЫ — что запускается само", "КОД — скрипты и пайплайны",
               "ДАННЫЕ — базы и MCP", "ЛИЦА — дашборды и скиллы (то, чем пользуешься)"]

# connected core = nodes touched by >=1 kept edge AND in a band we draw
deg = {}
for e in edges:
    deg[e["src"]] = deg.get(e["src"], 0) + 1
    deg[e["dst"]] = deg.get(e["dst"], 0) + 1
nodes = [aid for aid in deg if assets[aid]["kind"] in BAND]
# place: x by band, spread within band; bigger degree -> drawn later (on top) + labelled
W, ROWH, PAD = 1600, 230, 90
band_nodes = {0: [], 1: [], 2: [], 3: []}
for aid in nodes:
    band_nodes[BAND[assets[aid]["kind"]][0]].append(aid)

pos = {}
for b, lst in band_nodes.items():
    lst.sort(key=lambda a: (assets[a]["kind"], -deg.get(a, 0)))
    n = max(1, len(lst))
    for i, aid in enumerate(lst):
        x = PAD + (W - 2 * PAD) * (i + 0.5) / n
        # jitter rows within a band so labels don't fully overlap
        yj = (i % 3) * 26 - 26
        y = PAD + b * ROWH + ROWH / 2 + yj
        pos[aid] = (x, y)

H = PAD * 2 + 4 * ROWH

def esc(s): return html.escape(str(s or ""))

# edges svg
line_svg = []
for e in edges:
    if e["src"] not in pos or e["dst"] not in pos:
        continue
    x1, y1 = pos[e["src"]]; x2, y2 = pos[e["dst"]]
    line_svg.append(
        '<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" class="edge e-%s"/>'
        % (x1, y1, x2, y2, esc(e["edge_type"])))

# nodes svg
node_svg = []
for aid in sorted(nodes, key=lambda a: deg.get(a, 0)):
    x, y = pos[aid]
    a = assets[aid]
    k = a["kind"]; color = BAND[k][2 - 1]  # color is index 1
    color = BAND[k][1]
    r = 5 + min(10, deg.get(aid, 0))
    broken = a["status"] != "ok"
    stroke = "#e74c3c" if broken else "#0c0e12"
    sw = 3 if broken else 1
    label = ""
    if deg.get(aid, 0) >= 4 or broken:   # label only hubs + broken
        label = '<text x="%.0f" y="%.0f" class="lbl">%s</text>' % (x, y - r - 4, esc(a["name"])[:26])
    title = "%s [%s] deg=%d %s" % (a["name"], k, deg.get(aid, 0), a["detail"])
    node_svg.append(
        '<g class="node n-%s" data-kind="%s"><title>%s</title>'
        '<circle cx="%.0f" cy="%.0f" r="%d" fill="%s" stroke="%s" stroke-width="%d"/>%s</g>'
        % (k, k, esc(title), x, y, r, color, stroke, sw, label))

# band background bands + labels
band_bg = []
for b in range(4):
    y0 = PAD + b * ROWH
    band_bg.append('<rect x="0" y="%.0f" width="%d" height="%d" class="band b%d"/>' % (y0, W, ROWH, b % 2))
    band_bg.append('<text x="18" y="%.0f" class="bandlbl">%s</text>' % (y0 + 22, esc(BAND_LABELS[b])))

# legend / filters
kinds_present = sorted(set(assets[a]["kind"] for a in nodes))
legend = "".join(
    '<span class="leg" data-kind="%s" onclick="tog(this)"><i style="background:%s"></i>%s (%d)</span>'
    % (k, BAND[k][1], BAND[k][2], sum(1 for a in nodes if assets[a]["kind"] == k))
    for k in kinds_present)

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>System Architecture Map</title>
<style>
 body{{margin:0;background:#0c0e12;color:#e6e6e6;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
 .top{{padding:18px 24px 6px}} h1{{font-size:20px;margin:0 0 2px}} .sub{{color:#8a93a2;font-size:12px}}
 .legend{{padding:8px 24px;display:flex;gap:14px;flex-wrap:wrap}}
 .leg{{cursor:pointer;user-select:none;font-size:12px;display:flex;align-items:center;gap:5px;opacity:1}}
 .leg.off{{opacity:.3;text-decoration:line-through}} .leg i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
 .wrap{{overflow:auto;padding:0 12px 24px}}
 svg{{display:block;margin:0 auto;background:#0c0e12}}
 .band.b0{{fill:#11141a}} .band.b1{{fill:#0e1116}} .bandlbl{{fill:#5a6473;font-size:13px;font-weight:700;letter-spacing:.05em}}
 .edge{{stroke:#2b3140;stroke-width:1}} .edge.e-runs{{stroke:#e67e2255}} .edge.e-writes{{stroke:#2ecc7144}}
 .edge.e-reads{{stroke:#9b59b644}} .edge.e-uses{{stroke:#e8439344}} .edge.e-calls{{stroke:#34405044}}
 .node circle{{cursor:pointer;transition:r .1s}} .node:hover circle{{stroke:#fff;stroke-width:2}}
 .lbl{{fill:#aeb6c2;font-size:10px;text-anchor:middle;pointer-events:none}}
 .node.hide{{display:none}}
 .note{{color:#8a93a2;font-size:12px;padding:4px 24px 18px;max-width:1100px}}
</style></head><body>
<div class="top"><h1>🏛️ Карта архитектуры системы</h1>
<div class="sub">Score {score}/100 · {nn} связанных узлов · {ne} зависимостей · скан {gen} · поток: роботы → код → данные → лица</div></div>
<div class="legend">{legend}<span class="leg" style="margin-left:auto;cursor:default;opacity:.7">клик по цвету = скрыть/показать · наведи на узел = детали</span></div>
<div class="wrap"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">
 {bands}
 <g>{lines}</g>
 <g>{nodes}</g>
</svg></div>
<div class="note">Это <b>живое ядро</b> системы (то, что связано зависимостями). Полный каталog всех {total} активов (включая {dead} несвязанных скриптов, заметки, память) — на экране <b>System-Health.html</b> и в заметке <b>00-System/_System-MOC</b>. Красная обводка = сломано. Размер узла = сколько связей. Пересобирается ночным архитектором.</div>
</body>
<script>
function tog(el){{el.classList.toggle('off');var k=el.getAttribute('data-kind');
 document.querySelectorAll('.node.n-'+k).forEach(function(n){{n.classList.toggle('hide')}});}}
</script></html>""".format(
    score=meta.get("score", "?"), nn=len(nodes), ne=len(edges), gen=meta.get("generated_at", "?"),
    legend=legend, W=W, H=H, bands="".join(band_bg), lines="".join(line_svg), nodes="".join(node_svg),
    total=meta.get("total", "?"), dead=meta.get("dead_scripts", "?"))

open(OUT, "w", encoding="utf-8").write(HTML)
print("nodes %d  edges %d -> %s" % (len(nodes), len(edges), OUT))
