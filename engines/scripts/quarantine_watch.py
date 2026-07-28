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
r"""quarantine_watch.py -- watchdog: a NEW held package -> ping Anton at 02 POLICE.

Per alert-ownership-routing: a quarantined package is a "needs-Anton" event (could be a genuine
delayed delivery, could be an injection attempt) -> it must reach the clean 02-POLICE channel,
not be scrolled past in 03. This is the OWNED endpoint for layer 4.

0 tokens, deterministic. Dedups by id in `_deploy\.quarantine_alerted-<host>.json` so a package
that stays held is announced ONCE, not every run. A released/discarded package drops out of `held`
so it never re-alerts. Posts via the fleet bot (tg_bot_send.post_to 02-POLICE); if no bot token on
this machine the alert degrades to stdout (SessionStart deploy_check still surfaces it).

  python quarantine_watch.py            # ping for any NEW held package, rebuild dashboard
  python quarantine_watch.py --dry      # print what it WOULD ping, no send, no state write

Run as a periodic task (see install note in the quarantine skill). Canon: memory
quarantine-provenance-gate, alert-ownership-routing, remote-approval-qqq.
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quarantine_lib as q
import quarantine as qcli
from deploy_lib import DEPLOY, ME

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

POLICE = int(os.environ.get("TG_POLICE_CHAT", "-6491142604"))   # "02 POLICE" clean needs-Anton channel
STATE = os.path.join(DEPLOY, ".quarantine_alerted-%s.json" % ME)


def _load_alerted():
    try:
        with open(STATE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_alerted(ids):
    try:
        os.makedirs(DEPLOY, exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(sorted(ids), f, ensure_ascii=False)
    except Exception as e:
        print("[quarantine-watch] warn: could not save state (%s)" % e)


def _alert_text(new_held):
    lines = ["🛡️ КАРАНТИН: %d нов. посыл(ка/ок) задержан(а) на %s — НЕ применены." % (len(new_held), ME)]
    for r in new_held:
        lines.append("⛔ %s — %s [from=%s] · %s" % (
            r["id"], (r["title"] or "")[:60], r["from"] or "?", r["reason"][:80]))
    lines.append("Проверь источник → /quarantine (release/discard). Дашборд: _Dashboards/Quarantine.html")
    return "\n".join(lines)


def main():
    dry = "--dry" in sys.argv
    held = q.held(ME)
    alerted = _load_alerted()
    held_ids = {r["id"] for r in held}
    new_held = [r for r in held if r["id"] not in alerted]

    # rebuild the dashboard every run so the visual view is always current (cheap)
    if not dry:
        try:
            qcli.build_dashboard()
        except Exception as e:
            print("[quarantine-watch] dashboard build failed: %s" % e)

    if not new_held:
        print("[quarantine-watch] %s: %d held, 0 new -> no ping" % (ME, len(held)))
        # prune alerted-set of ids no longer held (released/discarded/applied) so a future
        # re-appearance of the same id re-alerts.
        if not dry and (alerted - held_ids):
            _save_alerted(alerted & held_ids)
        return 0

    text = _alert_text(new_held)
    if dry:
        print("[DRY] would ping 02-POLICE:\n" + text)
        return 0

    sent = False
    try:
        import tg_bot_send
        sent = tg_bot_send.post_to(POLICE, text)
    except Exception as e:
        print("[quarantine-watch] bot ping failed (%s)" % e)
    if not sent:
        print("[quarantine-watch] NOTE: alert not delivered via bot; surfaced here:\n" + text)

    # mark new ones alerted regardless of transport (deploy_check is the backstop surface),
    # and drop stale ids in one write.
    _save_alerted((alerted | held_ids) & held_ids)
    print("[quarantine-watch] %s: pinged %d new held package(s)" % (ME, len(new_held)))
    return 0


if __name__ == "__main__":
    import argparse  # validator gate (class fix 21.07): --help/unknown flag exit BEFORE any side effect; body still reads sys.argv
    _gate = argparse.ArgumentParser(description='quarantine dir watchdog (scheduled)')
    _gate.add_argument('--dry', action="store_true", help='no alerts, print only')
    _gate.parse_args()
    sys.exit(main())
