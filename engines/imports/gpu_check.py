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
r"""gpu_check.py — machine-agnostic accelerator probe. Run FIRST before any heavy compute,
on ANY machine. ASCII-only output. Also detects (and optionally kills) stuck brain_embed_*
GPU processes (the zombie trap).

USAGE:
  python gpu_check.py            # report GPU, torch device-readiness, and any zombies
  python gpu_check.py --kill     # also kill stuck brain_embed_* processes holding the GPU
Exit: 0 = GPU usable now; 2 = GPU present but torch is CPU-build; 1 = no usable GPU."""
# encoding guard (cp1252 print-crash class) -- auto-added 2026-06-29
import sys as _enc
try:
    _enc.stdout.reconfigure(encoding='utf-8'); _enc.stderr.reconfigure(encoding='utf-8')
except Exception: pass
import os, re, sys, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import brain_common as bc
except Exception:
    bc = None

def nvidia_smi():
    if not shutil.which('nvidia-smi'):
        return None, None
    try:
        q = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free',
                            '--format=csv,noheader'], capture_output=True, text=True, timeout=15)
        gpus = [l.strip() for l in q.stdout.splitlines() if l.strip()]
        hdr = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=15).stdout
        m = re.search(r'CUDA Version:\s*([\d.]+)', hdr)
        return gpus, (m.group(1) if m else None)
    except Exception as e:
        return None, str(e)[:80]

def torch_state():
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        mps = bool(getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available())
        dev = torch.cuda.get_device_name(0) if cuda else None
        return torch.__version__, cuda, mps, dev
    except Exception as e:
        return None, False, False, f'torch import failed: {str(e)[:60]}'

gpus, drv_cuda = nvidia_smi()
tver, tcuda, tmps, tdev = torch_state()

print('=== GPU CHECK ===')
if gpus:
    print('GPU(s):', ' | '.join(gpus)); print('driver CUDA:', drv_cuda)
else:
    print('no NVIDIA GPU (nvidia-smi not found) — could be Apple Silicon (MPS) or CPU-only')
print('torch:', tver, '| CUDA:', tcuda, '| MPS:', tmps, ('('+tdev+')' if tdev else ''))

# --- zombie detection ---
stale = bc.find_stale('brain_embed') if bc else []
if stale:
    print('\n!!! STALE brain_embed_* processes on GPU (zombie trap — they hold VRAM):')
    for pid, cl in stale:
        print(f'  PID {pid}: {cl}')
    if '--kill' in sys.argv:
        killed = bc.kill_pids([p for p, _ in stale])
        print('KILLED:', killed, '-> VRAM should now be free; re-run your job.')
    else:
        print('  -> run `python gpu_check.py --kill` to free the VRAM before relaunching.')

# --- verdict ---
print()
if tcuda:
    print('VERDICT: CUDA GPU READY — scripts auto-use it (device=cuda, fp16). brain_embed_update.py is single-instance locked.')
    sys.exit(0)
elif tmps:
    print('VERDICT: Apple GPU (MPS) READY — scripts use device=mps.')
    sys.exit(0)
elif gpus and tver and '+cpu' in (tver or ''):
    print('VERDICT: GPU PRESENT but torch is CPU-build -> install CUDA torch:')
    print('  pip install torch --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps')
    print('  (use cuXXX <= driver CUDA shown above). Then torch auto-uses the GPU.')
    sys.exit(2)
else:
    print('VERDICT: no usable GPU -> CPU. For big jobs the scripts checkpoint + resume.')
    sys.exit(1)
