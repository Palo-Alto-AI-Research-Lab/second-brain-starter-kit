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
codex_review.py - "Codex checks Claude" review pair (thin broker, REVERSE of cc_review.py).

Completes the two-way heterogeneous review pair. cc_review.py has Claude review
Codex's diff; THIS has Codex review Claude's (or anyone's) diff, so the final
verification is always done by a DIFFERENT vendor (the `tap` study: a hetero pair
catches a defect in 69.8% of reviews vs 53.1% same-vendor).

Runs Codex NATIVELY headless on Windows via `codex exec` (verified working on
codex-cli 0.141.0, 2026-07-07 - the old "codex exec hangs on Windows -> need WSL2"
claim is OBSOLETE for current versions). Read-only sandbox: Codex cannot write or
run anything, it only reasons over the diff we hand it. File-based handoff:
task.md (optional) + the diff -> review-codex-<ts>.md.

Usage:
  python codex_review.py [--repo PATH] [--range GITRANGE] [--diff PATCHFILE]
                         [--task TASKFILE] [--model MODEL] [--out DIR] [--timeout SEC]

Defaults: repo=cwd, range=working-tree changes vs HEAD.
Subscription only: Codex uses the ChatGPT-subscription login, not a paid API key.
"""
import argparse, json, os, subprocess, sys, time, shutil, tempfile

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

End with exactly one VERDICT line:
VERDICT: APPROVE   (no blocking issues)
or
VERDICT: REQUEST_CHANGES   (1+ MED/HIGH issues)

Output clean Markdown. Start with a one-line summary, then findings, then the VERDICT line.
Do NOT edit any files - this is a review only.
"""


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def _verdict_line(review):
    """Read the verdict by CONTENT via the one shared parser (scripts/_shared/).

    Never guess the shape of the line here: "## VERDICT:", "**Verdict:**", "> VERDICT:"
    are all real model output, and a shape-guess loses them SILENTLY. Local fallback
    keeps the review itself readable if _shared is missing on an old node -- but it
    says so out loud instead of quietly printing "(not stated)".
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
        rng = args.range.split()
        out = run(["git", "-C", repo, "diff"] + rng)
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
    ap.add_argument("--model", default="", help="codex model override (default = codex config)")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    if not shutil.which("codex"):
        sys.exit("ERROR: `codex` CLI not on PATH. Install: npm i -g @openai/codex")

    diff, src = get_diff(args)
    if not diff.strip():
        print("No changes to review (empty diff). Nothing for Codex to check.")
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

    # Codex exec: read-only sandbox (it cannot write/run), non-interactive, clean
    # final answer captured via --output-last-message so we skip the noisy framing.
    repo = args.repo if os.path.isdir(args.repo) else os.getcwd()
    last_fd, last_path = tempfile.mkstemp(suffix=".md", prefix="codex-last-")
    os.close(last_fd)
    # Windows: `codex` on PATH is an npm .cmd shim; CreateProcess can't exec a .cmd
    # directly (WinError 2) -> route through `cmd /c`. The prompt goes via STDIN (`-`)
    # so we never fight arg-quoting of a huge multi-line prompt through the shell.
    exe = shutil.which("codex") or "codex"
    base = ["cmd", "/c", exe] if exe.lower().endswith((".cmd", ".bat")) else [exe]
    cmd = base + ["exec", "-s", "read-only", "--skip-git-repo-check",
                  "-C", repo, "--output-last-message", last_path]
    model = args.model
    if not model:
        # ~/.codex/config.toml is shared with the Codex DESKTOP APP, which can pin a model the
        # CLI+ChatGPT account isn't allowed to use (16.07: `gpt-5.6-sol` dropped server-side ->
        # every exec died 400). codex_bridge.py self-heals and caches a known-good slug -- reuse it.
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "bridge-state", "_model.json"), encoding="utf-8") as fh:
                model = json.load(fh).get("model") or ""
        except Exception:
            model = ""
    if model:
        cmd += ["-m", model]
    cmd += ["-"]  # read prompt from stdin

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        os.unlink(last_path)
        sys.exit("ERROR: codex exec timed out after %ds (raise --timeout or shrink the diff)." % args.timeout)
    dt = time.time() - t0

    review = ""
    if os.path.isfile(last_path):
        with open(last_path, "r", encoding="utf-8", errors="replace") as f:
            review = f.read().strip()
        os.unlink(last_path)
    if not review:  # fallback: last-message file empty -> use raw stdout
        review = (proc.stdout or "").strip()
    if proc.returncode != 0 and not review:
        sys.exit("ERROR: codex exec failed (%ds): %s" % (int(dt), (proc.stderr or "").strip()[:500]))

    out_dir = args.out or repo
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(out_dir, "review-codex-%s.md" % ts)
    header = "# Codex review of Claude's change\n- when: %s\n- source: %s\n- reviewer: codex exec (read-only)\n- took: %ds\n\n" % (
        ts, src, int(dt))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + review + "\n")

    print("OK - review saved: %s" % out_path)
    print(_verdict_line(review))


if __name__ == "__main__":
    main()
