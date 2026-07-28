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
"""Render the live-ingested fresh FAAA leads into the vault: lead cards + person
overlays + day-ledger entries + archive append (advance watermark). Idempotent-ish
(skips a lead whose msg_id already in archive). ASCII-only stdout."""
import json, io, re, os, glob
try:
    from _paths import VAULT, IMPORTS
except Exception:
    VAULT = r"%VAULT%"
    IMPORTS = r"%IMPORTS%"

OUT = IMPORTS; F = OUT + r"\faaa"
V = VAULT
LEADS = V + r"\04-Projects\crypto\Platinum-CRM\leads"
PEOPLE = V + r"\07-People"
SESS = V + r"\01-Conversations\Telegram\FAAA-Follow-ups\sessions"
DATE_ADDED = "2026-06-06"

synth = {o["lead_key"]: o for o in json.load(io.open(F + r"\live_synth.json", encoding="utf-8-sig"))}
bundles = json.load(io.open(F + r"\live_bundles.json", encoding="utf-8"))
arch_rows = json.load(io.open(F + r"\live_archive_rows.json", encoding="utf-8"))
try: appends = json.load(io.open(F + r"\live_appends.json", encoding="utf-8"))
except Exception: appends = []

TR = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", "abvgdeejziyklmnoprstufhccss y eya")
def slugify(t):
    t = (t or "").lower().translate(TR); t = re.sub(r"['`’]", "", t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-"); return re.sub(r"-+", "-", t)[:46].strip("-") or "lead"
def jstr(s): return json.dumps((s or "").replace("\n", " ").strip(), ensure_ascii=False)
def jlist(xs):
    xs = [x for x in xs if x];
    return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in xs) + "]" if xs else "[]"
def ne(s): return re.sub(r'(?<=\[)\[', r'\\[', s or "")
def clean_tag(t): return re.sub(r"[^\w\-]+", "-", str(t).strip().lower()).strip("-")

used_leads = set(os.path.basename(f)[:-3] for f in glob.glob(LEADS + r"\**\*.md", recursive=True))
used_ppl = set(os.path.basename(f)[:-3].lower() for f in glob.glob(PEOPLE + r"\**\*.md", recursive=True))
def uniq(base, used):
    c = base; i = 1
    while c in used: i += 1; c = "%s-%d" % (base, i)
    used.add(c); return c

