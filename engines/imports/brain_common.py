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
r"""brain_common.py — shared helpers for the brain_* embedding/search scripts.
Encodes the GPU rules so every script behaves the same: single-instance lock,
device selection (cuda/mps/cpu) with optional wait-for-GPU, fp16 on CUDA, zombie cleanup.
Import from any brain_*.py in this folder."""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os, sys, time, subprocess
from pathlib import Path

# Deterministic GPU numbering: make CUDA device indices match nvidia-smi (PCI order).
# Without this, pinning CUDA_VISIBLE_DEVICES=<nvidia-smi idx> can select the WRONG card,
# because torch defaults to FASTEST_FIRST ordering. Proven on hub HUB1 (2026-07-01):
# RTX 5060 Ti sm_120 + GTX 1660 SUPER sm_75 -> nvidia-smi idx 1 = RTX, but FASTEST_FIRST
# made "1" resolve to the slow 1660 -> RAG would silently run on the weak Turing card.
os.environ.setdefault('CUDA_DEVICE_ORDER', 'PCI_BUS_ID')

# HF OFFLINE for EVERY brain_* script (class-fix 2026-07-04): models are cached locally;
# an unauthenticated HF-hub check on every model load once stalled reindexes 20+ min. Set it
# HERE — every script imports brain_common before loading a model — so no NEW script forgets.
# ROOT-FIX 2026-07-23 (Anton "ещё раз поищи корень"): FORCE-set, NOT setdefault. setdefault
# is a NO-OP when the parent env already holds HF_HUB_OFFLINE as ''/'0'/'false' (a poisoned
# session/interpreter env) -> HF reads offline=False -> per-shard revalidation of the 199
# e5 weight files against the HF hub on load -> 40-min stall on a blocked/rate-limited IP
# (0% GPU, ~40s CPU). PROVEN A/B: offline OFF + blocked net = hang >120s; offline ON = 47s.
# A fresh scheduled-task spawn is unset (fine); a session/manual run may inherit a poison ->
# setdefault couldn't save it, force-set does. Escape hatch for an INTENTIONAL model fetch:
# export BRAIN_ALLOW_HF_ONLINE=1. ORDER MATTERS: import brain_common BEFORE sentence_transformers.
_hf_online = os.environ.get('BRAIN_ALLOW_HF_ONLINE') == '1'
# Symmetric (Codex t3 catch 2026-07-23): when the hatch asks for online we must ACTIVELY set
# offline=0 — a pre-existing HF_HUB_OFFLINE=1 in the parent env would otherwise keep us offline
# and the intentional model fetch would silently fail.
_off = '0' if _hf_online else '1'
os.environ['HF_HUB_OFFLINE'] = _off
os.environ['TRANSFORMERS_OFFLINE'] = _off
# Import-order belt (Codex t3 catch): huggingface_hub freezes HF_HUB_OFFLINE into a module
# constant AT ITS IMPORT; if it was imported before brain_common, our os.environ write is too
# late to flip it. No live script imports HF top-level before brain_common (audited 2026-07-23),
# but patch the already-loaded constant too so the guarantee doesn't depend on import order.
try:
    import sys as _sys
    _hc = _sys.modules.get('huggingface_hub.constants')
    if _hc is not None:
        _hc.HF_HUB_OFFLINE = not _hf_online
except Exception:
    pass

try:
    from _paths import IMPORTS as _IMP        # portable: reads ~/.claude/machine.env
    IMPORTS = Path(_IMP)
except Exception:
    IMPORTS = Path(r'%IMPORTS%')   # HP17 fallback

# ---------------- process liveness (no psutil; safe on Windows) ----------------
def pid_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return False
    if os.name == 'nt':
        try:
            out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                                 capture_output=True, text=True, timeout=15).stdout
            return str(pid) in out
        except Exception:
            return True  # assume alive if we can't tell (safer for lock)
    else:
        try:
            os.kill(pid, 0); return True
        except OSError:
            return False

