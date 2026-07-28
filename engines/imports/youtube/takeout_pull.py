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
takeout_pull.py - the ACTOR that closes the "dropped Takeout handoff" class.

ROOT of the 2026-06 failure: a scoped YouTube->history export completed but the
7-day download link EXPIRED because the only follow-up was a PASSIVE calendar
reminder (fires into the void if no session is open). A reminder is not an actor.

This script is the deterministic (0-LLM-token) detector half of the forever-fix:
it scans Anton's a@ mailbox for Google Takeout "ready to download" emails, pulls
the archive id + download URL + expiry, computes DAYS-LEFT, and writes a machine
manifest + a loud human report. A nightly cron (armed separately, after /arch)
runs `--scan` and, on a LIVE link, pings 02-POLICE + drops a hanging-task chip so
a human/session downloads within the window.

The DOWNLOAD step itself is NOT here: Google Takeout download needs an
interactive a@ Google session (cookies), so it is driven through the already
logged-in Chrome (see skill /takeout-pull). This script's job = never let a ready
link go unnoticed again.

Usage (run from the gmail folder OR anywhere; needs network => Bash
dangerouslyDisableSandbox:true):
    python takeout_pull.py scan                 # scan a@ for ready Takeout exports
    python takeout_pull.py scan --label a --days 21
    python takeout_pull.py scan --json          # machine output only

Reuses Anton's Gmail connector (gmail_common.get_service) - single source of truth.
Stdlib only otherwise. Idempotent: re-running just refreshes the state file.
"""
import sys
import os
import re
import json
import argparse
import datetime as _dt

# Windows console is cp1252 -> force UTF-8 so Cyrillic subjects don't crash print().
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- locate Anton's Gmail connector (single source of truth) ----------------
GMAIL_DIR = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"),
                         "!CLAUDE-HP17 May26", "gmail")
if GMAIL_DIR not in sys.path:
    sys.path.insert(0, GMAIL_DIR)

try:
    from gmail_common import get_service, available_labels, whoami  # noqa: E402
except Exception as e:  # pragma: no cover - visibility layer: fail LOUD, not silent
    print(f"[FATAL] cannot import gmail_common from {GMAIL_DIR}: {e}")
    print("        (is this the HP17 machine with the Gmail connector + tokens?)")
    sys.exit(3)

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "_takeout_pull_state.json")

# Google Takeout "your data is ready" mail: subject varies by locale/product.
READY_SUBJECT_HINTS = [
    "ready to download",
    "data is ready",
    "готов",              # RU "архив готов"
    "download your",
]
DOWNLOAD_URL_RE = re.compile(r"https://[^\s\"'<>]*takeout[^\s\"'<>]*", re.I)
ARCHIVE_ID_RE = re.compile(r"archive/([A-Za-z0-9][A-Za-z0-9\-]{6,})", re.I)
# expiry phrasings: "available until June 27, 2026" / "download by 27 Jun 2026"
UNTIL_RE = re.compile(
    r"(?:until|by|before|до)\s+"
    r"([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}"        # June 27, 2026
    r"|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})",         # 27 June 2026
    re.I)


def _hdr(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _body_text(msg):
    import base64

    def dec(data):
        if not data:
            return ""
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")

    def walk(p):
        mt = p.get("mimeType", "")
        if mt.startswith("text/"):
            t = dec(p.get("body", {}).get("data"))
            if t:
                return t
        for part in p.get("parts", []) or []:
            t = walk(part)
            if t:
                return t
        return ""

    return walk(msg.get("payload", {}))


def _parse_date(s):
    s = s.strip().rstrip(",")
    for fmt in ("%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return _dt.datetime.strptime(s.replace(",", ""), fmt).date()
        except ValueError:
            continue
    return None


def _internal_date(msg):
    # Gmail internalDate = ms since epoch (UTC); the mail's send date.
    try:
        ms = int(msg.get("internalDate", "0"))
        return _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).date()
    except Exception:
        return None


def scan(label, days, today):
    svc = get_service(label)
    q = f'from:(google.com OR takeout) newer_than:{days}d'
    res = svc.users().messages().list(userId="me", q=q, maxResults=40).execute()
    ids = res.get("messages", [])
    found = []
    for m in ids:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        subj = _hdr(full, "Subject")
        low = subj.lower()
        if not any(h in low for h in READY_SUBJECT_HINTS):
            continue
        body = _body_text(full)
        urls = DOWNLOAD_URL_RE.findall(body)
        arch = ARCHIVE_ID_RE.search(body)
        sent = _internal_date(full)
        m_until = UNTIL_RE.search(body)
        expiry = _parse_date(m_until.group(1)) if m_until else None
        if expiry is None and sent is not None:
            expiry = sent + _dt.timedelta(days=7)  # Takeout window = 7 days
        days_left = (expiry - today).days if expiry else None
        found.append({
            "msg_id": m["id"],
            "subject": subj,
            "sent": sent.isoformat() if sent else None,
            "archive_id": arch.group(1) if arch else None,
            "download_url": urls[0] if urls else None,
            "expiry": expiry.isoformat() if expiry else None,
            "days_left": days_left,
            "status": ("LIVE" if (days_left is not None and days_left >= 0)
                       else "EXPIRED" if days_left is not None else "UNKNOWN"),
        })
    found.sort(key=lambda x: (x["days_left"] is None, x["days_left"] or 0), reverse=True)
    return found


def main():
    ap = argparse.ArgumentParser(description="Detect ready Google Takeout exports (the actor)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scan")
    sp.add_argument("--label", default="a", help="mailbox: a (personal, default) / a2 / bb")
    sp.add_argument("--days", type=int, default=21, help="look-back window (days)")
    sp.add_argument("--json", action="store_true", help="machine output only")
    args = ap.parse_args()

    if args.label not in available_labels():
        print(f"[!] mailbox '{args.label}' not authorized. Have: {available_labels()}")
        sys.exit(2)

    # Deterministic clock: env override so tests/cron are reproducible; else real today (UTC).
    ov = os.environ.get("TAKEOUT_PULL_TODAY")
    today = _dt.date.fromisoformat(ov) if ov else _dt.datetime.now(_dt.timezone.utc).date()

    found = scan(args.label, args.days, today)
    state = {"scanned_at": today.isoformat(), "label": args.label,
             "mailbox": whoami(args.label), "count": len(found), "items": found}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    live = [x for x in found if x["status"] == "LIVE"]
    print(f"=== Takeout scan: {whoami(args.label)} | {len(found)} ready-mails | "
          f"{len(live)} LIVE | today {today} ===")
    for x in found:
        flag = "🟢" if x["status"] == "LIVE" else ("🔴" if x["status"] == "EXPIRED" else "⚪")
        dl = f"{x['days_left']}d left" if x["days_left"] is not None else "?"
        print(f"{flag} {x['status']:8} [{dl:9}] {x['subject'][:55]}")
        print(f"     sent {x['sent']} | until {x['expiry']} | archive {x['archive_id']}")
    if live:
        print("\n>>> ACTION: a LIVE Takeout link exists — DOWNLOAD NOW (drive Chrome logged into a@).")
        print(f">>> state: {STATE_FILE}")
        sys.exit(0)
    elif found:
        print("\n(no live link — all ready-mails expired; re-create the export.)")
    else:
        print("\n(no Takeout 'ready' mails in window.)")


if __name__ == "__main__":
    main()