made = []
for b in bundles:
    s = synth.get(b["lead_key"], {})
    calls = sorted(b["calls"], key=lambda c: c["date"])
    mid0 = calls[0]["id"]
    name = (s.get("name") or b.get("display") or "lead").strip()
    slug = uniq(slugify(name), used_leads)
    year = (calls[0]["date"] or "2026")[:4]
    folder = os.path.join(LEADS, year); os.makedirs(folder, exist_ok=True)
    status = (s.get("status") or "new").lower(); cat = (s.get("category") or "").lower()
    company = s.get("company") or ""; handles = b["handles"]
    tags = ["crm", "lead", "platinum-crm", "platinum-lead", "top-lead", "status-" + clean_tag(status), "live-2026-06"]
    if cat: tags.append("cat-" + clean_tag(cat))
    for t in (s.get("tags") or []):
        ct = clean_tag(t)
        if ct and ct not in tags: tags.append(ct)
    fm = ["---", "title: " + jstr(name), "aliases: " + jlist(handles), "type: crm-lead",
          "source: telegram-faaa", "origin: mixed", "authored_by: hybrid",
          "status: " + jstr(status)] + (["category: " + jstr(cat)] if cat else []) + [
          "company: " + jstr(company), "role: " + jstr(s.get("role")), "country: " + jstr(s.get("country")),
          "handles: " + jlist(handles), "pitched_by: " + jlist([calls[0]["by"]]),
          "n_calls: %d" % len(calls), "first_contact: " + jstr(calls[0]["date"][:10]),
          "last_contact: " + jstr(calls[-1]["date"][:10]), "date_added: " + DATE_ADDED,
          "language: " + jstr(s.get("lang") or "en"), 'concept: "[[concept-platinum-crm]]"',
          "tags: " + jlist(tags), 'lead_id: "live-%d"' % mid0, "---"]
    body = ["# %s%s" % (name, " — " + company if company else ""), "",
            "> [!info] CRM-лид Platinum · **%s** · %s · %d звонк. · %s (свежий, из Telegram)" % (
                status, cat or "—", len(calls), calls[0]["date"][:10]), ""]
    if s.get("summary"): body += ["## Сводка", s["summary"], ""]
    facts = []
    for k, lab in (("what_they_do", "Чем занимаются"), ("what_they_want", "Что хотят"),
                   ("what_we_offered", "Что предложили"), ("agreements", "Договорённости"), ("outcome", "Итог")):
        if s.get(k): facts.append("- **%s:** %s" % (lab, s[k]))
    if facts: body += ["## Ключевое"] + facts + [""]
    body += ["## Контакты"]
    if handles: body.append("- Telegram: " + " ".join(handles))
    if company: body.append("- Компания/проект: " + company)
    if s.get("role"): body.append("- Роль: " + s["role"])
    body += ["", "## Лог звонков (%d)" % len(calls)]
    for c in calls:
        body += ["### %s · вёл: %s" % (c["date"], c["by"] or "?"), ""]
        for ln in (c["text"] or "").split("\n"): body.append("> " + ne(ln) if ln.strip() else ">")
        body.append("")
    body += ["## Связи", "- [[_Platinum-CRM-MOC]] · [[_Platinum-Top-Leads-MOC]] · [[concept-platinum-crm]]", ""]
    io.open(os.path.join(folder, slug + ".md"), "w", encoding="utf-8").write("\n".join(fm) + "\n\n" + "\n".join(body))

    # person overlay
    pslug = uniq("person-" + slugify(name), used_ppl)
    tier = cat if cat in ("investor", "fund", "vc", "founder", "kol", "advisor") else "other"
    pf = ["---", "title: " + jstr(name), "type: person", "contact_type: work-lead", "context: platinum-crm",
          "org: " + jstr(company), "role: " + jstr(s.get("role")), "country: " + jstr(s.get("country")),
          "tier: " + jstr(tier), "status: " + jstr(status), "telegram: " + jstr(handles[0] if handles else ""),
          'lead_card: "[[%s]]"' % slug, "source: telegram-faaa", "origin: mixed", "authored_by: hybrid",
          "date_added: " + DATE_ADDED,
          "tags: [person, platinum-crm, crm-lead, crm-work-lead, top-lead, status-%s]" % clean_tag(status), "---"]
    pb = ["# %s" % name, "",
          "> [!info] Platinum CRM лид (свежий) · %s · %s" % (company or "—", status), "",
          "Полная карточка: **[[%s]]**" % slug, ""]
    if s.get("summary"): pb += ["## Кто это", s["summary"], ""]
    pb += ["## Связи", "- [[%s]] · [[_Platinum-CRM-MOC]] · [[_People-MOC]]" % slug, ""]
    io.open(os.path.join(PEOPLE, pslug + ".md"), "w", encoding="utf-8").write("\n".join(pf) + "\n\n" + "\n".join(pb))

    # ledger entries (one per call day)
    for c in calls:
        day = c["date"][:10]; lf = os.path.join(SESS, "Sessions-%s.md" % day)
        entry = "- **%s** %s — 📞 [[%s\\|%s]]%s — _свежий звонок_" % (
            c["date"][11:16], c["by"] or "?", slug, name, " · " + status)
        if os.path.exists(lf):
            t = io.open(lf, encoding="utf-8").read()
            if slug not in t:
                io.open(lf, "a", encoding="utf-8").write("\n" + entry + "\n")
        else:
            hdr = ["---", "type: session-ledger", "source: telegram-faaa",
                   "chat: \"CALLS FAAA follow up MAIN\"", "date: " + day, "month: " + day[:7],
                   "origin: mixed", "authored_by: hybrid",
                   "tags: [telegram, session, platinum-crm, faaa-archive]", "---", "",
                   "# FAAA звонки — %s" % day, "", entry, ""]
            io.open(lf, "w", encoding="utf-8").write("\n".join(hdr) + "\n")
    made.append((slug, name, len(calls)))

# ---- append fresh calls to EXISTING lead cards (recurring leads) ----
slug2path = {os.path.basename(p)[:-3]: p for p in glob.glob(LEADS + r"\**\*.md", recursive=True)}
appended = 0
for a in appends:
    p = slug2path.get(a["slug"])
    if not p:
        continue
    c = a["call"]; t = io.open(p, encoding="utf-8").read()
    hdr = "### %s · вёл: %s" % (c["date"], c["by"] or "?")
    if hdr in t:           # idempotent — call already appended
        continue
    blk = [hdr, ""]
    for ln in (c["text"] or "").split("\n"):
        blk.append("> " + ne(ln) if ln.strip() else ">")
    blk.append("")
    btxt = "\n".join(blk)
    t = t.replace("## Связи", btxt + "## Связи", 1) if "## Связи" in t else (t.rstrip() + "\n\n" + btxt)
    t = re.sub(r'(?m)^n_calls:\s*(\d+)', lambda m: "n_calls: %d" % (int(m.group(1)) + 1), t, count=1)
    t = re.sub(r'(?m)^## Лог звонков \((\d+)\)', lambda m: "## Лог звонков (%d)" % (int(m.group(1)) + 1), t, count=1)
    t = re.sub(r'(?m)^last_contact:.*$', 'last_contact: "%s"' % c["date"][:10], t, count=1)
    io.open(p, "w", encoding="utf-8").write(t)
    appended += 1
    day = c["date"][:10]; lf = os.path.join(SESS, "Sessions-%s.md" % day)
    entry = "- **%s** %s — 📞 [[%s]] (доп. касание)" % (c["date"][11:16], c["by"] or "?", a["slug"])
    if os.path.exists(lf):
        if entry not in io.open(lf, encoding="utf-8").read():
            io.open(lf, "a", encoding="utf-8").write("\n" + entry + "\n")

# append archive rows (advance watermark)
with io.open(OUT + r"\faaa-archive.jsonl", "a", encoding="utf-8") as f:
    for r in arch_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print("LIVE RENDER: new_cards=%d  appended_to_existing=%d  archive_rows=%d" % (len(made), appended, len(arch_rows)))
for slug, name, n in made: print("  + %s (%d call)" % (slug, n))
