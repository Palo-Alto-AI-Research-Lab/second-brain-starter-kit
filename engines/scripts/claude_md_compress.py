#!/usr/bin/env python
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
"""CLAUDE.md compression harness (deterministic, loss-proof).

Splits CLAUDE.md into ordered (header, body) sections. Reassembles using a
compressed body where one is supplied in an OVERRIDES file, else keeps the ORIGINAL
body verbatim. So a section can NEVER be silently dropped: un-overridden sections
stay full-text, the file is always valid, and compression lands incrementally.

Usage:
  claude_md_compress.py index                 -> print ordered section index + bytes
  claude_md_compress.py build <overrides.md>  -> write CLAUDE.compressed.md (staging)
  claude_md_compress.py verify <staging>      -> headers-present + canon-resolve check

Overrides file format: blocks separated by a line '@@@ <exact section header text>'
followed by the full replacement section (including its own '## ' header line).

Canon: memory claude-md-compression-contract.
"""
import io, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.path.normpath(os.path.join(HERE, "..", "CLAUDE.md"))
STAGING = os.path.normpath(os.path.join(HERE, "..", "CLAUDE.compressed.md"))

def read(p):
    return io.open(p, encoding="utf-8").read()

def split_sections(text):
    """Return (preamble, [(header_line, full_section_text), ...]).
    A section starts at a line beginning with '## '."""
    lines = text.split("\n")
    sections = []
    preamble = []
    cur = None
    for ln in lines:
        if ln.startswith("## "):
            if cur is not None:
                sections.append(cur)
            cur = [ln, [ln]]
        else:
            if cur is None:
                preamble.append(ln)
            else:
                cur[1].append(ln)
    if cur is not None:
        sections.append(cur)
    sections = [(h, "\n".join(body)) for h, body in sections]
    return "\n".join(preamble), sections

def parse_overrides(text):
    """'@@@ header' delimited replacement blocks -> {header: replacement_text}."""
    out = {}
    parts = re.split(r"(?m)^@@@ ", text)
    for p in parts:
        if not p.strip():
            continue
        first_nl = p.find("\n")
        header = p[:first_nl].strip()
        body = p[first_nl + 1:].rstrip("\n")
        out[header] = body
    return out

def cmd_index():
    text = read(CLAUDE)
    pre, secs = split_sections(text)
    print("preamble bytes:", len(pre.encode("utf-8")))
    print("sections:", len(secs))
    rows = []
    for i, (h, body) in enumerate(secs):
        rows.append((len(body.encode("utf-8")), i, h))
    for b, i, h in sorted(rows, reverse=True):
        safe = h.encode("ascii", "replace").decode("ascii")
        print("%3d | %6d B | %s" % (i, b, safe[:78]))

def cmd_build(overrides_path):
    text = read(CLAUDE)
    pre, secs = split_sections(text)
    ov = parse_overrides(read(overrides_path))
    matched = 0
    out = [pre] if pre.strip() else []
    for h, body in secs:
        key = h[3:].strip() if h.startswith("## ") else h.strip()
        # match by header text after '## ', tolerant of trailing spaces
        repl = ov.get(h) or ov.get(key) or ov.get("## " + key)
        if repl is not None:
            # FORCE the replacement's header line to equal the ORIGINAL header,
            # so compression only touches the BODY and the strict verify stays meaningful.
            rlines = repl.split("\n")
            if rlines and rlines[0].startswith("## "):
                rlines[0] = h
            else:
                rlines = [h] + rlines
            out.append("\n".join(rlines))
            matched += 1
        else:
            out.append(body)
    newtext = "\n".join(out).rstrip("\n") + "\n"
    io.open(STAGING, "w", encoding="utf-8", newline="\n").write(newtext)
    print("overrides supplied:", len(ov), "| sections matched:", matched, "of", len(secs))
    print("staging:", STAGING)
    print("orig bytes:", os.path.getsize(CLAUDE), "-> staging bytes:", os.path.getsize(STAGING))

def cmd_verify(staging_path):
    orig = read(CLAUDE); stag = read(staging_path)
    _, osecs = split_sections(orig)
    _, ssecs = split_sections(stag)
    oheaders = [h for h, _ in osecs]
    sheaders = [h for h, _ in ssecs]
    missing = [h for h in oheaders if h not in sheaders]
    print("orig sections:", len(oheaders), "| staging sections:", len(sheaders))
    if missing:
        print("!!! MISSING SECTIONS (lost rules):")
        for m in missing:
            print("   -", m.encode("ascii", "replace").decode("ascii")[:78])
    else:
        print("OK: every original section header is present in staging.")
    # canon-resolve: every cited reglament/memory pointer should exist somewhere
    cites = set(re.findall(r"(?<![a-z\-])(reglament-[a-z0-9\-]+|protocol-[a-z0-9\-]+)", stag))
    vault = "%VAULT%"
    miss_canon = []
    for c in sorted(cites):
        hits = glob.glob(os.path.join(vault, "**", "*" + c + "*"), recursive=True)
        if not hits:
            miss_canon.append(c)
    print("distinct Bible/protocol pointers cited:", len(cites),
          "| unresolved:", len(miss_canon))
    for c in miss_canon:
        print("   ? no vault file for:", c)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    c = sys.argv[1]
    if c == "index": cmd_index()
    elif c == "build": cmd_build(sys.argv[2])
    elif c == "verify": cmd_verify(sys.argv[2] if len(sys.argv) > 2 else STAGING)
    else: print("unknown:", c)
