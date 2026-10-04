"""Host and process sampling from /proc (no extra dependencies): CPU of the
backend processes and mongod, resident memory, open file descriptors, open
TCP connections to the backend port, and whole-host CPU."""
import asyncio
import os

CLK = os.sysconf("SC_CLK_TCK")
NCPU = os.cpu_count() or 1


def _cpu_ticks(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/stat") as f:
            parts = f.read().rsplit(")", 1)[1].split()
        return int(parts[11]) + int(parts[12])
    except (OSError, IndexError, ValueError):
        return 0


def _rss_mb(pid: int) -> float:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def _fds(pid: int) -> int:
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return 0


def _host_ticks():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    idle = v[3] + v[4]
    return sum(v), idle


def _conns(port: int) -> int:
    hexport = f"{port:04X}"
    n = 0
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as f:
                next(f)
                for line in f:
                    p = line.split()
                    if p[1].endswith(":" + hexport) and p[3] == "01":
                        n += 1
        except OSError:
            pass
    return n


def children(pid: int) -> list:
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        out.append(p)
        try:
            with open(f"/proc/{p}/task/{p}/children") as f:
                todo += [int(c) for c in f.read().split()]
        except OSError:
            pass
    return out


def find_pid(name: str):
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                with open(f"/proc/{p}/comm") as f:
                    if f.read().strip() == name:
                        return int(p)
            except OSError:
                pass
    return None


class Sampler:
    def __init__(self, server_pid: int, port: int, interval: float = 0.25):
        self.server_pid, self.port, self.interval = server_pid, port, interval
        self.mongod = find_pid("mongod")
        self.samples = []
        self._task = None

    def _snap(self):
        pids = children(self.server_pid)
        return {"app_ticks": sum(_cpu_ticks(p) for p in pids),
                "mongo_ticks": _cpu_ticks(self.mongod) if self.mongod else 0,
                "host": _host_ticks(), "rss_mb": sum(_rss_mb(p) for p in pids),
                "fds": sum(_fds(p) for p in pids), "conns": _conns(self.port), "procs": len(pids)}

    async def _run(self):
        loop = asyncio.get_running_loop()
        prev, t_prev = self._snap(), loop.time()
        while True:
            await asyncio.sleep(self.interval)
            cur, t = self._snap(), loop.time()
            dt = max(t - t_prev, 1e-6)
            ht, hi = cur["host"][0] - prev["host"][0], cur["host"][1] - prev["host"][1]
            self.samples.append({
                "app_cpu_pct": (cur["app_ticks"] - prev["app_ticks"]) / CLK / dt * 100,
                "mongo_cpu_pct": (cur["mongo_ticks"] - prev["mongo_ticks"]) / CLK / dt * 100,
                "host_cpu_pct": (1 - hi / ht) * 100 if ht else 0.0,
                "rss_mb": cur["rss_mb"], "fds": cur["fds"], "conns": cur["conns"]})
            prev, t_prev = cur, t

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> dict:
        self._task.cancel()
        s = self.samples or [{"app_cpu_pct": 0, "mongo_cpu_pct": 0, "host_cpu_pct": 0, "rss_mb": 0,
                              "fds": 0, "conns": 0}]

        def stat(k):
            v = sorted(x[k] for x in s)
            return {"avg": round(sum(v) / len(v), 1), "p95": round(v[int(0.95 * (len(v) - 1))], 1),
                    "max": round(v[-1], 1)}
        return {"samples": len(s), "cpu_cores": NCPU, **{k: stat(k) for k in
                ("app_cpu_pct", "mongo_cpu_pct", "host_cpu_pct", "rss_mb", "fds", "conns")}}
