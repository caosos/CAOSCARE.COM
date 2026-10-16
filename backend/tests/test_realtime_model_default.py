"""Owner cost decision 2026-10-15: ordinary live conversation defaults to the
inexpensive Realtime mini and never silently falls back to the full model; the
provider-reported model is recorded per session as runtime evidence."""
import asyncio
import importlib
import json
import os
import types
import uuid

import pytest

from deps import db
from routes import realtime as rt
from routes import realtime_resident_session as rrs

TAG = f"rm{uuid.uuid4().hex[:8]}"


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


def test_default_and_empty_env_resolve_to_mini(monkeypatch):
    src = open(rt.__file__).read()
    assert 'DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1-mini"' in src
    monkeypatch.delenv("OPENAI_REALTIME_MODEL", raising=False)
    assert (os.environ.get("OPENAI_REALTIME_MODEL", rt.DEFAULT_REALTIME_MODEL).strip() or rt.DEFAULT_REALTIME_MODEL) == "gpt-realtime-2.1-mini"
    monkeypatch.setenv("OPENAI_REALTIME_MODEL", "   ")
    assert (os.environ.get("OPENAI_REALTIME_MODEL", rt.DEFAULT_REALTIME_MODEL).strip() or rt.DEFAULT_REALTIME_MODEL) == "gpt-realtime-2.1-mini"
    assert "gpt-realtime\"" not in src.split("DEFAULT_REALTIME_MODEL")[0]   # no full-model literal left as a default


def test_every_realtime_session_path_uses_one_constant():
    import inspect
    from routes import phone_aria
    assert "OPENAI_REALTIME_MODEL" in inspect.getsource(phone_aria)        # SIP bridge
    assert "OPENAI_REALTIME_MODEL" in inspect.getsource(rrs._mint)         # resident rooms
    assert "OPENAI_REALTIME_MODEL" in inspect.getsource(rt.create_aria_session)   # owner /aria
    import glob
    for f in glob.glob(os.path.join(os.path.dirname(rt.__file__), "*.py")):
        text = open(f).read()
        assert '"gpt-realtime-2.1"' not in text and '"gpt-realtime-2025' not in text, f   # no hard-coded full model anywhere


class FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *e): return False
    async def post(self, url, headers=None, json=None, **kw):
        FakeClient.last = json
        class R:
            status_code = 200; text = ""
            @staticmethod
            def json(): return {"value": "ek_fake", "expires_at": 0, "session": {"model": "gpt-realtime-2.1-mini", "audio": {"output": {"voice": json["session"]["audio"]["output"]["voice"]}}}}
        return R()


def test_resident_mint_records_provider_model(monkeypatch):
    monkeypatch.setattr(rrs, "httpx", types.SimpleNamespace(AsyncClient=FakeClient))
    monkeypatch.setattr(rrs, "_require_openai_key", lambda: "sk-test-not-real")
    room, sid = f"R{TAG}", f"rt_{TAG}"
    try:
        r = run(rrs.create_resident_session({"room": room, "kiosk_id": f"kio_{TAG}", "resident_id": f"res_{TAG}", "session_id": sid, "trigger_source": "manual_kiosk"}))
        body = json.loads(r.body)
        assert FakeClient.last["session"]["model"] == rrs.OPENAI_REALTIME_MODEL
        assert body["_caos"]["diagnostics"]["provider_model"] == "gpt-realtime-2.1-mini"
        ev = run(db.activation_events.find_one({"event": "session_provider_model", "session_id": sid}, {"_id": 0}))
        assert ev and ev["data"]["provider_model"] == "gpt-realtime-2.1-mini" and ev["data"]["requested_model"] == rrs.OPENAI_REALTIME_MODEL
    finally:
        run(db.resident_aria_leases.delete_many({"room": room}))
        run(db.activation_events.delete_many({"session_id": sid}))
