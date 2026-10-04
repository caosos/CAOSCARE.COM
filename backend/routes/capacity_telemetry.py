"""Capacity telemetry: what CAOSCare is actually being used for.

Two sources, both labelled by traffic class and by real vs simulated:
- an in-process Recorder fed by an HTTP middleware (every API request), the
  voice bridge (every turn) and create_receipt (every receipt write);
- host readings from /proc and /sys (CPU, load, memory, swap, disk, I/O
  wait, network, temperature).

Each uvicorn worker keeps its own Recorder and publishes it to
`capacity_worker_stats` every interval; the monitor merges them
(capacity_monitor.py). Simulated traffic is whatever a synthetic resident
produced or what carries `X-CAOSCare-Traffic: simulator`; it is never counted
as real resident or staff demand.
"""
import os
import shutil
import threading
import time

TRAFFIC_CLASSES = (
    "resident_voice", "resident_device", "pendant_help", "staff_dashboard", "staff_workflow",
    "simulator_resident", "simulator_staff", "background_jobs", "email_notification", "receipt_audit_writes",
)
SIM_HEADER = "x-caoscare-traffic"


def classify_request(path: str, method: str, simulated: bool = False) -> str:
    p = path.removeprefix("/api")
    resident_side = p.startswith(("/voice-bridge/turn", "/devices/public", "/realtime", "/kiosks",
                                  "/residents/public", "/tasks/resident-request", "/transportation/request",
                                  "/alerts", "/rf/event"))
    if simulated:
        return "simulator_resident" if resident_side else "simulator_staff"
    if p.startswith("/voice-bridge/turn") or p.startswith("/realtime"):
        return "resident_voice"
    if p.startswith("/devices/public"):
        return "resident_device"
    if p.startswith(("/rf/event", "/alerts/ai-escalate")) or (p.startswith("/alerts") and method == "POST"):
        return "pendant_help"
    if p.startswith(("/email", "/notifications")):
        return "email_notification"
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "staff_workflow"
    return "staff_dashboard"


def _pct(values, q):
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))], 1)


