---
name: follower-onboard
description: Onboard a NEW family/clan machine as a FOLLOWER-CONSUMER (v1 data-only) joining Anton's multi-machine Claude+vault network (Nina + Rita done; Artem / future next). A follower READS the Second Brain vault + canon (CLAUDE.md) + skills + memory as RECEIVE-ONLY data, runs NOTHING heavy locally (no RAG/reindex/torch), and the hub NEVER pushes executable hooks to it (a follower's stock Claude correctly refuses that as a backdoor). NOT a full hub migration (that = /migrate). Trigger on "/follower-onboard <name>", "подключи <имя> как ведомого", "собери пакет ведомого для <имя>", "onboard <name> as follower", "новый ноут коллеги/семьи как потребитель". Canon = memory [[machine-migration]] + Bible reglament-vozhak-vedomyy-canon-governance + reglament-multi-machine-claude-i-peredacha-mezhdu-mashinami §3f.
---

# /follower-onboard <имя> — подключить ведомого-потребителя (v1 data-only)

> 🧒 When reporting to Anton end with a child-simple "Простыми словами" recap (memory `eli5-always`). Reports TO Anton only — never inside the package files.

**Single command** to build + deliver a follower onboarding package. Drives the tested generator over the master template. Full state + every decision + the gotchas = memory [[machine-migration]] (**READ it first each run** — the project is live, this is where the hard-won traps live).

## The v1 shape (decided 2026-06-24, do NOT re-litigate)
A follower = **читальный зал данных**. The hub SYNCS DATA the follower READS; it NEVER pushes executable code.

| Folder | Follower-side type | Why |
|---|---|---|
| `Owner-Knowledge` (vault, Bible) | **Receive-Only** | reads the Second Brain |
| `claude-home` (CLAUDE.md + commands) | **Receive-Only** | the canon — whitelist `.stignore` blocks `hooks`/secrets/scripts |
| `claude-memory` | **Receive-Only** | "одна память" |
| `claude-imports` | **Receive-Only** | scripts (code only, big data ignored) |
| `claude-skills` | **Receive-Only** | uses all skills |
| `_machine-bus` | sendreceive (tiny, versioned) | the ONLY 2-way folder (mailbox) |

**ALL data folders RECEIVE-ONLY (skills too).** A sendreceive skills/vault share from a follower is a DATA-LOSS VECTOR — a follower's empty folder can propagate deletions cluster-wide (it wiped the hub's skills 2026-06-24). Contributions (skills + vault notes) go via the **moderated `_transit` channel** (`vault-proposals/<name>/`, `canon-proposals/`), hub folds them in — NOT direct sync.

**NO hub-pushed hooks / settings.json in v1.** A follower's stock Claude CORRECTLY refuses to let a remote machine push executable `hooks/**` (a backdoor); a pasted "authorization" is not sufficient proof. So the hub pushes **zero remote-exec**. **The inbox-robot is the one exception BY KIND — MANDATORY on every machine (Anton 2026-06-25), but installed LOCALLY by the follower's own Claude with the operator's explicit consent.** A local scheduled task the operator sets up ≠ a hub push, so it is NOT the backdoor the no-hooks rule blocks. It rides the `_machine-bus` (the only sendreceive folder). Install via bootstrap STEP 8/9 (`INBOX-ROBOT-LAUNCHER.md` in `_transit`). The v1/v2 axis is about DATA-scope (v2 adds the Telegram-leads connector), NOT about the robot — the robot is baseline-mandatory, orthogonal to v1/v2.

## Step 0 — CONSENT + QUICK WIN + PITCH (до любой техники; reglament-onboarding-pitch-vtoroy-mozg)
Порядок: (1) мини-согласие 4 вопроса (что·где·кто видит·как удалить); (2) быстрая победа на реальной жизни юзера — сохранить одну полезную вещь и показать возврат; (3) питч 7 пунктов простыми словами; (4) первое сохранение с квитанцией. В интро-CLAUDE.md ведомого вписать операционный блок «хранитель памяти» + memory-check в конце сессии (текст в реглументе). На чек-ине 1-2 недели проверить 3 activation-сигнала; ноль сигналов → питч не дошёл, повторить через новую быструю победу. Канон: `reglament-onboarding-pitch-vtoroy-mozg`.