def proc_start_token(pid):
    """Stable per-PROCESS identity token = its creation time. Two processes that happen to
    reuse the same PID have DIFFERENT creation times, so comparing this token defeats Windows
    PID-recycling (a crashed run's PID reassigned to an unrelated live process). Returns '' if
    it can't be determined — callers MUST treat '' as 'unknown' and fall back to the age
    tripwire, never as a match. Cross-platform + graceful (Anton-approved lock root-fix 2026-07-23)."""
    try:
        pid = int(pid)
    except Exception:
        return ''
    if os.name == 'nt':
        # Raw process creation time via Win32 GetProcessTimes = FILETIME (100ns ticks since
        # 1601-01-01 UTC). A UTC integer is timezone/DST-INVARIANT and stable for the life of the
        # process — unlike wmic `CreationDate`, whose LOCALIZED string can mutate across a DST flip
        # (same live process reports a different offset/hour) → false 'recycled' → STEALING a live
        # lock → two writers → corruption (Grok t3 catch 2026-07-23). Bonus: no subprocess (fast),
        # and works even on modern Win11 where wmic is removed. '' if the process can't be opened
        # (e.g. cross-user/permission) → caller falls back to the age tripwire (never a false steal).
        try:
            import ctypes
            from ctypes import wintypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid) or k.OpenProcess(0x0400, False, pid)  # QUERY_LIMITED_INFORMATION | QUERY_INFORMATION
            if not h:
                return ''
            try:
                c = wintypes.FILETIME(); e = wintypes.FILETIME(); kt = wintypes.FILETIME(); u = wintypes.FILETIME()
                if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(u)):
                    return ''
                return str((c.dwHighDateTime << 32) | c.dwLowDateTime)
            finally:
                k.CloseHandle(h)
        except Exception:
            return ''
    else:
        try:  # Linux: field 22 of /proc/<pid>/stat = starttime in clock ticks since boot
            with open(f'/proc/{pid}/stat', encoding='utf-8', errors='replace') as fh:
                data = fh.read()
            after = data.rsplit(')', 1)[-1].split()   # skip comm (may contain spaces/parens)
            return after[19] if len(after) > 19 else ''   # 22nd field, 0-based after comm+state
        except Exception:
            return ''

# ---------------- single-instance lock (prevents zombie multiplication) ----------------
# ARCHITECTURE RULE: Lock = "one instance of MY script", NOT "exclusive GPU access".
# Different roles get DIFFERENT names so they coexist on the GPU (fp16 + small batch fits):
#   brain_e5    -> reindex  (brain_embed_update.py)
#   synth_build -> build    (build_synth_packages_semantic.py)
#   browser_e5  -> browser  (browser-history/browser_search.py)
# Anything new that loads a model: pick a fresh name. Sharing the same name = self-throttling.
class Lock:
    """Refuses to start if another LIVE instance holds the lock. Auto-clears stale locks.
    busy_exit_code: process exit code when a LIVE holder blocks us. Default 3 = "loud red"
    (caller treats a collision as a failure). Pass 0 when a collision is BENIGN — i.e. the
    other live instance is already doing the same work, so this instance simply has nothing
    to do (e.g. the daily reindex colliding with one of many parallel sessions). The collision
    is still printed below, so it stays visible in the log either way.
    max_age_min: age tripwire against PID-reuse (consensus #5cef5f48, Anton 03-mandate
    2026-07-04) — a crashed run leaves its lock on disk, Windows recycles the dead PID for an
    unrelated LIVE process, pid_alive() then lies True forever and every next run silently
    skips. Older than max_age_min => treat as stale even if the pid looks alive (reclaim +
    warn). None (default) = off: GPU scripts legitimately hold their lock for hours.
    msg: optional custom busy-message (the default text is GPU-flavored)."""
    def __init__(self, name='brain_e5', busy_exit_code=3, max_age_min=None, msg=None):
        self.path = IMPORTS / f'_{name}.lock'
        self.busy_exit_code = busy_exit_code
        self.max_age_min = max_age_min
        self.msg = msg
    def __enter__(self):
        if self.path.exists():
            old, born, tok = '', 0, ''
            try:
                parts = self.path.read_text(encoding='utf-8').strip().split('|')
                old = parts[0]
                born = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                tok = parts[2] if len(parts) > 2 else ''   # stored process start-token ('' for legacy 2-field locks)
            except Exception:
                pass
            age_min = (time.time() - born) / 60.0 if born else None
            if old and pid_alive(old):
                # ROOT fix for PID-recycling (Anton-approved 2026-07-23): a PID looking alive is
                # NOT proof it's the SAME process. Compare the holder's start-token; if BOTH are
                # known and differ, the PID was recycled to a different process -> reclaim NOW
                # (no need to wait out max_age_min). Token unknown on either side ('') -> fall back
                # to the age tripwire (belt for when wmic/proc lookup fails).
                cur_tok = proc_start_token(old)
                recycled = bool(tok) and bool(cur_tok) and tok != cur_tok
                if recycled:
                    print(f'LOCK: holder PID {old} is alive but its start-time changed '
                          f'(stored {tok} != current {cur_tok}) — the PID was RECYCLED to a different '
                          f'process; reclaiming stale lock immediately: {self.path}')
                elif self.max_age_min is not None and age_min is not None and age_min > self.max_age_min:
                    print(f'LOCK: holder PID {old} looks alive but the lock is {age_min:.0f} min old '
                          f'(> {self.max_age_min} min) and start-token is unavailable — treating as a '
                          f'CRASHED run whose PID was recycled; reclaiming stale lock: {self.path}')
                else:
                    print(self.msg or
                          f'LOCK: another instance is running (PID {old}). Refusing to start a 2nd '
                          f'(this is what created the zombie pile-up). Kill it first or wait. '
                          f'Lock: {self.path}')
                    sys.exit(self.busy_exit_code)
            # stale lock -> reclaim
        # ATOMIC write (Grok t3 catch 2026-07-23): write to a temp file then os.replace so a
        # concurrent reader NEVER sees a half-written line — a truncated token would parse as a
        # non-empty garbage value != the holder's real token → false 'recycled' → stealing a live
        # lock. os.replace is atomic on same-volume (Windows + POSIX).
        tmp = self.path.with_name(self.path.name + f'.tmp{os.getpid()}')
        tmp.write_text(f'{os.getpid()}|{int(time.time())}|{proc_start_token(os.getpid())}',
                       encoding='utf-8')
        os.replace(tmp, self.path)
        return self
    def __exit__(self, *a):
        try:
            if self.path.exists() and self.path.read_text(encoding='utf-8').startswith(str(os.getpid())):
                self.path.unlink()
        except Exception:
            pass
        return False

