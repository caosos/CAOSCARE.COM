"""Real Mongo regression checks, isolated from the running care database.

Runs in a child process so Motor/env state cannot leak between test files.
Evidence is retained in the printed caos_level1_test_* database; no real
resident, device, lease, or receipt is modified and no voice API is called.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def test_level1_concurrency_and_room_isolation():
    env = {**os.environ, "DB_NAME": f"caos_level1_test_{uuid.uuid4().hex[:12]}"}
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--isolated"],
        env=env, text=True, capture_output=True, timeout=60,
    )
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr


async def run_isolated():
    assert os.environ.get("DB_NAME", "").startswith("caos_level1_test_")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from deps import db
    from routes.resident_activation import record_resident_activation
    from routes.kiosks import active_emergency_for_kiosk
    from routes.realtime_room_lease import claim_or_reuse_room_lease, release

    async def press(resident="resident_a", room="room_a", source="kiosk_button"):
        return await record_resident_activation(resident, room, source)

    results = await asyncio.gather(*(press() for _ in range(24)))
    assert len({r["alert_id"] for r in results}) == 1
    event_id = results[0]["alert_id"]
    doc = await db.alerts.find_one({"alert_id": event_id})
    assert doc["press_count"] == len(doc["presses"]) == 24
    assert await db.receipts.count_documents({"related_object_id": event_id}) == 1
    assert await db.alerts.count_documents({"resident_id": "resident_a", "status": "active"}) == 1

    # A different mapped source stays on the event; dismissal/release do
    # not close it. Resolving is the boundary for opening a new event.
    await db.alerts.update_one({"alert_id": event_id}, {"$set": {"activation_consumed_at": "test-dismissed"}})
    again = await press(source="rf_pendant")
    assert again["alert_id"] == event_id and again["activation_consumed_at"] is None
    await db.alerts.update_one({"alert_id": event_id}, {"$set": {"status": "resolved"}})
    fresh = await asyncio.gather(*(press() for _ in range(12)))
    assert len({r["alert_id"] for r in fresh}) == 1
    assert fresh[0]["alert_id"] != event_id
    newest = await db.alerts.find_one({"alert_id": fresh[0]["alert_id"]})
    assert newest["press_count"] == len(newest["presses"]) == 12

    # Existing duplicate historical events must remain intact. Only the
    # latest open event is adopted; new presses must not create a third.
    for i in range(2):
        await db.alerts.insert_one({"alert_id": f"legacy_{i}", "resident_id": "legacy",
                                    "room": "legacy_room", "status": "active",
                                    "created_at": f"2026-09-0{i+1}", "press_count": 1})
    legacy = await asyncio.gather(*(press("legacy", "legacy_room") for _ in range(12)))
    assert {r["alert_id"] for r in legacy} == {"legacy_1"}
    assert await db.alerts.count_documents({"resident_id": "legacy"}) == 2
    assert (await db.alerts.find_one({"alert_id": "legacy_0"}))["press_count"] == 1

    await db.alerts.update_one({"alert_id": newest["alert_id"]}, {"$set": {"auto_voice": True, "zone": "shared"}})
    for kid, room, zone, central in [
        ("own", "room_a", "shared", False),
        ("foreign", "room_b", "shared", False),
        ("unassigned", None, None, False),
        ("zone_only", None, "shared", False),
        ("central", None, None, True),
    ]:
        await db.kiosks.insert_one({"kiosk_id": kid, "room": room, "zone": zone, "is_central": central})
    assert (await active_emergency_for_kiosk("own"))["alert"]["alert_id"] == newest["alert_id"]
    assert (await active_emergency_for_kiosk("foreign"))["alert"] is None
    assert (await active_emergency_for_kiosk("unassigned"))["alert"] is None
    assert (await active_emergency_for_kiosk("zone_only"))["alert"]
    assert (await active_emergency_for_kiosk("central"))["alert"]
    await db.alerts.update_one({"alert_id": newest["alert_id"]}, {"$set": {"zone": None}})
    await db.kiosks.insert_one({"kiosk_id": "null_zone", "room": "other_room", "zone": None})
    assert (await active_emergency_for_kiosk("null_zone"))["alert"] is None

    claims = await asyncio.gather(*(
        claim_or_reuse_room_lease("lease_room", None, None, "test", f"session_{i}")
        for i in range(12)
    ))
    assert sum(r["claimed"] for r in claims) == 1
    winner = next(r["session_id"] for r in claims if r["claimed"])
    assert not (await release("lease_room", {"session_id": "stale"}))["ok"]
    # Preserve the ownership proof before exercising release's existing
    # deletion behavior. This is test evidence, not a production fix.
    await db.break_test_evidence.insert_one({"claims": claims, "winner": winner})
    assert (await release("lease_room", {"session_id": winner}))["ok"]
    assert (await db.alerts.find_one({"alert_id": newest["alert_id"]}))["status"] == "active"
    print(json.dumps({"database": db.name, "concurrent_presses": 24,
                      "concurrent_open_events": 1, "room_isolation": "passed",
                      "legacy_history": "preserved", "lease_winners": 1}))


if __name__ == "__main__":
    asyncio.run(run_isolated())
