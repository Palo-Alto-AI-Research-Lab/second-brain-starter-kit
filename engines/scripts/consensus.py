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
"""consensus.py -- autonomous machine<->machine CONSENSUS engine (Phase 1).

WHY: the machines already MOVE messages reliably (bus_send.py dual-rail), but they could not
NEGOTIATE a decision and converge WITHOUT Anton acting as courier. This adds the missing layer:
a structured propose -> counter -> accept -> commit negotiation with a deterministic tie-break,
an append-only decision log, idempotency over the redundant rails, and a hard human gate for
Tier-2. Synthesis of two Deep-Research reports (#19, #21) + our own canon.

ARCHITECTURE (Anton 2026-06-28):
  * SOURCE OF TRUTH (machine-readable): per-machine single-writer JSONL shards
      <bus>/_decisions/log-<MACHINE>.jsonl   (option A; single-writer => 0 Syncthing conflicts,
      same forever-fix as the read-bookmarks; git 3-way-merges append-only text cleanly).
      Each machine appends ONLY to its own shard; readers MERGE all shards by proposal_id and
      dedup events by event_id (idempotent across duplicate multi-rail delivery).
  * ALWAYS-ON DUAL + human-visible feed + recoverable record: Telegram chat 03. EVERY event is
      emitted through bus_send.py, which dual-sends to BOTH Telegram-03 and _machine-bus BY
      CONSTRUCTION (single rail is forbidden) -> "TG always on" is structural, not optional, and
      every envelope carries type+id+actor+subject so the negotiation is readable in plain sight
      and the ledger is reconstructable from Telegram alone if a shard is lost.

GOVERNANCE: hub HUB1 = fixed leader (disagree-and-commit tie-break). Tier-2
(money/outbound/irreversible/secrets/config) NEVER auto-commits -> escalates to Anton (QQQ).

Verbs:
  propose "<subject>" [--details '<json>'] [--tier N] [--id <id>] [--reversible]
  respond <id> accept|counter|reject ["text"]
  commit  <id>                      # record the agreed decision-of-record (the AGENT then applies it)
  verify  <id> "<proof>"            # cross-agent epistemic flag: both must verify before 'done'
  escalate <id> "<reason>"          # hand a stuck/risky proposal to Anton
  status  <id>                      # show one proposal's merged state + event timeline
  list    [--open|--all]            # list proposals (default: open ones)
  tick                              # deterministic driver: timeouts, round-cap, tie-break, Tier-2 gate
  pending [--json]                  # 0-LLM detector: open proposals AWAITING MY RESPONSE (judge work-list)
  approve <id> "<proof>"            # record the HUMAN's OK (QQQ: who/where/msg-id) -> unlocks commit for tier-2

Env: MACHINE_KEY / COMPUTERNAME = me; MACHINE_BUS_DIR = bus root; CONSENSUS_NO_BUS=1 skips the
dual-send (tests). Config <bus>/_decisions/consensus.json overrides leader/round_cap/timeout_min;
optional "peer_timeout_min": {"<MACHINE>": min} = per-machine SLA (sleeping laptop/mac get a
longer window than the always-on hub) -- effective deadline = slowest peer we are WAITING ON;
optional "quorum": {"enabled": bool, "presence_fresh_min": 45, "challenge_hours": 24} = Phase A
awake-committee + tentative_commit degraded path (dark until the whole fleet runs this build);
S3 keys: "armed_build" (must equal ENGINE_BUILD or the engine runs OBSERVE_ONLY) and
"observe_only": true (explicit kill-switch, wins over armed_build).
"""
import os, sys, json, glob, uuid, datetime, subprocess, re
import time as time_mod

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
BUS = os.environ.get("MACHINE_BUS_DIR", r"%VAULT%\_machine-bus")
ME  = os.environ.get("MACHINE_KEY", os.environ.get("COMPUTERNAME", "unknown")).strip()

# S1 IDENTITY LAYER (2026-07-04, spec = decision-consensus-blockchain-reuse-roadmap par.7-S1):
# per-machine Ed25519 keys; every event we WRITE gets a detached SSH signature (dark: absence
# of the module / key never blocks the ledger; enforcement is a later config flag once the
# whole fleet signs). Audit verb: `sigs`.
try:
    import fleet_sign
except Exception:
    fleet_sign = None

DEFAULTS = {"leader": "HUB1", "round_cap": 3, "timeout_min": 30}
TYPES = {"PROPOSE", "COUNTER", "ACCEPT", "REJECT", "COMMIT", "VERIFY", "ESCALATE", "HUMAN_APPROVED",
         "TENTATIVE_COMMIT", "FINALIZE"}

# QUORUM PHASE A (2026-07-02, Anton "++++", spec = vault dr-quorum-sleepy-fleet-2026-07-02):
# awake-committee snapshot at PROPOSE + explicit degraded path (TENTATIVE_COMMIT + challenge
# window) for tier-1. DARK-DEPLOYED behind a config flag: old engines don't know TENTATIVE_COMMIT,
# so "quorum": {"enabled": false} stays until the WHOLE fleet runs this build (same md5) --
# flipping early would recreate the divergent-engines class fixed 2026-07-02 morning.
# Presence lease = the existing .robot-alive-<MACHINE>.log stamps in the bus root (each inbox
# robot refreshes ~20 min): a machine is AWAKE iff its stamp is fresher than presence_fresh_min.


def _qcfg(cfg):
    q = cfg.get("quorum") or {}
    return {"enabled": bool(q.get("enabled")),
            "presence_fresh_min": int(q.get("presence_fresh_min", 45)),
            "challenge_hours": int(q.get("challenge_hours", 24))}


def _awake(qc):
    """Machines with a fresh presence stamp + ME (I am running, therefore awake)."""
    out = {ME}
    now = time_mod.time()
    for f in glob.glob(os.path.join(BUS, ".robot-alive-*.log")):
        name = os.path.basename(f)[len(".robot-alive-"):-len(".log")]
        try:
            if name and now - os.path.getmtime(f) <= qc["presence_fresh_min"] * 60:
                out.add(name)
        except Exception:
            continue
    return sorted(out)


# LEADER-DOWN FAILOVER (2026-07-10, ANCHOR1 self-setup session; ratified via Tier-1 consensus).
# GAP: the tie-break arbiter role (tier-0 timeout auto-resolve -- a single-writer function) is
# pinned to cfg["leader"]. If the leader dies, NOTHING re-assigns it: tier-0 proposals then sit
# unresolved until a human happens to notice (only the external dead-man's-switch pings). This
# lets any ticking NON-leader that observes the leader's presence stamp STALE past `leader_down_min`
# treat the fallback arbiter (cfg["fallback_arbiter"], default hub HUB1) as the effective
# arbiter FOR THAT TICK; the fallback arbiter also emits ONE 02/03 escalation ping per down-episode.
# Reuses the EXISTING presence lease (.robot-alive-<M>.log mtime, same as _awake) -- no new
# heartbeat. Fail-SAFE by construction: triggers ONLY on a STALE stamp (positive evidence); an
# ABSENT stamp does NOT fail over, and the leader itself (ME==leader) never deems itself down.
LEADER_DOWN_MIN_DEFAULT = 70
FALLBACK_ARBITER_DEFAULT = "HUB1"


def _leader_down_min(cfg):
    try:
        return int(cfg.get("leader_down_min") or LEADER_DOWN_MIN_DEFAULT)
    except Exception:
        return LEADER_DOWN_MIN_DEFAULT


def _presence_age_min(machine):
    """Age in MINUTES of a machine's presence stamp (.robot-alive-<M>.log mtime); None if absent."""
    try:
        f = os.path.join(BUS, ".robot-alive-%s.log" % machine)
        return (time_mod.time() - os.path.getmtime(f)) / 60.0
    except Exception:
        return None


def _effective_arbiter(cfg):
    """Who holds the tie-break function THIS tick + whether we FAILED OVER to the fallback.

    S9 ROAMING-LEADER (2026-07-16, Anton HUMAN_APPROVED #b89596dd "корона=оператор, машины равны"):
    when cfg["arbiter_order"] is present AND cfg["arbiter_order_armed"] is true, the tie-break
    arbiter is the FIRST machine in that ordered list whose presence stamp is FRESH (age <=
    leader_down_min). ME is always fresh (I am running). Absent/stale higher-priority machines are
    skipped to the next -- so a laptop that travels never wedges the fleet; the first live machine
    in Anton's priority order arbitrates, computed identically by every ticking peer -> single
    arbiter, no split. If NONE in the list is fresh, last resort = list head (with failed_over=True).
    `failed_over` is True whenever the acting arbiter is not the list head (used only for the ONE
    escalation ping). Dormant (armed False / key absent) -> legacy fixed-leader path below, so an
    S8 peer and an unarmed S9 peer behave identically (no divergent-engines class).
    Returns (arbiter, failed_over, arbiter_age_min_or_None)."""
    order = cfg.get("arbiter_order")
    if order and cfg.get("arbiter_order_armed"):
        thresh = _leader_down_min(cfg)
        for m in order:
            if m == ME:
                return m, (m != order[0]), None
            age = _presence_age_min(m)
            if age is not None and age <= thresh:
                return m, (m != order[0]), age
        return order[0], True, None
    # ---- legacy fixed-leader path (S8-compatible; unchanged behaviour) ----
    leader = cfg.get("leader")
    if leader == ME:
        return leader, False, None
    age = _presence_age_min(leader)
    if age is not None and age > _leader_down_min(cfg):
        return (cfg.get("fallback_arbiter") or FALLBACK_ARBITER_DEFAULT), True, age
    return leader, False, age


