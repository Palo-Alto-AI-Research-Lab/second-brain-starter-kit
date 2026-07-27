# -*- coding: utf-8 -*-
r"""temperature.py — LEAD TEMPERATURE, deterministic, 0 tokens.

Reference extract of the scoring core we run over ~14k leads nightly.
Pure functions + a selftest; no database, no paths, no vendor lock.

WHY IT EXISTS
  A CRM status field lies. Someone typed "interested" 14 months ago and nobody
  ever typed anything else. Status is HISTORY. Temperature must be COMPUTED
  from behaviour, every night, and it must DECAY on its own.

WHAT IT EMITS — two separate things, deliberately not collapsed into one tier:

  A. temperature_band     operational state now:  Hot / Warm / Lukewarm / Cold / Archived
  B. reactivation_priority 0..100 + band Now / This week / This month / Park
                          = among the dormant, who do I wake FIRST

  These answer different questions. One number cannot do both: your hottest
  live conversation needs no "reactivation", and your best reactivation
  candidate is by definition not hot.

THE MODEL
  priority = 0.35*Recency + 0.20*Frequency + 0.25*Depth + 0.20*Resurgence - 0.30*Penalty

  Every time-signal decays exponentially:   value = 2^(-days / half_life)

  half-lives (days), tuned by external deep-research, not by taste:
    reply 45 · call 60 · lead-initiated contact 75 · resurfacing 24 ·
    relationship memory 365 · unanswered-outbound PENALTY 30

  Penalty is the piece people skip and it is the one that keeps you from being
  a pest: if WE wrote last and got nothing back, priority drops, and recovers
  only as the silence ages out.

RULES FIRST, LLM SECOND
  Everything here is arithmetic — free, reproducible, explainable to the human.
  An LLM is called only for the leftovers (`needs_review`: intent, snooze
  requests, referrals) and never for the numbers themselves.

  python temperature.py selftest
"""
import math
import datetime

# --- half-lives, days ---
HL_REPLY, HL_CALL, HL_LEAD_INIT, HL_RESURG, HL_MEMORY, HL_PENALTY = 45, 60, 75, 24, 365, 30
# --- priority weights ---
W_REC, W_FREQ, W_DEPTH, W_RESURG, W_PEN = 0.35, 0.20, 0.25, 0.20, 0.30
FREQ_CAP = 40.0  # number of interactions that saturates the frequency term

ARCHIVE_STATUS = {"lost", "declined", "refund"}


def days_since(date_str, now):
    """'2026-07-27' | '2026-07-27T21:13:36' -> whole days ago, or None."""
    if not date_str:
        return None
    s = str(date_str)[:19].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return (now - datetime.datetime.strptime(s, fmt)).days
        except ValueError:
            continue
    return None


def decay(days, half_life):
    """2^(-days/half_life). Unknown or in the future -> 0.0."""
    if days is None or days < 0:
        return 0.0
    return 2.0 ** (-float(days) / float(half_life))


