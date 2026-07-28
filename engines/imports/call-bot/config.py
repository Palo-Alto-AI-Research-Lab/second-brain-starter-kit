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
config.py — single source of the canon values for the BB Platinum booking module.
Canon: reglament-buking-zvonkov-bb-platinum.md (Rita, 2026-06-23, final).
Change values HERE only; the daemon and tests read from here.
"""
import os

# --- Telegram ---------------------------------------------------------------
# Team chat «Календарь» where a lead's Calendly link is dropped.
CALENDAR_CHAT_ID = -5437873947

# Who may request a booking / approve with "+" (numeric IDs, not @handles).
# Polina (@helper_ox) and Arina (@helper_as) were REMOVED 2026-06-23.
BOOKING_ALLOWLIST = {
    9110567260: "Rita (@teammate_r)",
    970102884:  "Nina (@teammate_n)",
    226258979:  "Anton (@work_acct_a)",
    7303193973: "Anton (@corp_acct)",
    265315838:  "Anton (@work_acct_b)",
}

# Telethon account the bot posts proposals from in the team chat.
# Default = the dedicated bot identity used by the sibling monitor module.
# (Confirm with Anton; override via env CALLBOT_ACCOUNT.)
BOT_ACCOUNT = os.environ.get("CALLBOT_ACCOUNT", "PERSONAL_ACCT")

# --- Calendars (Google) -----------------------------------------------------
# Book ONLY into BB Platinum. Read A2 for conflicts only (never book there).
BOOK_CALENDAR = "owner.calendar@example.com"   # BB Platinum
CONFLICT_CALENDARS = [                              # both checked for conflicts
    "owner.calendar@example.com",
    "owner.work@example.com",                   # Detkovsky A2 (read-only)
]

# --- Rules ------------------------------------------------------------------
TIMEZONE = "Europe/Lisbon"
WINDOW_START_H = 6      # 06:00
WINDOW_END_H = 24       # 00:00 next day
BUFFER_MIN = 30         # BB strict: >=30 min before AND after any event
DEFAULT_DURATION_MIN = 30
DAYS_AHEAD = 14

# --- Booking-form defaults (Palo Alto) --------------------------------------
BOOK_NAME = "Palo Alto AI Research Lab"
BOOK_EMAIL = "owner.calendar@example.com"

# --- Runtime safety ---------------------------------------------------------
# DRY_RUN: read + compute + LOG, but NEVER post to chat or book. Default ON.
DRY_RUN = os.environ.get("CALLBOT_DRY_RUN", "1") != "0"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "booking_state.json")
LOG_PATH = os.path.join(BASE_DIR, "booking_daemon.log")

# === MONITOR module (Module 1: autonomous call monitor + follow-up) ==========
# Canon: reglament-avtonomnyy-monitor-zvonkov-bb-platinum.md (Rita 2026-06-23)
# + HANDOFF-monitor-session.md. Reuses the shared values above
# (TIMEZONE/WINDOW/BOOKING_ALLOWLIST/BOT_ACCOUNT/Telethon env/OAuth) — single source.
#
# Team chat «CALLS 889 MAIN FA FAAAA follow up» where the monitor reports/drafts.
CALLS_CHAT_ID = -1006070720018
# The calendar the monitor WATCHES for call events. BB Platinum ONLY
# (Anton 2026-06-25: A2 is NOT read by the monitor — that's the booking module).
MONITOR_CALENDAR = "owner.calendar@example.com"
# Anton's 4 Telegram handles added to every 🤝 call-group (+ the lead).
ANTON_GROUP_HANDLES = ["personal_acct", "work_acct_a", "corp_acct", "work_acct_b"]
# 🤝 = call-group marker; <> stays reserved for /intro groups (do NOT use here).
GROUP_NAME_TEMPLATE = "{lead} 🤝 Palo Alto AI Research Lab"
# How often to poll the calendar (minutes). Cheap (0 tokens); LLM only on a hit.
MONITOR_POLL_MIN = 5
# Monitor state/log (separate from the booking module's files).
MONITOR_STATE_PATH = os.path.join(BASE_DIR, "monitor_state.json")
MONITOR_LOG_PATH = os.path.join(BASE_DIR, "monitor_daemon.log")
# Telethon session env (one of these is sourced for BOT_ACCOUNT).
DIALOGS_ENV = r"%IMPORTS%\dialogs\.env"
MCP_ENV = r"C:\mcp\telegram-mcp\.env"
# Google OAuth (gmail client reused; calendar scope added by gcal_auth.py).
GMAIL_DIR = r"%WORKDIR%\gmail"
GCAL_TOKEN_DIR = os.path.join(BASE_DIR, "gcal_tokens")
