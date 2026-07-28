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
r"""quarantine.py -- CLI + dashboard for the incoming-package quarantine (layer 4).

Wraps quarantine_lib into the operations Anton (via Claude) actually does:

  python quarantine.py                 # print state + (re)build the visual dashboard
  python quarantine.py held            # just the HELD list (what needs attention)
  python quarantine.py dashboard       # (re)build _Dashboards\Quarantine.html, print its path
  python quarantine.py release <id> [note]   # Anton OK'd it -> becomes apply-now next deploy_check
  python quarantine.py discard <id> [note]   # not ours / hostile -> hidden from apply

release/discard are Tier-2 (releasing runs the package's install step) -> the SKILL only calls
these after Anton's explicit "+". This CLI just records the decision (append-only JSONL).

AK-47: pure stdlib, one static HTML file, no server. Canon: memory quarantine-provenance-gate.
"""
import os, sys, html, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quarantine_lib as q
from deploy_lib import BUS, ME

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DASH = os.path.join(BUS, "_Dashboards", "Quarantine.html")
# _Dashboards lives under the vault root, not the bus root
DASH = os.path.join(os.path.dirname(BUS) if os.path.basename(BUS) == "_machine-bus" else BUS,
                    "_Dashboards", "Quarantine.html")


def _e(s):
    return html.escape(str(s or ""))


def build_dashboard(target=ME):
    rows = q.quarantine_state(target)
    held = [r for r in rows if r["effective"] == "hold" and not r["applied"]]
    trusted = [r for r in rows if r["effective"] == "apply" and not r["applied"]]
    applied = [r for r in rows if r["applied"]]
    dropped = [r for r in rows if r["effective"] == "drop"]

    def card(r):
        badge = {"held": ("⛔ КАРАНТИН", "#ff6b8b"), "trusted": ("✅ доверенный", "#37d399")}
        lbl, col = badge.get(r["status"], ("?", "#9aa4b2"))
        pats = r["checks"].get("patterns") or []
        pat_html = ""
        if pats:
            items = ", ".join("%s <i>(%s)</i>" % (_e(p["pattern"]), _e(p["severity"])) for p in pats)
            pat_html = '<div class="pat">🔍 паттерны: %s</div>' % items
        sig = r["checks"].get("signature")
        sig_html = {"valid": '<span class="ok">подпись ✓</span>', "invalid": '<span class="bad">подпись ✗</span>'}.get(
            sig, '<span class="mut">без подписи (HMAC не подключён)</span>')
        dec = ""
        if r["decision"]:
            dec = '<div class="dec">🗳 решение: <b>%s</b> · %s</div>' % (_e(r["decision"]), _e(r["decided_ts"]))
        applied_badge = ' <span class="ap">применён</span>' if r["applied"] else ""
        return """<div class="card %s">
  <div class="top"><span class="id">%s</span><span class="bdg" style="background:%s">%s</span>%s</div>
  <div class="ttl">%s</div>
  <div class="meta">источник: <b>%s</b> · отправлено: %s · %s</div>
  <div class="rsn">%s</div>
  %s
  <div class="apply">примени: <code>%s</code></div>
  %s
</div>""" % (r["status"], _e(r["id"]), col, lbl, applied_badge, _e(r["title"]),
             _e(r["from"] or "(нет поля from)"), _e(r["sent"]), sig_html,
             _e(r["reason"]), pat_html, _e(r["apply"]), dec)

    def section(title, lst, hint=""):
        if not lst:
            return ""
        h = '<h2>%s <span class="cnt">%d</span></h2>' % (_e(title), len(lst))
        if hint:
            h += '<div class="hint">%s</div>' % _e(hint)
        return h + "".join(card(r) for r in lst)

    body = (section("⛔ В карантине — ждут твоего решения", held,
                    "Пришли из непроверенного источника или с плохой подписью. НЕ применены. "
                    "Скажи Claude «/quarantine release <id>» чтобы применить (после проверки), или «discard <id>» чтобы выбросить.")
            + section("✅ Доверенные — применятся сами", trusted,
                      "Валидная подпись или известная машина флота. deploy_check предложит их к установке как обычно.")
            + section("🗑 Выброшенные", dropped)
            + section("📦 Уже применённые", applied))
    if not body:
        body = '<div class="empty">Карантин пуст — непринятых посылок нет.</div>'

    page = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Карантин посылок — %s</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--ink:#e7ebf0;--mut:#9aa4b2;--line:#262b35;--acc:#5b9bff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:8px}
