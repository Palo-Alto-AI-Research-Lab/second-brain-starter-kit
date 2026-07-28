# engines/

The python the skills actually run.

Until now this kit shipped 101 skills and 17 scripts. Skills said things like "run
`brain_ask.py`" and the file was not in the box — 87 of the 101 pointed at something that
did not exist here. This directory closes that gap: **246 engines**, every one of them
cited by a published skill or document.

## Two homes, kept separate

| Folder | On the author's machines | What lives there |
|---|---|---|
| `engines/scripts/` | `~/.claude/scripts/` | fleet plumbing — the message bus, approvals, guards, review brokers |
| `engines/imports/` | the vault's `_imports/` folder | knowledge work — importers, the retrieval brain, dashboards, content tools |

They are split because the skills talk about two homes, and a flat pile of 246 files would
leave you guessing which is which.

## These files are samples, not a working install

Every engine carries a banner saying so. The data in them has been **substituted, not
stripped** — chat ids, handles, phone numbers, e-mail addresses and machine names were
replaced with plausible fakes of the same shape. That is deliberate: `<REDACTED>` teaches
nothing, while a fake of the same shape leaves the code readable and its structure intact.

Placeholders you will need to replace:

| Placeholder | Means |
|---|---|
| `%VAULT%` | your Obsidian vault root |
| `%VAULT_ROOT%` | the folder your vault sits in |
| `%IMPORTS%` | where you keep these engines' data |
| `%USERPROFILE%` | your home directory |
| `%WORKDIR%` | your working folder |
| `$HOME` | your home directory on macOS/Linux |

Two conventions worth knowing before something confuses you:

- **Machine names differ between the docs and the code.** The skills say `HUB-1`,
  `LAPTOP-1`, `ANCHOR-1`. The python says `HUB1`, `LAPTOP1`, `ANCHOR1`, because a hostname
  in python is not only prose — it is also a variable name, and `ANCHOR-1 = ...` is not
  something any parser will accept.
- **Paths to `secrets/*.env` are left in on purpose.** The paths tell you where to put your
  own credentials. No credential values are in this repo, and none should ever be.

All 246 files parse under Python 3.12. That is the only guarantee made — parsing is not
running, and none of them will do anything useful until you point them at your own vault,
your own accounts and your own keys.

## Where to start

`PASSPORTS.md` has one entry per engine: what it does, what goes in and out, what it needs
installed, and which skills call it — read straight from the source. For the engines you
are most likely to reach for, it also carries the hand-written half: **what breaks, how to
tell, and how to fix it**, written for someone who did not build the thing.

61 of the 246 have that hand-written half today — every engine cited by more than one
document. The other 185 say so plainly instead of filling the space with a sentence that
sounds like guidance and isn't; for those, read the source before you rely on them.

The most-cited engines, in order, are a reasonable reading path:

| Engine | Cited by | Does |
|---|---|---|
| `imports/vault_backup.py` | 22 docs | back up the vault before anything modifies it |
| `imports/brain_embed_update.py` | 21 docs | rebuild the embedding index over the vault |
| `imports/brain_ask.py` | 18 docs | semantic retrieval — the engine behind `/ask` |
| `imports/archive_original.py` | 6 docs | keep the raw original of anything imported |
| `scripts/bus_send.py` | 6 docs | send to other machines on both rails at once |
| `imports/namesearch/find_name.py` | 6 docs | find a person across spellings and layouts |
| `scripts/machine_bus.py` | 5 docs | the cross-machine mailbox itself |
| `scripts/approval.py` | 4 docs | ask the human a question and wait for a yes |

## What is not here

`../HANDOVER.md` §2а lists what exists on the author's machines but is not published, and
why — including 18 engines the skills cite that are not on the machine this was published
from. Nothing is skipped silently.