def score(lead, now=None):
    """lead = dict with the fields below. Returns band, priority, components. PURE.

    lead fields used:
      status          str   free-text CRM status (only 'lost/declined/refund' matter)
      n_calls         int   how many real calls happened
      first_contact   date  first time we ever touched
      last_contact    date  last touch of any kind
      last_inbound    date  last time THEY wrote/called us
      last_outbound   date  last time WE wrote them
      n_lead_msgs     int   messages authored by them
      n_our_msgs      int   messages authored by us
    """
    now = now or datetime.datetime.now()
    st = (lead.get("status") or "").lower()
    n_calls = lead.get("n_calls") or 0
    n_lead = lead.get("n_lead_msgs") or 0
    n_ours = lead.get("n_our_msgs") or 0

    d_contact = days_since(lead.get("last_contact"), now)
    d_first = days_since(lead.get("first_contact"), now)
    d_in = days_since(lead.get("last_inbound"), now)
    d_out = days_since(lead.get("last_outbound"), now)

    # --- decayed raw signals ---
    reply_rec = decay(d_in, HL_REPLY)
    call_rec = decay(d_contact, HL_CALL) if n_calls > 0 else 0.0
    lead_init = decay(d_in, HL_LEAD_INIT) if n_lead > 0 else 0.0
    known = [d for d in (d_first, d_contact) if d is not None]
    memory = decay(min(known), HL_MEMORY) if known else 0.0
    resurgence = decay(d_in, HL_RESURG) if n_lead > 0 else 0.0

    # --- components, each 0..1 ---
    recency = max(reply_rec, call_rec, lead_init, 0.25 * memory)
    touches = n_lead + n_ours
    frequency = min(1.0, math.log1p(touches) / math.log1p(FREQ_CAP)) if touches else 0.0
    depth = min(1.0, 0.55 * (1 if n_calls > 0 else 0) + 0.45 * min(1.0, n_lead / 8.0))

    # penalty: we spoke last and heard nothing since -> stop pushing, let it age out
    penalty = 0.0
    if d_out is not None and (d_in is None or d_out < d_in):
        penalty = decay(d_out, HL_PENALTY)

    raw = (W_REC * recency + W_FREQ * frequency + W_DEPTH * depth
           + W_RESURG * resurgence - W_PEN * penalty)
    priority = int(round(100 * max(0.0, min(1.0, raw))))

    if priority >= 75:
        rband = "Now"
    elif priority >= 60:
        rband = "This week"
    elif priority >= 45:
        rband = "This month"
    else:
        rband = "Park"

    # temperature band = live engagement, independent of the reactivation queue
    if st in ARCHIVE_STATUS:
        band = "Archived"
    else:
        engagement = 0.50 * recency + 0.30 * depth + 0.20 * frequency
        if engagement >= 0.50:
            band = "Hot"
        elif engagement >= 0.30:
            band = "Warm"
        elif engagement >= 0.15:
            band = "Lukewarm"
        else:
            band = "Cold"

    # one short reply and no call = too thin to judge by arithmetic -> hand to an LLM
    needs_review = 1 if (n_lead == 1 and n_calls == 0) else 0

    return {
        "temperature_band": band,
        "reactivation_priority": priority,
        "reactivation_band": rband,
        "needs_review": needs_review,
        "rp_recency": round(recency, 3),
        "rp_frequency": round(frequency, 3),
        "rp_depth": round(depth, 3),
        "rp_resurgence": round(resurgence, 3),
        "rp_penalty": round(penalty, 3),
    }


def _selftest():
    now = datetime.datetime(2026, 7, 27)

    def d(days):
        return (now - datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    live = score({"status": "negotiating", "n_calls": 2, "first_contact": d(43),
                  "last_contact": d(0), "last_inbound": d(0), "last_outbound": d(1),
                  "n_lead_msgs": 11, "n_our_msgs": 14}, now)
    assert live["temperature_band"] == "Hot", live
    assert live["reactivation_band"] in ("Now", "This week"), live

    cooled = score({"status": "interested", "n_calls": 1, "first_contact": d(900),
                    "last_contact": d(700), "last_inbound": d(700), "last_outbound": d(690),
                    "n_lead_msgs": 4, "n_our_msgs": 9}, now)
    assert cooled["reactivation_band"] == "Park", cooled
    assert cooled["reactivation_priority"] < live["reactivation_priority"], (cooled, live)

    dead = score({"status": "lost", "n_calls": 0, "first_contact": d(1200),
                  "last_contact": d(1200), "last_inbound": None, "last_outbound": d(1100),
                  "n_lead_msgs": 0, "n_our_msgs": 3}, now)
    assert dead["temperature_band"] == "Archived", dead

    # the pest guard: identical history, but WE wrote last and recently
    base = {"status": "contacted", "n_calls": 0, "first_contact": d(60),
            "last_contact": d(20), "last_inbound": d(20), "n_lead_msgs": 3, "n_our_msgs": 3}
    quiet = score(dict(base, last_outbound=d(25)), now)
    pushy = score(dict(base, last_outbound=d(2)), now)
    assert pushy["reactivation_priority"] < quiet["reactivation_priority"], (pushy, quiet)

    print("SELFTEST OK — decay ranks fresh over ancient, archived is archived, "
          "and unanswered outbound lowers priority instead of raising it.")


if __name__ == "__main__":
    _selftest()
