# -*- coding: utf-8 -*-
r"""demo.py — run the whole CRM engine on the shipped sample, in one command.

    python demo.py

No database, no network, no configuration. It loads `../sample-leads.json`,
re-scores every card with `temperature.py`, and prints three things:

  1. the band distribution        — is the model separating live from dead?
  2. the reactivation queue       — who would the agent wake first, and WHY
  3. an agreement check           — do our recomputed scores match the stored ones?

Point 3 is the interesting one, and the result is worth stating up front because
it decides what you have to build first. The stored scores came from the live
system, which reads three signals this export does not carry (PIPELINE.md §2:
`last_outbound`, `n_our_msgs`, `last_call` — all of them live in the message
store, not in the leads table). Run it and you will see:

  * the BAND reproduces exactly. Operational state survives the missing signals,
    because it leans on recency and depth, which the leads table already has.
  * the PRIORITY does not. It sags, because the penalty term needs `last_outbound`
    and the frequency term needs `n_our_msgs`.

So: you can get a useful Hot/Warm/Cold board out of a leads table alone, but the
"who do I wake first" queue is only honest once the message layer is wired in.
That is your build order, and this demo measures it rather than asserting it.
"""
import os
import sys
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import temperature  # noqa: E402

SAMPLE = os.path.join(HERE, "..", "sample-leads.json")
# The sample was exported on this date; score against it so the decay maths is
# reproducible instead of drifting every day you run the demo.
AS_OF = datetime.datetime(2026, 7, 28)


def load():
    with open(SAMPLE, encoding="utf-8") as f:
        return json.load(f)["cards"]


def to_lead(card):
    """Map an exported card onto the fields score() reads. Everything absent is
    passed as None on purpose — see the docstring: this is the demo's whole point."""
    return {
        "status": card.get("status"),
        "n_calls": card.get("n_calls"),
        "first_contact": card.get("first_contact"),
        "last_contact": card.get("last_contact"),
        "last_inbound": card.get("last_inbound"),
        "n_lead_msgs": card.get("lead_msgs"),
        # not present in a leads-table export:
        "last_call": None,
        "last_outbound": None,
        "n_our_msgs": None,
    }


def main():
    cards = load()
    print("loaded %d cards, scoring as of %s\n" % (len(cards), AS_OF.date()))

    bands, stored_bands, agree = {}, {}, 0
    scored = []
    for c in cards:
        s = temperature.score(to_lead(c), AS_OF)
        scored.append((c, s))
        bands[s["temperature_band"]] = bands.get(s["temperature_band"], 0) + 1
        sb = c.get("temperature_band")
        stored_bands[sb] = stored_bands.get(sb, 0) + 1
        if sb == s["temperature_band"]:
            agree += 1

    order = ["Hot", "Warm", "Lukewarm", "Cold", "Archived"]
    print("band distribution        recomputed | stored (live system)")
    for b in order:
        print("  %-10s %14d | %d" % (b, bands.get(b, 0), stored_bands.get(b, 0)))

    print("\ntop of the reactivation queue (who to wake first):")
    print("  %-22s %4s  %-12s %s" % ("lead", "pri", "band", "why"))
    for c, s in sorted(scored, key=lambda x: -x[1]["reactivation_priority"])[:8]:
        why = "rec=%.2f dep=%.2f freq=%.2f pen=%.2f" % (
            s["rp_recency"], s["rp_depth"], s["rp_frequency"], s["rp_penalty"])
        print("  %-22s %4d  %-12s %s" % (c["lead_slug"][:22],
                                         s["reactivation_priority"],
                                         s["reactivation_band"], why))

    pct = 100.0 * agree / len(cards)
    print("\nband agreement with the live system: %d/%d (%.0f%%)" % (agree, len(cards), pct))

    pairs = [(c["reactivation_priority"], s["reactivation_priority"])
             for c, s in scored if c.get("reactivation_priority") is not None]
    if pairs:
        deltas = [b - a for a, b in pairs]
        mean = sum(deltas) / len(deltas)
        worst = max(deltas, key=abs)
        print("priority delta (recomputed - stored): mean %+.1f, worst %+d, n=%d"
              % (mean, worst, len(pairs)))
    print("\nRead it this way: the band survives on the leads table alone, the priority")
    print("does not — it needs last_outbound (penalty), n_our_msgs (frequency) and")
    print("last_call (call recency) from the message store. See PIPELINE.md §2.")

    # A demo that cannot fail teaches nothing. These two must hold on any input.
    assert all(0 <= s["reactivation_priority"] <= 100 for _, s in scored), "priority out of range"
    assert all(s["temperature_band"] in order for _, s in scored), "unknown band emitted"
    print("\ninvariants OK: every priority in 0..100, every band known.")


if __name__ == "__main__":
    main()
