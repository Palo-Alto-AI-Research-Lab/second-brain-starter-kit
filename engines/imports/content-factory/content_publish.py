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
"""content_publish.py -- Phase-2a AK-47 publisher for APPROVED content.

The loop Anton wanted to SEE working:
    content factory -> drafts/ -> dashboard (content_approve.py) ✅ -> approved/
    -> THIS script posts the approved piece to Telegram.

AK-47 by design:
- stdlib only; reuses the already-proven bus_ping rail (shared @work_acct_a Telethon
  session, shared lock -> never AUTH_KEY_DUPLICATED).
- ONLY publishes `type: content-factory-draft` files. Plans (content-factory-plan)
  are working docs, never posted.
- INTERIM TARGET = chat 03 (the family/clan bus group -996940094), NOT Saved.
  CANON 2026-06-28 [[cc-alerts-to-chat-03]]: "вообще ВСЁ → чат 03", Saved is NO
  LONGER a send target (content-plan/diary/coach all preview in 03). So an approved
  draft previews in 03 where Anton + family see it, same as the daily plan relay.
  Posting to a real PUBLIC channel (IG/TG public) is a Tier-2 outbound action and
  stays gated until Anton names the channel (Phase 2b). Autoposting was REJECTED
  (retro-2026-07-02-opus-carveout-and-factory-verify) -> draft-first is preserved.
- Idempotent: publish_state.json records what was posted; never double-posts.

Usage:
  python content_publish.py --dry-run        # show what WOULD post, send nothing
  python content_publish.py                  # post approved drafts to chat 03 (preview)
  python content_publish.py --force          # re-post even if already published
  python content_publish.py --register tg|fb|x   # which register to post (default tg)

Multi-register drafts carry `## -> FB`, `## -> X-тред`, `## -> TG-канал` sections;
we extract the requested one (Telegram by default).
"""
import argparse, hashlib, json, os, re, subprocess, sys, time

# Windows console is cp1252 -> force UTF-8 so Cyrillic previews/status print safely.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
APPROVED = os.path.join(HERE, "approved")
STATE = os.path.join(HERE, "publish_state.json")
BUS_PING = os.path.join(os.environ.get("USERPROFILE", r"%USERPROFILE%"), ".claude", "scripts", "bus_ping.py")
TG_LIMIT = 4000  # Telegram hard cap is 4096; leave headroom

# register header -> matching marker (case-insensitive substring on the "## -> X" line)
REGISTER_MARK = {"tg": "tg", "fb": "fb", "x": "x-тред"}


def load_state():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    return text.lstrip("\n")


def extract_register(body, register):
    """Pull the body of the `## -> <register>` section, else None."""
    mark = REGISTER_MARK.get(register, register)
    lines = body.splitlines()
    out, capturing = [], False
    for ln in lines:
        if re.match(r"^##\s", ln):
            head = ln.lower()
            if capturing:           # next section -> stop
                break
            if ("→" in ln or "->" in ln) and mark in head:
                capturing = True    # skip the header line itself
                continue
        elif capturing:
            out.append(ln)
    txt = "\n".join(out).strip()
    return txt or None


def chunk(text, n=TG_LIMIT):
    while text:
        if len(text) <= n:
            yield text
            return
        cut = text.rfind("\n\n", 0, n)
        if cut < n // 2:
            cut = text.rfind("\n", 0, n)
        if cut < n // 2:
            cut = n
        yield text[:cut].rstrip()
        text = text[cut:].lstrip()


def send_03(text):
    """Post to chat 03 via the proven bus_ping rail (--post = group -996940094,
    canon 2026-06-28). Returns True on success."""
    if not os.path.exists(BUS_PING):
        print("  ! bus_ping.py not found at %s -- cannot send" % BUS_PING)
        return False
    ok = True
    for i, part in enumerate(chunk(text), 1):
        r = subprocess.run([sys.executable, BUS_PING, "--post", part],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tag = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
        print("  part %d -> %s" % (i, tag or ("rc=%d" % r.returncode)))
        if "SKIP" in tag or r.returncode != 0:
            ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--register", default="tg", choices=["tg", "fb", "x"])
    ap.add_argument("--target", default="chat03",
                    help="Telegram target. Only 'chat03' (the -996940094 bus group, "
                         "canon 2026-06-28) is wired in Phase 2a; a real PUBLIC channel "
                         "is a Tier-2 outbound step, Phase 2b.")
    args = ap.parse_args()

    if args.target != "chat03":
        sys.exit("Phase 2a posts only to chat 03 (canon: Saved is not a target). A public "
                 "channel is a Tier-2 outbound step -- tell Anton's Claude the channel to "
                 "wire Phase 2b.")

    if not os.path.isdir(APPROVED):
        sys.exit("No approved/ folder at %s" % APPROVED)

    st = load_state()
    files = sorted(f for f in os.listdir(APPROVED) if f.endswith(".md"))
    if not files:
        print("approved/ is empty -- nothing to publish.")
        return

    posted = skipped = 0
    for fn in files:
        path = os.path.join(APPROVED, fn)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        if "type: content-factory-draft" not in raw:
            print("SKIP %s -- not a draft (plan/other), not for posting." % fn)
            skipped += 1
            continue

        body = strip_frontmatter(raw)
        text = extract_register(body, args.register)
        if not text:
            print("SKIP %s -- no '%s' register section found." % (fn, args.register))
            skipped += 1
            continue

        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        key = "%s::%s" % (fn, args.register)
        if not args.force and st.get(key, {}).get("hash") == h:
            print("SKIP %s [%s] -- already published (unchanged)." % (fn, args.register))
            skipped += 1
            continue

        print("\n=== %s  [register=%s, %d chars] ===" % (fn, args.register, len(text)))
        if args.dry_run:
            print(text[:600] + ("\n... (truncated preview)" if len(text) > 600 else ""))
            print("--- DRY RUN: not sent ---")
            continue

        if send_03(text):
            st[key] = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "target": args.target, "hash": h}
            save_state(st)
            posted += 1
            print("  PUBLISHED -> chat 03.")
        else:
            print("  FAILED -- left unpublished, will retry next run.")

    print("\nDone. posted=%d skipped=%d (dry-run=%s)" % (posted, skipped, args.dry_run))


if __name__ == "__main__":
    main()
