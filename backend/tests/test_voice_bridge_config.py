"""Voice bridge configuration: model/provider selection and the backend bind
address. Pure functions; nothing is started or bound."""
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from routes.voice_bridge_config import DEFAULT_MODEL, SUPPORTED, log_selection, resolve_model
from serve import ALLOWED_HOSTS, DEFAULT_HOST, DEFAULT_PORT, resolve_bind


def test_model_default_is_explicit():
    cfg = resolve_model({})
    assert cfg == {"provider": "openai", "model": DEFAULT_MODEL, "ok": True, "error": None}
    assert DEFAULT_MODEL == "gpt-4o-mini"


def test_every_supported_model_is_accepted():
    for provider, models in SUPPORTED.items():
        for m in models:
            cfg = resolve_model({"CAOSCARE_VOICE_BRIDGE_PROVIDER": provider, "CAOSCARE_VOICE_BRIDGE_MODEL": m})
            assert cfg["ok"] and cfg["model"] == m


def test_unsupported_model_or_provider_is_refused_not_replaced():
    bad = resolve_model({"CAOSCARE_VOICE_BRIDGE_MODEL": "gpt-3.5-turbo"})
    assert not bad["ok"] and bad["model"] == "gpt-3.5-turbo" and "unsupported" in bad["error"]
    bad = resolve_model({"CAOSCARE_VOICE_BRIDGE_PROVIDER": "acme"})
    assert not bad["ok"] and "provider" in bad["error"]


def test_selection_is_logged(caplog):
    with caplog.at_level(logging.INFO):
        log_selection(resolve_model({"CAOSCARE_VOICE_BRIDGE_MODEL": "gpt-4.1"}))
        log_selection(resolve_model({"CAOSCARE_VOICE_BRIDGE_MODEL": "nope"}))
    text = caplog.text
    assert "voice bridge model: openai/gpt-4.1" in text and "voice bridge disabled" in text


def test_misconfigured_model_disables_bridge_turns():
    """A bad model name makes the bridge answer 503 with the reason; it does
    not fall back to another model."""
    code = ("import routes.voice_bridge as vb; from fastapi import HTTPException\n"
            "import asyncio\n"
            "try:\n"
            "    asyncio.run(vb.voice_bridge_turn(vb.VoiceBridgeTurn(text='hi', device_id='d'), 'Bearer t'))\n"
            "except HTTPException as e:\n"
            "    print(e.status_code, e.detail)\n")
    env = {**os.environ, "CAOSCARE_VOICE_BRIDGE_MODEL": "gpt-3.5-turbo", "CAOSCARE_VOICE_BRIDGE_TOKEN": "t"}
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                         env=env, text=True, capture_output=True, timeout=60)
    assert out.stdout.startswith("503 unsupported voice bridge model"), out.stdout + out.stderr


def test_bind_default_is_loopback():
    assert resolve_bind({}) == (DEFAULT_HOST, DEFAULT_PORT) == ("127.0.0.1", 8000)


def test_bind_allows_ha_vm_bridge_address():
    assert resolve_bind({"CAOSCARE_BIND_HOST": "192.168.122.1", "CAOSCARE_BIND_PORT": "8092"}) == ("192.168.122.1", 8092)
    assert "::1" in ALLOWED_HOSTS


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.151", "10.0.0.5", "localhost", "caoscare.local", ""])
def test_bind_refuses_wider_or_unknown_hosts(host):
    if host == "":
        assert resolve_bind({"CAOSCARE_BIND_HOST": host})[0] == "127.0.0.1"  # blank = default
        return
    with pytest.raises(ValueError):
        resolve_bind({"CAOSCARE_BIND_HOST": host})


@pytest.mark.parametrize("port", ["80", "0", "70000", "abc", "-1"])
def test_bind_refuses_bad_ports(port):
    with pytest.raises(ValueError):
        resolve_bind({"CAOSCARE_BIND_PORT": port})


def test_serve_refuses_to_start_on_wide_bind():
    out = subprocess.run([sys.executable, "serve.py"], cwd=Path(__file__).resolve().parents[1],
                         env={**os.environ, "CAOSCARE_BIND_HOST": "0.0.0.0"},
                         text=True, capture_output=True, timeout=30)
    assert out.returncode != 0 and "refusing to start" in out.stderr