## Step 1 — RECALL (don't duplicate)
Read memory [[machine-migration]] §FOLLOWER-LITE + §v1 DATA-ONLY + the SKILLS-WIPE incident. Confirm the hub's safety nets are still on (see Step 6).

## Step 2 — Operator name in 5 Russian cases + Latin
The generator swaps Rita→target across all declensions incl. **Cyrillic ALL-CAPS** (grep -i can't fold those). Example «Нина»: latin `Nina` · nom `Нина` · gen `Нина` · dat `Нина` · acc `Нина` · ins `Нина`. Non-Russian name → ask Anton for forms.

## Step 3 — Generate
```bash
python "%WORKDIR%\migration-prep\gen_follower_package.py" \
  --latin <Latin> --nom <И> --gen <Р> --dat <Д> --acc <В> --ins <Т>
```
Writes `migration-prep\<latin>-follower\`, verifies 0 residual leaks (Unicode-correct, ABORTS on any), builds the zip, creates `vault-proposals\<latin>\`. Hand the operator the **v1 data-only Windows/Mac bootstrap** (`BOOTSTRAP-PROMPT-<NAME>-v1-data.md`) — the autonomous prompt their Claude runs. Also bundle `follower-kit-v1\syncthing_follower_watchdog.ps1` + `install_follower_watchdog.ps1`.

## Step 3b — ⭐ ПЕРСОНАЛЬНЫЙ КОМПЛЕКТ вместо раздачи CLAUDE.md Антона (2026-07-27)
⛔ Не отдавать новому человеку личный `CLAUDE.md` Антона: в нём его пути к секретам, ID его чатов, раскладка его личных дисков + ~90% правил не про этого человека (проверено: 22 совпадения скана утечек).
Вместо этого собрать комплект по двум осям — человек × узел:
```bash
python ~/.claude/scripts/persona_build.py --person <ключ> --node <код узла>
```
- Нового человека сперва внести в `~/.claude/canon/people.json` (копия блока `_template`; разрешения `may_*` — строго `true/false`, пояснение в `<поле>_note`).
- Новый узел — в `~/.claude/canon/node_caps.json` (копия `_template`); незнакомый узел получает `_default` = минимум прав.
- Сборщик сам блокирует выдачу, если пол безопасности неполон или просочилось личное; проверить готовый комплект: `--check <папка>` (exit 0 = годен, 2 = проверена только половина).
- Общий закон (`canon/CORE.md` + `canon/FLOOR.md`) у всех побайтово одинаковый — правит только Антон, у ведомых receive-only.

## Step 4 — Deliver
**⚠️ NOT via Gmail** — Gmail scans archives and BLOCKS scripts (`.ps1`/`.py`) → the whole email bounces (caught 2026-06-24). **Use Telegram `send_file`** or `SendUserFile`. Caption: "paste BOOTSTRAP-...-v1-data.md into your Claude Code, one message."

## Step 5 — Hub-side share (REST works; on-disk key `hWPF…` in `config.xml`)
Add the follower device + share the 6 folders. Auto-discovery (`/rest/cluster/pending`) is **404 in Syncthing v2.1.1** → instead read `DeviceRejected` events to find a follower's DeviceID. **Use the follower's CURRENT device ID** (it changes after a Syncthing reinstall — a "one folder empty, others fine" symptom = device-ID drift on THAT share).

## Step 6 — Safety nets (verify ON before any follower joins)
- **Syncthing versioning** on every synced folder (skills=simple keep10, memory=trashcan, vault=staggered, home/imports=trashcan) → deletions recoverable from `.stversions`.
- **git backup INITIALIZED + committing** — FIRST run `powershell "$env:USERPROFILE\.claude\scripts\claude_git_backup_setup.ps1"` (idempotent: git-inits skills/memory/scheduled-tasks/_config-backup/scripts/hooks + sets a per-repo identity + a global git identity). **This is mandatory: a present-but-inert "Claude Config Git Snapshot" task commits NOTHING if the repos were never `git init`-ed — exactly how the hub sat unprotected until the 2026-06-24 skills wipe (only a stale manual mirror saved it).** THEN verify the 15-min "Claude Config Git Snapshot" task exists and actually commits (path-agnostic `claude_git_snapshot.ps1`, uses `$env:USERPROFILE`). Canon: [[claude-skills-git-backup]] + [[config-safety-backup-and-migration-check]].
- Followers **Receive-Only** (Step shape) — the deletion vector removed.

## The follower-side GOTCHAS (от Нина 2026-06-24 — put in the bootstrap so they're handled)
1. **`.stfolder` marker missing** after changing a folder's path → create the marker dir + `POST /rest/db/scan`.
2. **Receive-only phantom deletions** — changing an RO folder to a new empty path marks files as "local deletions" and Syncthing STOPS pulling (`need=0`, `local=0`, `global>0`). Fix: `POST /rest/db/revert?folder=<id>` → discards phantom changes, re-pulls from hub.
3. **★ Sandbox-Syncthing eviction (the big one)** — every Claude Code restart launches a SANDBOXED Syncthing inside `…\Packages\Claude_*\LocalCache\Local\Syncthing\` with a sandbox config (no hub device, wrong REST key → CSRF + 0 connections). It grabs port 8384 and evicts the correct daemon → sync silently stalls. **Fix = the follower watchdog** (`follower-kit-v1\syncthing_follower_watchdog.ps1` + `install_follower_watchdog.ps1`): every 10 min it checks REST-key + hub-connected; if wrong/dead, kills all syncthing.exe and relaunches with explicit `--home=%LOCALAPPDATA%\Syncthing`. INSTALL IT as part of every follower onboard.
4. **Battery-friendly scheduled tasks** — on a laptop a task without `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable` sits `State=Queued` and never runs. The install script already sets these.
5. **session_archive on RO-vault follower** — its default catalog path is inside the (RO) vault → won't sync up. Run with `SESSION_ARCHIVE_OUT=<synced-bus>\_session-archive-inbound\<machine>`.

## Step 6b — Tailscale join (MANDATORY for EVERY peer; gap caught 2026-07-16)
Каждый пир флота обязан быть в tailnet (владелец = owner.calendar@example.com, вход = Google SSO). Без этого нет прямого доступа (SSH/RDP на хаб открыты ТОЛЬКО из 100.64.0.0/10) — Syncthing/TG-шина работают и без tailnet, поэтому дыра НЕ видна в обычной работе (так MAC-1 прожил незамеченным вне сети до 2026-07-16). Шаги: (1) поставить Tailscale (Win: winget/installer; Mac: .pkg — ⚠️ needs the operator's admin password/Touch ID, headless-сессия упрётся — просить руки оператора СРАЗУ, не в конце); (2) `tailscale up` → Google SSO owner.calendar (пароль bb в secrets store); (3) verify с ХАБА: `tailscale status` показывает узел. Registry expected-узлов = `~/.claude/scripts/tailnet_expected.json` (hub) — ДОБАВИТЬ новый узел туда; ночной сторож `tailnet_guard.py` кричит в шину про отсутствующих. Канон: memory [[all-peers-in-tailnet]].

## Step 7 — Register + report
- `_machine-bus\machines.json` (role `follower-consumer`), memory `user-registry` + `session-machine-tagging` (+ per-machine default operator, see Bible reglament-pomechat-mashinu §ДЕФОЛТ оператора ПО МАШИНЕ).
- Report to Anton post-hoc (what onboarded, what's pending).

## Hard "нельзя"
NEVER ship `claude-secrets`/`claude-config`/`.claude.json`/connectors. Canon never edited by followers → `canon-proposals\`. Vault never directly written by followers → `vault-proposals\<name>\`. Headless `claude -p` on follower = subscription/OAuth (`set "ANTHROPIC_API_KEY="`). `.ps1` ASCII-only (PS 5.1 mangles Cyrillic).

## Don't duplicate
`/migrate` = full HUB move (different job). `/inbox` = the bus the (mandatory, locally-installed) inbox-robot rides. One markdown procedure + one tested generator + the kit scripts — no server/DB (AK-47).