h2{font-size:15px;margin:22px 0 6px;border-bottom:1px solid var(--line);padding-bottom:6px}
.cnt{color:var(--mut);font-weight:400}.hint{color:var(--mut);font-size:12.5px;margin:2px 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 15px;margin-bottom:10px}
.card.held{border-color:#5a2330;background:#1d1214}
.card.trusted{border-left:4px solid #37d399}
.top{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.id{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--acc)}
.bdg{font-size:10.5px;color:#0c0f14;border-radius:5px;padding:1px 8px;font-weight:700}
.ap{font-size:10.5px;background:#232a38;color:#9aa4b2;border-radius:5px;padding:1px 8px}
.ttl{font-weight:600;margin-top:5px}.meta{font-size:12px;color:var(--mut);margin-top:4px}
.rsn{font-size:12.5px;margin-top:6px}.pat{font-size:12px;color:#ffb454;margin-top:5px}
.apply{font-size:11.5px;color:#8b94a3;margin-top:6px;word-break:break-all}
.apply code{background:#0c0f14;padding:1px 5px;border-radius:4px}
.dec{font-size:12px;color:#7dd3fc;margin-top:5px}
.ok{color:#37d399}.bad{color:#ff6b8b;font-weight:700}.mut{color:var(--mut)}
.empty{color:var(--mut);text-align:center;padding:50px}
</style></head><body><div class="wrap">
<h1>🛡️ Карантин входящих посылок</h1>
<div class="sub">Машина <b>%s</b>. Посылки (фиксы/скрипты/задачи) с непроверенным происхождением держатся здесь и НЕ применяются вслепую. Две линзы одного механизма: тут — <b>безопасность</b>, в /alpha-review — <b>ценность</b>.</div>
%s
</div></body></html>""" % (_e(target), _e(target), body)

    os.makedirs(os.path.dirname(DASH), exist_ok=True)
    with open(DASH, "w", encoding="utf-8") as f:
        f.write(page)
    return DASH, len(held), len(trusted)


def _print_state(target=ME):
    rows = q.quarantine_state(target)
    held = [r for r in rows if r["effective"] == "hold" and not r["applied"]]
    print("Карантин %s: %d посылок, %d в КАРАНТИНЕ" % (target, len(rows), len(held)))
    for r in held:
        print("  ⛔ %-26s from=%-16s  %s" % (r["id"][:26], r["from"] or "(missing)", r["reason"]))


def main():
    # argparse (wave-1 2026-07-21): unknown flag / --help -> exit BEFORE recording any decision
    # (release runs the package's install step next deploy_check -- Tier-2 territory).
    p = argparse.ArgumentParser(
        prog="quarantine.py",
        description="CLI + dashboard for the incoming-package quarantine (layer 4). "
                    "No command = print state + rebuild the dashboard.")
    p.add_argument("cmd", nargs="?", choices=["held", "dashboard", "release", "discard"],
                   metavar="command", help="held | dashboard | release | discard (default: state+dashboard)")
    p.add_argument("pkg_id", nargs="?", metavar="id", help="package id (for release/discard)")
    p.add_argument("note", nargs="?", default="", help="optional decision note")
    ns = p.parse_args()
    cmd = ns.cmd or ""
    if cmd == "held":
        print(json.dumps(q.held(), ensure_ascii=False, indent=2))
        return 0
    if cmd in ("release", "discard"):
        if not ns.pkg_id:
            print("usage: quarantine.py %s <id> [note]" % cmd)
            return 1
        pkg_id, note = ns.pkg_id, ns.note
        decision = "released" if cmd == "release" else "discarded"
        rec = q.record_decision(pkg_id, decision, note=note)
        build_dashboard()
        print("[quarantine] %s -> %s (%s)" % (pkg_id, decision, rec["ts"]))
        if decision == "released":
            print("  теперь deploy_check предложит его к установке. Примени: deploy_apply.py %s" % pkg_id)
        return 0
    if cmd == "dashboard":
        path, nh, nt = build_dashboard()
        print("dashboard: %s (%d в карантине, %d доверенных)" % (path, nh, nt))
        return 0
    # default: state + dashboard
    _print_state()
    path, nh, nt = build_dashboard()
    print("dashboard: %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
