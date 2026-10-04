"""Room-targeted announcements (Voice PE slice 1): routing, authorization,
idempotency, truthful playback states and receipt linkage.

Runs only against a throwaway database (DB_NAME must start with
caos_ann_test) with fake providers and a mocked Home Assistant HTTP
transport - no live Home Assistant, no hardware, no external code.
"""
import ast
import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.skipif(not os.environ.get("DB_NAME", "").startswith("caos_ann_test"),
                                reason="needs a throwaway caos_ann_test* database")

LOOP = asyncio.new_event_loop()


def run(coro):
    return LOOP.run_until_complete(coro)


class FakeProvider:
    name = "fake"
    simulated = True

    def __init__(self, result=None, delay=0.0):
        self.calls = []
        self.result, self.delay = result, delay

    async def announce(self, target, message, *, preannounce, timeout_s):
        from announcement_providers import ProviderResult
        self.calls.append((target, message))
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.result or ProviderResult(True, "provider_reported_finished", started=True,
                                             finished=True, request={"t": target}, response={"ok": 1})


ADMIN = {"user_id": "u_admin", "role": "admin", "name": "Admin"}
MAINT = {"user_id": "u_maint", "role": "staff", "department": "maintenance", "name": "Maint"}
HOUSE = {"user_id": "u_house", "role": "staff", "department": "housekeeping", "name": "House"}
FAMILY = {"user_id": "u_fam", "role": "family", "name": "Family"}


@pytest.fixture(scope="module", autouse=True)
def seed():
    from deps import db
    from routes.room_announcements import ensure_indexes

    async def go():
        await db.client.drop_database(os.environ["DB_NAME"])
        await ensure_indexes()
        await db.kiosks.insert_many([
            {"kiosk_id": "k1", "name": "T1", "room": "T1", "zone": "z", "facility_id": "F1",
             "voice_device_ids": ["dev_t1", "assist_satellite.t1"]},
            {"kiosk_id": "k2", "name": "T2", "room": "T2", "zone": "z", "facility_id": "F1",
             "voice_device_ids": ["assist_satellite.t2"]},
            {"kiosk_id": "k3", "name": "T3", "room": "T3", "zone": "z", "facility_id": "F2",
             "voice_device_ids": ["assist_satellite.t3"]},
            {"kiosk_id": "k4", "name": "T4", "room": "T4", "zone": "z", "facility_id": "F1",
             "voice_device_ids": []}])
        await db.residents.insert_many([{"resident_id": f"r{i}", "name": f"R{i}", "room": f"T{i}"}
                                        for i in (1, 2, 3, 4)])
        await db.staff_tasks.insert_many([
            {"task_id": "task_m1", "room": "T1", "resident_id": "r1", "category": "maintenance",
             "visibility_role": "maintenance", "status": "in_progress"},
            {"task_id": "task_m2", "room": "T2", "resident_id": "r2", "category": "maintenance",
             "visibility_role": "maintenance", "status": "pending"}])
    run(go())
    yield
    from deps import db as d
    run(d.client.drop_database(os.environ["DB_NAME"]))


def req(**kw):
    from models_announcements import RoomAnnouncementRequest
    base = dict(community_id="F1", room="T1", message="Maintenance is on the way to your sink.",
                purpose="request_update", origin_type="task", origin_id="task_m1")
    base.update(kw)
    return RoomAnnouncementRequest(**base)


def go(r, user=None, provider=None, actor=None):
    from routes.actor_context import actor_from_user
    from routes.room_announcements import announce
    return run(announce(r, actor=actor or actor_from_user(user), user=user, provider=provider))


def receipts(ann_id):
    from deps import db
    return run(db.receipts.find({"related_object_id": ann_id}, {"_id": 0}).sort("created_at", 1)
               .to_list(100))


def chain(ann_id):
    return [r for r in receipts(ann_id) if r["action_type"] != "room_announcement_duplicate_ignored"]


def test_authorized_request_reaches_the_correct_room_adapter():
    p = FakeProvider()
    ann = go(req(idempotency_key="k-auth"), ADMIN, p)
    assert p.calls == [("assist_satellite.t1", "Maintenance is on the way to your sink.")]
    assert ann["kiosk_id"] == "k1" and ann["resident_id"] == "r1"
    assert ann["outcome"] == "played" and ann["state"] == "receipt_recorded"
    states = [h["state"] for h in ann["history"]]
    assert states == ["requested", "authorized", "queued", "sent_to_provider", "playback_started",
                      "playback_finished", "receipt_recorded"]
    assert ann["authorization"]["quiet_hours_policy"] == "none_defined"
    ok = go(req(idempotency_key="k-dept"), MAINT, FakeProvider())   # own department's request
    assert ok["outcome"] == "played" and ok["authority"] == "acts_for:maintenance"


