"""After each load level: check the database against what the rooms were told.

- every 200 response's receipt exists, and every voice-session receipt for
  the level's sessions was returned to a room (no missing, no orphan)
- every staff request and help event created for these residents has its
  own receipt and is named by a voice turn receipt (no orphan state change)
- at most one open request per resident per category, one open help event
  per resident (no duplicate workflow)
- every room that said a closing phrase got its session closed
"""
from collections import Counter


async def verify(db, turns: list, rooms: list) -> dict:
    residents = [r["resident_id"] for r in rooms]
    ok_turns = [t for t in turns if t.get("status") == 200]
    sessions = {t["session_id"] for t in ok_turns if t.get("session_id")}
    returned = {t["receipt_id"] for t in ok_turns if t.get("receipt_id")}
    stored = await db.receipts.find({"related_object_type": "voice_session",
                                     "related_object_id": {"$in": list(sessions)}},
                                    {"_id": 0, "receipt_id": 1, "evidence": 1, "action_type": 1,
                                     "resident_id": 1, "parent_receipt_id": 1}).to_list(100000)
    stored_ids = {r["receipt_id"] for r in stored}
    named = {w["id"] for r in stored for w in ((r.get("evidence") or {}).get("workflow_objects") or [])}
    wrong_resident = 0
    by_session_resident = {t["session_id"]: t["resident_id"] for t in ok_turns if t.get("session_id")}
    for r in await db.receipts.find({"related_object_type": "voice_session",
                                     "related_object_id": {"$in": list(sessions)}},
                                    {"_id": 0, "related_object_id": 1, "resident_id": 1}).to_list(100000):
        if by_session_resident.get(r["related_object_id"]) != r.get("resident_id"):
            wrong_resident += 1

    tasks = await db.staff_tasks.find({"resident_id": {"$in": residents}}, {"_id": 0}).to_list(10000)
    alerts = await db.alerts.find({"resident_id": {"$in": residents}}, {"_id": 0}).to_list(10000)
    orphan_tasks = []
    for t in tasks:
        has_receipt = await db.receipts.count_documents({"related_object_id": t["task_id"]})
        if not has_receipt or t["task_id"] not in named:
            orphan_tasks.append(t["task_id"])
    orphan_alerts = []
    for a in alerts:
        has_receipt = await db.receipts.count_documents({"$or": [{"related_object_id": a["alert_id"]},
                                                                 {"evidence.workflow_objects.id": a["alert_id"]}]})
        if not has_receipt or a["alert_id"] not in named:
            orphan_alerts.append(a["alert_id"])
    per = Counter((t["resident_id"], t["category"]) for t in tasks
                  if t.get("status") in ("pending", "acknowledged", "in_progress"))
    open_alerts = Counter(a["resident_id"] for a in alerts if a.get("status") in ("active", "acknowledged"))

    ending_rooms = {t["resident_id"] for t in turns if t["kind"] == "ending"}
    ended_ok = {t["resident_id"] for t in turns if t["kind"] == "ending" and t.get("status") == 200
                and t.get("continue_conversation") is False}
    closed = await db.voice_bridge_sessions.count_documents(
        {"session_id": {"$in": list(sessions)}, "status": "closed"})
    dev_ids = [d["device_id"] for d in await db.smart_devices.find(
        {"room": {"$in": [r["room"] for r in rooms]}}, {"device_id": 1}).to_list(10000)]
    commands = await db.device_commands.count_documents({"device_id": {"$in": dev_ids}})
    unverified = await db.device_commands.count_documents({"device_id": {"$in": dev_ids}, "verified": {"$ne": True}})
    return {
        "receipts_stored": len(stored),
        "missing_receipts": len(returned - stored_ids),
        "orphan_receipts": len(stored_ids - returned),
        "receipts_with_wrong_resident": wrong_resident,
        "tasks_created": len(tasks), "orphan_tasks": orphan_tasks,
        "help_events": len(alerts), "orphan_help_events": orphan_alerts,
        "duplicate_open_requests": {f"{k[0]}:{k[1]}": v for k, v in per.items() if v > 1},
        "duplicate_open_help_events": {k: v for k, v in open_alerts.items() if v > 1},
        "ending_requested": len(ending_rooms), "ending_succeeded": len(ended_ok), "sessions_closed": closed,
        "device_commands": commands, "device_commands_unverified": unverified,
    }
