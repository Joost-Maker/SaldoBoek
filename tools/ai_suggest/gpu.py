"""GPU-bewaking: het model moet op de eGPU draaien, zonder fallback.

1. Vóór elke modelaanroep: de eGPU (amdgpu-kaart ≥ 8 GiB) moet er zijn.
2. Na het eerste geslaagde antwoord: kaart-VRAM ≥ 4 GiB én het modelproces
   zelf moet ≥ 4 GiB VRAM op die kaart hebben (gemeten via /proc/*/fdinfo).
   Alleen de kaartcheck zegt niets als een ander proces de kaart al vult.
"""

import glob
import os
import re

GIB = 1024 ** 3
EGPU_MIN_TOTAL = 8 * GIB
MIN_RESIDENT = 4 * GIB
SPILL_RATIO = 0.9


class GuardError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _read(path):
    with open(path) as f:
        return f.read().strip()


def _read_int(path):
    try:
        return int(_read(path))
    except (OSError, ValueError):
        return None


def find_egpu(sysfs_root):
    """{'card', 'device', 'pdev', 'total'} van de grootste kaart ≥ 8 GiB, of None."""
    best = None
    for card in sorted(glob.glob(os.path.join(sysfs_root, "card[0-9]*"))):
        if not re.fullmatch(r"card\d+", os.path.basename(card)):
            continue  # connectors als card0-DP-5 overslaan
        device = os.path.join(card, "device")
        total = _read_int(os.path.join(device, "mem_info_vram_total"))
        if total is None or total < EGPU_MIN_TOTAL:
            continue
        if best is None or total > best["total"]:
            best = {
                "card": os.path.basename(card),
                "device": device,
                "pdev": os.path.basename(os.path.realpath(device)),
                "total": total,
            }
    return best


def require_egpu(sysfs_root):
    egpu = find_egpu(sysfs_root)
    if egpu is None:
        raise GuardError(2, "eGPU niet aangesloten — geen CPU/iGPU-fallback")
    return egpu


def card_used(egpu):
    return _read_int(os.path.join(egpu["device"], "mem_info_vram_used")) or 0


def _cmdline(proc_root, pid):
    try:
        with open(os.path.join(proc_root, pid, "cmdline"), "rb") as f:
            return [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return []


def _arg(args, flag):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def _ppid(proc_root, pid):
    try:
        for line in _read(os.path.join(proc_root, pid, "status")).splitlines():
            if line.startswith("PPid:"):
                return line.split()[1]
    except OSError:
        pass
    return None


def _pids(proc_root):
    try:
        return [p for p in os.listdir(proc_root) if p.isdigit()]
    except OSError:
        return []


def process_vram(proc_root, pid, pdev):
    """VRAM (bytes) van een proces op kaart `pdev`, per drm-client-id één keer.

    Gooit OSError als fdinfo niet leesbaar is.
    """
    fdinfo_dir = os.path.join(proc_root, pid, "fdinfo")
    clients = {}
    for name in os.listdir(fdinfo_dir):
        try:
            text = _read(os.path.join(fdinfo_dir, name))
        except OSError:
            continue
        fields = {}
        for line in text.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        if fields.get("drm-pdev") != pdev or "drm-memory-vram" not in fields:
            continue
        kib = int(fields["drm-memory-vram"].split()[0])
        client = fields.get("drm-client-id", name)
        clients[client] = max(clients.get(client, 0), kib)
    return sum(clients.values()) * 1024


def find_model_process(proc_root, alias, port):
    """(pid, args) van het modelproces met --alias <alias> onder de router op <port>."""
    for pid in _pids(proc_root):
        args = _cmdline(proc_root, pid)
        if _arg(args, "--alias") != alias:
            continue
        ppid = _ppid(proc_root, pid)
        if ppid and _arg(_cmdline(proc_root, ppid), "--port") == str(port):
            return pid, args
    return None, None


def other_holders(proc_root, pdev, exclude_pid, limit=3):
    holders = []
    for pid in _pids(proc_root):
        if pid == exclude_pid:
            continue
        try:
            vram = process_vram(proc_root, pid, pdev)
        except (OSError, ValueError):
            continue
        if vram >= 256 * 1024 ** 2:
            args = _cmdline(proc_root, pid)
            label = _arg(args, "--alias") or (os.path.basename(args[0]) if args else pid)
            holders.append((pid, label, vram))
    holders.sort(key=lambda h: h[2], reverse=True)
    return holders[:limit]


def post_check(egpu, proc_root, alias, port):
    """Na het eerste geslaagde antwoord. Geeft (rapportregel, spill-waarschuwing|None)."""
    used = card_used(egpu)
    if used < MIN_RESIDENT:
        raise GuardError(3, "model draait niet op de eGPU")

    pid, args = find_model_process(proc_root, alias, port)
    if pid is None:
        raise GuardError(3, f"model-proces niet gevonden op :{port}")
    try:
        resident = process_vram(proc_root, pid, egpu["pdev"])
    except (OSError, ValueError):
        raise GuardError(3, f"fdinfo onleesbaar voor pid {pid}")
    if resident < MIN_RESIDENT:
        raise GuardError(
            3, f"model draait niet op de eGPU ({resident / GIB:.1f} GiB resident)"
        )

    report = (
        f"eGPU {egpu['card']}: {used / GIB:.1f}/{egpu['total'] / GIB:.1f} GiB in gebruik, "
        f"model (pid {pid}) {resident / GIB:.1f} GiB resident"
    )

    warning = None
    model_path = _arg(args, "--model")
    try:
        size = os.path.getsize(model_path) if model_path else 0
    except OSError:
        size = 0
    if size and resident < SPILL_RATIO * size:
        others = other_holders(proc_root, egpu["pdev"], pid)
        wie = ", ".join(f"{label} (pid {p}, {v / GIB:.1f} GiB)" for p, label, v in others)
        warning = (
            f"WAARSCHUWING: model past niet volledig op de eGPU "
            f"({resident / GIB:.1f} van {size / GIB:.1f} GiB) — dit wordt traag."
            + (f" Andere VRAM-gebruikers: {wie}." if wie else "")
        )
    return report, warning
