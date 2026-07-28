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
"""Build a self-contained HTML dashboard from orphan-scan outputs."""
from __future__ import annotations
import csv, json, html, sys
from pathlib import Path

OUT = Path(r"%IMPORTS%\orphan-scan")
DASH_VAULT = Path(r"%VAULT%\_Dashboards\Vault-Orphans.html")

summary = json.loads((OUT / "scan-summary.json").read_text(encoding="utf-8"))

with open(OUT / "orphans-by-folder.csv", encoding="utf-8") as f:
    folder_rows = list(csv.DictReader(f))

with open(OUT / "orphans.csv", encoding="utf-8") as f:
    orphan_rows = list(csv.DictReader(f))

# Top folders bar chart data
folder_rows_top = sorted(folder_rows, key=lambda r: -int(r["orphans"]))[:40]
max_orphans = max((int(r["orphans"]) for r in folder_rows_top), default=1)

def bar(width_pct, color="#e74c3c"):
    return f'<div class="bar" style="width:{width_pct:.1f}%;background:{color}"></div>'

# Sample orphans per top folder (first 5 each)
samples_html = []
folder_to_samples = {}
for r in orphan_rows:
    folder_to_samples.setdefault(r["folder"], []).append(r["basename"])

rows_html = []
for r in folder_rows_top:
    f = r["folder"]
    o = int(r["orphans"]); t = int(r["total_md"]); pct = float(r["orphan_pct"])
    pct_of_max = (o / max_orphans) * 100.0
    samples = folder_to_samples.get(f, [])[:5]
    sample_str = "<br>".join(f'<span class="sample">{html.escape(s)}</span>' for s in samples)
    color = "#c0392b" if pct >= 80 else ("#e67e22" if pct >= 40 else "#f39c12")
    rows_html.append(f"""
    <tr>
      <td class="folder">{html.escape(f)}</td>
      <td class="num">{o:,}</td>
      <td class="num">{t:,}</td>
      <td class="pct">{pct:.1f}%</td>
      <td class="barcell">{bar(pct_of_max, color)}</td>
      <td class="samples">{sample_str}</td>
    </tr>""")

total_md = summary["total_md"]
total_orphans = summary["orphans"]
orphan_pct = summary["orphan_pct"]
scanned_at = summary["scanned_at"]

html_doc = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<title>Vault Orphans — {scanned_at}</title>
<style>
  * {{ box-sizing:border-box }}
  body {{ font:14px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
         background:#1a1a1a; color:#e8e8e8; margin:0; padding:24px; }}
  h1 {{ font-size:22px; margin:0 0 6px; color:#fff }}
  .subtitle {{ color:#999; margin-bottom:22px; font-size:13px }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px; }}
  .kpi {{ background:#262626; border-radius:10px; padding:16px 20px; }}
  .kpi .v {{ font-size:28px; font-weight:600; color:#fff; }}
  .kpi .l {{ color:#888; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
  .kpi.warn .v {{ color:#e67e22 }}
  .kpi.bad  .v {{ color:#e74c3c }}
  .kpi.ok   .v {{ color:#27ae60 }}
  table {{ width:100%; border-collapse:collapse; background:#222; border-radius:10px; overflow:hidden; }}
  th, td {{ padding:8px 12px; border-bottom:1px solid #333; vertical-align:top; }}
  th {{ background:#2c2c2c; color:#bbb; font-weight:600; font-size:12px; text-align:left;
        text-transform:uppercase; letter-spacing:.4px; position:sticky; top:0; }}
  td.folder {{ font-family:Consolas,monospace; font-size:12px; color:#9bd; max-width:380px;
               word-break:break-all; }}
  td.num, td.pct {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.pct {{ color:#e67e22; font-weight:600 }}
  .barcell {{ width:160px; }}
  .bar {{ height:14px; border-radius:3px; }}
  .samples {{ font-family:Consolas,monospace; font-size:11px; color:#888; max-width:300px; }}
  .sample {{ display:inline-block; }}
  .footer {{ margin-top:24px; color:#666; font-size:12px; }}
  .footer a {{ color:#5af }}
  .eli5 {{ background:#2a2618; border-left:4px solid #f39c12; padding:14px 18px;
           border-radius:6px; margin:18px 0; color:#ddd; }}
  .eli5 b {{ color:#f39c12 }}
</style></head><body>

<h1>🧒 Vault — карта сирот</h1>
<div class="subtitle">Скан от {scanned_at} · по правилу <code>no-orphan-notes-rule</code></div>

<div class="kpis">
  <div class="kpi"><div class="v">{total_md:,}</div><div class="l">всего живых .md</div></div>
  <div class="kpi bad"><div class="v">{total_orphans:,}</div><div class="l">сирот (0 входящих)</div></div>
  <div class="kpi warn"><div class="v">{orphan_pct:.1f}%</div><div class="l">доля сирот</div></div>
  <div class="kpi ok"><div class="v">{total_md - total_orphans:,}</div><div class="l">здоровых заметок</div></div>
</div>

<div class="eli5">
🧒 <b>Простыми словами:</b> Из {total_md:,} живых заметок в твоём Втором Мозге {total_orphans:,} ({orphan_pct:.1f}%) сейчас «висят в воздухе» — на них никто не ссылается. Это не значит, что они мусор; это значит, что их сложно поднять обычным <code>grep</code> по теме / человеку. Таблица ниже показывает, ГДЕ их больше всего. Видно, что главные виновники — большие батчевые импорты (CRM-фонды, эссе Cryptoeconomics, Apple Notes, Trello), которые завезли без «обложки» MOC. Чинить их можно дёшево: построить по одному MOC на папку, и большая часть сирот разом перестанет быть сиротами.
</div>

<table>
  <thead><tr>
    <th>Папка</th>
    <th class="num">Сирот</th>
    <th class="num">Всего</th>
    <th class="pct">%</th>
    <th>Доля от макс.</th>
    <th>Примеры (первые 5)</th>
  </tr></thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>

<div class="footer">
  Источники: <code>%IMPORTS%\\orphan-scan\\orphans.csv</code> (полный список),
  <code>orphans-by-folder.csv</code> (свод), <code>scan-summary.txt</code>.
  Канон-правило: <code>no-orphan-notes-rule</code> · <code>decision-context-capture-roadmap</code>.
</div>

</body></html>
"""

(OUT / "orphans.html").write_text(html_doc, encoding="utf-8")   # local copy: never synced, always safe
print(f"wrote {OUT / 'orphans.html'}")

# SINGLE WRITER gate (root-fix 2026-07-26): Vault-Orphans.html is a pure derivative of the
# SHARED vault, so exactly one node may write it (doctrine v2 -> Якорь: no hardware needed,
# must survive the hub being offline). Two nodes writing it produced .sync-conflict copies.
# The gate lives in code because a task disabled on a peer can quietly come back.
def _may_write() -> bool:
    if "--force" in sys.argv:
        return True
    try:
        # реестр -- из своей шары (_imports/sync): claude-home доезжает не на все узлы
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sync"))
        import derived_writers as dw
        return dw.guard("Vault-Orphans.html")
    except Exception:
        return True   # module not deployed here yet -> behave exactly as before

if _may_write():
    DASH_VAULT.parent.mkdir(parents=True, exist_ok=True)
    DASH_VAULT.write_text(html_doc, encoding="utf-8")
    print(f"wrote {DASH_VAULT}")
else:
    print("SKIP: this node is not the assigned writer of Vault-Orphans.html (--force to override)")
