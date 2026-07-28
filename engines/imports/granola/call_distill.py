#!/usr/bin/env python3
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
"""Stage 1 distillation: verbatim Granola transcript -> structured JSON via Sonnet.
Reads raw call JSON (from granola_pull.py), distills each NEW call into
commitments / facts / objections / alpha, each grounded with a transcript quote.
Speaker channels (microphone|speaker) are mapped to named participants from the
calendar invitees. Idempotent (distill_state.json keyed by note id + updated_at).

Model routing: grunt=Sonnet via `claude -p --model sonnet` on the SUBSCRIPTION path
(ANTHROPIC_API_KEY popped, never paid API). Canonical pattern reused from
claude_sessions\\judge_sessions_llm.py.

Outputs:
- distilled note per call -> 04-Projects\\granola-meetings\\_distilled\\<slug>.md
- commitments appended -> _imports\\granola\\commitments.jsonl (one row per commitment)
- distill_state.json advances watermark

Usage: python call_distill.py [--limit N] [--only <note_id>] [--dry]
Stdout ASCII-only (Windows cp1252).
"""
import os, sys, json, glob, re, subprocess, shutil, time

RAW_DIRS = [r"%IMPORTS%\granola\raw",
            r"%IMPORTS%\fireflies\raw"]   # both feed the same distiller
STATE = r"%IMPORTS%\granola\distill_state.json"
COMMIT_LOG = r"%IMPORTS%\granola\commitments.jsonl"
DISTILL_DIR = r"%VAULT%\04-Projects\granola-meetings\_distilled"
MODEL = "sonnet"

SCHEMA_HINT = """Return ONLY a JSON object, no prose, with EXACTLY these keys:
{
 "lang": "ru|en|mixed",
 "one_line": "<=1 sentence, what this call was about>",
 "participants": [{"name":"<best-known name or handle>","role":"<our-side|lead|other>","channel":"microphone|speaker|unknown"}],
 "commitments": [{"owner":"<name>","what":"<promise/next step>","due":"<date/relative or ''>","quote":"<verbatim transcript snippet proving it>"}],
 "facts": [{"fact":"<atomic fact about the lead/project: numbers, stage, product>","quote":"<verbatim snippet>"}],
 "objections": [{"objection":"<concern/pushback raised>","by":"<name>","quote":"<snippet>"}],
 "alpha": [{"signal":"<non-obvious insight worth acting on: intro, timing, competitive, deal term; for INTERNAL/team calls: a decision made, a risk flagged, a recurring blocker, a process/idea worth adopting>","why":"<why it matters>","quote":"<snippet>"}]
}
Rules: EVERY item MUST include a verbatim "quote" copied from the transcript (not paraphrased). If a category is empty, use []. Never invent people or facts not in the transcript. Map channel 'microphone' = our side (the account owner), 'speaker' = the counterpart, using the participant list.
INTERNAL/TEAM calls (planerka, standup, planning, ops sync between our own people): these are NOT a reason to return empty categories — STILL extract commitments (who promised what) and alpha (decisions taken, risks/blockers surfaced, ideas/process improvements worth keeping). facts/objections may be [] if genuinely absent.
CRITICAL: ALWAYS return the JSON object, even if the call is NOT a VC/deal-flow call (personal, family, logistics, test, small talk). In that case set one_line to describe what it actually was and use [] only for the categories that truly have nothing. NEVER reply with prose or a refusal instead of the JSON."""

PROMPT_TMPL = """You are extracting structured deal-flow data from ONE verbatim call transcript (VC/startup call, may be Russian, English or mixed). Do NOT summarize loosely; extract grounded structured facts.

MEETING TITLE: %(title)s
CALENDAR INVITEES (names/emails, use to name speakers): %(invitees)s

%(schema)s

TRANSCRIPT (speaker channel in brackets; 'microphone'=our account owner, 'speaker'=counterpart):
%(transcript)s
"""


