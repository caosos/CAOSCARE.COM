"""Read-only Claude session discovery (agent_control/discovery.py).

Pure filesystem test: a fake ~/.claude/sessions directory and a fake /proc.
No database, no live session touched."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_control import discovery  # noqa: E402


def _proc(root, pid, ppid, start, parent="bash"):
    d = root / str(pid)
    (d / "fd").mkdir(parents=True)
    # comm, (state ppid ... field 22 = start time)
    fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)] + ["0"] * 5
    (d / "stat").write_text(f"{pid} (claude) " + " ".join(fields))
    os.symlink("/dev/pts/9", d / "fd" / "0")
    (root / str(ppid)).mkdir(exist_ok=True)
    (root / str(ppid) / "comm").write_text(parent + "\n")


def test_discovery_reads_allowlisted_fields_and_flags_ambiguity(tmp_path, monkeypatch):
    sess, proc = tmp_path / "sessions", tmp_path / "proc"
    sess.mkdir()
    proc.mkdir()
    monkeypatch.setenv("CAOSCARE_CLAUDE_SESSIONS_DIR", str(sess))
    base = {"kind": "interactive", "cwd": str(tmp_path), "status": "idle",
            "messagingSocketPath": "/run/secret.sock", "authToken": "SECRET"}
    (sess / "101.json").write_text(json.dumps({**base, "pid": 101, "sessionId": "s-a", "name": "a", "procStart": "500"}))
    (sess / "102.json").write_text(json.dumps({**base, "pid": 102, "sessionId": "s-a", "name": "b", "procStart": "600"}))
    (sess / "103.json").write_text(json.dumps({**base, "pid": 103, "sessionId": "s-c", "name": "c", "procStart": "700"}))
    (sess / "104.json").write_text(json.dumps({**base, "pid": 104, "sessionId": "s-d", "name": "dead", "procStart": "1"}))
    (sess / "101.abc.key").write_text("TOP-SECRET-KEY")
    _proc(proc, 101, 11, 500)
    _proc(proc, 102, 12, 600)
    _proc(proc, 103, 13, 999)            # pid reused: start time differs from registry

    out = {s["name"]: s for s in discovery.discover(proc_root=str(proc))}
    assert set(out) == {"a", "b", "c", "dead"}
    blob = json.dumps(out)
    assert "SECRET" not in blob and "secret.sock" not in blob and "TOP-SECRET-KEY" not in blob
    assert out["a"]["alive"] and out["a"]["tty"] == "/dev/pts/9" and out["a"]["parent_comm"] == "bash"
    assert out["a"]["stable_key"] == "101:500"
    # Two live processes on one session id: neither is identifiable by session id.
    assert out["a"]["session_id_shared"] and out["b"]["session_id_shared"]
    assert out["c"]["pid_matches_registry"] is False and out["c"]["stable_key"] is None
    assert out["dead"]["alive"] is False and out["dead"]["stable_key"] is None
    assert out["a"]["cwd_branch"] is None          # tmp dir is not a git checkout


def test_missing_sessions_dir_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CAOSCARE_CLAUDE_SESSIONS_DIR", str(tmp_path / "nope"))
    assert discovery.discover() == []


def test_discovery_has_no_write_or_signal_calls():
    src = open(discovery.__file__).read()
    for banned in ("os.kill", "send_signal", "write_text", "import socket", "Popen",
                   "shell=True", "ptrace", "\"w\")"):
        assert banned not in src, banned
    assert 'glob("*.json")' in src
