---
name: intro
description: Make a warm INTRODUCTION between two (or more) people from Anton's Telegram, the "познакомь X с Y" operation that is his core product (a warm intro is his currency of exchange). Trigger on "/intro", "познакомь X с Y", "познакомь X и Y", "сделай интро X и Y", "сведи X и Y", "introduce X and Y", "intro X to Y". DEFAULT flow REQUIRES Anton's approval first: resolve and confirm BOTH identities, show the plan, then on his "+" create the group, post the intro blurb, DM each side, and log to the CRM. Skip the approval gate ONLY when Anton explicitly says so ("без апрува"). Creates a 3-way Telegram group titled `Name1 <> Name2 <> Palo Alto Research Lab`. Requires the send-enabled Telegram MCP. Pairs with telegram-lead-outreach; the intro itself is grounded in vault concept-investor-taxonomy and protocol-endorsement-intro-funnel.
---

# /intro: warm-introduction automation

Anton's matchmaking is a conveyor: a warm intro is the product he trades. This skill turns "познакомь X с Y" into one repeatable operation, run from his Telegram account.

Proven live 2026-06-19 (test pair Rita @teammate_r + Nataly @teammate_n). Standing rules live in memory [[intro-automation]] and [[no-long-dashes]].

## Flow

### 1. RESOLVE both people
For each name, identify the real person before doing anything:
- `/find` or `namesearch` over names.db, the Platinum CRM `leads`/`contacts`, and Telegram `resolve_username` / `search_contacts`.
- Disambiguate name collisions (Anton has many same-name contacts: 8 Denises, several Karim) using `get_common_chats`, company, recent calls.
- Capture for each: real name, @handle, tg_id, company, and the Latin first name for the title.

### 2. CONFIRM (DEFAULT: ON, approval required)
Show Anton a compact ДО to ПОСЛЕ block:
- who each person resolved to (name, @handle, company),
- the exact group title that will be created,
- which account will send.
Wait for his "+". Do NOT create anything before that.
Skip this gate ONLY if Anton explicitly says "без апрува" in the request.

### 3. CREATE the group
- `create_group` from the chosen account, title = `LatinName1 <> LatinName2 <> Palo Alto Research Lab`.
- The `<>` sign goes between ALL elements. Names are LATIN only, taken from the lead's own name. Pass the title with plain `<>` AT creation. Never HTML-escape it. Never rely on renaming afterward (see gotchas).
- Account label "default" = @work_acct_a (id 184939070); "corp_acct" is the company voice. Pick the account with the warmest existing thread to each lead.

### 4. INTRO blurb in the group
- Right after creating the group, get its invite link via `export_chat_invite`.
- Short, warm, in Anton's voice. State who each person is and why they are a fit, INCLUDE the group link ("Группа: <link>" / "Group: <link>"), close with "дальше за вами".
- LANGUAGE: write to each lead in THEIR language. A Russian-speaking lead gets Russian, an English-speaking lead gets English. Detect language from the CRM card (country / language field), the vault person note, or the prior DM-thread language. If the two leads share no common language, write the group blurb bilingually (RU plus EN).
- No long dashes anywhere (use a colon, comma, or parentheses). See [[no-long-dashes]].

### 5. DM each side
- A one-line personal heads-up to each participant, written IN THAT PERSON'S language, including the group invite link so they can jump straight in.

### 6. LOG and close the loop
- Mark both in the Platinum CRM at the INTRO stage.
- Set a watcher to close the loop later ("как прошёл разговор?", Anton's double-intro rule).

## Telegram-MCP connector gotchas
- `edit_chat_title` FAILS on basic groups (CHAT-ERR-838): you cannot rename after creation, so always create with the final correct title in one shot.
- There is no delete for Telegram basic groups, only `leave_chat` (which leaves a ghost group for the others). Get the title right the first time.
- Adding mutual contacts works. If a non-contact's privacy blocks adding, fall back to `export_chat_invite` and send the link.
- Pace intros one at a time with gaps (anti-ban). Never mass-create.

## Hard stops (defer to operating-agreement + bible)
Pause and ask Anton when an intro carries money, a commitment, secrets, or would be a mass blast. A plain social intro with no such payload is fine to run after his approval.

## Report to Anton
Short summary of what was created plus the group title and who is in it, then a `🧒 Простыми словами` recap. No long dashes.