# ---------------- device selection (cuda / mps / cpu) ----------------
def _gpu_free_mb():
    """[(index, free_MiB, compute_cap_float), ...] per NVIDIA GPU via nvidia-smi.
    No torch/CUDA init. [] on failure. compute_cap lets us prefer the most POWERFUL card
    (e.g. RTX 5060 Ti cc12.0 over GTX 1660 SUPER cc7.5), not merely the one with most free
    VRAM. Older drivers without the compute_cap column degrade to cc=0.0 (free-VRAM ranking)."""
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,memory.free,compute_cap',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=15)
        out = []
        for line in r.stdout.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2 and parts[0].isdigit():
                cc = 0.0
                if len(parts) >= 3:
                    try: cc = float(parts[2])
                    except Exception: cc = 0.0
                out.append((int(parts[0]), int(float(parts[1])), cc))
        return out
    except Exception:
        return []

def _best_gpu(gpus, min_free_mb):
    """Index of the card to use for compute, or None. Anton's rule (2026-07-01): ALWAYS load the
    most powerful card, NEVER the weak one. So candidates are restricted to the HIGHEST-compute-cap
    tier present — on the hub that's the RTX 5060 Ti (cc12.0); the GTX 1660 SUPER (cc7.5) is
    excluded from compute entirely and left to drive the monitors. Among top-tier cards we pick
    the one with most free VRAM. Returns None if no top-tier card clears min_free_mb, so the
    caller WAITS for it (wait_gpu_min) or falls back to CPU — but never drops to a weaker card.
    When all cards share the same cap (or cap is unknown = 0.0) this is plain most-free-VRAM
    balancing across them, unchanged from before."""
    if not gpus:
        return None
    top_cc = max(g[2] for g in gpus)
    tier = [g for g in gpus if g[2] >= top_cc - 1e-9 and g[1] >= min_free_mb]
    if not tier:
        return None
    tier.sort(key=lambda t: t[1], reverse=True)   # most free VRAM among the top-cc tier
    return tier[0][0]

def _cuda_free_bytes():
    try:
        import torch
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info(); return free
    except Exception:
        pass
    return 0