class Recorder:
    """Thread-safe counters for one interval. snapshot() returns and resets."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        self.started = time.time()
        self.api = {c: {"requests": 0, "errors": 0, "latency_ms": []} for c in TRAFFIC_CLASSES}
        self.voice = {"turns": 0, "real": 0, "simulated": 0, "latency_s": [], "outcomes": {}, "classes": {},
                      "timeouts": 0, "llm_failures": 0, "rate_limited": 0}
        self.receipts = {"writes": 0, "write_ms": []}
        self.reports = 0
        self.staff_users = set()
        self.live_board_users = set()

    def request(self, cls: str, latency_ms: float, status: int, path: str = "", user: str = None):
        with self._lock:
            a = self.api.setdefault(cls, {"requests": 0, "errors": 0, "latency_ms": []})
            a["requests"] += 1
            a["errors"] += status >= 500
            if len(a["latency_ms"]) < 5000:
                a["latency_ms"].append(latency_ms)
            if "/reports" in path:
                self.reports += 1
            if user and cls in ("staff_dashboard", "staff_workflow"):
                self.staff_users.add(user)
                if path.endswith(("/alerts/feed", "/ops/overview")):
                    self.live_board_users.add(user)

    def voice_turn(self, priority_class: str, outcome: str, latency_s: float, simulated: bool,
                   error: str = None):
        with self._lock:
            v = self.voice
            v["turns"] += 1
            v["simulated" if simulated else "real"] += 1
            v["outcomes"][outcome] = v["outcomes"].get(outcome, 0) + 1
            v["classes"][priority_class] = v["classes"].get(priority_class, 0) + 1
            if len(v["latency_s"]) < 5000:
                v["latency_s"].append(latency_s)
            e = (error or "").lower()
            if "429" in e or "rate limit" in e:
                v["rate_limited"] += 1
            elif "timeout" in e or "timed out" in e or "budget" in e:
                v["timeouts"] += 1
            elif e:
                v["llm_failures"] += 1

    def receipt_write(self, ms: float):
        with self._lock:
            self.receipts["writes"] += 1
            if len(self.receipts["write_ms"]) < 5000:
                self.receipts["write_ms"].append(ms)

    def snapshot(self) -> dict:
        with self._lock:
            out = {
                "interval_s": round(time.time() - self.started, 1),
                "api": {c: {"requests": a["requests"], "errors": a["errors"],
                            "p50_ms": _pct(a["latency_ms"], .5), "p95_ms": _pct(a["latency_ms"], .95),
                            "latency_sum_ms": round(sum(a["latency_ms"]), 1)}
                        for c, a in self.api.items()},
                "voice": {**{k: v for k, v in self.voice.items() if k != "latency_s"},
                          "latency_s": list(self.voice["latency_s"])},
                "receipts": {"writes": self.receipts["writes"], "write_ms": list(self.receipts["write_ms"])},
                "reports": self.reports, "staff_users": sorted(self.staff_users),
                "live_board_users": sorted(self.live_board_users),
            }
            self._reset()
        return out


RECORDER = Recorder()


# ---------------------------------------------------------------- host ----

def _read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def cpu_ticks() -> list:
    """[(total, idle, iowait)] for the whole host then each core."""
    out = []
    for line in _read("/proc/stat").splitlines():
        if not line.startswith("cpu"):
            break
        v = [int(x) for x in line.split()[1:]]
        out.append((sum(v), v[3] + v[4], v[4]))
    return out


def disk_io() -> tuple:
    """(io_ms, ios) summed over whole disks (sdX, nvmeXnY, vdX)."""
    ms = ios = 0
    for line in _read("/proc/diskstats").splitlines():
        p = line.split()
        if len(p) < 14:
            continue
        name = p[2]
        if name.startswith(("sd", "vd")) and not name[-1].isdigit() or (name.startswith("nvme") and "p" not in name[4:]):
            ios += int(p[3]) + int(p[7])
            ms += int(p[6]) + int(p[10])
    return ms, ios


def net_bytes() -> tuple:
    rx = tx = 0
    for line in _read("/proc/net/dev").splitlines()[2:]:
        name, data = line.split(":", 1)
        if name.strip() == "lo":
            continue
        f = data.split()
        rx, tx = rx + int(f[0]), tx + int(f[8])
    return rx, tx


def vm_swap() -> tuple:
    d = dict(line.split() for line in _read("/proc/vmstat").splitlines() if line.startswith(("pswpin", "pswpout")))
    return int(d.get("pswpin", 0)), int(d.get("pswpout", 0))


def memory() -> dict:
    m = {}
    for line in _read("/proc/meminfo").splitlines():
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) / 1024
    total, avail = m.get("MemTotal", 0), m.get("MemAvailable", 0)
    return {"total_mb": round(total), "available_mb": round(avail), "used_mb": round(total - avail),
            "used_pct": round((total - avail) / total * 100, 1) if total else None,
            "swap_used_mb": round(m.get("SwapTotal", 0) - m.get("SwapFree", 0))}


def temperature_c():
    best = None
    for root in ("/sys/class/hwmon", "/sys/class/thermal"):
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for e in entries:
            for f in ("temp1_input", "temp"):
                raw = _read(f"{root}/{e}/{f}").strip()
                if raw.lstrip("-").isdigit():
                    c = int(raw) / 1000
                    if 0 < c < 130:
                        best = max(best or c, c)
    return best


def host_counters() -> dict:
    """Raw cumulative counters; host_reading() turns two of these into rates."""
    return {"t": time.monotonic(), "cpu": cpu_ticks(), "disk": disk_io(), "net": net_bytes(), "swap": vm_swap()}


def host_reading(prev: dict, cur: dict, disk_path: str = "/") -> dict:
    dt = max(cur["t"] - prev["t"], 1e-6)
    cores = []
    for (t0, i0, w0), (t1, i1, w1) in zip(prev["cpu"], cur["cpu"]):
        dtot = max(t1 - t0, 1)
        cores.append({"busy_pct": round((1 - (i1 - i0) / dtot) * 100, 1), "iowait_pct": round((w1 - w0) / dtot * 100, 1)})
    total = cores[0] if cores else {"busy_pct": None, "iowait_pct": None}
    d_ms, d_ios = cur["disk"][0] - prev["disk"][0], cur["disk"][1] - prev["disk"][1]
    du = shutil.disk_usage(disk_path)
    load = _read("/proc/loadavg").split()
    return {
        "cpu_pct": total["busy_pct"], "iowait_pct": total["iowait_pct"],
        "cpu_per_core_pct": [c["busy_pct"] for c in cores[1:]], "cores": max(1, len(cores) - 1),
        "load_1": float(load[0]) if load else None, "load_5": float(load[1]) if load else None,
        "load_15": float(load[2]) if load else None,
        "memory": memory(),
        "swap_in_per_s": round((cur["swap"][0] - prev["swap"][0]) / dt, 2),
        "swap_out_per_s": round((cur["swap"][1] - prev["swap"][1]) / dt, 2),
        "disk_total_gb": round(du.total / 1e9, 1), "disk_free_gb": round(du.free / 1e9, 1),
        "disk_used_pct": round(du.used / du.total * 100, 1),
        "disk_latency_ms": round(d_ms / d_ios, 2) if d_ios else 0.0,
        "net_rx_bps": round((cur["net"][0] - prev["net"][0]) / dt), "net_tx_bps": round((cur["net"][1] - prev["net"][1]) / dt),
        "temperature_c": temperature_c(),
    }