@pytest.mark.parametrize("user,kw,reason", [
    (HOUSE, {}, "not_authorized"),
    (FAMILY, {"origin_type": "staff_direct", "origin_id": None}, "not_authorized"),
    (MAINT, {"origin_type": "staff_direct", "origin_id": None}, "not_authorized"),
    (ADMIN, {"priority": "emergency"}, "no_emergency_announcement_policy"),
    (ADMIN, {"room": "T4"}, "room_disconnected"),
    (ADMIN, {"room": "T1", "origin_id": "task_m2"}, "origin_room_mismatch"),
])
def test_unauthorized_or_unroutable_request_is_rejected_with_a_receipt(user, kw, reason):
    p = FakeProvider()
    ann = go(req(idempotency_key=f"rej-{reason}-{user['user_id']}", **kw), user, p)
    assert p.calls == [] and ann["outcome"] == "rejected"
    rs = chain(ann["announcement_id"])
    assert [r["action_type"] for r in rs] == ["room_announcement_requested", "room_announcement_rejected"]
    assert rs[-1]["failure_reason"] == reason and rs[-1]["status"] == "failed"


def test_anonymous_http_caller_is_rejected_with_a_receipt():
    from fastapi import FastAPI
    from routes import room_announcements as ra

    app = FastAPI()
    app.include_router(ra.router, prefix="/api")

    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/room-announcements", json=req(idempotency_key="anon").model_dump(
                mode="json", exclude_none=True))
    resp = run(call())
    assert resp.status_code == 401
    body = resp.json()
    assert body["outcome"] == "rejected" and body["failure_reason"] == "unauthenticated"
    assert chain(body["announcement_id"])[0]["result_label"] == "unverified"


def test_wrong_community_is_rejected():
    p = FakeProvider()
    ann = go(req(community_id="F2", idempotency_key="xc"), ADMIN, p)
    assert p.calls == [] and ann["failure_reason"] == "cross_community"
    ann = go(req(community_id="F1", room="T3", origin_type="staff_direct", origin_id=None,
                 idempotency_key="xc2"), ADMIN, p)
    assert p.calls == [] and ann["failure_reason"] == "cross_community"


def test_duplicate_request_does_not_play_twice():
    from routes.actor_context import actor_from_user
    from routes.room_announcements import announce
    p = FakeProvider(delay=0.05)

    async def many():
        return await asyncio.gather(*[announce(req(idempotency_key="dup"), actor=actor_from_user(ADMIN),
                                               user=ADMIN, provider=p) for _ in range(5)])
    out = run(many())
    assert len(p.calls) == 1
    assert sum(1 for a in out if a.get("duplicate")) == 4
    again = go(req(idempotency_key="dup"), ADMIN, p)          # later retry
    assert again["duplicate"] and len(p.calls) == 1
    dups = [r for r in receipts(again["announcement_id"])
            if r["action_type"] == "room_announcement_duplicate_ignored"]
    assert len(dups) == 5 and all(r["correlation_id"] == again["correlation_id"] for r in dups)
    staff_direct = req(origin_type="staff_direct", origin_id=None)   # derived key (no caller key)
    first, second = go(staff_direct, ADMIN, p), go(staff_direct, ADMIN, p)
    assert second["duplicate"] and second["announcement_id"] == first["announcement_id"]
    assert len(p.calls) == 2


def test_provider_timeout_remains_failed_unverified():
    from announcement_providers import ProviderResult
    p = FakeProvider(ProviderResult(False, "none", failure="provider_timeout", timed_out=True))
    ann = go(req(idempotency_key="to"), ADMIN, p)
    assert ann["outcome"] == "unverified_timeout" and ann["failure_reason"] == "provider_timeout"
    last = chain(ann["announcement_id"])[-1]
    assert last["action_type"] == "room_announcement_failed" and last["result_label"] == "unverified"
    assert "playback_finished" not in [h["state"] for h in ann["history"]]


def test_provider_acceptance_is_not_completed_playback():
    from announcement_providers import ProviderResult
    p = FakeProvider(ProviderResult(True, "provider_accepted", request={}, response={"status_code": 200}))
    ann = go(req(idempotency_key="acc"), ADMIN, p)
    assert ann["outcome"] == "unconfirmed" and ann["evidence_level"] == "provider_accepted"
    rs = chain(ann["announcement_id"])
    assert not any(r["action_type"] == "room_announcement_playback_finished" for r in rs)
    assert all(r["status"] != "completed" for r in rs)
    assert rs[-1]["result_label"] == "unverified" and rs[-1]["status"] == "acknowledged"


