#!/usr/bin/env python3
"""Private, one-shot Room 214 conversation export.

Writes JSON only to the caller-supplied path. It never prints transcript text.
The workflow encrypts the file before any artifact upload.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone

from bson import json_util
from dotenv import dotenv_values
from pymongo import MongoClient


ROOM_VALUES = ["214", 214]


def as_utc(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def in_window(doc, fields, cutoff):
    for field in fields:
        value = doc
        for part in field.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        stamp = as_utc(value)
        if stamp and stamp >= cutoff:
            return True
    return False


def without_id(doc):
    clean = dict(doc)
    clean.pop("_id", None)
    return clean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()

    config = dotenv_values(args.env)
    missing = [key for key in ("MONGO_URL", "DB_NAME") if not config.get(key)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    client = MongoClient(config["MONGO_URL"], serverSelectionTimeoutMS=5000)
    db = client[config["DB_NAME"]]
    client.admin.command("ping")

    residents = list(db.residents.find(
        {"room": {"$in": ROOM_VALUES}},
        {"_id": 0, "resident_id": 1, "room": 1, "preferred_name": 1, "name": 1},
    ))
    resident_ids = [r["resident_id"] for r in residents if r.get("resident_id")]

    conversation_scope = [{"room": {"$in": ROOM_VALUES}}]
    if resident_ids:
        conversation_scope.append({"resident_id": {"$in": resident_ids}})
    recent_turns = [
        without_id(d) for d in db.conversations.find(
            {"$or": conversation_scope}, {"_id": 0}
        ).sort("created_at", -1).limit(10000)
        if in_window(d, ("created_at",), cutoff)
    ]

    room_lease_events = [
        without_id(d) for d in db.resident_aria_lease_events.find(
            {"lease.room": {"$in": ROOM_VALUES}}, {"_id": 0}
        ).sort("at", -1).limit(5000)
        if in_window(d, ("at", "created_at"), cutoff)
    ]

    session_ids = {
        d.get("session_id") for d in recent_turns if d.get("session_id")
    }
    session_ids.update(
        d.get("lease", {}).get("session_id") for d in room_lease_events
        if d.get("lease", {}).get("session_id")
    )
    session_ids.discard(None)

    conversations = [
        without_id(d) for d in db.conversations.find(
            {"session_id": {"$in": sorted(session_ids)}}, {"_id": 0}
        ).sort("created_at", 1)
    ] if session_ids else []
    diagnostics = [
        without_id(d) for d in db.realtime_diagnostics.find(
            {"session_id": {"$in": sorted(session_ids)}}, {"_id": 0}
        ).sort("created_at", 1)
    ] if session_ids else []

    device_commands = [
        without_id(d) for d in db.device_commands.find(
            {"$or": [
                {"room": {"$in": ROOM_VALUES}},
                {"issued_by": "kiosk:room:214"},
                {"metadata.room": {"$in": ROOM_VALUES}},
            ]},
            {"_id": 0},
        ).sort("created_at", -1).limit(5000)
        if in_window(d, ("created_at", "issued_at", "completed_at"), cutoff)
    ]

    sessions = []
    for session_id in sorted(session_ids):
        turns = [d for d in conversations if d.get("session_id") == session_id]
        events = [d for d in diagnostics if d.get("session_id") == session_id]
        leases = [
            d for d in room_lease_events
            if d.get("lease", {}).get("session_id") == session_id
        ]
        timestamps = []
        for d in turns + events:
            stamp = as_utc(d.get("created_at"))
            if stamp:
                timestamps.append(stamp)
        for d in leases:
            stamp = as_utc(d.get("at") or d.get("created_at"))
            if stamp:
                timestamps.append(stamp)
        sessions.append({
            "session_id": session_id,
            "started_at": min(timestamps).isoformat() if timestamps else None,
            "ended_at": max(timestamps).isoformat() if timestamps else None,
            "turns": turns,
            "diagnostics": events,
            "lease_events": leases,
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff": cutoff.isoformat(),
        "room": "214",
        "residents": residents,
        "sessions": sessions,
        "device_commands": device_commands,
        "summary": {
            "session_count": len(sessions),
            "turn_count": sum(len(s["turns"]) for s in sessions),
            "diagnostic_count": sum(len(s["diagnostics"]) for s in sessions),
            "response_done_count": sum(
                1 for s in sessions for d in s["diagnostics"]
                if d.get("event_type") == "response_done"
            ),
            "usage_record_count": sum(
                1 for s in sessions for d in s["diagnostics"]
                if isinstance(d.get("meta"), dict) and d["meta"].get("usage")
            ),
            "device_command_count": len(device_commands),
        },
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, default=json_util.default, ensure_ascii=False)
    summary = payload["summary"]
    print("EXPORT_SUMMARY " + " ".join(
        f"{key}={value}" for key, value in summary.items()
    ))


if __name__ == "__main__":
    main()