def pick_device(force_cpu=False, wait_gpu_min=0, min_free_gb=1.6, verbose=True):
    """Return 'cuda' | 'mps' | 'cpu'. Honors --cpu, waits up to wait_gpu_min for VRAM, falls back.

    Multi-GPU selection (2026-06-22; refined 2026-07-01): on a box with >1 NVIDIA card, auto-pin
    this process to the MOST POWERFUL card that has free VRAM (compute_cap first, free-VRAM as
    tie-break) via CUDA_VISIBLE_DEVICES *before* torch touches CUDA. This sends quality/fast
    compute to the new RTX 5060 Ti (cc12.0) rather than the old GTX 1660 (cc7.5). Combined with
    CUDA_DEVICE_ORDER=PCI_BUS_ID (set at import) so the pinned index matches nvidia-smi. Still
    returns the plain string 'cuda' — the pinned card becomes
    cuda:0 — so every `== 'cuda'` caller is unaffected. If CUDA_VISIBLE_DEVICES is already set
    (caller pinned it, e.g. a future sharded Variant-B run), it is respected and we don't auto-pick.
    If nvidia-smi is unavailable, falls back to the original torch-only behavior unchanged."""
    if force_cpu:
        return 'cpu'

    min_free_mb = min_free_gb * 1024
    auto_pinned = False
    if os.environ.get('CUDA_VISIBLE_DEVICES', '').strip() == '':
        gpus = _gpu_free_mb()
        if gpus:                       # nvidia-smi works -> balance here, pre-torch
            auto_pinned = True
            deadline = time.time() + wait_gpu_min * 60
            while True:
                idx = _best_gpu(gpus, min_free_mb)
                if idx is not None:
                    os.environ['CUDA_VISIBLE_DEVICES'] = str(idx)
                    if verbose:
                        cc = next((g[2] for g in gpus if g[0] == idx), 0.0)
                        print(f'GPU auto-pin -> CUDA_VISIBLE_DEVICES={idx} '
                              f'(most powerful free of {len(gpus)} GPUs, cc{cc})')
                    break
                if time.time() >= deadline:
                    auto_pinned = False   # nothing free -> let torch/CPU fallback decide
                    if verbose:
                        print(f'all {len(gpus)} GPUs busy (< {min_free_gb} GB free) after '
                              f'{wait_gpu_min} min -> falling back to CPU')
                    break
                if verbose:
                    print(f'all GPUs busy (< {min_free_gb} GB free) — waiting '
                          f'({int(deadline-time.time())}s left)')
                time.sleep(20)
                gpus = _gpu_free_mb()

    try:
        import torch
    except Exception:
        return 'cpu'
    need = min_free_gb * 1e9
    if torch.cuda.is_available():
        if auto_pinned:
            return 'cuda'              # nvidia-smi already confirmed room on the pinned card
        deadline = time.time() + wait_gpu_min * 60
        while True:
            free = _cuda_free_bytes()
            if free > need:
                return 'cuda'
            if time.time() >= deadline:
                if verbose:
                    print(f'GPU busy ({free/1e9:.1f} GB free < {min_free_gb} GB needed) after '
                          f'{wait_gpu_min} min wait -> falling back to CPU')
                break
            if verbose:
                print(f'GPU busy ({free/1e9:.1f} GB free) — waiting for {min_free_gb} GB... '
                      f'({int(deadline-time.time())}s left)')
            time.sleep(20)
    try:
        if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
            return 'mps'
    except Exception:
        pass
    return 'cpu'

def _fp16_is_fast():
    """True only on GPUs where fp16 actually accelerates (tensor cores, Ampere+ = cc>=8.0).
    On Turing 16-series (GTX 1660/SUPER, cc 7.5) and older, fp16 has NO tensor-core path and
    benchmarks ~4x SLOWER than fp32 (hub HUB1, 2026-06-25: 8 vs 33 chunks/sec) — this
    silently made every reindex ~4x slow and was the root cause of the never-finishing reindex
    loop. RTX A3000 (laptop, cc 8.6) keeps fp16. Decision: decision-always-on-memory-architecture
    / memory reindex-routine."""
    try:
        import torch
        major, _ = torch.cuda.get_device_capability()
        return major >= 8
    except Exception:
        return False

def load_model(model_name, device, fp16=True):
    """Load a SentenceTransformer on the chosen device; fp16 ONLY where it's actually faster
    (Ampere+ tensor cores). On Turing/older CUDA cards we force fp32 — faster there, see
    _fp16_is_fast()."""
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model_name, device=device)
    if fp16 and device == 'cuda' and _fp16_is_fast():
        try:
            m = m.half()
        except Exception as e:
            print('fp16 unavailable, using fp32:', str(e)[:60])
    return m

# ---------------- zombie / stale GPU process cleanup ----------------
def gpu_python_pids():
    """PIDs currently holding GPU compute contexts (NVIDIA)."""
    try:
        r = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
                           capture_output=True, text=True, timeout=15)
        return [l.strip() for l in r.stdout.splitlines() if l.strip().isdigit()]
    except Exception:
        return []

def cmdline_of(pid):
    if os.name != 'nt':
        try:
            return subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ''
    try:
        r = subprocess.run(['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine', '/format:list'],
                           capture_output=True, text=True, timeout=15)
        return ' '.join(x.strip() for x in r.stdout.splitlines() if x.strip()).replace('CommandLine=', '')
    except Exception:
        return ''

def find_stale(substr='brain_embed', exclude_pid=None):
    """Our brain_embed_* processes currently on the GPU (potential zombies)."""
    out = []
    me = str(os.getpid())
    for pid in gpu_python_pids():
        if pid == me or (exclude_pid and pid == str(exclude_pid)):
            continue
        cl = cmdline_of(pid)
        if substr in cl:
            out.append((pid, cl[:120]))
    return out

def kill_pids(pids):
    killed = []
    for pid in pids:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, timeout=15)
            else:
                os.kill(int(pid), 9)
            killed.append(pid)
        except Exception:
            pass
    return killed
