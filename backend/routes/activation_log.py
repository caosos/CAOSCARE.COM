"""Append-only activation observability log (Level 1 observability
requirement, 2026-09-07).

One collection - db.activation_events - one row per meaningful state
transition across every layer of a Resident Aria activation:

    rf -> resident_event -> kiosk -> wake -> lease -> realtime

Common envelope, every row correlatable by any of:
    room, resident_id, alert_id, activation_id, kiosk_id,
    client_instance_id, session_id, ts

`ts` is the authoritative SERVER timestamp. A client-supplied timestamp may
ride along in `ts_client` for diagnostics only - never rely on client clock
ordering. Writes are fire-and-forget: a telemetry failure must never affect
an activation, and raw evidence (db.rf_events, db.alerts, lease events,
realtime_diagnostics) is never mutated or replaced by this log - it only
adds a correlated, ordered index over what already happened.
"""
import logging
import uuid
from typing import Optional

from deps import db
from models import now_utc

log = logging.getLogger(__name__)

LAYERS = ("rf", "resident_event", "kiosk", "wake", "lease", "realtime")


def new_activation_id() -> str:
    """A correlation id for one activation cycle - opened when an event is
    created or re-armed from a consumed state, stable for the life of that
    cycle. Same shape/semantics as the field the parallel main-checkout
    work uses, so the two converge rather than fork."""
    return uuid.uuid4().hex


async def alog(
    layer: str,
    event: str,
    *,
    activation_id: Optional[str] = None,
    room: Optional[str] = None,
    resident_id: Optional[str] = None,
    alert_id: Optional[str] = None,
    kiosk_id: Optional[str] = None,
    client_instance_id: Optional[str] = None,
    session_id: Optional[str] = None,
    rf_device_id: Optional[str] = None,
    data: Optional[dict] = None,
    ts_client: Optional[str] = None,
) -> None:
    try:
        await db.activation_events.insert_one({
            "ts": now_utc().isoformat(),
            "ts_client": ts_client,
            "layer": layer,
            "event": event,
            "activation_id": activation_id,
            "room": room,
            "resident_id": resident_id,
            "alert_id": alert_id,
            "kiosk_id": kiosk_id,
            "client_instance_id": client_instance_id,
            "session_id": session_id,
            "rf_device_id": rf_device_id,
            "data": data or {},
        })
    except Exception as e:  # never propagate into an activation path
        log.warning(f"activation_events log dropped ({layer}/{event}): {e}")
