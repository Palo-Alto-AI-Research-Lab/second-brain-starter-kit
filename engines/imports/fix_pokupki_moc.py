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
"""Deterministically drop superseded reglament lines from _Pokupki-Rules MOC + fix count."""
import pathlib
import os
try:
    from _paths import VAULT as _VROOT
except Exception:
    _VROOT = r"%VAULT%"
f = pathlib.Path(os.path.join(_VROOT, "01-Conversations", "Telegram", "Pokupki", "_Pokupki-Rules.md"))
SUP = [
 "reglament-pokupki-esli-na-zapros-antona-nuzhno-dat-bolee-treh-pozitsiy-of",
 "reglament-pokupki-esli-v-chate-bolee-treh-odinakovyh-pozitsiy-predostavly",
 "reglament-pokupki-kazhdyy-assistent-ezhednevno-pishet-otchet-o-pokupkah-v",
 "reglament-pokupki-kazhdyy-assistent-kazhdoe-utro-pishet-plan-na-den-v-cha",
 "reglament-pokupki-na-kazhdyy-zapros-antona-trebuyuschiy-otveta-prikladyva",
 "reglament-pokupki-pri-lyuboy-otgruzke-vsegda-ukazyvat-tsenu-dostavki",
 "reglament-pokupki-pri-otgruzke-vsegda-skidyvat-skrinshot-i-ukazyvat-tsenu",
 "reglament-pokupki-pri-vypolnenii-lyubogo-zaprosa-poiska-issledovaniya-pro",
]
lines = f.read_text(encoding="utf-8").split("\n")
out, removed = [], 0
for ln in lines:
    if any(s in ln for s in SUP):
        removed += 1
        continue
    out.append(ln)
txt = "\n".join(out)
txt = txt.replace("> 82 правил из чата «Покупки»",
                  f"> {82-removed} активных правил из чата «Покупки» (+{removed} superseded скрыто)")
f.write_text(txt, encoding="utf-8")
print("removed", removed, "-> active", 82-removed)
