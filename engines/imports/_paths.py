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
"""_paths.py -- ONE place _imports ENGINE scripts resolve machine-specific roots.

Reads ~/.claude/machine.env (per-machine; schema in
~/.claude/_config-backup/machine.env.template) with HP17 fallbacks, so a MISSING or
partial machine.env NEVER breaks a script. Mirrors hooks/_machine_paths.py (same
machine.env FILE = single source of truth) for the _imports side, since _imports is
NOT on the hooks dir's import path.

Usage (root-level engine scripts):
    try:
        from _paths import VAULT
    except Exception:
        VAULT = r"%VAULT%"   # HP17 fallback

Decision: decision-unified-multi-machine-platform (Phase 3b). AK-47: tiny, stdlib,
fallbacks everywhere. _imports is NOT synced (each machine its own copy) -> machine.env
is what makes a copied engine script land on the right paths on a Mac/other-user box.
One-time import scripts are FROZEN historical artifacts (won't run cross-OS) -> not refactored.
"""
import os


def _home():
    return os.path.expanduser("~")


def _load_env():
    d = {}
    try:
        p = os.path.join(_home(), ".claude", "machine.env")
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if v:
                        d[k.strip()] = v
    except Exception:
        pass
    return d


_ENV = _load_env()


def get(key, default=""):
    return _ENV.get(key) or os.environ.get(key) or default


# The 5 Phase-1 coupling dimensions, resolved once. Identical on both Windows boxes
# today (fallbacks); per-machine on Mac/other-user via that machine's machine.env.
VAULT = get("OBSIDIAN_VAULT", r"%VAULT%")
IMPORTS = get("IMPORTS_ROOT", r"%IMPORTS%")
PYTHON_EXE = get("PYTHON_EXE", "python")
# Secrets STORE (dir with *.env). Default is home-relative so it lands on the right
# C:\Users\<user> on any Windows box; Macs/other layouts override via machine.env.
SECRETS = get("SECRETS_DIR", os.path.join(_home(), "!CLAUDE-HP17 May26", "secrets"))


def memory_dir():
    """Live agent-memory dir for THIS machine (encoded working-dir name differs per machine)."""
    name = get("CLAUDE_MEMORY_NAME", "C--Users----CLAUDE-HP17-May26")
    return os.path.join(_home(), ".claude", "projects", name, "memory")
