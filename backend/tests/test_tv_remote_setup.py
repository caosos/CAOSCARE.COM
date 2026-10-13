from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest
from fastapi import HTTPException

from routes import tv_remote_setup as setup


def body(**values):
    base = {"phase": "start", "resident_id": "res1", "session_id": "sid1"}
    return setup.SetupInput(**{**base, **values})


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(setup, "find_live_session", AsyncMock(return_value={"room": "214"}))
    monkeypatch.setattr(setup, "_tv", AsyncMock(return_value={
        "device_id": "tv1", "room": "214", "kind": "tv", "label": "Room 214 TV",
        "protocol": "mock", "endpoint": "esphome.puck", "capabilities": ["power", "volume_step"],
    }))
    monkeypatch.setattr(setup, "_receipt", AsyncMock(return_value={"receipt_id": "rcpt1"}))
    return monkeypatch


def run(coro):
    return asyncio.run(coro)


def test_unknown_brand_changes_nothing(fake, monkeypatch):
    inserts = AsyncMock()
    monkeypatch.setattr(setup, "db", SimpleNamespace(tv_remote_setups=SimpleNamespace(insert_one=inserts)))
    result = run(setup.tv_remote_setup(body(vendor="unknown")))
    assert result["ok"] is False and "did not change" in result["message"]
    inserts.assert_not_awaited()


def test_test_requires_clear_permission_and_suspect_turn_never_sends(fake, monkeypatch):
    pending = {"setup_id": "s1", "resident_id": "res1", "session_id": "sid1", "room": "214",
               "device_id": "tv1", "candidate_id": "sony_sirc12", "state": "candidate_ready"}
    monkeypatch.setattr(setup, "db", SimpleNamespace(tv_remote_setups=SimpleNamespace(
        find_one=AsyncMock(return_value=pending), update_one=AsyncMock())))
    send = AsyncMock()
    monkeypatch.setattr(setup, "execute_ir_blaster", send)
    with pytest.raises(HTTPException) as denied:
        run(setup.tv_remote_setup(body(phase="test", setup_id="s1", confirmation_text="maybe")))
    assert denied.value.status_code == 409
    with pytest.raises(HTTPException):
        run(setup.tv_remote_setup(body(phase="test", setup_id="s1", confirmation_text="yes", turn_suspect=True)))
    send.assert_not_awaited()


def test_confirmed_exact_test_is_restored_then_registry_saved(fake, monkeypatch):
    pending = {"setup_id": "s1", "resident_id": "res1", "session_id": "sid1", "room": "214",
               "device_id": "tv1", "candidate_id": "sony_sirc12", "state": "test_sent_unverified",
               "vendor": "Sony", "model": "Bravia"}
    update_setup = AsyncMock()
    update_device = AsyncMock()
    after = {"device_id": "tv1", "room": "214", "kind": "tv", "protocol": "ir_blaster",
             "ir_codeset": "sony_sirc12", "vendor": "Sony", "model": "Bravia"}
    monkeypatch.setattr(setup, "db", SimpleNamespace(
        tv_remote_setups=SimpleNamespace(find_one=AsyncMock(return_value=pending), update_one=update_setup),
        smart_devices=SimpleNamespace(update_one=update_device, find_one=AsyncMock(return_value=after))))
    send = AsyncMock(return_value={"detail": "sent", "verified": False})
    registry = AsyncMock(return_value={"receipt_id": "registry1"})
    monkeypatch.setattr(setup, "execute_ir_blaster", send)
    monkeypatch.setattr(setup, "record_device_change", registry)
    result = run(setup.tv_remote_setup(body(phase="confirm", setup_id="s1", worked=True,
                                           confirmation_text="Yes, that worked")))
    assert result["ok"] and result["receipt_id"] == "registry1"
    assert send.await_args.args[2] == 1  # restore exactly the one-step test
    update_device.assert_awaited_once()
    registry.assert_awaited_once()


def test_clear_no_rejects_candidate_without_registry_write(fake, monkeypatch):
    pending = {"setup_id": "s1", "resident_id": "res1", "session_id": "sid1", "room": "214",
               "device_id": "tv1", "candidate_id": "sony_sirc12", "state": "test_sent_unverified",
               "vendor": "Sony", "model": "Bravia"}
    monkeypatch.setattr(setup, "db", SimpleNamespace(tv_remote_setups=SimpleNamespace(
        find_one=AsyncMock(return_value=pending), update_one=AsyncMock())))
    monkeypatch.setattr(setup, "execute_ir_blaster", AsyncMock(return_value={"detail": "sent"}))
    registry = AsyncMock()
    monkeypatch.setattr(setup, "record_device_change", registry)
    result = run(setup.tv_remote_setup(body(phase="confirm", setup_id="s1", worked=False,
                                           confirmation_text="No, nothing happened")))
    assert result["ok"] and "did not save" in result["message"]
    registry.assert_not_awaited()
