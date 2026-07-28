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
# deploy_apply.py <id> [--force|--confirm] -- record that a deliverable is APPLIED on THIS machine.
# verify starting with a known command (deploy_lib.verify_kind == 'cmd') is EXECUTED; a human
# description ('note') is never exec'd -- check it by hand, then re-run with --confirm.
# On pass writes DONE-<host>/<id>.ok (which syncs to hub = the ACK). --force skips verify entirely.
# Call AFTER you (Claude/Anton) actually performed the install step.
# Canon: reglament-raskatka-fiksov-deploy-manifest.
import os, sys, argparse
from deploy_lib import ME, read_pending, done_marker, verify_kind, run_verify


def main():
    # argparse (wave-1 2026-07-21): unknown flag / --help -> exit BEFORE touching DONE markers.
    p = argparse.ArgumentParser(
        prog="deploy_apply.py",
        description="Record that deliverable <id> is APPLIED on THIS machine (runs its verify, "
                    "writes DONE-<host>/<id>.ok which syncs to hub = the ACK).")
    p.add_argument("id", nargs="?", help="deliverable id from PENDING-%s" % ME)
    p.add_argument("--force", action="store_true", help="skip verify entirely")
    p.add_argument("--confirm", action="store_true",
                   help="a descriptive (non-command) verify was checked by hand")
    ns = p.parse_args()
    if not ns.id:
        print("usage: deploy_apply.py <id> [--force|--confirm]")
        return 1
    did = ns.id
    force = ns.force
    confirm = ns.confirm
    e = next((x for x in read_pending(ME) if x.get("id") == did), None)
    if not e:
        print("[deploy] id '%s' not in PENDING-%s (wrong id, or never registered)" % (did, ME))
        return 1
    v = (e.get("verify") or "").strip()
    kind = verify_kind(v)
    note = ""
    if v and not force:
        if kind == "note":
            if not confirm:
                print("[deploy] verify у '%s' ОПИСАТЕЛЬНЫЙ (не команда), не исполняю:" % did)
                print("    %s" % v)
                print("[deploy] проверь по описанию руками, затем: deploy_apply.py %s --confirm" % did)
                return 3
            note = " (descriptive verify, confirmed by hand)"
        else:
            # Same judge as the sweep (deploy_lib.run_verify): cwd=SCRIPTS, PYTHONPATH -> our
            # scripts dir, interpreter + `~` normalised for this OS. A raw subprocess here made
            # good packages look broken on Windows peers, who then force-applied blind.
            ok, rc = run_verify(v, timeout=60)
            if not ok:
                print("[deploy] verify FAILED for '%s' (exit %d) -- NOT marking done. Fix apply, or re-run with --force." % (did, rc))
                return 2
    m = done_marker(ME, did)
    os.makedirs(os.path.dirname(m), exist_ok=True)
    with open(m, "w", encoding="utf-8") as f:
        f.write("applied+verified%s\n" % note)
    print("[deploy] OK '%s' applied+verified on %s -> DONE marker written (syncs to hub = ACK)" % (did, ME))
    return 0


sys.exit(main())