def claude_exe():
    for c in ("claude", "claude.cmd"):
        p = shutil.which(c)
        if p:
            return p
    for guess in (os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
                  os.path.expanduser("~/.npm-global/bin/claude")):
        if os.path.exists(guess):
            return guess
    return "claude"


def call_sonnet(prompt):
    """Return (json_obj, err). err='AUTH' if the CLI is not logged in."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # subscription/OAuth path, never paid API
    try:
        r = subprocess.run([claude_exe(), "-p", "--model", MODEL],
                           input=prompt, capture_output=True, text=True,
                           timeout=360, env=env, encoding="utf-8")
    except Exception as e:
        return None, "EXC:" + str(e)[:60]
    out = (r.stdout or "") + (r.stderr or "")
    if re.search(r"Not logged in|Please run /login|Invalid API key|authMethod"
                 r"|Failed to authenticate|API Error: 401|OAuth.*(?:revoked|expired)", out):
        return None, "AUTH"
    # extract first JSON object
    m = re.search(r"\{.*\}", r.stdout or "", re.S)
    if not m:
        return None, "NOJSON:" + (r.stdout or "")[:60].replace("\n", " ")
    try:
        return json.loads(m.group(0)), None
    except Exception as e:
        return None, "BADJSON:" + str(e)[:40]


TRANSLIT = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
'ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}

def slugify(t):
    s = "".join(TRANSLIT.get(c, c) for c in (t or "call").lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "call"


def build_transcript(tr, cap=48000):
    """Flatten transcript segments into channel-tagged lines, capped for the model."""
    lines = []
    for seg in tr:
        sp = seg.get("speaker")
        ch = sp.get("source") if isinstance(sp, dict) else (sp or "unknown")
        tx = (seg.get("text") or "").strip()
        if tx:
            lines.append("[%s] %s" % (ch, tx))
    body = "\n".join(lines)
    if len(body) > cap:
        body = body[:cap] + "\n...[truncated]"
    return body


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {}


def render_distilled(d, meta):
    title = meta.get("title") or "Call"          # key can exist as null -> default won't apply
    date = (meta.get("created_at") or "")[:10]
    L = ["---",
         'title: "Distilled: %s"' % title.replace('"', "'"),
         "date: %s" % date, "type: call-distilled", "source: granola-distill",
         "granola_id: %s" % meta["id"], "lang: %s" % d.get("lang", ""),
         "origin: mixed", "authored_by: hybrid", "auto_generated: true",
         "tags: [granola, call-distilled, crm]", "---", "",
         "# Distilled: %s" % title, "",
         "> %s" % d.get("one_line", ""), ""]
    def sect(name, items, fmt):
        L.append("## " + name)
        if not items:
            L.append("_none_")
        for it in items:
            L.append(fmt(it))
        L.append("")
    sect("Commitments", d.get("commitments", []),
         lambda c: '- **%s** — %s%s\n  > "%s"' % (c.get("owner",""), c.get("what",""),
                   (" (due: %s)" % c["due"]) if c.get("due") else "", c.get("quote","")))
    sect("Facts", d.get("facts", []),
         lambda f: '- %s\n  > "%s"' % (f.get("fact",""), f.get("quote","")))
    sect("Objections", d.get("objections", []),
         lambda o: '- %s — _%s_\n  > "%s"' % (o.get("objection",""), o.get("by",""), o.get("quote","")))
    sect("Alpha", d.get("alpha", []),
         lambda a: '- **%s** — %s\n  > "%s"' % (a.get("signal",""), a.get("why",""), a.get("quote","")))
    return "\n".join(L), date


def main():
    dry = "--dry" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else 0
    only = sys.argv[sys.argv.index("--only")+1] if "--only" in sys.argv else None
    os.makedirs(DISTILL_DIR, exist_ok=True)
    state = load_state()
    files = []
    for _rd in RAW_DIRS:
        files += sorted(glob.glob(os.path.join(_rd, "*.json")))
    todo = []
    for f in files:
        nid = os.path.basename(f)[:-5]
        if only and nid != only:
            continue
        d = json.load(open(f, encoding="utf-8"))
        upd = d.get("updated_at", "")
        if state.get(nid) == upd:
            continue
        tr = d.get("transcript")
        if not (isinstance(tr, list) and tr):
            state[nid] = upd            # nothing to distill (no transcript)
            continue
        todo.append((nid, f, d))
    if limit:
        todo = todo[:limit]
    print("raw=%d already=%d to_distill=%d" % (len(files), len(state), len(todo)))
    if dry or not todo:
        if not dry:
            json.dump(state, open(STATE, "w", encoding="utf-8"))
        return
    done = auth_fail = err = 0
    commits = 0
    for nid, f, d in todo:
        inv = [ (a.get("name") or a.get("email") or "") for a in (d.get("attendees") or []) ]
        prompt = PROMPT_TMPL % {"title": d.get("title",""), "invitees": ", ".join(inv),
                                "schema": SCHEMA_HINT, "transcript": build_transcript(d.get("transcript"))}
        obj, e = call_sonnet(prompt)
        if e == "AUTH":
            auth_fail += 1
            print("AUTH_DOWN %s -- headless Sonnet not logged in; leaving undistilled" % nid[-6:])
            break                       # no point hammering; all will fail the same
        if e and e.startswith("NOJSON"):
            # retry ONCE with a stricter nudge; if still prose, stub-and-mark-done
            obj, e2 = call_sonnet(prompt + "\n\nREMINDER: output ONLY the JSON object, nothing else.")
            if e2 and e2.startswith("NOJSON") and e2 != "NOJSON:":
                # non-deal-flow / unparseable -> minimal stub so it never retry-loops.
                # 401-class fix 2026-07-28: stub ONLY when the model actually returned prose
                # (NOJSON with non-empty text). An EMPTY stdout means the CLI call itself
                # failed (rate-limit, timeout, auth error the regex didn't know) -- stubbing
                # then marked 207 calls done during the 27.07 OAuth outage. Empty -> skip, retry
                # next run.
                obj = {"lang": "", "one_line": "Non-deal-flow or unparseable call (Sonnet returned prose).",
                       "participants": [], "commitments": [], "facts": [], "objections": [], "alpha": []}
                e = None
                print("STUB %s (non-deal-flow/unparseable)" % nid[-6:])
            elif e2:
                e = e2                      # failed call (empty/BADJSON/EXC) -> ERR path, no state
            else:
                e = None
        if e:
            err += 1
            print("ERR %s %s" % (nid[-6:], e))
            continue
        try:
            body, date = render_distilled(obj, d)
            with open(os.path.join(DISTILL_DIR, "%s-%s.md" % (date, slugify(d.get("title") or "call"))), "w", encoding="utf-8") as fh:
                fh.write(body)
            with open(COMMIT_LOG, "a", encoding="utf-8") as fh:
                for c in (obj.get("commitments") or []):
                    fh.write(json.dumps({"granola_id": nid, "date": date, "title": d.get("title") or "",
                                         **c}, ensure_ascii=False) + "\n")
                    commits += 1
        except Exception as ex:
            err += 1
            print("RENDER_ERR %s %s" % (nid[-6:], str(ex)[:50]))
            continue
        state[nid] = d.get("updated_at", "")
        done += 1
        if done % 5 == 0:                       # checkpoint: a crash never loses progress / re-appends
            json.dump(state, open(STATE, "w", encoding="utf-8"))
    json.dump(state, open(STATE, "w", encoding="utf-8"))
    print("DONE distilled=%d commitments=%d auth_down=%d errors=%d" % (done, commits, auth_fail, err))


if __name__ == "__main__":
    main()
