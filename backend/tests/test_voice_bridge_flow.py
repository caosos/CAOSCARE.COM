"""Voice bridge end to end, isolated from the care database.

Runs the real /api/voice-bridge routes (FastAPI TestClient) in a child
process against a throwaway caos_vb_test_* database, with a scripted
stand-in for the language model. Simulates what Home Assistant sends after
speech-to-text; no audio, no HA, no OpenAI call, no real room touched.
"""
import os
from pathlib import Path
import subprocess
import sys
import uuid


def test_voice_bridge_flow():
    env = {**os.environ, "DB_NAME": f"caos_vb_test_{uuid.uuid4().hex[:12]}",
           "CAOSCARE_VOICE_BRIDGE_TOKEN": "test-bridge-token", "OPENAI_API_KEY": "",
           "CAOSCARE_VOICE_BRIDGE_BUDGET_S": "6"}
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"],
                            env=env, text=True, capture_output=True, timeout=120)
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- child ----

DEVICE = "ha_dev_voicepe_101"
TODAY_DINNER = "Roast chicken"


def fake_llm_factory(state):
    """Scripted model: tool calls keyed on the resident's latest words."""
    def call(name, args):
        state["n"] += 1
        return {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": f"c{state['n']}", "type": "function",
             "function": {"name": name, "arguments": __import__("json").dumps(args)}}]}}]}

    def say(text):
        return {"choices": [{"message": {"content": text}}]}

    def fake(path, payload, timeout=60):
        if state.get("mode") == "down":
            raise RuntimeError("provider unavailable")
        if state.get("mode") == "slow":
            import time
            time.sleep(timeout + 0.5)
            raise TimeoutError("read timed out")
        msgs = payload["messages"]
        last = msgs[-1]
        if last["role"] == "tool":
            body = last["content"]
            if state.get("mode") == "down_after_tool":
                raise RuntimeError("provider failed after tool")
            if '"items"' in body and TODAY_DINNER in body:
                return say(f"**Dinner** tonight is {TODAY_DINNER}.")
            if "Chair yoga" in body:
                return say("There's Chair yoga at 2:00 PM.")
            if "request created" in body or "already an open" in body:
                return say("I've sent that to the staff. It's on its way!")
            if '"found"' in body:
                return say("Your request is on file and waiting for a staff member.")
            return say("Okay.")
        user = next(m["content"] for m in reversed(msgs) if m["role"] == "user").lower()
        if "dinner" in user:
            return call("get_menu", {"meal_period": "dinner"})
        if "what time is that" in user:
            history = " ".join(m.get("content") or "" for m in msgs if m["role"] == "assistant")
            return say("Dinner is served at 5 PM." if TODAY_DINNER in history else "What do you mean?")
        if "activities" in user:
            return call("get_todays_schedule", {})
        if "sink" in user:
            return call("request_staff_help", {"category": "maintenance", "summary": "sink leaking"})
        if "nurse" in user or "help getting up" in user:
            return call("request_staff_help", {"category": "nursing", "summary": "needs help getting up",
                                               "priority": "high"})
        if "status" in user or "anyone" in user:
            return call("check_request_status", {})
        return say("I'm here.")
    return fake


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    assert os.environ["DB_NAME"].startswith("caos_vb_test_")
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient
    import routes.voice_bridge as vb
    from routes import voice_bridge_devices
    from routes.realtime_facility import today_facility_date

    state = {"n": 0}
    vb._post_openai = fake_llm_factory(state)
    app = FastAPI()
    api = APIRouter(prefix="/api")
    api.include_router(vb.router)
    api.include_router(voice_bridge_devices.router)
    app.include_router(api)
    from deps import require_admin
    app.dependency_overrides[require_admin] = lambda: {"user_id": "user_admin_t", "role": "admin", "name": "T Admin"}
    H = {"Authorization": "Bearer test-bridge-token"}

    with TestClient(app) as c:
        from deps import db

        def run(coro):
            return c.portal.call(lambda: coro)

        async def seed():
            from routes.voice_bridge_session import ensure_indexes
            await ensure_indexes()
            from routes.departments import seed_default_departments
            await seed_default_departments()
            today = today_facility_date()
            await db.facilities.insert_one({"facility_id": "fac_t", "name": "Test Community",
                                            "is_active": True, "created_at": "2026-01-01"})
            await db.kiosks.insert_many([
                {"kiosk_id": "kio_101", "name": "101", "room": "101", "zone": "w", "voice_device_ids": [DEVICE]},
                {"kiosk_id": "kio_102", "name": "102", "room": "102", "zone": "w", "voice_device_ids": ["ha_dev_102"]}])
            await db.residents.insert_many([
                {"resident_id": "res_101", "name": "Ada Test", "preferred_name": "Ada", "room": "101"},
                {"resident_id": "res_102", "name": "Bo Test", "preferred_name": "Bo", "room": "102"}])
            await db.menu_items.insert_one({"menu_id": "m1", "date": today, "meal_period": "dinner",
                                            "item_name": TODAY_DINNER, "status": "approved"})
            await db.schedule_items.insert_one({"schedule_id": "s1", "date": today, "time_label": "2:00 PM",
                                                "title": "Chair yoga", "category": "activity"})
        run(seed())

        def turn(text, conv="conv1", device=DEVICE, **kw):
            return c.post("/api/voice-bridge/turn", headers=H,
                          json={"text": text, "conversation_id": conv, "device_id": device, **kw})

        async def receipts(**q):
            return await db.receipts.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)

        # -- device/resident mapping; menu; continuity ------------------------
        r = turn("What's for dinner?").json()
        assert TODAY_DINNER in r["response_text"] and "**" not in r["response_text"], r
        assert r["continue_conversation"] is True and r["session_id"] == "vb_conv1"
        assert r["speech_format"] == "plain_text" and "audio" not in r  # text only; HA owns TTS
        r2 = turn("What time is that?").json()
        assert "5 PM" in r2["response_text"], r2  # history reached the model
        conv_turns = run(db.conversations.count_documents({"session_id": "vb_conv1", "resident_id": "res_101"}))
        assert conv_turns == 4
        print("OK menu, continuity, mapping (res_101 / room 101)")

        # -- receipts carry provenance and chain ------------------------------
        rs = run(receipts(related_object_id="vb_conv1"))
        assert [x["action_type"] for x in rs] == ["voice_turn", "voice_turn"]
        first, second = rs
        assert first["correlation_id"] == first["receipt_id"] and first["parent_receipt_id"] is None
        assert second["parent_receipt_id"] == first["receipt_id"]
        assert second["correlation_id"] == first["receipt_id"]
        ev = first["evidence"]
        assert ev["device_id"] == DEVICE and ev["kiosk_id"] == "kio_101" and ev["facility_id"] == "fac_t"
        assert ev["utterance"] == "What's for dinner?" and ev["tools"][0]["name"] == "get_menu"
        assert first["identity_basis"] == "unverified_room_claim" and first["result_label"] == "unverified"
        assert first["authority"] == f"registered_voice_device:{DEVICE}->kio_101"
        assert first["room"] == "101" and first["resident_id"] == "res_101"
        assert first["before_state"]["turn_count"] == 0 and first["after_state"]["turn_count"] == 1
        assert first["next_state"] == "awaiting_resident"
        print("OK turn receipts: provenance + chain")

        # -- activities --------------------------------------------------------
        r = turn("What activities are on today?", conv="conv2").json()
        assert "Chair yoga" in r["response_text"], r
        print("OK activities")

        # -- maintenance request, duplicate protection, arrival guard --------
        r = turn("My sink is leaking.", conv="conv3").json()
        assert "on its way" not in r["response_text"].lower(), r  # arrival-claim guard
        tasks = run(db.staff_tasks.find({"resident_id": "res_101"}, {"_id": 0}).to_list(50))
        assert len(tasks) == 1 and tasks[0]["category"] == "maintenance" and tasks[0]["room"] == "101", (r, tasks, run(db.realtime_diagnostics.find({"session_id": "vb_conv3"}, {"_id": 0, "meta": 1}).to_list(9)))
        assert tasks[0]["conversation_session_id"] == "vb_conv3"
        task_rc = run(receipts(related_object_id=tasks[0]["task_id"]))
        assert task_rc and task_rc[0]["authority"] == "registered_endpoint:kio_101"
        turn_rc = run(receipts(related_object_id="vb_conv3"))[-1]
        wo = turn_rc["evidence"]["workflow_objects"]
        assert wo[0]["id"] == tasks[0]["task_id"] and wo[0]["receipt_id"] == task_rc[0]["receipt_id"]
        # HA retry: identical utterance seconds later -> answered once
        d = turn("My sink is leaking.", conv="conv3").json()
        assert d.get("duplicate") is True and d["response_text"] == r["response_text"]
        assert run(db.staff_tasks.count_documents({"resident_id": "res_101"})) == 1
        assert run(receipts(related_object_id="vb_conv3"))[-1]["action_type"] == "voice_turn_duplicate_ignored"
        # a real repeat later (outside the retry window) joins the open request
        run(db.voice_bridge_sessions.update_one({"session_id": "vb_conv3"}, {"$set": {"last_turn_key": None}}))
        turn("My sink is leaking.", conv="conv3")
        t = run(db.staff_tasks.find({"resident_id": "res_101"}, {"_id": 0}).to_list(50))
        assert len(t) == 1 and t[0].get("re_request_count", 0) == 1
        print("OK maintenance request, duplicate protection, arrival guard")

        # -- nursing request + status follow-up --------------------------------
        r = turn("I need a nurse, I need help getting up.", conv="conv4").json()
        nurse = run(db.staff_tasks.find_one({"resident_id": "res_101", "category": "nursing"}, {"_id": 0}))
        assert nurse and nurse["priority"] == "high"
        r = turn("Is anyone coming? What's the status?", conv="conv4").json()
        assert "check_request_status" in r["tools_used"], r
        print("OK nursing request, status follow-up")

        # -- session ending phrases -------------------------------------------
        for i, phrase in enumerate(["That'll be all.", "That'll be all, Aria.", "Goodbye, Aria.",
                                    "I'm done.", "Thank you, goodbye."]):
            conv = f"end{i}"
            turn("What's for dinner?", conv=conv)
            calls_before = state["n"]
            tasks_before = run(db.staff_tasks.count_documents({}))
            e = turn(phrase, conv=conv).json()
            assert e["continue_conversation"] is False and e.get("session_ended") is True, (phrase, e)
            assert state["n"] == calls_before, phrase  # no model call
            assert run(db.staff_tasks.count_documents({})) == tasks_before  # no workflow action
            s = run(db.voice_bridge_sessions.find_one({"session_id": f"vb_{conv}"}))
            assert s["status"] == "closed" and s["closed_at"]
            end_rc = run(receipts(related_object_id=f"vb_{conv}"))[-1]
            assert end_rc["action_type"] == "voice_session_ended" and end_rc["next_state"] == "idle_wake"
            assert end_rc["evidence"]["ended_by"] == "resident_phrase"
            assert end_rc["evidence"]["device_id"] == DEVICE and end_rc["resident_id"] == "res_101"
        # not an ending: more words than a closing phrase
        n = turn("I'm done eating, can you tell me what's for dinner?", conv="end0b").json()
        assert n["continue_conversation"] is True
        # a later turn on a closed conversation opens a new session
        again = turn("What's for dinner?", conv="end0").json()
        assert again["session_id"] == "vb_end0-r2" and again["continue_conversation"] is True
        print("OK session-ending phrases (5), new session after close")

        # -- unknown device, cross-room conversation ---------------------------
        u = turn("What's for dinner?", conv="x1", device="ha_dev_unknown")
        assert u.status_code == 404
        ref = run(receipts(related_object_id="ha_dev_unknown"))
        assert ref and ref[0]["action_type"] == "voice_turn_refused" and ref[0]["status"] == "failed"
        hijack = turn("What's for dinner?", conv="conv1", device="ha_dev_102")
        assert hijack.status_code == 409
        assert c.post("/api/voice-bridge/turn", headers={"Authorization": "Bearer wrong"},
                      json={"text": "hi", "device_id": DEVICE}).status_code == 401
        missing = c.post("/api/voice-bridge/turn", headers=H, json={"text": "hi"})
        assert missing.status_code == 422
        print("OK unknown device + cross-room rejection with refusal receipts")

        # -- provider failure / timeout: spoken fallback, no orphan state ------
        tasks_before = run(db.staff_tasks.count_documents({}))
        state["mode"] = "down"
        f = turn("My sink is leaking again badly.", conv="fail1").json()
        assert "trouble" in f["response_text"] and f["continue_conversation"] is True
        frc = run(receipts(related_object_id="vb_fail1"))[-1]
        assert frc["status"] == "failed" and frc["result_label"] == "failed" and "unavailable" in frc["failure_reason"]
        assert run(db.staff_tasks.count_documents({})) == tasks_before
        state["mode"] = "slow"
        import time as _t
        t0 = _t.monotonic()
        s = turn("Hello there.", conv="slow1").json()
        assert _t.monotonic() - t0 < 12 and "trouble" in s["response_text"]
        assert run(receipts(related_object_id="vb_slow1"))[-1]["status"] == "failed"
        # failure after the request was filed: honest reply, the request stands
        state["mode"] = "down_after_tool"
        g = turn("I need a nurse, I need help getting up.", conv="fail2").json()
        assert "passed your request" in g["response_text"], g
        grc = run(receipts(related_object_id="vb_fail2"))[-1]
        assert grc["status"] == "failed" and grc["evidence"]["workflow_objects"], grc
        state["mode"] = None
        print("OK provider failure, timeout, failure-after-tool")

        # -- no orphan state: every bridge-created task has receipts and is named by a turn receipt
        named = {w["id"] for x in run(receipts(related_object_type="voice_session"))
                 for w in (x.get("evidence") or {}).get("workflow_objects", [])}
        for tdoc in run(db.staff_tasks.find({}, {"_id": 0}).to_list(100)):
            assert run(db.receipts.count_documents({"related_object_id": tdoc["task_id"]})) >= 1
            assert tdoc["task_id"] in named, tdoc["task_id"]
        for sdoc in run(db.voice_bridge_sessions.find({}, {"_id": 0}).to_list(100)):
            assert run(db.receipts.count_documents({"related_object_id": sdoc["session_id"]})) == sdoc["turn_count"] + \
                run(db.receipts.count_documents({"related_object_id": sdoc["session_id"],
                                                 "action_type": "voice_turn_duplicate_ignored"}))
        print("OK no orphan state changes")

        # -- emergency words: escalated at once, no model call, receipt ------
        calls_before = state["n"]
        em = turn("I fell and I can't get up.", conv="em1").json()
        assert em["priority_class"] == "emergency" and state["n"] == calls_before, em
        alert = run(db.alerts.find_one({"resident_id": "res_101", "status": {"$in": ["active", "acknowledged"]}}))
        assert alert and alert["severity"] == "emergency"
        erc = run(receipts(related_object_id="vb_em1"))[-1]
        assert erc["action_type"] == "voice_emergency_escalated"
        assert erc["evidence"]["workflow_objects"][0]["id"] == alert["alert_id"]
        assert "on the way" not in em["response_text"].lower()

        # -- no capacity: lower priority answered at once, honestly, with a receipt
        from routes.voice_bridge_admission import Admission
        real = vb.ADMISSION
        vb.ADMISSION = Admission(max_active=1, reserved=0)
        run(vb.ADMISSION.acquire(5, 0.1))  # the only slot is busy
        tasks_before = run(db.staff_tasks.count_documents({}))
        dfr = turn("Tell me a story about the sea.", conv="busy1").json()
        assert dfr["deferred"] is True and dfr["continue_conversation"] is True
        drc = run(receipts(related_object_id="vb_busy1"))[-1]
        assert drc["action_type"] == "voice_turn_deferred" and drc["status"] == "cancelled"
        em2 = turn("Help me!", conv="busy2").json()  # emergency never waits for capacity
        assert em2["priority_class"] == "emergency" and not em2.get("deferred")
        assert run(db.staff_tasks.count_documents({})) == tasks_before
        vb.ADMISSION = real
        print("OK emergency fast path, honest deferral at capacity")

        # -- admin device mapping: move a device between rooms, with receipts ---
        m = c.put("/api/voice-bridge/devices/ha_dev_new", json={"kiosk_id": "kio_102"})
        assert m.status_code == 200 and m.json()["room"] == "102"
        m = c.put("/api/voice-bridge/devices/ha_dev_new", json={"kiosk_id": "kio_101"}).json()
        assert m["previous_kiosk_id"] == "kio_102"
        k102 = run(db.kiosks.find_one({"kiosk_id": "kio_102"}))
        assert "ha_dev_new" not in k102["voice_device_ids"]  # one room per device
        mrc = run(receipts(related_object_id="ha_dev_new"))
        assert [x["action_type"] for x in mrc] == ["voice_device_mapped", "voice_device_mapped"]
        assert mrc[1]["before_state"] == {"kiosk": "kio_102"} and mrc[1]["after_state"] == {"kiosk": "kio_101"}
        assert c.delete("/api/voice-bridge/devices/ha_dev_new").status_code == 200
        assert turn("hello", conv="gone", device="ha_dev_new").status_code == 404
        print("OK admin device mapping with receipts")

        # -- room isolation: nothing written for room 102 ----------------------
        assert run(db.staff_tasks.count_documents({"room": "102"})) == 0
        assert run(db.conversations.count_documents({"resident_id": "res_102"})) == 0
        print("OK room isolation")

        run(db.client.drop_database(os.environ["DB_NAME"]))
    print("ALL VOICE BRIDGE FLOW CHECKS PASSED")


if __name__ == "__main__" and "--isolated" in sys.argv:
    main()