def _leaderdown_signal(cfg, failed_over, leader_age):
    """Emit exactly ONE 02/03 escalation ping when the leader goes down, and one RECOVERED note
    when it returns -- idempotent across ticks via a synced state file. ONLY the fallback arbiter
    signals, so N peers do not N-plex the alert. Uses the EXISTING _police (02 + ntfy) / _bus (03)
    rails -- no new channel."""
    fallback = cfg.get("fallback_arbiter") or FALLBACK_ARBITER_DEFAULT
    if ME != fallback:
        return
    st_path = os.path.join(_dir(), "leaderdown-%s.json" % ME)
    try:
        was_down = bool(json.load(open(st_path, encoding="utf-8")).get("down"))
    except Exception:
        was_down = False
    if failed_over and not was_down:
        _police("👑⬇️ LEADER DOWN: %s presence stale %.0fmin (>%dmin). %s (fallback) assumes the "
                "tie-break arbiter role for the fleet until the leader's heartbeat returns."
                % (cfg.get("leader"), leader_age or 0, _leader_down_min(cfg), ME))
        try:
            json.dump({"down": True, "since": _iso(_now()), "leader": cfg.get("leader")},
                      open(st_path, "w", encoding="utf-8"))
        except Exception:
            pass
    elif (not failed_over) and was_down:
        _bus("👑✅ LEADER RECOVERED: %s presence fresh again; %s stands down from fallback arbiter."
             % (cfg.get("leader"), ME))
        try:
            json.dump({"down": False, "recovered": _iso(_now())}, open(st_path, "w", encoding="utf-8"))
        except Exception:
            pass


# Tier-tripwire: deterministic keyword guard against TIER MIS-CLASSIFICATION (DR #2 top risk).
# The whole Tier-2->QQQ safety gate hinges on the agent labelling --tier correctly; if it
# mislabels a destructive action as Tier-0 the gate never fires. This bumps tier to 2 on any
# dangerous keyword, regardless of the agent's label. List is an editable txt (Anton maintains
# it "with a hammer"); a built-in fallback keeps the guard alive if the file is missing.
TRIPWIRE_FILE = os.path.join(SCRIPTS, "tier_tripwire.txt")
_TRIPWIRE_FALLBACK = [
    "delete", "удали", "rm -", "drop", "wipe", "truncate", "format", "overwrite", "purge",
    "remove-item", "send", "отправ", "wire", "transfer", "перевод", "оплат", "деньги", "money",
    "рассыл", "mass", "publish", "deploy", "secret", "секрет", "пароль", "password", "token",
    "api key", "credential", ".env", "canon", "канон", "claude.md", "operating-agreement",
    "uninstall", "revoke", "factory reset", "git push --force",
]


def _tripwire_terms():
    """Editable keyword list (one per line, # comments); fall back to built-in if file missing."""
    try:
        terms = []
        for ln in open(TRIPWIRE_FILE, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                terms.append(ln.lower())
        return terms or list(_TRIPWIRE_FALLBACK)
    except Exception:
        return list(_TRIPWIRE_FALLBACK)


def _tripwire_hit(text):
    """Return the first dangerous term found in text, else None.

    Word-terms that START with a word char (Latin/Cyrillic letter, digit, or '_')
    match only at a WORD START: not preceded by another word char. So 'send' fires
    on 'send money' / 'sending' but NOT on the same letters buried inside an
    identifier like 'bus_send' (preceded by '_'). Suffix inflections still match
    (deploy->deployment, отправ->отправить), preserving the stem intent. Phrases or
    terms starting with punctuation ('.env', 'rm -', 'api key') keep plain substring.
    Fixes the 2026-06-30 false-positive where 'bus_send.py' tripped the 'send' term.
    The gate stays fail-safe: this only removes a FALSE class, real terms still catch.
    """
    low = (text or "").lower()
    for t in _tripwire_terms():
        if t and (t[0].isalnum() or t[0] == "_"):
            if re.search(r"(?<!\w)" + re.escape(t), low):
                return t
        elif t and t in low:
            return t
    return None


def _tripwire_scan_text(subject, details=None):
    """Text the tripwire guards = the ACTION (`subject`), NOT the supporting `details`/evidence.

    Scanning evidence prose caused FALSE Tier-2 bumps when a proposal merely MENTIONED a
    dangerous word as diagnostic context (2026-06-30: "laptop sends cluster-config" tripped
    'send'; "apikey matches" tripped 'apikey' — neither was the action). The action verb of a
    genuine Tier-2 lives in the subject ("wire $X", "delete Y", "publish Z", "revoke token"),
    so guarding the subject keeps the gate fail-safe while dropping the mention-in-evidence
    false class. Fail-safe: a blank/whitespace subject falls back to scanning details too, so
    the gate is NEVER blind. Put evidence in --details to keep it out of the guard.
    """
    subject = subject or ""
    if subject.strip():
        return subject
    return "%s %s" % (subject, details or "")


def _dir():
    d = os.path.join(BUS, "_decisions")
    os.makedirs(d, exist_ok=True)
    return d


def _cfg():
    p = os.path.join(_dir(), "consensus.json")
    c = dict(DEFAULTS)
    try:
        with open(p, encoding="utf-8") as fh:
            c.update(json.load(fh))
    except Exception:
        pass
    return c


def _shard():
    return os.path.join(_dir(), "log-%s.jsonl" % ME)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt):
    # microsecond precision: kills same-second ordering ties between PROPOSE/COUNTER/ACCEPT
    # (a real causality bug -- two events in the same second sorted by shard filename, not order).
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_ts(s):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):  # new + back-compat
        try:
            return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass
    return _now()


VOTE_TYPES = {"ACCEPT", "COUNTER", "REJECT", "COMMIT", "VERIFY", "TENTATIVE_COMMIT"}


# PROOF-GRADING (2026-07-21, Anton's mandate 2026-07-20 «чиним корень класса DONE-без-доказательства»;
# incidents: #f2e71c9a worktree-hook stood DONE with 2 VERIFYs while the replacement NEVER ran;
# #545f4ba6 delivery-claim; hub blind --force). A VERIFY counts as *proven* only when its proof
# text carries at least one DETERMINISTIC piece of evidence — a command exit code (exit 0 / rc=0),
# a content hash (md5/sha1/sha256 hex), or a before→after counter. Bare prose («сделал, всё ок»)
# = *unproven* and no longer closes a thread once the rule is armed.
# ARM / BACK-COMPAT: config key "proof_grading_after" (ISO ts, like sig_enforce_after). Absent or
# empty -> legacy behaviour, every VERIFY counts (old engines + old threads unbroken). Events with
# ts <= threshold are grandfathered proven, so arming never re-opens history. This is NOT a
# cryptographic liar-proof (one can type "exit 0" without running anything) — it is a structural
# floor: the proof must at least CLAIM something re-checkable (re-run the command → same exit /
# hash / counter), which is exactly what the worktree-hook VERIFYs never had.
_PROOF_PATTERNS = (
    re.compile(r"(?<!\w)(?:exit(?:\s*code)?|rc|returncode|errorlevel|код)\s*[=:]?\s*0(?!\d)", re.I),
    re.compile(r"\b(?:[0-9a-f]{64}|[0-9a-f]{40}|[0-9a-f]{32})\b", re.I),   # sha256/sha1/md5
    re.compile(r"\d+\s*(?:->|→|=>)\s*\d+"),                                 # counter N->M
    re.compile(r"(?:до|before|было)\W{0,3}\d+.{0,60}?(?:после|after|стало)\W{0,3}\d+", re.I | re.S),
)


def _proof_grading_after(cfg=None):
    try:
        return ((cfg or _cfg()).get("proof_grading_after") or "").strip()
    except Exception:
        return ""


def _proof_grade(proof):
    """'proven' iff the text carries a deterministic evidence pattern, else 'unproven'."""
    return "proven" if any(p.search(proof or "") for p in _PROOF_PATTERNS) else "unproven"


def _verify_proven(ev, threshold):
    """Grade one VERIFY event under the armed threshold (ts <= threshold = grandfathered)."""
    if not threshold:
        return True
    if (ev.get("ts") or "") <= threshold:
        return True
    return _proof_grade(ev.get("proof", "")) == "proven"


def _wm_path():
    return os.path.join(_dir(), "wm-%s.json" % ME)


def _wm_load():
    try:
        return json.load(open(_wm_path(), encoding="utf-8"))
    except Exception:
        return {}


# S3 VERIFIED-ACTIVATION (2026-07-05, proposal #723594f6, seed SEED-S3-dark-build):
# a freshly DELIVERED engine must be inert until the fleet-wide activation epoch flips.
# Mechanism = one config key: consensus.json "armed_build" must equal THIS build's id,
# else every mutating path (shard append, bus send, police ping) is quarantined into an
# observation log ("what I WOULD have done"). Old engines ignore the key; a lagging peer
# that clobbers a live engine with this build therefore FAILS SAFE (observes, never acts).
# Explicit "observe_only": true in config = kill-switch that wins even when armed.
ENGINE_BUILD = "S9-20260716"

# ---- S2 (Consensus-2.0) TYPED-PROPOSAL SHADOW (2026-07-23, task-2026-07-17-shadow-builds; queue
# row #7 in Shadow-First-Queue.md). PONAROSHKU / dark: on every REAL propose the engine ALSO
# classifies the proposal into the v2 schema (risk_tier / track / freeze) and writes ONE observe
# record answering the honest sensor question "would this proposal have BENEFITED from typing?".
# ZERO behavior change -- the live negotiation path is untouched; this only appends to the
# per-machine observe shard (single-writer, same file as S3's OBSERVE_ONLY log).
#
# Flag `proposal_v2_shadow` in consensus.json (Anton 17.07 "default OFF, пишет observe-лог"):
#   absent / false / "shadow"  -> SHADOW (DEFAULT): classify + log, behavior AS NOW. The week-long
#                                 data-collection state this build ships.
#   "off"                      -> kill-switch: skip the shadow observer entirely (still 0 behavior
#                                 change) -- an operator brake if the shadow ever misbehaves.
#   true / "armed"             -> RESERVED for the FUTURE flip to real typed routing/freeze. NOT
#                                 built in S2-20260723; an armed value changes NOTHING yet and is
#                                 treated as SHADOW (data keeps flowing) -- "не армить на прод".
# Datchik (flip-or-kill after a week): `consensus.py v2-shadow` counts DISTINCT real proposals that
# would_benefit==True over the window. shadow_review.py sees build S2-20260723 in the shadows and
# scores agreement (the would_append rides the SAME (pid, PROPOSE) the armed engine really wrote).
S2_SHADOW_BUILD = "S2-20260723"

