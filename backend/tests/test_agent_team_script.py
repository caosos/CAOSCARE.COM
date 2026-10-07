"""Static acceptance checks for the persistent CAOSCare agent-team launcher.

These tests deliberately do not start Claude or tmux in CI. Host/runtime
acceptance lives in docs/CAOSCARE_AGENT_TEAM_RUNBOOK.md.
"""
from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "caos-agent-team"


def test_agent_team_launcher_is_executable_and_bash_valid():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr


def test_agent_team_launcher_help_is_host_independent():
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert "start-all" in proc.stdout
    assert "recover" in proc.stdout
    assert "nudge" in proc.stdout
    assert "Ctrl-b" in proc.stdout


def test_launcher_targets_only_dedicated_named_sessions():
    text = SCRIPT.read_text()
    assert 'PREFIX="${CAOS_AGENT_SESSION_PREFIX:-caos-agent}"' in text
    assert "caoscare-1-" not in text
    assert "kill-server" not in text
    assert "kill-session -a" not in text
