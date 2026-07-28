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
cc_review.py - "Claude checks Codex" review pair (thin broker).

The heterogeneous review pattern from the `tap` study (Claude+Codex catches a
defect in 69.8% of reviews vs 53.1% for a same-vendor pair). Codex GENERATES the
code (interactively on Windows, which works); this broker captures Codex's change
as a diff and has Claude REVIEW it independently. Pure Windows, no WSL2, no extra
logins. File-based handoff: task.md (optional) + the diff -> review-<ts>.md.

Usage:
  python cc_review.py [--repo PATH] [--range GITRANGE] [--diff PATCHFILE]
                      [--task TASKFILE] [--model opus|sonnet] [--out DIR]

Defaults: repo=cwd, range=working-tree changes vs HEAD, model=opus.
Subscription only: this script blanks ANTHROPIC_API_KEY so `claude -p` uses the
Claude.ai OAuth bucket, never a paid API key.
"""
import argparse, os, subprocess, sys, time, shutil, tempfile

MAX_DIFF_CHARS = 120_000  # keep the prompt sane; truncate giant diffs with a note

REVIEW_PROMPT = """You are an INDEPENDENT senior code reviewer. The diff below was written by a
DIFFERENT AI coding agent (OpenAI Codex). Your job is to catch what it got wrong,
acting as an adversarial second pair of eyes. Be specific and grounded in the diff.

Review for, in priority order:
1. CORRECTNESS bugs (logic errors, off-by-one, wrong conditions, broken edge cases,
   null/empty/overflow, race conditions, resource leaks).
2. SECURITY (injection, unsafe input, secret handling, auth/permission gaps).
3. BREAKAGE (does it break existing behavior, contracts, or callers?).
4. SIMPLIFICATION / reuse (clearly over-complex code that should be simpler).

Rules:
- Only report issues you can justify from the diff. No vague "consider maybe".
- For each finding: file:line (best effort) - severity [HIGH/MED/LOW] - what's wrong - the fix.
- If the change is clean, say so plainly. Do not invent problems.

End with exactly one VERDICT line:
VERDICT: APPROVE   (no blocking issues)
or
VERDICT: REQUEST_CHANGES   (1+ MED/HIGH issues)

Output clean Markdown. Start with a one-line summary, then findings, then the VERDICT line.
"""


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def get_diff(args):
    if args.diff:
        with open(args.diff, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), "patchfile:" + args.diff
    repo = args.repo or os.getcwd()
    if not os.path.isdir(os.path.join(repo, ".git")):
        sys.exit("ERROR: %s is not a git repo. Use --diff PATCHFILE or --repo PATH." % repo)
    if args.range:
        rng = args.range.split()
        out = run(["git", "-C", repo, "diff"] + rng)
        src = "git diff " + args.range
    else:
        # working-tree changes (staged + unstaged) vs HEAD
        out = run(["git", "-C", repo, "diff", "HEAD"])
        src = "git diff HEAD (working tree)"
    if out.returncode != 0:
        sys.exit("ERROR: git diff failed: " + out.stderr.strip())
    return out.stdout, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--range", default="")
    ap.add_argument("--diff", default="")
    ap.add_argument("--task", default="")
    ap.add_argument("--model", default="opus", choices=["opus", "sonnet"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if not shutil.which("claude"):
        sys.exit("ERROR: `claude` CLI not on PATH.")

    diff, src = get_diff(args)
    if not diff.strip():
        print("No changes to review (empty diff). Nothing for Claude to check.")
        return
    truncated = ""
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        truncated = "\n\n[diff truncated to %d chars]\n" % MAX_DIFF_CHARS

    task_block = ""
    if args.task and os.path.isfile(args.task):
        with open(args.task, "r", encoding="utf-8", errors="replace") as f:
            task_block = "## TASK Codex was asked to do\n%s\n\n" % f.read().strip()

    prompt = "%s\n%s## DIFF (Codex's change), source: %s\n```diff\n%s\n```%s\n" % (
        REVIEW_PROMPT, task_block, src, diff, truncated)

    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = ""  # force subscription OAuth, never paid key

    t0 = time.time()
    proc = subprocess.run(["claude", "-p", "--model", args.model],
                          input=prompt, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    dt = time.time() - t0
    if proc.returncode != 0:
        sys.exit("ERROR: claude -p failed (%ds): %s" % (int(dt), proc.stderr.strip()[:500]))
    review = proc.stdout.strip()

    out_dir = args.out or (args.repo if os.path.isdir(args.repo) else os.getcwd())
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(out_dir, "review-%s.md" % ts)
    header = "# Claude review of Codex's change\n- when: %s\n- source: %s\n- model: %s\n- took: %ds\n\n" % (
        ts, src, args.model, int(dt))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + review + "\n")

    verdict = next((ln for ln in review.splitlines() if ln.strip().startswith("VERDICT")), "VERDICT: (not stated)")
    print("OK - review saved: %s" % out_path)
    print(verdict.strip())


if __name__ == "__main__":
    main()
