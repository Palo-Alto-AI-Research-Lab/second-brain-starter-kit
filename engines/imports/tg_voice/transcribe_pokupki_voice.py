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
Transcribe the downloaded «Покупки» voice .ogg -> pokupki_voice_transcripts.jsonl (keyed by msg_id).
Pure-local (does NOT touch your Telegram account), idempotent (skips msg_ids already done),
resumable. I (Claude) can run this myself once the .ogg exist.

  pip install faster-whisper
  python transcribe_pokupki_voice.py

Tune for your machine:
  MODEL  = small (good CPU tradeoff) | medium | large-v3 (best Russian, slowest)
  DEVICE = cpu | cuda  (use cuda if you have an NVIDIA GPU — many× faster for 9.4k files)
"""
import json, re, os, sys
from pathlib import Path

# Engine = shared whisper_best.py (GPU pin + large-v3 + biasing + anti-hallucination;
# proven 2026-07-01..04). RULE: local whisper only, NEVER Telegram STT
# (reglament-voice-transcribe-only-local-whisper-never-telegram).
sys.path.insert(0, r"%IMPORTS%")
import whisper_best as wb

OGG_DIR = Path(r"C:\TG-Media\pokupki-voice")
OUT = Path(r"%IMPORTS%\pokupki_voice_transcripts.jsonl")
GLOSSARY = wb.load_glossary(r"%IMPORTS%\tg_voice\glossary_pokupki.txt")

done = set()
if OUT.exists():
    for l in OUT.read_text(encoding="utf-8").splitlines():
        if l.strip():
            done.add(json.loads(l)["msg_id"])

oggs = sorted(OGG_DIR.glob("*.ogg"))
print(f"{len(oggs)} .ogg found, {len(done)} already transcribed")
model, dev = wb.load_model()
n = 0
with OUT.open("a", encoding="utf-8") as f:
    for og in oggs:
        m = re.search(r"_(\d+)\.ogg$", og.name)
        if not m:
            continue
        mid = int(m.group(1))
        if mid in done:
            continue
        text, info = wb.transcribe(og, glossary=GLOSSARY)
        f.write(json.dumps({"msg_id": mid, "file": og.name, "lang": info.language,
                            "dur": round(info.duration, 1), "text": text}, ensure_ascii=False) + "\n")
        f.flush(); n += 1
        if n % 50 == 0:
            print(f"{n} new transcribed (last msg_id {mid})", flush=True)
print("DONE new", n, "->", OUT)