def _ha(handler, monkeypatch):
    import announcement_providers
    import device_adapters
    monkeypatch.setattr(device_adapters, "HA_BASE_URL", "http://ha.test")
    monkeypatch.setattr(device_adapters, "HA_TOKEN", "test-token")
    real = httpx.AsyncClient
    monkeypatch.setattr(announcement_providers.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return announcement_providers.HomeAssistantAssistSatellite()


def test_ha_playback_evidence_produces_the_correct_receipt(monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.method == "GET":
            return httpx.Response(200, json={"entity_id": "assist_satellite.t1", "state": "idle"})
        return httpx.Response(200, json=[
            {"entity_id": "assist_satellite.t2", "state": "responding"},   # other room: ignored
            {"entity_id": "assist_satellite.t1", "state": "responding"},
            {"entity_id": "assist_satellite.t1", "state": "idle"}])
    ann = go(req(idempotency_key="ha-ok"), ADMIN, _ha(handler, monkeypatch))
    assert ann["outcome"] == "played" and ann["evidence_level"] == "provider_reported_finished"
    assert seen[-1][1] == "/api/services/assist_satellite/announce" and seen[-1][2] == "Bearer test-token"
    fin = [r for r in chain(ann["announcement_id"]) if r["action_type"] == "room_announcement_playback_finished"]
    assert len(fin) == 1 and fin[0]["status"] == "completed" and fin[0]["result_label"] == "verified"
    assert "not an acoustic confirmation" in fin[0]["evidence"]["limitation"]


@pytest.mark.parametrize("handler,outcome,failure", [
    (lambda r: httpx.Response(200, json={"state": "unavailable"}), "failed", "device_unavailable"),
    (lambda r: httpx.Response(200, json={"state": "idle"}) if r.method == "GET"
     else httpx.Response(500, json={"message": "Satellite is busy"}), "failed", "satellite_busy"),
    (lambda r: httpx.Response(200, json={"state": "idle"}) if r.method == "GET"
     else httpx.Response(200, json=[]), "unconfirmed", None),
    (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("t")), "unverified_timeout", "provider_timeout"),
])
def test_ha_provider_failure_states(monkeypatch, handler, outcome, failure):
    ann = go(req(idempotency_key=f"ha-{outcome}-{failure}"), ADMIN, _ha(handler, monkeypatch))
    assert ann["outcome"] == outcome and ann.get("failure_reason") == failure


def test_every_state_change_links_to_origin_and_no_receipt_is_orphaned():
    from deps import db
    anns = run(db.room_announcements.find({}, {"_id": 0}).to_list(500))
    assert anns
    for a in anns:
        rs = chain(a["announcement_id"])
        assert rs[0]["action_type"] == "room_announcement_requested"
        assert rs[0]["correlation_id"] == rs[0]["receipt_id"] and rs[0]["parent_receipt_id"] is None
        for prev, cur in zip(rs, rs[1:]):
            assert cur["correlation_id"] == rs[0]["receipt_id"]
            assert cur["parent_receipt_id"] == prev["receipt_id"]
        ids = {r["receipt_id"] for r in rs}
        assert {h["receipt_id"] for h in a["history"]} <= ids
        assert a["state"] == "receipt_recorded" and a["final_receipt_id"] in ids
        assert a["actor_id"] and a["actor_type"]
    ann_ids = {a["announcement_id"] for a in anns}
    all_rs = run(db.receipts.find({"related_object_type": "room_announcement"}, {"_id": 0}).to_list(2000))
    assert all_rs and all(r["related_object_id"] in ann_ids for r in all_rs)


def test_no_external_project_code_is_required():
    backend = Path(__file__).resolve().parents[1]
    allowed = {"dataclasses", "typing", "httpx", "device_adapters", "hashlib", "os", "datetime",
               "fastapi", "fastapi.encoders", "fastapi.responses", "pymongo.errors", "deps",
               "models", "models_announcements", "pydantic", "announcement_providers",
               "routes.actor_context", "routes.receipts", "routes.room_announcement_policy",
               "routes.task_lifecycle", "routes.realtime_facility", "routes.staff_scope"}
    for f in ("announcement_providers.py", "models_announcements.py",
              "routes/room_announcements.py", "routes/room_announcement_policy.py"):
        tree = ast.parse((backend / f).read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert mods <= allowed, (f, mods - allowed)
