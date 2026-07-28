#!/usr/bin/env python3
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
codex_pair.py - FULL-AUTO heterogeneous pair: Codex implements, Claude reviews.

Unlocked once Codex runs headless under WSL2 (it hangs headless on native Windows).
Flow: a task -> `codex exec --full-auto` edits a repo inside WSL (Linux fs, fast) ->
capture the git diff -> hand it to the Claude reviewer (cc_review.py) -> verdict.
The `tap` study: this Claude+Codex heterogeneity catches a defect in 69.8% of reviews
vs 53.1% same-vendor. Subscription only on both legs (ChatGPT for Codex, Claude.ai OAuth).

Usage:
  python codex_pair.py --task "implement X" [--repo-wsl /root/work] [--model sonnet|opus]

Notes:
- --repo-wsl is a path INSIDE the Ubuntu-24.04 distro (default /root/work). Keep work on
  the Linux fs, not /mnt/c (slow + known deadlocks). For your real Windows projects use
  the Windows-native skill /codex-review instead (Codex edits in Windows, Claude reviews).
"""
import argparse, os, subprocess, sys, time

DISTRO = "Ubuntu-24.04"


def wsl(cmd_str):
    return subprocess.run(
        ["wsl.exe", "-d", DISTRO, "-u", "root", "--", "bash", "-lc", cmd_str],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--repo-wsl", default="/root/work")
    ap.add_argument("--model", default="sonnet", choices=["opus", "sonnet"])
    ap.add_argument("--out", default=os.getcwd())
    args = ap.parse_args()
    repo = args.repo_wsl.replace("\\", "/")
    # Git-Bash (MSYS) mangles a WSL path like /root/x into 'C:/Program Files/Git/root/x'
    # when passed on its command line. Recover the intended Linux path.
    for anchor in ("/root", "/home", "/tmp", "/mnt"):
        idx = repo.find(anchor)
        if idx > 0 and ":" in repo[:idx]:
            repo = repo[idx:]
            break
    if not repo.startswith("/"):
        sys.exit("ERROR: --repo-wsl must be an absolute WSL path (e.g. /root/work), got: %r" % args.repo_wsl)

    # 1. ensure repo is a git repo, snapshot a clean baseline so the diff is just Codex's work
    wsl("mkdir -p '%s'; cd '%s'; git rev-parse --git-dir >/dev/null 2>&1 || "
        "{ git init -q; git config user.email pair@local; git config user.name pair; }" % (repo, repo))
    # keep bytecode/venv noise out of the review diff
    wsl("cd '%s'; printf '__pycache__/\\n*.pyc\\n.venv/\\nnode_modules/\\n' > .gitignore" % repo)
    wsl("cd '%s'; git add -A; git commit -qm baseline-pre-codex 2>/dev/null || true" % repo)

    # 2. write the task to a file inside WSL (avoids shell-quoting hell), run Codex headless
    task_b64 = args.task.encode("utf-8").hex()
    wsl("python3 -c \"import sys,binascii;open('/root/.codex_task','wb').write(binascii.unhexlify('%s'))\"" % task_b64)
    print("[1/3] Codex implementing (headless, WSL)...")
    t0 = time.time()
    r = wsl("cd '%s'; codex exec --full-auto \"$(cat /root/.codex_task)\"" % repo)
    if r.returncode != 0:
        sys.exit("ERROR: codex exec failed: " + (r.stderr or r.stdout)[:600])
    print("    Codex done in %ds." % int(time.time() - t0))

    # 3. capture Codex's diff
    d = wsl("cd '%s'; git add -A; git diff --cached" % repo)
    diff = d.stdout
    if not diff.strip():
        print("Codex made no changes - nothing to review.")
        return
    diff_path = os.path.join(args.out, "codex-change-%s.diff" % time.strftime("%Y%m%d-%H%M%S"))
    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff)
    print("[2/3] Codex diff captured: %s (%d chars)" % (diff_path, len(diff)))

    # 4. Claude reviews the diff via the existing broker
    task_path = os.path.join(args.out, "codex-task.txt")
    with open(task_path, "w", encoding="utf-8") as f:
        f.write(args.task)
    print("[3/3] Claude reviewing Codex's change...")
    cc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc_review.py")
    rv = subprocess.run([sys.executable, cc, "--diff", diff_path, "--task", task_path,
                         "--model", args.model, "--out", args.out],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(rv.stdout)
    if rv.returncode != 0:
        sys.stderr.write(rv.stderr)


if __name__ == "__main__":
    main()