# track = deterministic keyword routing (0 LLM, AK-47). FIRST match wins; else "general". The
# point of a track is that today's engine routes ONLY on risk_tier -- track/freeze are invisible
# to it, so a sensitive-but-low-tier proposal slips the tier-only net. That gap IS the sensor.
V2_TRACKS = (
    ("financial", ("деньг", "оплат", "payment", "invoice", "счёт", " trade", "покуп", "перевод",
                   "transfer", "crypto", "usdt", "budget", "spend", "refund", "рефанд", "выплат")),
    ("secrets",   ("secret", "пароль", "token", "credential", "api key", "api-key", "приватн ключ",
                   "private key", "seed phrase", "мнемоник")),
    ("outbound",  ("outreach", "письм", "email", "публик", "рассыл", "reply", "отправ наруж",
                   "post to", "tweet", "коммент", " dm ", "лид", "напиши клиент")),
    ("canon",     ("canon", "reglament", "регламент", "правил", "claude.md", "memory.md", "библи",
                   "bible", "operating-agreement", "standing-", "always-loaded")),
    ("infra",     ("sync", "syncthing", "heartbeat", "leader", "arbiter", "fence", "shard",
                   "consensus", " cron", "scheduled", "watchdog", "backup", "config", "engine",
                   "ledger", "quorum")),
)


def _v2_shadow_mode(cfg=None):
    """'shadow' (default -> classify & log, behavior unchanged) | 'off' (kill-switch, no log)."""
    v = (cfg or _cfg()).get("proposal_v2_shadow")
    if isinstance(v, str) and v.strip().lower() == "off":
        return "off"
    return "shadow"   # absent/false/"shadow"/true/"armed" all shadow-log in this build (not armed)


def _v2_track(subject, details):
    hay = (subject or "")
    if isinstance(details, dict):
        hay += " " + json.dumps(details, ensure_ascii=False)
    elif details:
        hay += " " + str(details)
    hay = hay.lower()
    for name, kws in V2_TRACKS:
        if any(k in hay for k in kws):
            return name
    return "general"


def _v2_classify(subject, details, tier, reversible, tripwire_hit):
    """Deterministic v2 typing + the HONEST would_benefit verdict. Falsifiable by design: proposals
    that are already tier-2 (engine escalates) or trivial (general/low-tier) return False -- only a
    SENSITIVE track carried at a LOW tier (the net the tier-only engine misses) returns True."""
    tier = int(tier or 0)
    track = _v2_track(subject, details)
    sensitive = track in ("financial", "secrets", "outbound", "canon")
    # freeze = "hold this before it commits": sensitive class, or already tier-2, or a tripwire hit.
    freeze = sensitive or tier >= 2 or bool(tripwire_hit)
    if tier >= 2:
        return {"risk_tier": tier, "track": track, "freeze": freeze, "would_benefit": False,
                "reason": "tier-2 already escalates to human; type/track adds no routing",
                "tripwire": bool(tripwire_hit)}
    if sensitive:
        return {"risk_tier": tier, "track": track, "freeze": freeze, "would_benefit": True,
                "reason": "track=%s at tier-%d would be frozen/routed; tier-only engine auto-paths it"
                          % (track, tier), "tripwire": bool(tripwire_hit)}
    return {"risk_tier": tier, "track": track, "freeze": freeze, "would_benefit": False,
            "reason": "track=general, tier<2, no freeze -- tier-only path adequate",
            "tripwire": bool(tripwire_hit)}


