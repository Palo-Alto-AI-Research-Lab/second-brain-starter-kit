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
  1) budget slot      — RESERVE one of today's slots (we run 3-5/day per account)
  2) human jitter     — 40-110s random pause, so the pattern isn't machine-flat
  3) FloodWait respect— when the platform says "wait N", wait exactly N, once

  Then the send is confirmed: the reservation becomes a logged dispatch. The log is
  the thing that lets a human ask "what did you send today" and get a real answer
  instead of a reassurance.

  Note the order: the slot is taken BEFORE dispatch, not checked before dispatch.
  An external reviewer broke the obvious `if can_send(): send()` design twice — a
  race (two processes both see room, both send) and a crash window (platform
  accepted, process died before the log was written, retry double-sends at a real
  human). Reserving first closes both: see the header of budget.py. The failure
  mode is now "we send one message fewer than allowed", which is the right way for
  an outbound agent to be wrong.

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

    if dry_run:
        return {"ok": True, "dry_run": True, "remaining": budget.remaining(acc),
                "would_record": "%s -> %s (%s)" % (acc, lead_slug, kind)}

    # Layer 1: TAKE a slot (atomic). None = cap reached; nothing is dispatched.
    tok = budget.reserve(acc, lead_slug, kind)
    if tok is None:
        return {"ok": False, "reason": "budget",
                "msg": "%s already at today's cap (%d/%d)" % (
                    acc, budget.taken_today(acc), budget.get_limit(acc))}

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
                try:
                    await client.send_message(entity, text)  # one retry after the wait
                except Exception as e2:
                    # Retry failed. We do NOT know whether the first attempt landed,
                    # so the slot stays consumed — under-send beats double-send.
                    return {"ok": False, "reason": "error", "msg": repr(e2), "slot": "held"}
            else:
                # A rate limit is refusal BEFORE delivery: nothing went out, give it back.
                budget.release(tok)
                return {"ok": False, "reason": "floodwait", "seconds": secs}
        else:
            # Unknown failure = unknown delivery. Keep the slot; a human sees it via
            # budget.stale_reservations().
            return {"ok": False, "reason": "error", "msg": repr(e), "slot": "held"}

    # Dispatch accepted. If the process dies right here, the slot is already spent,
    # so a retry cannot send this message to the same person twice.
    budget.confirm(tok, text)
    return {"ok": True, "n_today": budget.sent_today(acc)}


if __name__ == "__main__":
    # No live network here — prove the gate path with a fake client.
    class _Fake:
        async def send_message(self, *a, **k):
            return None

    async def _t():
        print("dry_run ->", await safe_send(_Fake(), "x", "hi", "ACCOUNT_A",
                                            "demo", "test", dry_run=True))

    asyncio.run(_t())
