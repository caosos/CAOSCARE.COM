#!/usr/bin/env python3
"""Wait until the backend started by THIS gate run is healthy.

Used by run_backend_tests.sh. Healthy means GET /api/health answers
{"ok": true, ...} AND echoes this run's id as "gate_run_id" (server.py adds
it only when CAOSCARE_TEST_GATE_RUN_ID is set, which only the gate does).
So another process answering on the same port can never pass for ours.

Exit codes:
  0  our backend is healthy
  3  our backend process exited (e.g. it could not bind the port)
  4  a server answered on the port but it is not this run's backend
  5  timed out waiting

Standard library only, so it runs with any python3.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie child still "exists"; treat it as gone.
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except OSError:
        return True


def _health(port: int):
    """Parsed /api/health JSON, or None if nothing usable answered."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            return json.loads(r.read().decode() or "null")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def wait(port: int, run_id: str, pid: int, timeout: float, interval: float = 0.5) -> int:
    deadline = time.monotonic() + timeout
    while True:
        if pid and not _alive(pid):
            print(f"gate: backend process {pid} exited before becoming healthy", file=sys.stderr)
            return 3
        body = _health(port)
        if isinstance(body, dict):
            if body.get("gate_run_id") != run_id:
                print(f"gate: a server on port {port} answered /api/health but it is not this "
                      f"run's backend (gate_run_id={body.get('gate_run_id')!r})", file=sys.stderr)
                return 4
            if body.get("ok") is True:
                return 0
        if time.monotonic() >= deadline:
            print(f"gate: backend on port {port} not healthy after {timeout:.0f}s", file=sys.stderr)
            return 5
        time.sleep(interval)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--pid", type=int, default=0, help="our backend's pid (0 = do not check)")
    p.add_argument("--timeout", type=float, default=30)
    a = p.parse_args(argv)
    return wait(a.port, a.run_id, a.pid, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
