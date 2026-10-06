"""The backend test gate's own isolation (scripts/run_backend_tests.sh).

Defect this guards (2026-10-05): when another gate's backend already held the
port, ours failed to bind, the curl health check was answered by the other
backend, and pytest ran against a server using a different database. All
runs also shared one log file.

These tests have no side effects: they use throwaway HTTP servers on free
ports, a stub `mongosh` and a stub backend Python that only record that they
were called. They never drop a database or start a backend, so they are safe
inside the gate itself.
"""
import json
import os
import re
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(BACKEND, "scripts", "run_backend_tests.sh")
sys.path.insert(0, os.path.join(BACKEND, "scripts"))

import gate_wait_healthy  # noqa: E402


def _health_server(body):
    """Serve `body` as JSON on GET /api/health; returns (server, port)."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = json.dumps(body).encode()
            self.send_response(200 if self.path == "/api/health" else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stub(path, marker):
    with open(path, "w") as f:
        f.write(f'#!/bin/sh\necho "$0 $*" >> "{marker}"\nexit 0\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def _run_gate(tmp_path, port):
    marker = tmp_path / "invoked.txt"
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    _stub(stubs / "mongosh", marker)
    _stub(stubs / "python3", marker)
    env = {k: v for k, v in os.environ.items() if k != "CAOSCARE_TEST_LOG"}
    env.update(PATH=f"{stubs}:{env.get('PATH', '')}",
               CAOSCARE_TEST_PORT=str(port),
               CAOSCARE_TEST_DB="caoscare_gate_isolation_never_used",
               CAOSCARE_TEST_VENV_PY=str(stubs / "python3"),
               TMPDIR=str(tmp_path))
    r = subprocess.run(["bash", GATE], env=env, capture_output=True, text=True, timeout=60)
    return r, r.stdout + r.stderr, marker


# --- occupied port -----------------------------------------------------------

def test_occupied_port_refused_before_any_side_effect(tmp_path):
    srv, port = _health_server({"ok": True, "db": "up"})  # looks perfectly healthy
    try:
        r, out, marker = _run_gate(tmp_path, port)
    finally:
        srv.shutdown()
    assert r.returncode != 0, out
    assert f"Port {port}" in out and "already in use" in out, out
    assert "Dropping" not in out and "Running pytest" not in out, out
    assert not marker.exists(), "mongosh or the backend was invoked: " + marker.read_text()


def test_each_run_gets_its_own_log_and_run_id(tmp_path):
    srv, port = _health_server({"ok": True})
    try:
        outs = [_run_gate(tmp_path, port)[1] for _ in range(2)]
    finally:
        srv.shutdown()
    logs = [re.search(r"Backend log: (\S+)", o).group(1) for o in outs]
    ids = [re.search(r"Gate run (\S+)", o).group(1) for o in outs]
    assert logs[0] != logs[1] and all(os.path.isfile(p) for p in logs), logs
    assert ids[0] != ids[1], ids
    assert not any("caoscare_backend_test_gate.log" == os.path.basename(p) for p in logs)


# --- health check must belong to this run ------------------------------------

@pytest.mark.parametrize("body", [
    {"ok": True, "db": "up"},                          # another gate's / an older backend
    {"ok": True, "db": "up", "gate_run_id": "other"},  # another gate run
])
def test_foreign_backend_is_rejected(body):
    srv, port = _health_server(body)
    try:
        assert gate_wait_healthy.wait(port, "this-run", pid=0, timeout=3, interval=0.05) == 4
    finally:
        srv.shutdown()


def test_matching_run_id_passes():
    srv, port = _health_server({"ok": True, "db": "up", "gate_run_id": "this-run"})
    try:
        assert gate_wait_healthy.wait(port, "this-run", pid=os.getpid(), timeout=3) == 0
    finally:
        srv.shutdown()


def test_our_backend_with_db_down_is_not_healthy():
    srv, port = _health_server({"ok": False, "db": "down", "gate_run_id": "this-run"})
    try:
        assert gate_wait_healthy.wait(port, "this-run", pid=0, timeout=0.3, interval=0.05) == 5
    finally:
        srv.shutdown()


def test_nothing_listening_times_out():
    assert gate_wait_healthy.wait(_free_port(), "this-run", pid=0, timeout=0.3, interval=0.05) == 5


def test_dead_backend_fails_fast_even_if_port_answers():
    # Our backend died (e.g. could not bind) while another server answers on the port.
    srv, port = _health_server({"ok": True, "db": "up", "gate_run_id": "this-run"})
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    try:
        assert gate_wait_healthy.wait(port, "this-run", pid=p.pid, timeout=3) == 3
    finally:
        srv.shutdown()


def test_unreaped_dead_backend_counts_as_dead():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with open(f"/proc/{p.pid}/stat") as f:
                if f.read().split(")")[-1].split()[0] == "Z":
                    break
            time.sleep(0.02)
        assert gate_wait_healthy._alive(p.pid) is False
    finally:
        p.wait()


# --- the server side of the contract -----------------------------------------

def test_health_echoes_run_id_only_under_gate_hooks(monkeypatch):
    import asyncio
    import server

    monkeypatch.setenv("CAOSCARE_TEST_GATE_RUN_ID", "run-xyz")
    monkeypatch.delenv("CAOSCARE_TEST_HOOKS", raising=False)
    assert "gate_run_id" not in asyncio.run(server.health())
    monkeypatch.setenv("CAOSCARE_TEST_HOOKS", "1")
    assert asyncio.run(server.health())["gate_run_id"] == "run-xyz"
    monkeypatch.delenv("CAOSCARE_TEST_GATE_RUN_ID")
    assert "gate_run_id" not in asyncio.run(server.health())


def test_gate_backend_is_this_run():
    """Inside the gate: the backend every other test talks to is this run's."""
    run_id = os.environ.get("CAOSCARE_TEST_GATE_RUN_ID")
    base = os.environ.get("REACT_APP_BACKEND_URL")
    if not run_id or not base:
        pytest.skip("only meaningful inside scripts/run_backend_tests.sh")
    with urllib.request.urlopen(f"{base}/api/health", timeout=5) as r:
        assert json.loads(r.read()).get("gate_run_id") == run_id
