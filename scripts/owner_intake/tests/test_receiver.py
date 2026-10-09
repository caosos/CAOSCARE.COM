import json, os, stat, subprocess, sys
from pathlib import Path
import pytest

RX = Path(__file__).resolve().parents[1] / "receiver.py"
FAKE = '#!/usr/bin/env python3\nimport os,sys\nimport json;open(os.environ["FAKE_GH_LOG"],"a").write(json.dumps(sys.argv[1:])+"\\n")\nsys.exit(1 if os.environ.get("FAKE_GH_FAIL") else 0)\n'


@pytest.fixture
def env(tmp_path):
    gh = tmp_path / "gh"; gh.write_text(FAKE); gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return dict(os.environ, CAOS_INTAKE_DIR=str(tmp_path / "d"), CAOS_INTAKE_GH=str(gh),
                FAKE_GH_LOG=str(tmp_path / "calls.log")), tmp_path


def run(e, *a):
    return subprocess.run([sys.executable, str(RX), *a], env=e, capture_output=True, text=True)


def posts(tmp):
    p = tmp / "calls.log"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def test_received_recorded_once(env):
    e, tmp = env
    run(e, "received", "da-abc", "--issue", "117")
    assert "already recorded" in run(e, "received", "da-abc", "--issue", "117").stdout
    assert len((tmp / "d/ledger.jsonl").read_text().splitlines()) == 1


def test_post_format_and_dedupe(env):
    e, tmp = env
    run(e, "received", "da-abc", "--issue", "117")
    r = run(e, "status", "da-abc", "ACK", "--issue", "117", "--note", "seen", "--post")
    assert r.returncode == 0
    assert len(posts(tmp)) == 1 and "body=<!-- caos:coordinator -->\nACK da-abc seen" in posts(tmp)[0]
    assert "nothing to do" in run(e, "status", "da-abc", "ACK", "--issue", "117", "--post").stdout
    assert len(posts(tmp)) == 1
    run(e, "status", "da-abc", "WORKING", "--issue", "117", "--post")
    assert len(posts(tmp)) == 2


def test_failed_post_retried_not_recorded(env):
    e, tmp = env
    assert run(dict(e, FAKE_GH_FAIL="1"), "status", "da-x", "ACK", "--issue", "1", "--post").returncode == 1
    assert not (tmp / "d/ledger.jsonl").exists() or "da-x" not in (tmp / "d/ledger.jsonl").read_text()
    assert run(e, "status", "da-x", "ACK", "--issue", "1", "--post").returncode == 0
    assert len(posts(tmp)) == 2


def test_status_without_post_then_post_once(env):
    e, tmp = env
    run(e, "status", "da-y", "ACK", "--issue", "1")
    assert posts(tmp) == []
    run(e, "status", "da-y", "ACK", "--issue", "1", "--post")
    run(e, "status", "da-y", "ACK", "--issue", "1", "--post")
    assert len(posts(tmp)) == 1


def test_list_open(env):
    e, tmp = env
    run(e, "received", "da-1", "--issue", "1"); run(e, "received", "da-2", "--issue", "1")
    run(e, "status", "da-2", "DONE", "--issue", "1")
    out = run(e, "list", "--open").stdout
    assert "da-1" in out and "da-2" not in out
    assert "da-2" in run(e, "list").stdout
