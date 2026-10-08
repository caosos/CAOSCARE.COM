"""B3: the unauthenticated by-kiosk lookup returns only an allowlist of
resident fields (no medical notes, contacts, DOB, memory)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from deps import db  # noqa: E402
from routes.residents import PUBLIC_KIOSK_RESIDENT_FIELDS, resident_by_kiosk  # noqa: E402

ROOM = "T-B3-ALLOWLIST"


async def _run():
    await db.residents.delete_many({"room": ROOM})
    await db.kiosks.delete_many({"room": ROOM})
    await db.residents.insert_one({
        "resident_id": "res_b3test", "name": "B3 Test", "preferred_name": "Bee",
        "room": ROOM, "pendant_id": "p", "medical_notes": "SECRET-DX",
        "emergency_contact": "555-0100", "date_of_birth": "1940-01-01",
        "preferences": "SECRET-PREF", "memory": "SECRET-MEM",
        "clinical_thresholds": {"x": 1}, "synthetic": True,
    })
    await db.kiosks.insert_one({"kiosk_id": "kio_b3test", "name": "k", "room": ROOM})
    try:
        out = await resident_by_kiosk("kio_b3test")
    finally:
        await db.residents.delete_many({"room": ROOM})
        await db.kiosks.delete_many({"room": ROOM})
    return out


def test_by_kiosk_returns_only_allowlisted_resident_fields():
    out = asyncio.run(_run())
    assert out["kiosk"]["kiosk_id"] == "kio_b3test"
    assert set(out["resident"]) == set(PUBLIC_KIOSK_RESIDENT_FIELDS)
    assert out["resident"]["preferred_name"] == "Bee"
    assert "SECRET" not in str(out)
