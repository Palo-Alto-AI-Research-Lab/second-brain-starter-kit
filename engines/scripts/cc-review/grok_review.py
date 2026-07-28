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
grok_review.py - "Grok checks Claude" review lane (THIRD vendor, sibling of codex_review.py).

WHY (Anton 2026-07-20, после покупки SuperGrok Heavy): у нас уже есть гетеро-пара
Claude<->Codex (cc_review.py / codex_review.py). Grok Build CLI даёт ТРЕТИЙ независимый
вендор с другой обучающей базой -> третий голос там, где два спорят, и запасной ревьюер,
когда квота Codex выжжена. Тот же контракт: читает дифф, не трогает файлы, отдаёт
VERDICT: APPROVE | REQUEST_CHANGES.

Engine: `grok -p` (Grok Build CLI, headless single-turn). Подписка SuperGrok Heavy по
X-логину (@lab_x_acct), НЕ платный xAI API-ключ. Проверено на Mac16 2026-07-20:
grok-build 0.2.106, grok-4.5.

⚠️ Read-only гарантируется --tools '' (без файловых/шелл-инструментов) + --no-subagents:
у Grok Build по умолчанию есть запись и шелл, и с --permission-mode dontAsk он ими
пользуется. Не убирать эти флаги.

Usage:
  python grok_review.py [--repo PATH] [--range GITRANGE] [--diff PATCHFILE]
                        [--task TASKFILE] [--out DIR] [--timeout SEC] [--effort E]

Defaults: repo=cwd, range=working-tree changes vs HEAD, effort=high.
"""
import argparse, os, subprocess, sys, time, shutil

MAX_DIFF_CHARS = 120_000  # keep the prompt sane; truncate giant diffs with a note

REVIEW_PROMPT = """You are an INDEPENDENT senior code reviewer. The diff below was written by a
DIFFERENT AI coding agent (Anthropic Claude). Your job is to catch what it got wrong,
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
- Review only. Do not attempt to edit, write, or run anything.

End with exactly one VERDICT line:
VERDICT: APPROVE   (no blocking issues)
or
VERDICT: REQUEST_CHANGES   (1+ MED/HIGH issues)

Output clean Markdown. Start with a one-line summary, then findings, then the VERDICT line.
"""


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def _verdict_line(review):
    """Read the verdict by CONTENT via the one shared parser (scripts/_shared/).

    Grok writes "## VERDICT: REQUEST_CHANGES", others write "**Verdict:**" or
    "> VERDICT:" -- guessing the line's shape loses those SILENTLY, which is how
    this bug shipped twice. Fallback stays loud if _shared is missing.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "_shared"))
    try:
        import verdict_parse
    except ImportError:
        return "VERDICT: (unreadable) ⚠️  <- нет scripts/_shared/verdict_parse.py; смотри отчёт"
    return verdict_parse.verdict_line(review)


def get_diff(args):
    if args.diff:
        with open(args.diff, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), "patchfile:" + args.diff
    repo = args.repo or os.getcwd()
    if not os.path.isdir(os.path.join(repo, ".git")):
        sys.exit("ERROR: %s is not a git repo. Use --diff PATCHFILE or --repo PATH." % repo)
    if args.range:
        out = run(["git", "-C", repo, "diff"] + args.range.split())
        src = "git diff " + args.range
    else:
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
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--effort", default="high", help="grok reasoning effort (default high)")
    args = ap.parse_args()

    if not shutil.which("grok"):
        sys.exit("ERROR: `grok` CLI not on PATH. Install: brew install --cask grok-build, then `grok login --device-auth`.")

    diff, src = get_diff(args)
    if not diff.strip():
        print("No changes to review (empty diff). Nothing for Grok to check.")
        return
    truncated = ""
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        truncated = "\n\n[diff truncated to %d chars]\n" % MAX_DIFF_CHARS

    task_block = ""
    if args.task and os.path.isfile(args.task):
        with open(args.task, "r", encoding="utf-8", errors="replace") as f:
            task_block = "## TASK Claude was asked to do\n%s\n\n" % f.read().strip()

    prompt = "%s\n%s## DIFF (Claude's change), source: %s\n```diff\n%s\n```%s\n" % (
        REVIEW_PROMPT, task_block, src, diff, truncated)

    repo = args.repo if os.path.isdir(args.repo) else os.getcwd()
    # --tools '' strips every built-in tool (no write, no shell, no web) -> the agent can
    # only reason over the prompt. --no-subagents keeps it a single cheap turn.
    cmd = ["grok", "-p", prompt, "--cwd", repo, "--tools", "", "--no-subagents",
           "--no-memory", "--effort", args.effort, "--output-format", "plain"]

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        sys.exit("ERROR: grok timed out after %ds (raise --timeout or shrink the diff)." % args.timeout)
    dt = time.time() - t0

    review = (proc.stdout or "").strip()
    if proc.returncode != 0 and not review:
        sys.exit("ERROR: grok failed (%ds): %s" % (int(dt), (proc.stderr or "").strip()[:500]))
    if not review:
        sys.exit("ERROR: grok returned an empty review (%ds). Check `grok login`." % int(dt))

    out_dir = args.out or repo
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(out_dir, "review-grok-%s.md" % ts)
    header = ("# Grok review of Claude's change\n- when: %s\n- source: %s\n"
              "- reviewer: grok -p (grok-4.5, tools disabled)\n- took: %ds\n\n" % (ts, src, int(dt)))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + review + "\n")

    print("OK - review saved: %s" % out_path)
    print(_verdict_line(review))


if __name__ == "__main__":
    main()
