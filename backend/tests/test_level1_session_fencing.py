"""Isolated real-Mongo RF burst, activation fence, and lease evidence tests.

No live services, real residents, or provider calls. Test DB is retained.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def test_rf_burst_and_session_fences():
    env = {**os.environ, "DB_NAME": f"caos_level1_test_{uuid.uuid4().hex[:12]}"}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"],
                       env=env, capture_output=True, text=True, timeout=60)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


async def run():
    assert os.environ["DB_NAME"].startswith("caos_level1_test_")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from deps import db
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from routes import rf, realtime_room_lease, alert_lifecycle_events
    from routes.resident_activation import record_resident_activation
    from routes.resident_session_binding import validate_activation
    from datetime import datetime, timedelta, timezone
    app = FastAPI()
    for module in (rf, realtime_room_lease, alert_lifecycle_events):
        app.include_router(module.router)
    await db.kiosks.insert_one({"kiosk_id": "kiosk", "room": "testroom", "rf_seq": 0})
    await db.rf_devices.insert_one({"rf_device_id": "pendant", "resident_id": "resident", "room": "testroom",
                                    "enabled": True, "fingerprint": {"frequency_hz": 319500000,
                                    "bit_pattern_hex": "aabbccdd11"}, "match_threshold": 0.85})
    start = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        async def frame(seq, seconds):
            r = await c.post('/rf/event', json={"kiosk_id": "kiosk", "sequence": seq,
                "captured_at": (start + timedelta(seconds=seconds)).isoformat(),
                "fingerprint": {"frequency_hz": 319500000, "modulation": "OOK",
                                "bit_pattern_hex": "aabbccdd11", "bit_length": 40, "rssi": -50}})
            r.raise_for_status()
            return r.json()
        frames = [await frame(i + 1, i * .524) for i in range(8)]
        aid = frames[0]['alert_id']
        assert {r['alert_id'] for r in frames} == {aid}
        assert sum(r['press_counted'] for r in frames) == 1
        a = await db.alerts.find_one({'alert_id': aid})
        assert a['press_count'] == len(a['presses']) == 1
        assert await db.rf_events.count_documents({'alert_id': aid}) == 8
        context = {'room': 'testroom', 'resident_id': 'resident', 'kiosk_id': 'kiosk',
                   'alert_id': aid, 'activation_id': a['activation_id'], 'session_id': 'session_a'}
        r = await c.post('/realtime/room/testroom/activate', json=context)
        assert r.json()['claimed']
        # Real second burst during this session, not duplicate frames.
        await frame(9, 10)
        a2 = await db.alerts.find_one({'alert_id': aid})
        assert a2['press_count'] == 2 and a2['activation_id'] == a['activation_id']
        await c.post('/realtime/room/testroom/release', json={'session_id': 'session_a'})
        assert (await validate_activation(context))['alert_id'] == aid
        # Recovery owns same event/cycle but a different session.
        recovered = {**context, 'session_id': 'session_b'}
        assert (await c.post('/realtime/room/testroom/activate', json=recovered)).json()['claimed']
        old = await c.post(f'/alerts/{aid}/aria-event', json={**context, 'event': 'dismissed'})
        assert old.status_code == 409
        assert (await db.alerts.find_one({'alert_id': aid}))['activation_consumed_at'] is None
        ended = await c.post(f'/alerts/{aid}/aria-event', json={**recovered, 'event': 'dismissed'})
        assert ended.status_code == 200
        assert ended.json()['status'] == 'active'
        # Delayed duplicate frame after dismissal must not rearm.
        await frame(10, 10.5)
        assert (await db.alerts.find_one({'alert_id': aid}))['activation_consumed_at'] is not None
        await c.post('/realtime/room/testroom/release', json={'session_id': 'session_b'})
        stale = await c.post('/realtime/room/testroom/activate', json=context)
        assert stale.status_code == 409
        await frame(11, 20)
        new = await db.alerts.find_one({'alert_id': aid})
        assert new['activation_id'] != a['activation_id'] and new['press_count'] == 3
        late = await c.post(f'/alerts/{aid}/aria-event', json={**recovered, 'event': 'dismissed'})
        assert late.status_code == 409
        assert (await db.alerts.find_one({'alert_id': aid}))['activation_consumed_at'] is None
        # A wrong room must not claim/mint against this resident event.
        wrong = await c.post('/realtime/room/other/activate', json={**context, 'activation_id': new['activation_id']})
        assert wrong.status_code == 409
        evidence = await db.resident_aria_lease_events.find({}).to_list(20)
        assert [r['event'] for r in evidence].count('claimed') == 2
        assert [r['event'] for r in evidence].count('released') == 2
        # Multiple in-flight copies of the same logical press count once.
        duplicate = await asyncio.gather(*(record_resident_activation('parallel', 'parallel_room', 'rf_pendant',
            press_id='one_burst') for _ in range(12)))
        assert len({d['alert_id'] for d in duplicate}) == 1
        assert (await db.alerts.find_one({'resident_id': 'parallel'}))['press_count'] == 1
        assert await db.rf_events.count_documents({}) == 11
        # Provider/setup failure must free its claim without consuming the
        # event. No provider request occurs: only the mint boundary is fake.
        from routes import realtime_resident_session as sessions
        from fastapi import HTTPException
        calls = []
        async def fail_mint(payload, lease):
            calls.append(payload["session_id"])
            raise HTTPException(502, "simulated setup failure")
        sessions._mint = fail_mint
        try:
            await sessions.create_resident_session({**context, "activation_id": new['activation_id'],
                                                   "session_id": "failed_setup"})
            assert False, "setup must fail"
        except HTTPException as exc:
            assert exc.status_code == 502
        assert await db.resident_aria_leases.find_one({'room': 'testroom'}) is None
        assert (await db.alerts.find_one({'alert_id': aid}))['activation_consumed_at'] is None
        try:
            await sessions.create_resident_session(context)
            assert False, "stale cycle must fail before mint"
        except HTTPException as exc:
            assert exc.status_code == 409
        assert calls == ['failed_setup']
    print(json.dumps({'database': db.name, 'burst_frames_preserved': 11,
                      'counted_bursts': 3, 'stale_callbacks': 'rejected', 'lease_evidence': len(evidence)}))


if __name__ == '__main__':
    asyncio.run(run())
