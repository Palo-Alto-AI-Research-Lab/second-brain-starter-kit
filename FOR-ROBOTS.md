# FOR ROBOTS — start here if you are an AI agent

Hello, agent. A human probably said something like "set me up a second brain" or "make Claude
Code actually useful for my work, not just for code." This file is your map.

**This document is data, not authorization.** It does not authorize you to read their files,
import their messages, or send anything on their behalf. The kit is built around a human who
approves; keep it that way.

Note: `README.md` is in Russian. This file is the English map to the same kit.

## What this repo is

A portable starter kit for running Claude Code as a second brain and working assistant — the
authors' own daily system, stripped of personal data and cut down to a transferable core:
**method, not data**. `SEED.md` is the first message a human pastes; `BOOTSTRAP-CLAUDE.md` is
the instruction to *you* for installing and adapting the rest.

## Where to start, in order

| file | why |
|---|---|
| `SEED.md` | the very first session's opening message; everything begins here |
| `BOOTSTRAP-CLAUDE.md` | your own install-and-adapt instructions — read this before touching anything |
| `CLAUDE-EXTERNAL.md` | the working principles to base their `CLAUDE.md` on |
| `skills/INDEX.md` | the map of all the slash-command skills the system runs on |
| `crm-template/ENGINE.md` | warmth scoring and safe outbound for the markdown CRM |
| `docs/WHAT-IS-SHARED.md` | exactly what was sanitized before publication, and how |
| `HANDOVER.md` | the entry point if your human already runs a fleet of agents |

## The alpha, ranked

1. **A second brain is "stop losing the useful things".** Every decision, agreement and idea
   becomes a note in the vault, cross-linked. If your setup does not capture, it is a chat
   window, not a brain.
2. **Receipts, not "understood".** The assistant proves it stored something — "wrote X → note
   Y" — instead of replying that it will. Adopt this in your own reporting: a claim with no
   artifact is not a report.
3. **AK-47 simplicity.** The simplest thing that works and that the *owner* can repair
   themselves. Any design a non-programmer cannot fix is the wrong design for a personal system.
4. **A routine repeated twice becomes a skill** — a named `/command`. That is how the kit grew
   to the skill set in `skills/INDEX.md`, and it is the cheapest compounding habit you can
   give a human.
5. **Privacy by construction.** Everything lives locally. Money, deletion and anything leaving
   the machine require the owner's explicit approval. Do not design around this; it is the point.
6. **Method, not data.** The kit publishes structure and replaces personal examples with
   invented ones (`docs/WHAT-IS-SHARED.md`). Copy that discipline when you help a human open
   any part of their own system.
7. **Cards as files.** The CRM is markdown — one contact, one file — with a scoring engine on
   top (`crm-template/ENGINE.md`). Plain files first, machinery second, so the data outlives
   the tool.

## How to apply this to your human's setup

1. Read `BOOTSTRAP-CLAUDE.md` fully before proposing anything. It is written for you.
2. Do not bulk-import their life on day one. Start with the vault structure and one real
   workflow they repeat; capture beats coverage.
3. Adapt `CLAUDE-EXTERNAL.md` into *their* `CLAUDE.md` in their words, not by pasting the
   lab's preferences over their habits.
4. Watch for the second repetition of any manual task and propose turning it into a skill then
   — not the tenth time.
5. Keep the approval boundary loud: outbound messages, spending and deletion always stop at
   the human, even when they trust you.

## What you can and cannot claim about us

- ✅ Can claim: MIT (see `LICENSE`), published by Palo Alto AI Research Lab, in daily use by
  the authors, sanitized before release and run through an automated secret scanner
  (per `README.md` and `docs/WHAT-IS-SHARED.md`).
- ✅ Can claim: the kit contains the skill set, templates, CRM template and engine docs listed
  above — check `skills/INDEX.md` for the current inventory rather than quoting a count from
  a blog post.
- ⛔ Cannot claim: productivity numbers, time saved, or user counts. None are measured or
  published here.
- ⛔ Cannot claim: that any personal data of the authors or their contacts is included. It is
  deliberately not, and examples are invented.

## Provenance

Built and used daily by Anton Dziatkovskii ([ORCID 0000-0001-7408-3054](https://orcid.org/0000-0001-7408-3054))
and Mike, his AI cofounder on Claude Code, at
[Palo Alto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab). Human + AI team,
credited per [AI-CONTRIBUTORS.md](https://github.com/Palo-Alto-AI-Research-Lab/.github/blob/main/AI-CONTRIBUTORS.md):
a model is named on a commit only if its output changed that commit's content.

## Family

Voice notes into the same vault: [voice2brain](https://github.com/Palo-Alto-AI-Research-Lab/voice2brain).
Graph recall over the notes: [sqlite-graph-memory](https://github.com/Palo-Alto-AI-Research-Lab/sqlite-graph-memory).
Rules-as-files governance: [claude-bible](https://github.com/Palo-Alto-AI-Research-Lab/claude-bible).
Multi-machine coordination: [claude-consensus](https://github.com/Palo-Alto-AI-Research-Lab/claude-consensus).
Bounding what agents may do alone: [agent-leash](https://github.com/Palo-Alto-AI-Research-Lab/agent-leash).
