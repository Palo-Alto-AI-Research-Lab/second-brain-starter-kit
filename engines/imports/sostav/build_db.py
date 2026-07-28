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
"""Sostav community → SQLite (corpus + people SQL). Deterministic, 0 LLM tokens."""
import json, glob, os, re, sqlite3, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

SRC = os.path.expanduser(r"~\Downloads\Telegram Desktop")
DB  = os.path.join(os.path.dirname(__file__), "sostav.db")
URL = re.compile(r'https?://[^\s)>\]"]+', re.I)

def text_of(m):
    t = m.get("text","")
    if isinstance(t,str): return t
    if isinstance(t,list):
        return "".join(x if isinstance(x,str) else x.get("text","") for x in t)
    return ""

def domain(u):
    try: return re.sub(r'^www\.','',u.split('/')[2].lower())
    except: return ""

if os.path.exists(DB): os.remove(DB)
c = sqlite3.connect(DB)
c.executescript("""
CREATE TABLE messages(topic TEXT, msg_id INT, from_name TEXT, from_id TEXT, date TEXT,
  unixtime INT, text TEXT, rx INT, reply_to INT, reply_count INT, is_fwd INT, fwd_from TEXT, n_links INT);
CREATE TABLE reactions(topic TEXT, msg_id INT, emoji TEXT, cnt INT);
CREATE TABLE links(topic TEXT, msg_id INT, url TEXT, domain TEXT, rx INT);
CREATE TABLE authors(from_id TEXT PRIMARY KEY, name TEXT, handle TEXT, msgs INT, chars INT,
  rx_recv INT, rx_given INT, first_seen TEXT, last_seen TEXT, topics TEXT,
  sig_msg_id INT, sig_topic TEXT, sig_rx INT, sig_text TEXT, intro_text TEXT);
CREATE TABLE topics(topic TEXT PRIMARY KEY, msgs INT, authors INT, first TEXT, last TEXT);
""")

authors = {}  # from_id -> dict
name_handle = {}  # collect @handles mentioned for a name
HANDLE = re.compile(r'@([A-Za-z][A-Za-z0-9_]{3,31})')

files = sorted(glob.glob(os.path.join(SRC,"Состав*.json")))
for f in files:
    topic = os.path.basename(f).replace("Состав. ","").replace(".json","")
    data = json.load(open(f,encoding="utf-8"))
    msgs = [m for m in data.get("messages",[]) if m.get("type")=="message"]
    replyc = collections.Counter()
    for m in msgs:
        if m.get("reply_to_message_id"): replyc[m["reply_to_message_id"]]+=1
    tmin=tmax=None; tauth=set()
    for m in msgs:
        mid=m.get("id"); fn=m.get("from") or "?"; fid=m.get("from_id") or fn
        tx=text_of(m).strip()
        reacts=m.get("reactions") or []
        rx=sum(x.get("count",0) for x in reacts)
        rc=replyc.get(mid,0)
        isfwd=1 if m.get("forwarded_from") else 0
        d=(m.get("date") or "")[:10]; ut=m.get("date_unixtime")
        links=URL.findall(tx)
        c.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (topic,mid,fn,fid,d,ut,tx,rx,m.get("reply_to_message_id"),rc,isfwd,m.get("forwarded_from"),len(links)))
        for r in reacts:
            c.execute("INSERT INTO reactions VALUES(?,?,?,?)",(topic,mid,r.get("emoji",""),r.get("count",0)))
            # rx_given via recent reactors
            for rr in (r.get("recent") or []):
                gid=rr.get("from_id")
                if gid: authors.setdefault(gid,{}); authors[gid]["rx_given"]=authors[gid].get("rx_given",0)+1
                        # ensure name
                if gid and rr.get("from"): authors[gid].setdefault("name",rr["from"])
        for u in links:
            c.execute("INSERT INTO links VALUES(?,?,?,?,?)",(topic,mid,u,domain(u),rx))
        # author agg
        a=authors.setdefault(fid,{})
        a["name"]=fn; a["msgs"]=a.get("msgs",0)+1; a["chars"]=a.get("chars",0)+len(tx)
        a["rx_recv"]=a.get("rx_recv",0)+rx
        a.setdefault("topics",set()).add(topic)
        if d:
            a["first"]=min(a.get("first",d),d); a["last"]=max(a.get("last",d),d)
        # signature = highest-rx long message
        if len(tx)>=60 and rx > a.get("sig_rx",-1):
            a["sig_rx"]=rx; a["sig_id"]=mid; a["sig_topic"]=topic; a["sig_text"]=tx[:1200]
        # intro candidate = long message with self-intro markers (prefer Общий)
        if len(tx)>=120 and re.search(r'меня зовут|мен[яе] завут|привет всем|я \w+ и я|серийный предприниматель|зовут меня', tx, re.I):
            cur=a.get("intro_text","")
            if topic=="Общий" or len(tx)>len(cur):
                a["intro_text"]=tx[:2000]
        # collect handles
        for h in HANDLE.findall(tx):
            pass
        tmin=d if tmin is None else min(tmin,d); tmax=d if tmax is None else max(tmax,d)
        tauth.add(fid)
    c.execute("INSERT INTO topics VALUES(?,?,?,?,?)",(topic,len(msgs),len(tauth),tmin,tmax))
    print(f"{topic:<20} {len(msgs):>6} msgs  {len(tauth):>4} authors")

for fid,a in authors.items():
    if not a.get("name"): continue
    c.execute("INSERT OR REPLACE INTO authors VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (fid,a.get("name"),a.get("handle"),a.get("msgs",0),a.get("chars",0),
               a.get("rx_recv",0),a.get("rx_given",0),a.get("first"),a.get("last"),
               ",".join(sorted(a.get("topics",[]))),a.get("sig_id"),a.get("sig_topic"),
               a.get("sig_rx",0),a.get("sig_text"),a.get("intro_text")))
c.commit()

n_msg=c.execute("select count(*) from messages").fetchone()[0]
n_auth=c.execute("select count(*) from authors where name is not null").fetchone()[0]
print(f"\nDB: {DB}")
print(f"messages={n_msg}  authors={n_auth}")
print("\nTOP 12 by reactions received (influence):")
for r in c.execute("select name,msgs,rx_recv,topics from authors order by rx_recv desc limit 12"):
    print(f"  {r[2]:>5}♥  {r[0][:28]:<28} msgs={r[1]:<5} [{r[3][:50]}]")
c.close()
