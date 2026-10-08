"""Pilot 1 calling (Lane F): call lifecycle, Asterisk ARI event mapping, the
local dial-target endpoint, phone tools, the OpenAI SIP webhook and the
sideband loop - against an isolated real-Mongo database. No Asterisk, ATA,
SIP trunk or OpenAI account is contacted: OpenAI calls and the sideband
WebSocket are fakes, webhooks are signed with a fabricated secret.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_email_inbound import TEST_SECRET, _sign  # noqa: E402


def test_telephony_flow():
    env = {**os.environ, "DB_NAME": f"caos_telephony_test_{uuid.uuid4().hex[:10]}",
           "OPENAI_WEBHOOK_SECRET": TEST_SECRET, "CAOS_TELEPHONY_TOKEN": "local-test-token"}
    env.pop("RESEND_API_KEY", None)
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"],
                       env=env, capture_output=True, text=True, timeout=90)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


class FakeWS:
    def __init__(self, events):
        self.events, self.sent = events, []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for e in self.events:
            await asyncio.sleep(0)
            yield json.dumps(e)

    async def close(self):
        pass


async def run():
    assert os.environ["DB_NAME"].startswith("caos_telephony_test_")
    import httpx
    from deps import db
    from fastapi import FastAPI
    from routes import call_lifecycle as lc, asterisk_ari_events as ari, telephony_local, phone_aria
    from routes.phone_aria_tools import run_phone_tool
    from routes.phone_aria_sideband import run_sideband

    await db.phone_endpoints.insert_many([
        {"endpoint_id": "p1", "extension": "214", "kind": "room", "room": "214", "active": True, "created_at": "1"},
        {"endpoint_id": "p2", "extension": "200", "kind": "front_desk", "active": True, "created_at": "2"},
    ])
    await db.residents.insert_one({"resident_id": "res_t", "name": "Helen Test", "room": "214"})
    await db.departments.insert_many([{"slug": "maintenance", "label": "Maintenance", "active": True},
                                      {"slug": "administration", "label": "Administration", "active": True}])
    await db.family_contacts.insert_many([
        {"contact_id": "fam_ok", "resident_id": "res_t", "name": "Susan", "relationship": "daughter",
         "phone": "(501) 555-0123", "allow_calls": True, "notify_on": []},
        {"contact_id": "fam_no", "resident_id": "res_t", "name": "Bob", "phone": "5015550199",
         "allow_calls": False, "notify_on": []},
    ])

    # 1) Lifecycle only moves forward; outcome receipts are new rows.
    c = await lc.create_call("front_desk", target_extension="200", target_label="the front desk", room="214")
    for s in ("dialing", "ringing", "connected"):
        assert (await lc.advance(c["call_id"], s, source="asterisk"))["applied"]
    assert not (await lc.advance(c["call_id"], "ringing", source="asterisk"))["applied"]  # late event
    assert (await lc.advance(c["call_id"], "ended", source="asterisk", detail="Normal Clearing"))["applied"]
    done = await lc.get_call(c["call_id"])
    assert [h["state"] for h in done["history"]] == ["requested", "dialing", "ringing", "connected", "ended"]
    assert done["hangup_cause"] == "Normal Clearing" and done["connected_at"]
    kinds = sorted(r["action_type"] for r in await db.receipts.find({"related_object_id": c["call_id"]}).to_list(9))
    assert kinds == ["call.front_desk.connected", "call.front_desk.requested"]
    assert "Nobody has answered" in lc.spoken_call_state({**done, "state": "ringing"})

    # 2) ARI: dial 0 and 911 are recorded lazily from Asterisk events.
    chan = lambda cid, ext: {"channelvars": {"CAOS_CALL_ID": cid}, "caller": {"number": ext}}  # noqa: E731
    assert ari.interpret({"type": "Dial", "dialstatus": "BUSY", "caller": chan("x", "1")})[1:3] == ("unanswered", "busy")
    assert ari.interpret({"type": "Dial", "dialstatus": "ANSWER", "caller": {"channelvars": {}}}) is None
    await ari.handle_event({"type": "Dial", "dialstatus": "", "caller": chan("fd0-1", "214")})
    await ari.handle_event({"type": "Dial", "dialstatus": "NOANSWER", "caller": chan("fd0-1", "214")})
    fd = await lc.get_call("fd0-1")
    assert fd["kind"] == "front_desk" and fd["room"] == "214" and fd["resident_id"] == "res_t" and fd["state"] == "unanswered"
    await ari.handle_event({"type": "Dial", "dialstatus": "", "caller": chan("emg-1", "214")})
    assert (await lc.get_call("emg-1"))["kind"] == "emergency"
    assert await db.notifications.find_one({"related_object_id": "emg-1", "department": "administration"})
    assert await ari.handle_event({"type": "Dial", "dialstatus": "", "caller": chan("random-9", "214")}) is None

    # 3) Local dial-target: fail-closed, local only, one-time.
    app = FastAPI()
    app.include_router(telephony_local.router)
    app.include_router(phone_aria.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as h:
        hdr = {"x-caos-telephony-token": "local-test-token"}
        xfer = await lc.create_call("front_desk", with_token=True, target_extension="200", target_label="the front desk")
        assert (await h.get(f"/telephony/local/dial-target/{xfer['dial_token']}")).status_code == 403
        r = await h.get(f"/telephony/local/dial-target/{xfer['dial_token']}", headers=hdr)
        assert r.text == f"{xfer['call_id']}|PJSIP/200"
        assert (await h.get(f"/telephony/local/dial-target/{xfer['dial_token']}", headers=hdr)).text == ""
        fam = await lc.create_call("family", with_token=True, family_contact_id="fam_no", resident_id="res_t")
        assert (await h.get(f"/telephony/local/dial-target/{fam['dial_token']}", headers=hdr)).text == ""
        fam = await lc.create_call("family", with_token=True, family_contact_id="fam_ok", resident_id="res_t")
        assert (await h.get(f"/telephony/local/dial-target/{fam['dial_token']}", headers=hdr)).text.endswith("|PJSIP/+15015550123@trunk")

        # 4) Signed OpenAI webhook accepts a known Aria call, rejects others.
        posts = []

        async def fake_post(path, body):
            posts.append((path, body))
            return 200
        started = []

        async def fake_sideband(call):
            started.append(call["call_id"])
        phone_aria.openai_post = fake_post
        import routes.phone_aria_sideband as sb
        sb.run_sideband, real_sideband = fake_sideband, sb.run_sideband

        async def hook(payload):
            body = json.dumps(payload).encode()
            mid, ts = f"msg_{uuid.uuid4().hex[:6]}", str(int(time.time()))
            return await h.post("/telephony/openai/webhook", content=body, headers={
                "webhook-id": mid, "webhook-timestamp": ts, "webhook-signature": _sign(TEST_SECRET, mid, ts, body)})
        incoming = {"type": "realtime.call.incoming", "data": {"call_id": "rtc_1", "sip_headers": [
            {"name": "X-CAOS-Call-Id", "value": "aria-1"}, {"name": "X-CAOS-Extension", "value": "214"}]}}
        r = (await hook(incoming)).json()
        await asyncio.sleep(0)  # the sideband is a background task
        assert r["accepted"] and started == ["aria-1"], r
        path, body = posts[-1]
        assert path == "/realtime/calls/rtc_1/accept" and body["type"] == "realtime"
        assert "## On the telephone" in body["instructions"] and "Susan" in body["instructions"] and "Bob" not in body["instructions"]
        assert "dial 9 1 1" in body["instructions"]
        aria_call = await lc.get_call("aria-1")
        assert aria_call["room"] == "214" and aria_call["openai_call_id"] == "rtc_1"
        assert (await hook(incoming)).json().get("duplicate")
        stray = {"type": "realtime.call.incoming", "data": {"call_id": "rtc_2", "sip_headers": []}}
        assert (await hook(stray)).json()["rejected"] and posts[-1][0] == "/realtime/calls/rtc_2/reject"
        bad = await h.post("/telephony/openai/webhook", content=b"{}", headers={
            "webhook-id": "m", "webhook-timestamp": str(int(time.time())), "webhook-signature": "v1,nope"})
        assert bad.status_code == 401
        sb.run_sideband = real_sideband

    # 5) Tools: approved family only; end_call needs the resident's goodbye.
    posts.clear()
    out = await run_phone_tool("call_family_contact", {"contact_id": "fam_no"}, aria_call, "call bob", fake_post)
    assert out["output"]["ok"] is False
    out = await run_phone_tool("call_family_contact", {"contact_id": "fam_ok"}, aria_call, "call my daughter", fake_post)
    await out["after_speech"]()
    assert posts[-1][0] == "/realtime/calls/rtc_1/refer" and posts[-1][1]["target_uri"].startswith("sip:77")
    child = await db.call_sessions.find_one({"parent_call_id": "aria-1", "kind": "family"})
    assert child["target_label"] == "Susan (daughter)" and child["state"] == "requested"
    assert (await run_phone_tool("end_call", {}, aria_call, "what time is it", fake_post))["output"]["ok"] is False

    # 6) Sideband: transcripts persisted, request filed, hang-up after goodbye is spoken.
    ws = FakeWS([
        {"type": "input_audio_buffer.speech_stopped"},
        {"type": "conversation.item.input_audio_transcription.completed", "transcript": "My sink is leaking."},
        {"type": "response.function_call_arguments.done", "name": "request_staff_help", "call_id": "fc1",
         "arguments": json.dumps({"category": "maintenance", "summary": "sink is leaking"})},
        {"type": "response.output_audio_transcript.done", "transcript": "I've filed that for maintenance."},
        {"type": "conversation.item.input_audio_transcription.completed", "transcript": "Okay, goodbye."},
        {"type": "response.function_call_arguments.done", "name": "end_call", "call_id": "fc2", "arguments": "{}"},
        {"type": "response.done", "response": {"output": [{"type": "function_call"}]}},
        {"type": "response.done", "response": {"output": [{"type": "message"}]}},
    ])

    async def connect(_):
        return ws
    posts.clear()
    await real_sideband(aria_call, connect=connect, openai_post=fake_post)
    assert ws.sent[0]["type"] == "session.update" and ws.sent[1]["type"] == "response.create"
    outputs = [json.loads(m["item"]["output"]) for m in ws.sent if m["type"] == "conversation.item.create"]
    assert outputs[0]["ok"] and outputs[0]["filed"]
    task = await db.staff_tasks.find_one({"conversation_session_id": "phone_aria-1"})
    assert task and task["visibility_role"] == "maintenance" and task["resident_words"] == "My sink is leaking."
    turns = await db.conversations.find({"session_id": "phone_aria-1"}).to_list(10)
    assert {t["role"] for t in turns} == {"user", "assistant"}
    assert posts == [("/realtime/calls/rtc_1/hangup", {})]

    print(json.dumps({"database": db.name, "ok": True}))
    await db.client.drop_database(db.name)


if __name__ == "__main__":
    asyncio.run(run())