def _v2_shadow_observe(ev, subject, details, tier, reversible, tripwire_hit, cfg=None):
    """Dark S2 sensor. Wrapped so a bug here can NEVER break a live propose (the whole raison
    d'etre of shadow-first: dark code in the live engine must fail silently, not brick it)."""
    try:
        cfg = cfg or _cfg()
        if _v2_shadow_mode(cfg) == "off":
            return
        v2 = _v2_classify(subject, details, tier, reversible, tripwire_hit)
        rec = {"ts": _iso(_now()), "machine": ME, "build": S2_SHADOW_BUILD, "kind": "would_append",
               "event": {"proposal_id": ev.get("proposal_id"), "type": "PROPOSE",
                         "subject": (subject or "")[:70]},
               "v2": v2}
        with open(os.path.join(_dir(), "observe-%s.jsonl" % ME), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("   [S2-shadow] track=%s freeze=%s would_benefit=%s (%s)"
              % (v2["track"], v2["freeze"], v2["would_benefit"], S2_SHADOW_BUILD))
    except Exception as e:
        print("   (S2 shadow observe skipped: %s)" % e)

# ---- S1-ENFORCE (QQQ Anton 2026-07-06 "qqq на Ed25519 enforce, делай"; consensus #e9299b25;
# DR26-07-06-HUB-03 containment p.1). Config key `sig_enforce_after` (ISO ts, set at activation):
# every event STRICTLY NEWER must carry a GOOD Ed25519 sig from the signers registry.
#   unsigned newer than threshold -> QUARANTINED (dropped on read; raw line stays in shard for audit)
#   BAD sig (forged/tampered/revoked/unknown signer) -> QUARANTINED
#   signed but registry unreadable locally (verify=None) -> KEPT + loud warn: a node that cannot
#     see signers/ must not silently discard the fleet's ledger (fail-open-with-alarm, not brick;
#     local tampering is outside the message-spoof threat model this closes).
# Events at/before the threshold = grandfathered legacy (the whole pre-enforce history).
_SIG_DROPS = {}   # event_id -> (reason, actor, type, ts) -- accumulated per process, reported by tick


def _sig_enforce_after(cfg=None):
    try:
        return ((cfg or _cfg()).get("sig_enforce_after") or "").strip()
    except Exception:
        return ""


def _observe_only(cfg=None):
    cfg = cfg or _cfg()
    if cfg.get("observe_only"):
        return True
    return cfg.get("armed_build") != ENGINE_BUILD


def _observe_log(kind, payload):
    """Append one would-be action to the per-machine observation shard (single-writer)."""
    rec = {"ts": _iso(_now()), "machine": ME, "build": ENGINE_BUILD, "kind": kind}
    rec.update(payload)
    try:
        with open(os.path.join(_dir(), "observe-%s.jsonl" % ME), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print("   (observe log write failed: %s)" % e)


def _append(ev):
    """Append one event to MY shard only (single-writer).

    PHASE B-lite VOTE WATERMARK (2026-07-03, spec = dr-quorum-sleepy-fleet §slashing-protection):
    before appending a VOTE event, refuse REGRESSIVE signing -- a new vote on proposal P must be
    strictly newer than my last recorded vote ts for P. Catches the restored-backup ghost, the
    double live instance, and wake clock-jumps re-voting the past (our F5VYGLV incident class).
    The watermark lives in the SYNCED _decisions dir (wm-<ME>.json, single-writer): restoring
    this machine from an old backup cannot roll it back -- peers re-sync the newer copy."""
    if _observe_only():
        _observe_log("would_append", {"event": ev})
        print("   [OBSERVE_ONLY] would append %s #%s -> observe-%s.jsonl (build %s not armed; ledger untouched)"
              % (ev.get("type"), (ev.get("proposal_id") or "?")[:8], ME, ENGINE_BUILD))
        return True
    if ev.get("type") in VOTE_TYPES:
        wm = _wm_load()
        last = wm.get(ev.get("proposal_id") or "")
        if last and ev.get("ts", "") <= last:
            print("REFUSED (watermark): my last vote on #%s is %s, new event ts %s is not newer "
                  "-> regressive/replayed vote blocked (restored backup? duplicate instance?)"
                  % ((ev.get("proposal_id") or "?")[:8], last, ev.get("ts")))
            return False
        wm[ev["proposal_id"]] = ev.get("ts", "")
        try:
            json.dump(wm, open(_wm_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception as e:
            print("   (watermark write failed: %s -- vote still recorded)" % e)
    with open(_shard(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return True


def _all_events():
    """Read every shard, dedup by event_id (idempotent over redundant multi-rail delivery).
    S1-ENFORCE gate lives HERE -- the single choke point every reader (state, tick, pending,
    ingest dedup) goes through, so both rails (file shards + TG-ingested shard) are covered."""
    enforce = _sig_enforce_after()
    sig_cache = None
    if enforce and fleet_sign is not None:
        try:
            sig_cache = fleet_sign._cache_load()
        except Exception:
            sig_cache = set()
    seen, out = set(), []
    noreg_warned = False
    for f in sorted(glob.glob(os.path.join(_dir(), "log-*.jsonl"))):
        # STRESS-FIX 2026-07-02: try PER LINE, not per file -- one corrupt line (partial write,
        # sync-conflict junk) used to silently drop EVERY event after it in that shard.
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            eid = ev.get("event_id")
            if eid in seen:
                continue
            seen.add(eid)
            if enforce and fleet_sign is not None and ev.get("ts", "") > enforce:
                if not ev.get("sig"):
                    if eid not in _SIG_DROPS:
                        _SIG_DROPS[eid] = ("unsigned", ev.get("actor"), ev.get("type"), ev.get("ts"))
                    continue
                try:
                    v = fleet_sign.verify_event(ev, sig_cache)
                except Exception:
                    v = None
                if v is False:
                    if eid not in _SIG_DROPS:
                        _SIG_DROPS[eid] = ("BAD-SIG", ev.get("actor"), ev.get("type"), ev.get("ts"))
                    continue
                if v is None and not noreg_warned:
                    noreg_warned = True
                    print("   ⚠️ sig-enforce: cannot verify (signers registry unreadable here) -> "
                          "keeping signed events UNVERIFIED; fix _engine/signers/ access")
            out.append(ev)
    out.sort(key=lambda e: e.get("ts", ""))
    return out


def _by_proposal():
    groups = {}
    for ev in _all_events():
        groups.setdefault(ev.get("proposal_id"), []).append(ev)
    return groups


def _state(evs):
    """Derive the current state of one proposal from its merged, time-sorted events."""
    evs = sorted(evs, key=lambda e: e.get("ts", ""))
    prop = next((e for e in evs if e.get("type") == "PROPOSE"), evs[0])
    _grading_threshold = _proof_grading_after()
    s = {
        "proposal_id": prop.get("proposal_id"),
        "subject": prop.get("subject", ""),
        "proposer": prop.get("actor", "?"),
        "tier": int(prop.get("risk_tier", 0) or 0),
        "created": prop.get("ts"),
        "rounds": sum(1 for e in evs if e.get("type") in ("PROPOSE", "COUNTER")),
        "accepts": sorted({e["actor"] for e in evs if e.get("type") == "ACCEPT"}),
        "verifies": sorted({e["actor"] for e in evs if e.get("type") == "VERIFY"}),
        # PROOF-GRADING: actors with >=1 *proven* VERIFY (== verifies while the rule is unarmed)
        "proven_verifies": sorted({e["actor"] for e in evs if e.get("type") == "VERIFY"
                                   and _verify_proven(e, _grading_threshold)}),
        "committers": sorted({e["actor"] for e in evs if e.get("type") == "COMMIT"}),
        "events": evs,
        "last_ts": evs[-1].get("ts"),
    }
    # Causality-robust status (do NOT rely on the single "last event"): find the latest POSITION
    # on the table (PROPOSE or COUNTER); the side that did NOT make it can ACCEPT it. This handles
    # both "responder accepts proposal" and "proposer accepts a counter" without ts fragility.
    positions = [e for e in evs if e.get("type") in ("PROPOSE", "COUNTER")]
    latest_pos = positions[-1] if positions else prop
    pos_ts, owner = latest_pos.get("ts", ""), latest_pos.get("actor")
    accept_after = [e for e in evs if e.get("type") == "ACCEPT"
                    and e.get("actor") != owner and e.get("ts", "") >= pos_ts]
    # WEDGE-FIX 2026-07-14 (#dd6e2002/#5cef5f48): a recorded HUMAN_APPROVED counts as an ACCEPT
    # of the position on the table -- Anton is the supreme voice; the event's actor is just the
    # scribe that recorded his OK (so no actor!=owner filter). A later COUNTER moves pos_ts past
    # it and invalidates it, exactly like a peer ACCEPT. Without this, a human-approved proposal
    # with no peer ACCEPT could never reach 'agreed' and sat wedged (case #5cef5f48, 10 days).
    accept_after += [e for e in evs if e.get("type") == "HUMAN_APPROVED"
                     and e.get("ts", "") >= pos_ts]
    reject_after = [e for e in evs if e.get("type") == "REJECT" and e.get("ts", "") >= pos_ts]
    types = [e.get("type") for e in evs]
    esc_ts = max((e.get("ts", "") for e in evs if e.get("type") == "ESCALATE"), default="")
    # Guard #3 (anti split-brain): only ONE machine should ever apply+COMMIT a given proposal.
    # COMMITs from >1 distinct actor = the partition healed and two sides diverged -> conflict,
    # never silently "committed". Detected on merge; must escalate to Anton for reconciliation.
    if len(s["committers"]) > 1:
        s["status"] = "conflict"
    elif "FINALIZE" in types:
        # Phase B-lite hard finality: committed + independently verified + challenge lane quiet.
        # Never reopened in place -- only superseded by a NEW proposal referencing this one.
        s["status"] = "finalized"
    elif "COMMIT" in types:
        s["status"] = "committed"
    elif "ESCALATE" in types and not (
            _human_approvals(evs)
            or (s["tier"] < 2 and any(e.get("type") == "ACCEPT" and e.get("ts", "") > esc_ts
                                      for e in accept_after))):
        # WEDGE-FIX 2026-07-14: an escalation is a QUESTION, not a tombstone. "ESCALATE in
        # types" used to make it PERMANENT -- the status stayed 'escalated' even after the very
        # answer the escalation asked for arrived, and tick() intentionally skips 'escalated'
        # -> #dd6e2002 (leader ACCEPT 13 min AFTER a stale escalate) and #5cef5f48 (Anton's
        # recorded HUMAN_APPROVED) sat wedged for 10 days with a perfectly healthy fleet.
        # ANSWERED = (a) any recorded HUMAN_APPROVED (that is literally what it asked for --
        # any tier), or (b) tier<2 only: a peer/leader ACCEPT newer than the last ESCALATE.
        # Tier>=2 stays human-gated: peer accepts alone can NEVER unstick it, and cmd_commit
        # still independently refuses tier>=2 without a recorded human approval.
        s["status"] = "escalated"
    elif accept_after:
        s["status"] = "agreed"
    elif reject_after:
        s["status"] = "rejected"
    elif [e for e in evs if e.get("type") == "TENTATIVE_COMMIT" and e.get("ts", "") >= pos_ts]:
        # Quorum Phase A degraded path: committed tentatively, challenge window open. A COUNTER
        # after it becomes the new latest position -> this branch stops matching -> "countered"
        # (the tentative is naturally reopened by any objection).
        s["status"] = "tentative"
    elif latest_pos.get("type") == "COUNTER":
        s["status"] = "countered"
    else:
        s["status"] = "proposed"
    return s


def _deadline(s, cfg):
    # SLA-fix 2026-07-02 (peer request): sleeping nodes (laptop/mac) need a longer response
    # window than the always-on hub, else tier-1 proposals die to timeout while the peer sleeps
    # (case #a7c918ff). cfg["peer_timeout_min"] = {"<MACHINE>": minutes}; the effective timeout
    # is the SLOWEST machine we are WAITING ON (= everyone in the map except the owner of the
    # latest position). Machines absent from the map / empty map -> global timeout_min.
    positions = [e for e in s["events"] if e.get("type") in ("PROPOSE", "COUNTER")]
    owner = (positions[-1] if positions else s["events"][0]).get("actor")
    waiting = [int(v) for k, v in (cfg.get("peer_timeout_min") or {}).items() if k != owner]
    mins = max(waiting) if waiting else int(cfg["timeout_min"])
    return _parse_ts(s["created"]) + datetime.timedelta(minutes=mins)


def _bus(text):
    """Dual-send through bus_send.py -> TG-03 + _machine-bus BY CONSTRUCTION (TG always on)."""
    if _observe_only():
        _observe_log("would_bus", {"text": text})
        print("   [OBSERVE_ONLY] would bus: %s" % text[:160])
        return
    if os.environ.get("CONSENSUS_NO_BUS"):
        print("   (bus skipped: CONSENSUS_NO_BUS)")
        return
    try:
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "bus_send.py"), "ALL", text],
                       timeout=90)
    except Exception as e:
        print("   (bus_send failed: %s)" % e)


# TOP-ESCALATION (Anton 2026-06-30): "02 POLICE" group. Machines post here ONLY when consensus
# genuinely CANNOT resolve (round-cap with no agreement / timeout on a tier>0 proposal / manual
# escalate) and a human (ANY of Anton/Nina/Rita/Artem) must answer NOW. Routine Tier-2 QQQ
# approvals stay in chat 03 — keep this channel STRICTLY for deadlocks. Best-effort, never raises.
POLICE_GROUP = -6491142604


def _police(text):
    if _observe_only():
        _observe_log("would_police", {"text": text})
        print("   [OBSERVE_ONLY] would police-ping: %s" % text[:160])
        return
    if os.environ.get("CONSENSUS_NO_BUS"):
        return
    try:
        sys.path.insert(0, SCRIPTS)
        import bus_ping
        # CLASS-FIX 2026-07-06 (Anton: "почему в 02 давно нет сообщений?"): this used to call
        # bus_ping.send(text, POLICE_GROUP) -- but send() takes ONE arg and posts to 03. Every
        # police ping since the 2-arg call landed died as a swallowed TypeError => chat 02 went
        # SILENT while the constitution said "ASK first in 02". Correct entry = bus_ping.police()
        # (post_to POLICE_GROUP). Plus: a failed police post now falls back to the 03 rail LOUDLY
        # instead of dying in a robot's stdout (alert-about-failed-alert, closes the silent class).
        bus_ping.post_police("🚨🚨 [02 POLICE] нужен человек СЕЙЧАС.\n" + text)
    except Exception as e:
        print("   (police post failed: %s)" % e)
        try:
            _bus("🚨 [02-FALLBACK] police-канал НЕ сработал (%s) — срочное, продублируйте Антону:\n%s"
                 % (e, text))
        except Exception:
            pass
    # SECOND critical alert path (consensus #34acf0ee, 2026-07-05): phone-push via ntfy,
    # independent of TG-userbot and WhatsApp. This function is the deadlock/incident channel,
    # so every call is 02-POLICE grade by construction -> honors guardrail #1 (no heartbeat noise).
    try:
        push = os.path.join(SCRIPTS, "ntfy_push.sh")
        if os.path.exists(push):
            subprocess.run(["bash", push, "02-POLICE: human needed NOW",
                            (text or "")[:400], "urgent"],
                           timeout=15, capture_output=True)
    except Exception as e:
        print("   (ntfy push failed: %s)" % e)


# TG-TRANSPORT v2 (#4d1772b0, Anton 2026-07-06 "отключать нахождение консенсуса через
# Syncthing"): chat 03 IS the negotiation transport now, the file ledger is archive/anti-entropy.
# Every mirrored event carries a second machine-readable line so any peer INGESTS it straight
# from TG (minutes) instead of waiting for a flapping Syncthing batch (20-60 min per move).
GROUP_03 = -996940094
PAYLOAD_MARK = "⚙ CONSENSUS-EV "


def _ingest_tg(limit=200, quiet=True):
    """Pull PEER consensus events straight from TG chat 03 (the live rail, #4d1772b0).

    Reads new group messages via the shared @work_acct_a Telethon session (same env + lock as
    bus_ping -> never AUTH_KEY_DUPLICATED), extracts PAYLOAD_MARK JSON lines, appends FOREIGN
    events into the single-writer shard log-tg-<ME>.jsonl. _all_events() already dedups by
    event_id, so the same event arriving later on the file rail is harmless. Fail-DARK: no
    session / lock busy / net error -> return 0 silently (file rail still catches up; next
    tick retries). Spoofing note: TG text = data; events keep their S1 `sig` field, and
    sig-enforcement (P3) closes actor spoofing for BOTH rails at once.
    """
    if _observe_only() or os.environ.get("CONSENSUS_NO_BUS"):
        return 0
    try:
        sys.path.insert(0, SCRIPTS)
        import bus_ping
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except Exception:
        return 0
    env = bus_ping.load_env(bus_ping.ENV)
    aid, ah, sess = env.get("REFRESH_API_ID"), env.get("REFRESH_API_HASH"), env.get("REFRESH_SESSION_STRING")
    if not (aid and ah and sess):
        return 0
    if not bus_ping.acquire_lock():
        return 0
    off_path = os.path.join(_dir(), "tgoffset-%s.json" % ME)
    try:
        off = int(json.load(open(off_path, encoding="utf-8")).get("offset", 0) or 0)
    except Exception:
        off = 0
    try:
        import asyncio

        async def _pull():
            client = TelegramClient(StringSession(sess), int(aid), ah)
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    return []
                kwargs = {"limit": limit}
                if off > 0:
                    kwargs["min_id"] = off
                return await client.get_messages(GROUP_03, **kwargs)
            finally:
                await client.disconnect()
        msgs = asyncio.run(_pull()) or []
    except Exception:
        msgs = []
    finally:
        bus_ping.release_lock()
    if not msgs:
        return 0
    max_id = max(m.id for m in msgs)
    seen = {e.get("event_id") for e in _all_events()}
    shard = os.path.join(_dir(), "log-tg-%s.jsonl" % ME)
    n = 0
    for m in msgs:
        for ln in (m.message or "").splitlines():
            if not ln.startswith(PAYLOAD_MARK):
                continue
            try:
                ev = json.loads(ln[len(PAYLOAD_MARK):])
            except Exception:
                continue
            if not (isinstance(ev, dict) and ev.get("event_id") and ev.get("proposal_id") and ev.get("type")):
                continue
            if ev.get("actor") == ME or ev["event_id"] in seen:
                continue
            seen.add(ev["event_id"])
            with open(shard, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            n += 1
    try:
        json.dump({"offset": max_id}, open(off_path, "w", encoding="utf-8"))
    except Exception:
        pass
    if n and not quiet:
        print("ingest-tg: +%d peer event(s) from chat 03" % n)
    return n


def _emit(ev, extra="", police=False):
    short = ev["proposal_id"][:8]
    tier = ev.get("risk_tier")
    tier_s = (" tier=%s" % tier) if tier is not None else ""
    line = "🤝 [CONSENSUS] %s #%s%s by %s: %s" % (
        ev["type"], short, tier_s, ev["actor"], (ev.get("subject") or ev.get("text") or "")[:140])
    if extra:
        line += " | " + extra
    # TG-TRANSPORT v2: full event as a machine line under the human line (chat 03 = the rail).
    payload = dict(ev)
    if len(json.dumps(payload, ensure_ascii=False)) > 3000:
        payload.pop("details", None)
        payload["details_dropped"] = True
    _bus(line + "\n" + PAYLOAD_MARK + json.dumps(payload, ensure_ascii=False))
    if police:
        _police(line)


def _sig_fail_note(reason):
    """ENGINE-VISIBILITY (#94389335): dark mode must stay dark for the LEDGER, but never
    silent for the OPERATOR. A signing failure keeps the event flowing (unsigned), and
    additionally: one stderr line + a bump of the sig_fail-<MACHINE> counter next to the
    shard. The nightly consensus_config_guard reads that counter and alarms when it grows
    -- otherwise sig-enforce day arrives and this node's events get quarantined wholesale
    with nobody having seen it coming.

    Known + accepted: two processes on THIS machine (live session + inbox robot) can
    read-modify-write concurrently and lose an increment. The file is per-machine, so no
    cross-machine race exists, and an undercount still reads >0 -- the guard alarms on
    GROWTH, not on an exact tally. Deliberately not locked: a visibility aid must never
    become a new way for the ledger to block."""
    sys.stderr.write("⚠️ consensus: EVENT SIGNING FAILED on %s (%s) -> event goes UNSIGNED; "
                     "fix fleet_sign/keys before sig_enforce_after kicks in\n" % (ME, reason))
    try:
        p = os.path.join(_dir(), "sigfail-%s.json" % ME)
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            d = {}
        d["count"] = int(d.get("count") or 0) + 1
        d["last_ts"] = _iso(_now())
        d["last_reason"] = str(reason)[:300]
        d["machine"] = ME
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except Exception:
        pass  # counter is a visibility aid, never a blocker


def _mkevent(etype, proposal_id, **kw):
    ev = {"event_id": uuid.uuid4().hex, "proposal_id": proposal_id, "type": etype,
          "actor": ME, "ts": _iso(_now())}
    ev.update({k: v for k, v in kw.items() if v is not None})
    if fleet_sign is not None:
        try:
            sig = fleet_sign.sign_event(ev)
            if sig:
                ev["sig"], ev["signer"] = sig, ME
            else:
                _sig_fail_note("sign_event returned empty")
        except Exception as e:
            # dark mode: signing must never block the ledger -- but it must be VISIBLE
            _sig_fail_note("%s: %s" % (type(e).__name__, e))
    return ev


# ---------------- verbs ----------------

def cmd_propose(subject, details=None, tier=0, pid=None, reversible=False):
    pid = pid or uuid.uuid4().hex
    d = None
    if details:
        try:
            d = json.loads(details)
        except Exception:
            d = {"note": details}
    tier = int(tier)
    hit = _tripwire_hit(_tripwire_scan_text(subject, details))
    if hit and tier < 2:
        print("   ⚠️ TIER-TRIPWIRE: matched '%s' -> bumping tier %s->2 (safety gate; tune %s)"
              % (hit, tier, os.path.basename(TRIPWIRE_FILE)))
        tier = 2
    cfg = _cfg()
    qc = _qcfg(cfg)
    kw = {}
    if reversible:
        kw["reversible"] = True
    committee = None
    if qc["enabled"]:
        # Quorum Phase A: freeze the awake committee AT SNAPSHOT TIME (never recomputed at the
        # deadline -- "no moving denominator", OpenZeppelin snapshot pattern via the quorum DR).
        committee = _awake(qc)
        kw["committee"] = committee
    ev = _mkevent("PROPOSE", pid, subject=subject, details=d, risk_tier=tier, **kw)
    _append(ev)
    _v2_shadow_observe(ev, subject, d, tier, reversible, hit, cfg)   # S2 dark sensor (0 behavior)
    print("PROPOSED #%s tier=%s: %s" % (pid[:8], tier, subject))
    extra = "awaiting response (cap=%s rounds, %smin)" % (cfg["round_cap"], cfg["timeout_min"])
    if committee is not None:
        extra += " | committee=" + ",".join(committee)
        if tier == 1 and committee == [ME]:
            # Honest unreachability, declared OUT LOUD instead of waiting on fantasy quorum.
            note = ("strict quorum UNREACHABLE at snapshot (no awake peer); path = %s"
                    % ("tentative_commit after timeout + challenge window" if reversible
                       else "human escalation at timeout (irreversible without peers)"))
            print("   ⚠️ " + note)
            extra += " | ⚠️ " + note
    _emit(ev, extra=extra)
    if int(tier) >= 2:
        esc = _mkevent("ESCALATE", pid, subject=subject, text="Tier-2 proposal needs Anton's OK (QQQ)")
        _append(esc)
        _emit(esc, extra="❓ НУЖЕН ТВОЙ ОК — ответь QQQ=да / NO=нет")
        print("   Tier-2 -> escalated to Anton (no auto-commit).")
    return pid


def _resolve(idfrag):
    groups = _by_proposal()
    hits = [p for p in groups if p and p.startswith(idfrag)]
    if len(hits) == 1:
        return hits[0], groups[hits[0]]
    if not hits:
        print("no proposal matches #%s" % idfrag)
    else:
        print("ambiguous #%s -> %s" % (idfrag, ", ".join(h[:8] for h in hits)))
    return None, None


def cmd_respond(idfrag, decision, text=None):
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    s = _state(evs)
    dmap = {"accept": "ACCEPT", "counter": "COUNTER", "reject": "REJECT"}
    etype = dmap.get(decision.lower())
    if not etype:
        print("decision must be accept|counter|reject"); return 2
    ev = _mkevent(etype, pid, subject=s["subject"], text=text, risk_tier=s["tier"])
    if not _append(ev):
        return 1
    print("%s #%s: %s" % (etype, pid[:8], text or ""))
    _emit(ev)
    return 0


def _human_approvals(evs):
    return [e for e in evs if e.get("type") == "HUMAN_APPROVED"]


def cmd_approve(idfrag, proof):
    """QQQ-CLOSURE 2026-07-02 (peer-found gap): tier-2 escalates to Anton, but after his QQQ the
    ledger had NO closure path -- cmd_commit hard-refused tier>=2, so human-approved proposals sat
    ESCALATED forever (case #e53fd7fe). This verb RECORDS the human approval; `commit` then allows
    tier>=2 only WITH a recorded approval. Auto-commit without approve stays banned. Proof string
    is REQUIRED and must say who/where (e.g. 'Anton QQQ, 02-POLICE msg 1790183')."""
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    if not (proof or "").strip():
        print("approve requires a proof string (who/where/msg-id of the human OK)"); return 2
    s = _state(evs)
    if _human_approvals(evs):
        print("already HUMAN-APPROVED #%s (idempotent skip)" % pid[:8]); return 0
    ev = _mkevent("HUMAN_APPROVED", pid, subject=s["subject"], proof=proof, risk_tier=s["tier"])
    _append(ev)
    print("HUMAN-APPROVED #%s: %s" % (pid[:8], proof))
    _emit(ev, extra="tier-%s одобрен человеком -> commit разблокирован" % s["tier"])
    return 0


def cmd_commit(idfrag):
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    s = _state(evs)
    if s["tier"] >= 2 and not _human_approvals(evs):
        print("REFUSED: Tier-2 needs a RECORDED human approval first -> `approve <id> \"<proof>\"` (QQQ); auto-commit stays banned."); return 1
    if s["status"] not in ("agreed",) and ME != _cfg()["leader"]:
        print("not agreed yet (status=%s) and you are not the leader -> cannot commit." % s["status"]); return 1
    ev = _mkevent("COMMIT", pid, subject=s["subject"], text="decision of record; applying")
    if not _append(ev):
        return 1
    print("COMMITTED #%s: %s  (now APPLY the change, then `verify`)" % (pid[:8], s["subject"]))
    _emit(ev, extra="agent applies the change, then both VERIFY")
    return 0


def cmd_verify(idfrag, proof):
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    s = _state(evs)
    # Guard #2 (independent re-verify): the agent that APPLIED the change (the committer) may
    # self-verify, but "globally done" needs at least one INDEPENDENT verify from a machine that
    # did NOT apply it -- a second machine re-checking, not the applier vouching for itself.
    committer = s["committers"][0] if s["committers"] else None
    prior_proofs = [e.get("proof", "").strip() for e in evs if e.get("type") == "VERIFY"]
    if committer and ME == committer:
        print("   note: you COMMITTED #%s -> this is a SELF-verify; still needs an INDEPENDENT machine's verify." % pid[:8])
    if proof.strip() and proof.strip() in prior_proofs:
        print("   ⚠️ RUBBER-STAMP GUARD: your proof duplicates a prior VERIFY verbatim -> re-check INDEPENDENTLY (re-run / re-read), don't copy.")
    # PROOF-GRADING: stamp the grade into the event (visibility even while unarmed; old engines
    # ignore the extra key). When armed, an unproven VERIFY is recorded but does NOT count toward
    # DONE — the worktree-hook class (#f2e71c9a: 2 prose VERIFYs closed a thread over a hook that
    # never ran) dies here.
    threshold = _proof_grading_after()
    grade = _proof_grade(proof)
    if grade == "unproven":
        print("   %s UNPROVEN VERIFY: голая проза не доказывает работу ЗАМЕНЫ. Дай детерминированную "
              "улику: команда + exit 0 / md5-sha хэш / счётчик до->после.%s"
              % ("⛔" if threshold else "⚠️",
                 " Записываю, но в зачёт DONE это НЕ идёт (proof_grading armed)." if threshold
                 else " (пока предупреждение; после активации proof_grading_after перестанет закрывать тред)"))
    ev = _mkevent("VERIFY", pid, subject=s["subject"], proof=proof, proof_grade=grade)
    if not _append(ev):
        return 1
    after = sorted(set(s["verifies"]) | {ME})
    mine_proven = _verify_proven(ev, threshold)
    proven_after = sorted(set(s["proven_verifies"]) | ({ME} if mine_proven else set()))
    independent = [a for a in proven_after if a != committer]
    print("VERIFY #%s by %s [%s]: %s" % (pid[:8], ME, grade, proof))
    done = len(proven_after) >= 2 and len(independent) >= 1
    if done:
        extra = "✅ both verified (incl. independent%s) -> DONE" % (", proven" if threshold else "")
    elif threshold and len(after) >= 2 and len(proven_after) < 2:
        extra = ("⚠️ %d verify(ies) но только %d PROVEN -> тред НЕ закрыт; нужен детерминированный "
                 "proof (exit 0 / хэш / счётчик до->после)" % (len(after), len(proven_after)))
    elif len(after) >= 2 and not [a for a in after if a != committer]:
        extra = "⚠️ 2 verifies but all by the committer -> need an INDEPENDENT machine"
    else:
        extra = "awaiting the other machine's independent verify"
    _emit(ev, extra=extra)
    if done:
        print("   cross-agent validation complete (>=2 distinct%s, >=1 independent of the applier) -> globally done."
              % (" proven" if threshold else ""))
    return 0


def cmd_escalate(idfrag, reason):
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    s = _state(evs)
    ev = _mkevent("ESCALATE", pid, subject=s["subject"], text=reason)
    _append(ev)
    print("ESCALATED #%s -> Anton: %s" % (pid[:8], reason))
    _emit(ev, extra="❓ НУЖЕН ТВОЙ ОК — ответь QQQ=да / NO=нет", police=True)
    return 0


def _print_state(s):
    print("#%s  [%s]  tier=%s  rounds=%s  by %s" % (
        s["proposal_id"][:8], s["status"].upper(), s["tier"], s["rounds"], s["proposer"]))
    print("   subject: %s" % s["subject"])
    if s["accepts"]:
        print("   accepts: %s" % ", ".join(s["accepts"]))
    if s["verifies"]:
        if _proof_grading_after():
            marks = ", ".join(a + ("" if a in s["proven_verifies"] else "(UNPROVEN)")
                              for a in s["verifies"])
            print("   verified by: %s  (%s)" % (marks,
                  "DONE" if len(s["proven_verifies"]) >= 2 else "need 2 PROVEN"))
        else:
            print("   verified by: %s  (%s)" % (", ".join(s["verifies"]),
                  "DONE" if len(s["verifies"]) >= 2 else "need 2"))


def cmd_status(idfrag):
    pid, evs = _resolve(idfrag)
    if not pid:
        return 2
    s = _state(evs)
    _print_state(s)
    print("   timeline:")
    for e in s["events"]:
        print("     %s  %-9s %-16s %s" % (e.get("ts"), e.get("type"), e.get("actor"),
              (e.get("text") or e.get("proof") or e.get("subject") or "")[:80]))
    return 0


def cmd_list(which="open"):
    groups = _by_proposal()
    if not groups:
        print("(no proposals yet)"); return 0
    rows = [_state(evs) for evs in groups.values()]
    rows.sort(key=lambda s: s.get("created") or "")
    openset = {"proposed", "countered", "agreed", "tentative"}
    shown = 0
    for s in rows:
        if which == "open" and s["status"] not in openset:
            continue
        _print_state(s)
        shown += 1
    if not shown:
        print("(no %s proposals)" % which)
    return 0


def cmd_tick():
    """Deterministic driver (0-LLM). Applies timeout, round-cap, tie-break, Tier-2 gate.
    Mutates ONLY the log (append ESCALATE / leader-auto-ACCEPT); never edits user files -- the
    AGENT performs the agreed change when it sees status=agreed/committed."""
    _ingest_tg()   # TG-TRANSPORT v2: pull fresh peer events from chat 03 BEFORE judging state
    cfg = _cfg()
    qc = _qcfg(cfg)
    # LEADER-DOWN FAILOVER: resolve who holds the tie-break function THIS tick. Normally the
    # leader; if the leader's presence is stale past leader_down_min the fallback arbiter takes
    # over for this tick and (from the fallback machine only) pings 02/03 once per down-episode.
    arb, failed_over, leader_age = _effective_arbiter(cfg)
    if failed_over:
        print("👑⬇️ [LEADER-DOWN FAILOVER] leader %s presence stale %.0fmin (>%dmin) -> arbiter=%s this tick"
              % (cfg.get("leader"), leader_age or 0, _leader_down_min(cfg), arb))
    _leaderdown_signal(cfg, failed_over, leader_age)
    groups = _by_proposal()
    # S1-ENFORCE visibility: police NEW quarantined events exactly once (state file dedups
    # across tick runs -- a robot ticking every 10min must not re-ping the same forgery).
    if _SIG_DROPS:
        rep_path = os.path.join(_dir(), "sigdrops-reported-%s.json" % ME)
        try:
            reported = set(json.load(open(rep_path, encoding="utf-8")))
        except Exception:
            reported = set()
        fresh = {eid: d for eid, d in _SIG_DROPS.items() if eid not in reported}
        if fresh:
            lines = ["  %s %s %s@%s %s" % (d[0], (eid or "?")[:8], d[1], d[3], d[2])
                     for eid, d in sorted(fresh.items(), key=lambda kv: kv[1][3] or "")][:10]
            _police("🚫 sig-enforce QUARANTINE on %s: %d event(s) rejected (unsigned/bad sig after %s)\n%s"
                    % (ME, len(fresh), _sig_enforce_after(cfg), "\n".join(lines)))
            try:
                json.dump(sorted(reported | set(fresh)), open(rep_path, "w", encoding="utf-8"))
            except Exception:
                pass
    if not groups:
        print("(tick: no proposals)"); return 0
    now = _now()
    acted = 0
    for pid, evs in groups.items():
        s = _state(evs)
        # Phase B-lite: promote committed -> FINALIZED once independently verified (>=2 distinct,
        # >=1 not the committer). Leader-only marker (single writer). Old engines ignore FINALIZE.
        if qc["enabled"] and s["status"] == "committed" and ME == cfg["leader"]:
            committer = s["committers"][0] if s["committers"] else None
            # PROOF-GRADING: finality rides on PROVEN verifies only (== all verifies while unarmed)
            independent = [a for a in s["proven_verifies"] if a != committer]
            if len(s["proven_verifies"]) >= 2 and independent:
                print("#%s committed + independently verified -> FINALIZE" % pid[:8])
                if not os.environ.get("CONSENSUS_DRY"):
                    ev = _mkevent("FINALIZE", pid, subject=s["subject"],
                                  text="hard finality: >=2 verifies incl. independent; supersede-only from here")
                    _append(ev); _emit(ev, extra="✅ finalized")
                acted += 1
                continue
        if s["status"] in ("committed", "escalated", "rejected", "finalized"):
            continue
        overdue = now > _deadline(s, cfg)
        # Quorum Phase A: finalize a clean tentative commit once its challenge window closed.
        # LEADER-ONLY write (one finalizer -> no two-machine COMMIT race -> no false split-brain).
        if qc["enabled"] and s["status"] == "tentative":
            tcs = [e for e in s["events"] if e.get("type") == "TENTATIVE_COMMIT"]
            tc_deadline = _parse_ts(tcs[-1].get("ts", "")) + datetime.timedelta(hours=qc["challenge_hours"])
            if now > tc_deadline and ME == cfg["leader"]:
                print("#%s tentative challenge window closed clean -> finalize (COMMIT)" % pid[:8])
                if not os.environ.get("CONSENSUS_DRY"):
                    ev = _mkevent("COMMIT", pid, subject=s["subject"],
                                  text="tentative finalized: %sh challenge window closed with no objection" % qc["challenge_hours"])
                    _append(ev); _emit(ev, extra="degraded path finalized")
                acted += 1
            else:
                print("#%s [tentative] challenge window open (until %s)" % (pid[:8], _iso(tc_deadline)))
            continue
        # 0) Guard #3: split-brain detected (>1 machine committed the same proposal) -> never
        #    auto-resolve; hand to Anton for reconciliation (the leader's log is authoritative).
        if s["status"] == "conflict":
            print("#%s SPLIT-BRAIN: committed by %s -> escalate for reconciliation" % (
                pid[:8], ", ".join(s["committers"])))
            if not os.environ.get("CONSENSUS_DRY"):
                ev = _mkevent("ESCALATE", pid, subject=s["subject"],
                              text="split-brain: conflicting commits by %s" % ", ".join(s["committers"]))
                _append(ev); _emit(ev, extra="❓ QQQ — два коммита разошлись, нужен Антон")
            acted += 1; continue
        # 1) Tier-2 still UNANSWERED -> ensure escalated (belt & suspenders).
        # S8-FIX 2026-07-14 (hub repro 12:13-12:16: 2 ticks = 2 waves x 7 QQQ to 02-POLICE):
        # this branch ran BEFORE the agreed-check and ignored HUMAN_APPROVED -- after the S7
        # wedge-fix made approved tier-2 items 'agreed' (no longer skipped as escalated), this
        # branch RE-ESCALATED an already-answered tier-2 EVERY tick = police spam loop. A tier-2
        # that is agreed/tentative or carries a recorded human approval is ANSWERED -- never
        # re-ask. The unanswered-tier-2 floor stays intact.
        if s["tier"] >= 2 and s["status"] not in ("agreed", "tentative") and not _human_approvals(evs):
            print("#%s Tier-2 still open -> escalate to Anton" % pid[:8])
            if not os.environ.get("CONSENSUS_DRY"):
                ev = _mkevent("ESCALATE", pid, subject=s["subject"], text="Tier-2 auto-gate")
                _append(ev); _emit(ev, extra="❓ QQQ=да / NO=нет")
            acted += 1; continue
        # 2) agreed but uncommitted -> remind the responsible actor to apply + commit.
        # S8-FIX part 2 (hub-reported): dual-VERIFIED agreed items sat [AGREED] forever when the
        # proposer never ran `commit` (the work is done and independently verified -- only the
        # decision-of-record line is missing). The LEADER (single writer, no commit race) closes
        # them: >=2 verifies + (tier<2 or human-approved) -> auto-COMMIT; next tick FINALIZEs.
        if s["status"] == "agreed":
            # PROOF-GRADING: auto-close only on PROVEN verifies (== all verifies while unarmed)
            if (ME == cfg["leader"] and len(s["proven_verifies"]) >= 2
                    and (s["tier"] < 2 or _human_approvals(evs))):
                print("#%s AGREED + %d proven verifies -> leader auto-COMMIT (record closes)" % (
                    pid[:8], len(s["proven_verifies"])))
                if not os.environ.get("CONSENSUS_DRY"):
                    ev = _mkevent("COMMIT", pid, subject=s["subject"],
                                  text="leader auto-commit: agreed + independently verified (>=2), record was the only missing piece")
                    _append(ev); _emit(ev, extra="closed by leader tick")
            else:
                print("#%s AGREED -> ready to commit & apply (proposer=%s)" % (pid[:8], s["proposer"]))
            acted += 1; continue
        # 3) round cap hit without agreement -> tie-break = hand to Anton (Phase 1 conservative)
        if s["rounds"] >= int(cfg["round_cap"]) and s["status"] != "agreed":
            print("#%s round-cap %s hit, no agreement -> escalate (tie-break)" % (pid[:8], cfg["round_cap"]))
            if not os.environ.get("CONSENSUS_DRY"):
                ev = _mkevent("ESCALATE", pid, subject=s["subject"], text="no agreement after %s rounds" % cfg["round_cap"])
                _append(ev); _emit(ev, extra="❓ QQQ решает спор", police=True)
            acted += 1; continue
        # 4) timeout with no response: Tier-0 + I am the leader -> disagree-and-commit (autonomy)
        if overdue and s["status"] == "proposed":
            if s["tier"] == 0 and ME == arb:
                positions = [e for e in s["events"] if e.get("type") in ("PROPOSE", "COUNTER")]
                latest = positions[-1] if positions else s["events"][0]
                owner, pos_ts = latest.get("actor"), latest.get("ts", "")
                mine_after = [e for e in s["events"] if e.get("type") == "ACCEPT"
                              and e.get("actor") == ME and e.get("ts", "") >= pos_ts]
                if owner == ME:
                    # LOOP-FIX 2026-07-02 (case #f60135de: 17 identical self-ACCEPTs, 21:12->08:03):
                    # a self-accept NEVER counts in _state (accept must come from a non-owner), so
                    # tick re-accepted my own proposal every 20 min forever. Disagree-and-commit on
                    # the leader's OWN tier-0 proposal = COMMIT directly (decision of record).
                    print("#%s Tier-0 timeout on MY OWN proposal -> leader disagree-and-commit (COMMIT)" % pid[:8])
                    if not os.environ.get("CONSENSUS_DRY"):
                        ev = _mkevent("COMMIT", pid, subject=s["subject"],
                                      text="leader disagree-and-commit: own tier-0 proposal, no peer response by deadline")
                        _append(ev); _emit(ev, extra="tier-0 timeout tie-break; peer may still VERIFY/object")
                elif mine_after:
                    # idempotency belt: my ACCEPT is already on the table but the state did not
                    # advance -> never spam another one; surface the anomaly instead of looping.
                    print("#%s already accepted by me, state stuck=%s -> escalate (anomaly, no re-spam)" % (pid[:8], s["status"]))
                    if not os.environ.get("CONSENSUS_DRY"):
                        ev = _mkevent("ESCALATE", pid, subject=s["subject"],
                                      text="stuck: leader ACCEPT recorded but state not advancing")
                        _append(ev); _emit(ev, extra="state anomaly, needs a look")
                else:
                    print("#%s Tier-0 timeout -> leader auto-accepts (disagree-and-commit)" % pid[:8])
                    if not os.environ.get("CONSENSUS_DRY"):
                        ev = _mkevent("ACCEPT", pid, subject=s["subject"], text="leader auto-accept on timeout")
                        _append(ev); _emit(ev, extra="leader tie-break (Tier-0 timeout)")
            else:
                if s["tier"] == 0:
                    # S3 FIX (the #dd6e2002 false-wake): a NON-leader on a tier-0 timeout used to
                    # fall through to the generic "timeout, tier>0 needs human" ESCALATE + police
                    # ping -- waking Anton for a call the leader auto-resolves minutes later.
                    # Tier-0 tie-break is the LEADER's job (single writer); a non-leader waits
                    # and says so. Log line only: no ESCALATE event, no human ping.
                    print("#%s tier-0 timeout on NON-arbiter -> awaiting arbiter (%s) tie-break; not escalating"
                          % (pid[:8], arb))
                    acted += 1; continue
                prop_ev = next((e for e in s["events"] if e.get("type") == "PROPOSE"), {})
                if qc["enabled"] and s["tier"] == 1 and prop_ev.get("reversible"):
                    # Quorum Phase A degraded path: REVERSIBLE tier-1 with no strict certificate by
                    # the deadline -> leader writes an explicit, loudly-logged TENTATIVE_COMMIT with
                    # a challenge window, instead of waking Anton. Irreversible keeps the human floor.
                    if ME == cfg["leader"]:
                        # PHASE C (2026-07-03): degraded-path budget. If the fleet leans on
                        # tentative_commit more than degraded_week_cap times per ISO-week, the
                        # committee shape is wrong (quorum DR lesson: constant liveness-rescue =
                        # broken design) -> escalate to human instead of quietly routing around quorum.
                        cap = int((cfg.get("quorum") or {}).get("degraded_week_cap", 3))
                        # counter lives in the BUS _decisions dir (like the watermark): synced =
                        # fleet-visible + single-writer, and test sandboxes are isolated by
                        # construction (a SCRIPTS-dir path leaked state between real runs & tests).
                        cnt_path = os.path.join(_dir(), "degraded-%s.json" % ME)
                        week = _now().strftime("%G-W%V")
                        try:
                            cnt = json.load(open(cnt_path, encoding="utf-8"))
                        except Exception:
                            cnt = {}
                        used = int(cnt.get(week, 0))
                        if used >= cap:
                            print("#%s degraded path OVERUSED (%s/%s this week) -> escalate for human review (Phase C)" % (
                                pid[:8], used, cap))
                            if not os.environ.get("CONSENSUS_DRY"):
                                ev = _mkevent("ESCALATE", pid, subject=s["subject"],
                                              text="Phase C auto-promote: tentative_commit used %s/%s this week -- committee shape needs review" % (used, cap))
                                _append(ev); _emit(ev, extra="⚠️ degraded-budget exhausted", police=True)
                        else:
                            print("#%s tier-1 reversible timeout -> TENTATIVE_COMMIT (challenge %sh; degraded %s/%s this week)" % (
                                pid[:8], qc["challenge_hours"], used + 1, cap))
                            if not os.environ.get("CONSENSUS_DRY"):
                                ev = _mkevent("TENTATIVE_COMMIT", pid, subject=s["subject"],
                                              text="degraded path: no strict quorum by deadline; challenge window %sh open" % qc["challenge_hours"])
                                if _append(ev) and not _observe_only():
                                    cnt[week] = used + 1
                                    json.dump(cnt, open(cnt_path, "w", encoding="utf-8"))
                                    _emit(ev, extra="⚠️ degraded commit -- counter/reject within %sh reopens (%s/%s week budget)" % (
                                        qc["challenge_hours"], used + 1, cap))
                    else:
                        print("#%s tier-1 reversible timeout -> awaiting LEADER's tentative_commit (single writer)" % pid[:8])
                else:
                    print("#%s timeout, tier=%s -> escalate (only Tier-0 auto-resolves)" % (pid[:8], s["tier"]))
                    if not os.environ.get("CONSENSUS_DRY"):
                        ev = _mkevent("ESCALATE", pid, subject=s["subject"], text="timeout, tier>0 needs human")
                        _append(ev); _emit(ev, extra="❓ QQQ=да / NO=нет", police=True)
            acted += 1; continue
        print("#%s [%s] waiting (rounds=%s, %s)" % (
            pid[:8], s["status"], s["rounds"], "overdue" if overdue else "within window"))
    if not acted:
        print("(tick: nothing actionable)")
    return 0


def cmd_pending(as_json=False):
    """GAP-FIX 2026-07-02 (case #a7c918ff): tick is deterministic and can only timeout/escalate --
    it never ANSWERS a peer's propose, so every tier-1 died to "timeout, tier>0 needs human".
    This verb is the missing detector: open proposals where the MOVE IS MINE (latest position
    PROPOSE/COUNTER made by someone else, status still open, tier<2 -- Tier-2 stays human-gated).
    inbox_robot.cmd greps its output to WAKE the LLM judge; the judge uses it as the work-list,
    then answers via `respond <id> accept|counter|reject`."""
    _ingest_tg()   # TG-TRANSPORT v2: the judge's work-list must see chat-03 events, not stale files
    groups = _by_proposal()
    rows = []
    for pid, evs in groups.items():
        s = _state(evs)
        # "tentative" included: a late-waking peer SHOULD judge a degraded commit while its
        # challenge window is open (accept -> agreed; counter -> reopens) -- the challenge lane.
        if s["status"] not in ("proposed", "countered", "tentative") or s["tier"] >= 2:
            continue
        positions = [e for e in s["events"] if e.get("type") in ("PROPOSE", "COUNTER")]
        latest = positions[-1] if positions else None
        if not latest or latest.get("actor") == ME:
            continue
        rows.append({"id": s["proposal_id"], "short": s["proposal_id"][:8], "tier": s["tier"],
                     "from": latest.get("actor"), "position": latest.get("type"),
                     "subject": s["subject"], "text": latest.get("text") or ""})
    if as_json:
        print(json.dumps(rows, ensure_ascii=False)); return 0
    if not rows:
        print("(pending: nothing awaits my response)"); return 0
    for r in rows:
        print("AWAIT-MY-RESPONSE #%s tier=%s from=%s %s: %s" % (
            r["short"], r["tier"], r["from"], r["position"], r["subject"][:160]))
    return 0


def cmd_sigs():
    """S1 (dark) ledger signature audit: verify every SIGNED event against the signers
    registry (<bus>/_engine/signers/*.pub minus REVOKED). Unsigned = legacy (fine while
    the fleet rolls out keys); BAD = tampered/forged/revoked/unknown -> loud + exit 1.
    Visibility must exist BEFORE any enforcement flag ever flips."""
    if fleet_sign is None:
        print("fleet_sign.py not available -> nothing to audit"); return 2
    try:
        cache = fleet_sign._cache_load()
    except Exception:
        cache = set()
    ok = bad = unsigned = 0
    bad_lines = []
    for ev in _all_events():
        v = fleet_sign.verify_event(ev, cache)
        if v is True:
            ok += 1
        elif v is False:
            bad += 1
            bad_lines.append("  ❌ BAD SIG %s %-9s signer=%s #%s: %s" % (
                ev.get("ts"), ev.get("type"), ev.get("signer") or ev.get("actor"),
                (ev.get("proposal_id") or "?")[:8], (ev.get("subject") or ev.get("text") or "")[:60]))
        else:
            unsigned += 1
    enf = _sig_enforce_after()
    print("sigs audit: %d ok · %d BAD · %d unsigned(legacy) · enforce=%s"
          % (ok, bad, unsigned, ("after %s" % enf) if enf else "DARK (audit only)"))
    if _SIG_DROPS:
        print("   quarantined by enforce gate this run: %d" % len(_SIG_DROPS))
    for ln in bad_lines[:20]:
        print(ln)
    if bad:
        print("   ⚠️ BAD signatures found -> do NOT trust those events; escalate to Anton.")
    return 1 if bad else 0


def _getopt(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def cmd_v2_shadow(as_json=False, days=7):
    """Honest S2 sensor (0 LLM, read-only): over the last `days`, how many DISTINCT real proposals
    would have BENEFITED from v2 typing (track/freeze) that the tier-only engine misses? This is
    the flip-or-kill number -- ≥N/week -> typing earns its keep (Anton sets N); 0 -> tier-only is
    enough, kill the build with evidence. Sibling to shadow_review.py's agreement score."""
    def _strict_ts(s):   # None on failure (unlike _parse_ts which falls back to now())
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.datetime.strptime(s or "", fmt).replace(tzinfo=datetime.timezone.utc)
            except Exception:
                continue
        return None
    now = _now()
    horizon = now - datetime.timedelta(days=days)
    seen, bad_ts, corrupt = {}, 0, 0
    for f in sorted(glob.glob(os.path.join(_dir(), "observe-*.jsonl"))):
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                corrupt += 1
                continue
            if r.get("build") != S2_SHADOW_BUILD or r.get("kind") != "would_append":
                continue
            v2 = r.get("v2")
            if not isinstance(v2, dict):
                continue
            m = r.get("machine") or os.path.basename(f)
            pid = (r.get("event") or {}).get("proposal_id") or "?"
            t = _strict_ts(r.get("ts"))
            if t is None:      # unparseable ts -> can't window it, don't credit it
                bad_ts += 1
                continue
            # distinct decision = (machine, proposal_id); keep the LATEST record's verdict
            k = (m, pid)
            if k not in seen or t > seen[k]["t"]:
                seen[k] = {"t": t, "in_window": t >= horizon, "v2": v2, "subject":
                           (r.get("event") or {}).get("subject", "")}
    inwin = [d for d in seen.values() if d["in_window"]]
    benefit = [d for d in inwin if d["v2"].get("would_benefit")]
    tracks = {}
    for d in benefit:
        tk = d["v2"].get("track", "?")
        tracks[tk] = tracks.get(tk, 0) + 1
    out = {"build": S2_SHADOW_BUILD, "window_days": days, "distinct_proposals": len(inwin),
           "would_benefit": len(benefit), "by_track": tracks, "bad_ts": bad_ts,
           "corrupt_lines": corrupt, "total_seen_alltime": len(seen)}
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print("== S2 SHADOW SENSOR (%s) · окно %d дн ==" % (S2_SHADOW_BUILD, days))
    print("   реальных пропозалов в окне: %d · из них выиграли бы от типа/трека: %d"
          % (len(inwin), len(benefit)))
    if tracks:
        print("   по трекам: " + ", ".join("%s=%d" % kv for kv in sorted(tracks.items())))
    if bad_ts:
        print("   ⚠️ %d записей с нечитаемым ts (в окно не идут)" % bad_ts)
    if corrupt:
        print("   ⚠️ %d битых строк в observe (пропущены)" % corrupt)
    print("   всего S2-теней за всё время: %d" % len(seen))
    if len(benefit) == 0:
        print("   💡 флип-или-убить: 0 в окне → tier-only движка достаточно → кандидат на УБИТЬ с уликой")
    else:
        print("   💡 флип-или-убить: %d/нед выиграли бы → кандидат на ФЛИП (порог N решает Антон)"
              % len(benefit))
    return 0


USAGE = """usage: consensus.py <verb> [args]   (full design notes: header of this file)

  propose  "<ACTION one line>" [--details "<evidence>"] [--tier 0|1|2] [--id <pid>] [--reversible]
  respond  <id> accept|counter|reject [<note>]
  commit   <id>                      status=agreed + tier<2 -> commit, then APPLY, then verify
  verify   <id> "<proof>"            done globally only when >=2 machines verify; proof must be
                                     DETERMINISTIC (exit 0 / md5-sha hash / counter N->M) once
                                     config "proof_grading_after" is armed -- prose won't close
  escalate <id> "<why>"              -> Anton via 02 POLICE (QQQ)
  approve  <id> "<who/where/msg-id>" record Anton's QQQ ok on a tier-2 proposal
  status   <id>                      one proposal + its timeline
  list     [--all]                   open (default) or every proposal
  pending  [--json]                  0-LLM worklist: what awaits MY response
  tick                               deterministic driver: timeouts, rounds, escalations
  ingest-tg                          pull peer events off the TG-03 rail
  sigs                               ledger signature audit
  v2-shadow [--json] [--days N]      S2 dark sensor: real proposals that would_benefit from typing

  -h | --help                        this text (also works after any verb)

note: `propose` refuses a subject starting with '-' -- a stray flag must never become the
      subject line and get broadcast to 03 (incident #4b814fec)."""


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    # CLI-HYGIENE (#94389335): -h/--help works bare AND after any verb, so nobody has to
    # read 1100 lines of header to recall an argument order.
    if a[0] in ("-h", "--help", "help") or "--help" in a[1:] or "-h" in a[1:]:
        print(USAGE); return 0
    cmd = a[0]
    if cmd == "propose" and len(a) >= 2:
        if a[1].startswith("-"):
            print("refusing: subject starts with '-' (%r) -- looks like a stray flag, not an "
                  "action. Put the ACTION first, evidence in --details.\n" % a[1], file=sys.stderr)
            print(USAGE)
            return 2
        return cmd_propose(a[1], details=_getopt(a, "--details"),
                           tier=_getopt(a, "--tier", 0), pid=_getopt(a, "--id"),
                           reversible=("--reversible" in a)) and 0
    if cmd == "respond" and len(a) >= 3:
        return cmd_respond(a[1], a[2], " ".join(a[3:]) or None)
    if cmd == "commit" and len(a) >= 2:
        return cmd_commit(a[1])
    if cmd == "verify" and len(a) >= 3:
        return cmd_verify(a[1], " ".join(a[2:]))
    if cmd == "escalate" and len(a) >= 3:
        return cmd_escalate(a[1], " ".join(a[2:]))
    if cmd == "status" and len(a) >= 2:
        return cmd_status(a[1])
    if cmd == "list":
        return cmd_list("all" if "--all" in a else "open")
    if cmd == "tick":
        return cmd_tick()
    if cmd == "ingest-tg":
        n = _ingest_tg(quiet=False)
        print("ingest-tg: %d new peer event(s)" % n)
        return 0
    if cmd == "pending":
        return cmd_pending("--json" in a)
    if cmd == "approve" and len(a) >= 3:
        return cmd_approve(a[1], " ".join(a[2:]))
    if cmd == "sigs":
        return cmd_sigs()
    if cmd == "v2-shadow":
        return cmd_v2_shadow(as_json=("--json" in a), days=int(_getopt(a, "--days", 7) or 7))
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
