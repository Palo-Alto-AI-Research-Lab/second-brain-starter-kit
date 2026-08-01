# AGENTS.md — working in this repo

Written for AI coding agents, and equally readable by a human contributor. Short on purpose.
Русская сводка — в конце.

## What this repo is

A working "Claude Code as a second brain + working assistant" setup, stripped of personal data and
cut down to a portable core: **the method, not the data.** 101 skills, a CRM engine with sample
data, vault templates, engine passports, and the seed message that starts the first session.

The primary reader is **someone else's agent**, bootstrapping a system for its own operator. That
shapes everything below: instructions must survive being executed by a model that has never seen
this repo, on a machine you know nothing about.

## Layout

- `SEED.md` — the first message a user pastes into Claude Code. Everything starts here.
- `BOOTSTRAP-CLAUDE.md` — instructions to the installing agent.
- `CLAUDE-EXTERNAL.md` — the working principles that become the user's own `CLAUDE.md`.
- `skills/` — 101 skill commands, mapped in `skills/INDEX.md`.
- `crm-template/` — markdown "card = file" CRM plus the scoring engine and demo data.
- `engines/` — the published engines; `engines/PASSPORTS.md` is their catalogue.
- `templates/`, `docs/` — note templates, onboarding, and what is/isn't shared.
- `HANDOVER.md` — entry point if the reader already runs a fleet of agents.

## How to verify a change

The one command that exercises real logic end to end, offline:

```bash
cd crm-template/reference
python demo.py     # scores the shipped sample, prints bands, queue, and an agreement check
```

Read what it prints before you "fix" it: **the priority column is expected not to reproduce
exactly**, because the export deliberately does not carry three signals that live in the message
store. That gap is documented, not a bug — a PR that makes the numbers agree by changing the model
is going the wrong way.

If you changed a skill or a doc, verification is different: paste the before/after of the concrete
file, per `docs/HOW-TO-CONTRIBUTE.md`. Abstract "this could be improved" is nearly impossible to
judge and will come back as a question.

## Conventions

- **Method, not data.** Every example is fictional. No real names, chat identifiers, paths,
  machine names, or credentials — in code, skills, templates, or sample data. This is the one rule
  with no exceptions; `docs/WHAT-IS-SHARED.md` says exactly what is and isn't published.
- **AK-47.** The simplest thing that works, repairable by a non-engineer. A simplification that
  removes a rule or halves a skill without losing anything is the *most* valuable PR here.
- **Receipts, not "understood".** A skill proves it saved something ("wrote X → note Y"); it does
  not report success on faith.
- **A passport for every engine.** New engine → an entry in `engines/PASSPORTS.md`: what it does,
  input, output, who calls it, what breaks, how to tell, how to fix. Where the judgement half is
  not written yet, the passport says so plainly rather than guessing — keep that honesty.
- **Portable paths.** No absolute paths and no drive letters. The reader's machine is not yours.
- Russian and English both live here. Match the language of the file you are editing.

## Boundaries — what needs a human

- **`SEED.md` and `BOOTSTRAP-CLAUDE.md`.** They are executed verbatim by someone else's agent on a
  machine you cannot see. A wrong instruction there does damage before anyone reads it.
- **Anything that widens what is shared** — a new export, a new sample file, a new field.
- **Removing a skill** from the published set.

## По-русски, коротко

Это метод, а не данные: все примеры вымышленные, ничего личного в репо не попадает. Проверка
изменения — `python crm-template/reference/demo.py` (офлайн, на демо-данных); для правок текста —
до→после на конкретном файле, формат в `docs/HOW-TO-CONTRIBUTE.md`. Самые ценные PR —
**упрощения**. Правки в `SEED.md` и `BOOTSTRAP-CLAUDE.md` — только через issue: их дословно
исполняет чужой агент на чужой машине.

## The deal

Your copyright stays yours, there is no CLA, and issues labelled `accepted` are free to take —
comment "claiming this". Full terms:
[CONTRIBUTING.md](https://github.com/Palo-Alto-AI-Research-Lab/.github/blob/main/CONTRIBUTING.md).

If an AI wrote your change, say so in the PR and confirm you ran it. Welcome here — we do it daily.
Unread generated code is the one thing that gets closed on sight.
