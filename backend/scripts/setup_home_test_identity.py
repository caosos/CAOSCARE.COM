"""Room 214 home test identity (RQ-037).

Creates a clearly-named test resident and pins the Room 214 kiosk to it, so a
home test of Room 214's real lights and Aria leaves the room's registered
resident (Helen Torres) with no new conversations, memories or requests.
Idempotent. Never edits or deletes any other resident.

    cd backend && .venv/bin/python scripts/setup_home_test_identity.py            # set up + pin
    cd backend && .venv/bin/python scripts/setup_home_test_identity.py --revert   # unpin (history kept)
    ... --dry-run   # show what would happen
Options: --kiosk-id (default kio_dc8c06a19608), --db-name / MONGO_URL from .env.
Writes one receipt per change (actor system:setup_home_test_identity).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from models import Resident  # noqa: E402

KIOSK_ID = "kio_dc8c06a19608"
TEST_ROOM_LABEL = "214-HOME"
TEST_NAME = "Michael Chambers (Room 214 home test)"
ACTOR = "system:setup_home_test_identity"


async def _receipt(database, action, **kw):
    from routes.receipts import create_receipt
    return await create_receipt(
        action_type=action, source="system", requested_by=ACTOR,
        related_object_type="kiosk", related_object_id=kw.pop("kiosk_id"), **kw,
    )


async def setup(database, kiosk_id=KIOSK_ID, dry_run=False) -> dict:
    kiosk = await database.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise SystemExit(f"Kiosk {kiosk_id} not found")
    res = await database.residents.find_one({"name": TEST_NAME}, {"_id": 0})
    created = False
    if not res:
        created = True
        res = Resident(name=TEST_NAME, preferred_name="Michael", room=TEST_ROOM_LABEL,
                       pendant_id="HOME-TEST-NONE",
                       memory="Test identity for home testing of Room 214. Not a care resident.").model_dump()
        res["created_at"] = res["created_at"].isoformat()
        if not dry_run:
            await database.residents.insert_one(dict(res))
    out = {"resident_id": res["resident_id"], "resident_created": created, "room_label": res["room"],
           "kiosk_id": kiosk_id, "kiosk_room": kiosk["room"], "previous_pin": kiosk.get("resident_id"),
           "dry_run": dry_run}
    if kiosk.get("resident_id") != res["resident_id"] and not dry_run:
        await database.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": {"resident_id": res["resident_id"]}})
        await _receipt(database, "kiosk_pinned", kiosk_id=kiosk_id, room=kiosk["room"],
                       resident_id=res["resident_id"], result=f"pinned to {res['resident_id']}")
    return out


async def revert(database, kiosk_id=KIOSK_ID, dry_run=False) -> dict:
    kiosk = await database.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise SystemExit(f"Kiosk {kiosk_id} not found")
    prev = kiosk.get("resident_id")
    if prev and not dry_run:
        await database.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": {"resident_id": None}})
        await _receipt(database, "kiosk_unpinned", kiosk_id=kiosk_id, room=kiosk["room"],
                       resident_id=prev, result=f"unpinned from {prev}")
    return {"kiosk_id": kiosk_id, "unpinned_from": prev, "dry_run": dry_run,
            "note": "Test resident and its history are kept."}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kiosk-id", default=KIOSK_ID)
    a = ap.parse_args()
    from deps import db
    print(await (revert if a.revert else setup)(db, a.kiosk_id, a.dry_run))


if __name__ == "__main__":
    asyncio.run(main())
