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
Rail 1+2 APPLY (idempotent, DATA-DRIVEN): weave WhatsApp person notes into the graph.
Single source of truth = people_verified.json (the Sonnet judge appends NEW verified people;
this script only APPLIES it, so it is safe to run EVERY night, 0 tokens).
- Adds a "## 🔗 Граф" section to each WhatsApp note (verified person/CRM target + concepts).
- Adds a back-link into the rich target (kind person/crm, has back_path) = bidirectional.
Idempotent: skips a note if the marker / back-link is already present. Run AFTER vault_backup.
"""
import os, io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
WA = r"%VAULT%\01-Conversations\WhatsApp"
V  = r"%VAULT%"
HERE = r"%IMPORTS%\whatsapp"
MARK = "## 🔗 Граф"

people = json.load(open(os.path.join(HERE, "people_verified.json"), encoding="utf-8"))

def add_graph_section(wa, label, target, why, concepts):
    p = os.path.join(WA, wa + ".md")
    if not os.path.exists(p): return f"  MISS {wa}"
    t = open(p, encoding="utf-8").read()
    if MARK in t: return f"  skip(has) {wa}"
    concs = ", ".join(f"[[{c}]]" for c in concepts) if concepts else "—"
    sect = f"\n{MARK}\n- 🧑 {label}: [[{target}]] ({why})\n- 🧩 Концепты: {concs}\n"
    anchor = "## 🗃 Данные"
    t = t.replace(anchor, sect.strip() + "\n\n" + anchor, 1) if anchor in t else t.rstrip() + "\n" + sect
    open(p, "w", encoding="utf-8").write(t)
    return f"  + {wa} -> [[{target}]] + {len(concepts)} concepts"

def add_backlink(wa, relpath):
    p = os.path.join(V, relpath)
    if not os.path.exists(p): return f"  MISS-target {relpath}"
    t = open(p, encoding="utf-8").read()
    if f"[[{wa}]]" in t: return f"  skip(has) back {wa}"
    open(p, "w", encoding="utf-8").write(
        t.rstrip() + f"\n- 💬 WhatsApp: [[{wa}]] — живая переписка (см. WhatsApp-слой)\n")
    return f"  back+ {relpath} -> [[{wa}]]"

print("=== WhatsApp notes: graph section ===")
for r in people:
    label = "Контакт" if r.get("kind") == "stub" else "Человек"
    print(add_graph_section(r["wa_note"], label, r["target"], r.get("why",""), r.get("concepts",[])))
print("=== rich targets: back-link ===")
for r in people:
    if r.get("back_path"):
        print(add_backlink(r["wa_note"], r["back_path"]))
