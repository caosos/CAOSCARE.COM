"""Failure-path tests for scripts/restart_dev_backend.sh.

Runs a TEMPLATED COPY of the script (port, root and interpreter substituted to a temp sandbox with a fake
uvicorn and a stub mongosh), so the real :8092 service is never touched."""
import os, shutil, socket, subprocess, sys, textwrap, threading, time
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "restart_dev_backend.sh"

FAKE_SERVER = textwrap.dedent("""
    import sys, http.server, signal
    port = int(sys.argv[sys.argv.index('--port') + 1])
    if 'STUB_IGNORE_TERM' in __import__('os').environ: signal.signal(signal.SIGTERM, signal.SIG_IGN)
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}')
        def log_message(self, *a): pass
    http.server.HTTPServer(('127.0.0.1', port), H).serve_forever()
""")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def box(tmp_path):
    port = free_port()
    while True:
        cand = free_port()
        if cand not in (port, port + 1) and port + 1 != cand:
            break
    root = tmp_path / "repo"; (root / "scripts").mkdir(parents=True); (root / "backend").mkdir()
    (root / "backend" / "server.py").write_text("")
    (tmp_path / "fake_server.py").write_text(FAKE_SERVER)
    py = tmp_path / "py"
    py.write_text(f'#!/bin/bash\n[ "$1" = "-c" ] && exit ${{STUB_IMPORT_RC:-0}}\n'
                  f'[ -n "$STUB_START_FAIL" ] && [ "$STUB_START_FAIL" != "after_cand" ] && exit 1\n'
                  f'exec {sys.executable} {tmp_path}/fake_server.py "$@"\n')
    py.chmod(0o755)
    stubs = tmp_path / "bin"; stubs.mkdir()
    m = stubs / "mongosh"; m.write_text('#!/bin/bash\n[ -n "$STUB_MONGO_FAIL" ] && exit 1\necho "${STUB_LEASES:-0}"\n'); m.chmod(0o755)
    text = SCRIPT.read_text()
    text = text.replace("PORT=8092 ", f"PORT={port} ").replace("/home/caoscare-1/CAOSCARE-INTEGRATION", str(root))
    text = text.replace("/home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3", str(py))
    assert str(port) in text and str(root) in text
    s = root / "scripts" / "restart_dev_backend.sh"; s.write_text(text); s.chmod(0o755)
    procs = []
    yield dict(script=s, port=port, root=root, py=py, env_extra={"PATH": f"{stubs}:{os.environ['PATH']}"}, procs=procs)
    for p in procs:
        p.kill()
    subprocess.run(["pkill", "-f", str(tmp_path / "fake_server.py")])


def run(box, *args, **env):
    e = {**os.environ, **box["env_extra"], **{k: str(v) for k, v in env.items()}}
    return subprocess.run([str(box["script"]), *args], capture_output=True, text=True, env=e, timeout=120)


def start_old(box, **env):
    """A fake 'dev backend' already listening, with the right cmdline and cwd."""
    e = {**os.environ, **{k: str(v) for k, v in env.items()}}
    p = subprocess.Popen([str(box["py"]), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", str(box["port"])],
                         cwd=box["root"] / "backend", env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    box["procs"].append(p)
    threading.Thread(target=p.wait, daemon=True).start()  # reap like init would, so a stopped pid really disappears
    for _ in range(40):
        if socket.socket().connect_ex(("127.0.0.1", box["port"])) == 0:
            break
        time.sleep(0.25)
    return p


def alive(p):
    return p.poll() is None


def test_rejects_unsupported_arguments(box):
    r = run(box, "--port", "9999")
    assert r.returncode == 2 and "unsupported" in r.stderr


def test_refuses_wrong_root(box):
    text = box["script"].read_text().replace(f'EXPECT_ROOT="{box["root"]}"', 'EXPECT_ROOT="/nowhere"')
    box["script"].write_text(text)
    assert run(box).returncode == 2


def test_missing_interpreter_and_import_failure(box):
    box["py"].rename(str(box["py"]) + ".gone")
    assert "interpreter missing" in run(box).stderr
    box["py"] = Path(str(box["py"]) + ".gone"); box["py"].rename(str(box["py"])[:-5])
    box["py"] = Path(str(box["py"])[:-5])
    assert "import server failed" in run(box, STUB_IMPORT_RC=1).stderr


def test_active_lease_and_uncertain_state_do_not_restart(box):
    old = start_old(box)
    assert "live lease" in run(box, STUB_LEASES=1).stderr
    assert "cannot read leases" in run(box, STUB_MONGO_FAIL=1).stderr
    assert alive(old)


def test_wrong_process_on_port_is_not_killed(box):
    other = subprocess.Popen([sys.executable, "-m", "http.server", str(box["port"]), "--bind", "127.0.0.1"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    box["procs"].append(other)
    time.sleep(1)
    r = run(box)
    assert r.returncode == 2 and "not the dev backend" in r.stderr and alive(other)


def test_bind_conflict_on_spare_port(box):
    s = socket.socket(); s.bind(("127.0.0.1", box["port"] + 1)); s.listen(1)
    try:
        r = run(box)
        assert r.returncode == 2 and "spare port" in r.stderr
    finally:
        s.close()


def test_new_code_failing_to_start_leaves_service_running(box):
    old = start_old(box)
    r = run(box, STUB_START_FAIL="1")
    assert r.returncode == 2 and "did not start healthy" in r.stderr and alive(old)


def test_check_only_changes_nothing(box):
    old = start_old(box)
    r = run(box, "--check")
    assert r.returncode == 0 and "candidate_started_ok=1" in r.stdout and alive(old)


def test_stop_failure_exits_nonzero_and_old_survives(box):
    old = start_old(box, STUB_IGNORE_TERM=1)
    r = run(box)
    assert r.returncode == 4 and "STOP FAILED" in r.stderr and alive(old)


def test_successful_restart_new_pid_owns_port(box):
    old = start_old(box)
    r = run(box)
    assert r.returncode == 0 and "RESTART OK" in r.stdout, r.stdout + r.stderr
    old.wait(timeout=10)
    assert not alive(old)
    new_pid = int(r.stdout.split("RESTART OK pid=")[1].split()[0])
    assert new_pid != old.pid
    box["procs"].append(type("P", (), {"kill": lambda self, p=new_pid: os.kill(p, 9)})())
