# -*- coding: utf-8 -*-
r"""safe_send.py — the ONE live-send wrapper every outbound function calls.

Reference extract of the module that stands between our agent and other people's
inboxes. Sanitized: account names and paths are placeholders, the scars are real.

THE POINT
  An agent that can message people will eventually message people badly: too many,
  too fast, or into a rate limit that gets the account flagged. You do not fix that
  with a rule in a prompt ("be careful"). You fix it by making the unsafe path
  impossible to take: there is exactly one send function, and it is this one.

THREE LAYERS, IN ORDER
  1) budget gate      — is this account still under today's cap (we run 3-5/day)?
  2) human jitter     — 40-110s random pause, so the pattern isn't machine-flat
  3) FloodWait respect— when the platform says "wait N", wait exactly N, once

  Then the send is recorded: counted against the budget and written to an audit log.
  The log is the thing that lets a human ask "what did you send today" and get a
  real answer instead of a reassurance.

WHAT THIS MODULE DOES NOT DO
  It never writes the message. Copy is authored upstream (by the strongest model,
  in the human's own voice, and for cold outreach reviewed by a human). This module
  only gates and delivers text it is handed. Separating "who decides what to say"
  from "who is allowed to press send" is most of the safety.

SESSION REUSE RULE (learned the hard way)
  1 session = 1 IP = 1 process. Use a DEDICATED session per account; never the
  auth key a live listener is already holding, or the platform invalidates both.

  await safe_send(client, entity, text, acc="ACCOUNT_A", lead_slug="acme", kind="drip")
    -> {"ok": True,  "n_today": 3}
    -> {"ok": False, "reason": "budget"}
    -> {"ok": False, "reason": "floodwait", "seconds": N}
"""
import os
import sys
import asyncio
import random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import budget  # noqa: E402  — kept importable/testable without any network client

MIN_PAUSE = float(os.environ.get("DRIP_MIN_PAUSE", "40"))
MAX_PAUSE = float(os.environ.get("DRIP_MAX_PAUSE", "110"))
# A FloodWait longer than this is not worth sleeping through — report and move on.
FLOOD_GIVEUP = float(os.environ.get("DRIP_FLOOD_GIVEUP", "300"))


async def safe_send(client, entity, text, acc, lead_slug=None, kind="drip",
                    pause=True, dry_run=False):
    """Send `text` to `entity` through an already-connected client, but only if the
    account is still under today's budget. Returns a result dict; never raises on the
    expected blocked/flood cases — a caller looping over 40 leads must not die on one."""
    acc = (acc or "").strip().upper()

    # Layer 1: budget gate (the anti-ban knob a human can turn without reading code)
    if not budget.can_send(acc):
        return {"ok": False, "reason": "budget",
                "msg": "%s already at today's cap (%d/%d)" % (
                    acc, budget.sent_today(acc), budget.get_limit(acc))}

    if dry_run:
        return {"ok": True, "dry_run": True,
                "would_record": "%s -> %s (%s)" % (acc, lead_slug, kind)}

    # Layer 2: human jitter
    if pause:
        await asyncio.sleep(random.uniform(MIN_PAUSE, MAX_PAUSE))

    # Layer 3: send, and respect a rate limit exactly as the platform stated it
    try:
        from telethon.errors import FloodWaitError
    except Exception:
        FloodWaitError = None
    try:
        await client.send_message(entity, text)
    except Exception as e:
        if FloodWaitError is not None and isinstance(e, FloodWaitError):
            secs = getattr(e, "seconds", 0)
            if secs and secs <= FLOOD_GIVEUP:
                await asyncio.sleep(secs + 1)
                await client.send_message(entity, text)  # one retry after the wait
            else:
                return {"ok": False, "reason": "floodwait", "seconds": secs}
        else:
            return {"ok": False, "reason": "error", "msg": repr(e)}

    n = budget.record_send(acc, lead_slug, kind, text)
    return {"ok": True, "n_today": n}


if __name__ == "__main__":
    # No live network here — prove the gate path with a fake client.
    class _Fake:
        async def send_message(self, *a, **k):
            return None

    async def _t():
        print("dry_run ->", await safe_send(_Fake(), "x", "hi", "ACCOUNT_A",
                                            "demo", "test", dry_run=True))

    asyncio.run(_t())
