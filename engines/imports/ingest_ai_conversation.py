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
r"""ingest_ai_conversation.py — wrap a single AI chat transcript (Claude/ChatGPT) into a
STAGED vault note that (a) preserves the raw transcript verbatim and (b) scaffolds the
epistemic-decay schema (intent / valid_as_of / volatility / interpretation_confidence /
revisit_if) plus the structure Вопрос->интент->рассуждение->решение->триггер.

Deterministic scaffolding only; the analytic sections are left as <!-- LLM-fill --> for the
curation pass (same "deterministic parse + LLM curation" pattern as the other source adapters).
Cyrillic-safe: writes UTF-8, prints ASCII only (per the Windows cp1252 stdout rule).

USAGE:
  python ingest_ai_conversation.py --in transcript.txt --title "Remote Control с телефона" \
      [--source claude-conversation] [--origin mixed] [--volatility volatile] \
      [--date 2026-06-03] [--out-dir <staging dir>]

After it writes the staged note: fill the LLM sections, set intent/value_score/tags,
move into the vault, then `brain_embed_update.py` to index (so freshness shows in brain_ask).
"""
import argparse, datetime, re, os
from pathlib import Path

try:
    from _paths import IMPORTS
except Exception:
    IMPORTS = r"%IMPORTS%"

_CYR = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
_LAT = ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r',
        's','t','u','f','h','c','ch','sh','sch','','y','','e','yu','ya']
TRANSLIT = str.maketrans({c: l for c, l in zip(_CYR, _LAT)})  # dict form: allows multi-char (ё->yo)

def slugify(text):
    text = (text or '').lower()[:60].translate(TRANSLIT)
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text).strip('-') or 'ai-conversation'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--source', default='claude-conversation')
    ap.add_argument('--origin', default='mixed')         # anton|mixed|external -- ASK at real ingest
    ap.add_argument('--authored-by', dest='authored_by', default='hybrid')
    ap.add_argument('--volatility', default='volatile')  # durable|slow|volatile
    ap.add_argument('--date', default=None)              # date_recorded; default = today
    ap.add_argument('--out-dir', dest='out_dir',
                    default=os.path.join(IMPORTS, "staging", "01-Conversations", "AI"))
    a = ap.parse_args()

    raw = Path(a.inp).read_text(encoding='utf-8', errors='ignore').strip()
    today = datetime.date.today().isoformat()
    drec = (a.date or today)
    slug = "%s-%s" % (drec[:10], slugify(a.title))
    out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (slug + '.md')

    # fence longer than any backtick run inside the transcript, so raw text can't break out
    runs = [len(m) for m in re.findall(r'`+', raw)]
    fence = '`' * max(3, (max(runs) + 1) if runs else 3)

    fm = (
        '---\n'
        'title: "%s"\n' % a.title.replace('"', "'") +
        'type: ai-conversation\n'
        'source: %s\n' % a.source +
        'authored_by: %s\n' % a.authored_by +
        'origin: %s\n' % a.origin +
        'date_recorded: %s\n' % drec +
        'date_added: %s\n' % today +
        'valid_as_of: %s\n' % drec +
        'volatility: %s\n' % a.volatility +
        'interpretation_confidence: high      # -> low + interpretation_note if source was garbled voice/ASR\n'
        'interpretation_note: ""\n'
        'intent: ""                           # one line: what was being decided/solved\n'
        'language: ru\n'
        'tags: [ai-conversation]\n'
        'value_score: 0.0\n'
        'mentioned_entities: { people: [], projects: [] }\n'
        'unresolved_flags: []\n'
        'related_concepts: []\n'
        'revisit_if: ""                       # trip-wire to reopen any decision captured here\n'
        'expires_when: ""\n'
        '---\n'
    )

    body = (
        '\n# %s\n\n' % a.title +
        '## Интент\n<!-- LLM-fill: одна строка — что пытались решить -->\n\n'
        '## Распознавание / контекст\n<!-- LLM-fill: если источник — кривое голосовое, чем именно интерпретация неуверенна (→ interpretation_note) -->\n\n'
        '## Рассуждение\n<!-- LLM-fill: ключевые ходы мысли, проверки, противоречия -->\n\n'
        '## Решение / ответ\n<!-- LLM-fill -->\n\n'
        '## Альтернативы\n<!-- LLM-fill: таблица вариант / когда брать / минусы -->\n\n'
        '## Триггеры пересмотра\n<!-- LLM-fill: при каком условии решение/факт переоткрыть; перенести в revisit_if -->\n\n'
        '## Источники\n<!-- LLM-fill: ссылки/доки с датой обращения -->\n\n'
        '## Исходный транскрипт\n'
        '> Сохранён дословно. Не редактировать.\n\n'
        + fence + 'text\n' + raw + '\n' + fence + '\n'
    )

    out.write_text(fm + body, encoding='utf-8')
    print('WROTE', str(out))   # ASCII path only (slug is transliterated)

if __name__ == '__main__':
    main()
