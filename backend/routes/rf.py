"""RF pairing + reception (sub-GHz SDR).

This is the backend half of [FW-006] in the blueprint. The kiosk runs an
Android-side SDR daemon (Nooelec NESDR SMArt v5 over USB OTG). The flow:

  ADMIN UI → POST /api/rf/listen-start
              → backend creates a capture window in db.rf_captures
              → backend pushes a queued command for the kiosk's bridge
              → bridge demodulates, builds a fingerprint, POSTs back
              → admin polls GET /api/rf/listen/{id}
              → admin tags it with POST /api/rf/pair
              → saved to db.rf_devices, future matches auto-alert.

Live presses come in via POST /api/rf/event from the bridge daemon, signed
with an HMAC of the per-kiosk secret. We match the pattern against every
enabled RFDevice on the same frequency and fire an alert on the best match.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import hmac
import hashlib
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Header, Body, Request

from deps import db, get_current_user, require_admin
from models import (
    RFDevice, RFCapture, RFFingerprint, RFListenStart, RFPair, RFEventIn,
    RFDeviceAssign, now_utc,
)
from routes.resident_activation import record_resident_activation
from routes.rf_bridge_health import mark_bridge_polled
from routes.rf_pairing_guard import hamming_similarity, find_pairing_conflict

router = APIRouter(prefix="/rf", tags=["rf"])

DEFAULT_BANDS_HZ = [315_000_000, 319_000_000, 433_920_000, 868_000_000, 915_000_000]
DEFAULT_LISTEN_SECONDS = 10
DEFAULT_TEST_SECONDS = 5
# Live events and pairing-time conflict checks both need to consider two
# devices "on the same frequency" - real rtl_433 measurements drift by a
# few kHz per packet, so an exact match is too fragile (see rf_event()).
FREQ_TOLERANCE_HZ = 50_000
# One physical button press on a real Interlogix-Security pendant produces
# ~8 RF frames within ~1-3s (live-evidenced 2026-08-29). Frame-level
# coalescing (same press's own repeat frames) plus the deeper
# incident-level activation gating (repeat presses during an ALREADY
# ACTIVE session - real live defect, 2026-08-30, room 401) both live in
# routes/resident_activation.py now (generalized 2026-09-06 from device-
# scoped to resident-scoped, per the Level 1 directive - see that
# module's docstring for the full history).


def _iso(doc: dict) -> dict:
    for k in ("created_at", "started_at", "expires_at", "completed_at",
              "last_seen_at", "captured_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


# ---------------- Pairing flow (admin) ----------------

@router.post("/listen-start")
async def listen_start(payload: RFListenStart, user=Depends(require_admin)):
    """Open a capture window. The kiosk's bridge daemon will pick this up
    on its next poll, run the SDR for `duration_seconds`, then POST the
    captured fingerprint back via /api/rf/listen/{capture_id}/captured."""
    kiosk = await db.kiosks.find_one({"kiosk_id": payload.kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(404, detail="Kiosk not found")

    bands = payload.bands or DEFAULT_BANDS_HZ
    duration = max(2, min(payload.duration_seconds or DEFAULT_LISTEN_SECONDS, 60))
    capture = RFCapture(
        kiosk_id=payload.kiosk_id,
        requested_by=user.get("user_id") if isinstance(user, dict) else None,
        bands=bands,
        status="pending",
        expires_at=now_utc() + timedelta(seconds=duration + 2),
    )
    doc = capture.model_dump()
    doc["started_at"] = doc["started_at"].isoformat()
    doc["expires_at"] = doc["expires_at"].isoformat()
    await db.rf_captures.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.get("/listen/{capture_id}")
async def listen_status(capture_id: str, user=Depends(require_admin)):
    doc = await db.rf_captures.find_one({"capture_id": capture_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, detail="Capture not found")
    # Auto-timeout if past expiry
    if doc["status"] in ("pending", "listening"):
        expiry = doc["expires_at"]
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)
        if datetime.now(timezone.utc) > expiry:
            await db.rf_captures.update_one(
                {"capture_id": capture_id},
                {"$set": {"status": "timeout", "completed_at": now_utc().isoformat()}},
            )
            doc["status"] = "timeout"
    return _iso(doc)


@router.post("/listen/{capture_id}/captured")
async def listen_captured(
    capture_id: str,
    fingerprint: RFFingerprint = Body(...),
    x_rf_signature: Optional[str] = Header(default=None, alias="X-RF-Signature"),
):
    """Bridge daemon → backend. The kiosk posts the fingerprint it heard.
    Public endpoint signed with the per-kiosk HMAC. No bearer token here
    because the bridge is a device, not a logged-in user."""
    doc = await db.rf_captures.find_one({"capture_id": capture_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, detail="Capture not found")
    if doc["status"] not in ("pending", "listening"):
        raise HTTPException(409, detail=f"Capture is {doc['status']}")

    # Optional HMAC verification — bridge must sign with kiosk's secret if set.
    kiosk = await db.kiosks.find_one({"kiosk_id": doc["kiosk_id"]}, {"_id": 0, "rf_secret": 1})
    secret = (kiosk or {}).get("rf_secret")
    if secret and x_rf_signature:
        body = fingerprint.model_dump_json().encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_rf_signature):
            raise HTTPException(401, detail="Bad RF signature")

    fp_doc = fingerprint.model_dump()
    await db.rf_captures.update_one(
        {"capture_id": capture_id},
        {"$set": {"status": "captured", "captured": fp_doc, "completed_at": now_utc().isoformat()}},
    )
    return {"ok": True}


@router.post("/pair")
async def pair(payload: RFPair, user=Depends(require_admin)):
    """Bind a captured fingerprint to a resident as a paired device."""
    cap = await db.rf_captures.find_one({"capture_id": payload.capture_id}, {"_id": 0})
    if not cap:
        raise HTTPException(404, detail="Capture not found")
    if cap.get("status") != "captured" or not cap.get("captured"):
        raise HTTPException(409, detail="Capture has no fingerprint to pair")

    room = None
    if payload.resident_id:
        r = await db.residents.find_one({"resident_id": payload.resident_id}, {"_id": 0, "room": 1})
        if r:
            room = r.get("room")

    fingerprint = RFFingerprint(**cap["captured"])
    battery_ok = (fingerprint.decoded or {}).get("battery_ok")

    conflict = await find_pairing_conflict(fingerprint, payload.match_threshold, FREQ_TOLERANCE_HZ)
    pairing_warning = None
    if conflict and not payload.override:
        raise HTTPException(
            409,
            detail={
                "error": "similar_device_conflict",
                "message": (
                    f"This pendant reads {conflict['score']:.0%} similar to already-paired device "
                    f"'{conflict['device'].get('label')}' ({conflict['device'].get('room') or 'no room'}) "
                    f"on a nearby frequency - too close to the {payload.match_threshold:.2f} match "
                    "threshold for real-world signal noise to safely tell them apart. Retry with "
                    "override=true if you're certain these are different physical pendants."
                ),
                "conflicting_device_id": conflict["device"].get("rf_device_id"),
                "score": conflict["score"],
            },
        )
    if conflict:
        pairing_warning = (
            f"Paired despite {conflict['score']:.0%} similarity to "
            f"{conflict['device'].get('rf_device_id')} (admin override)"
        )

    device = RFDevice(
        label=payload.label,
        resident_id=payload.resident_id,
        room=room,
        fingerprint=fingerprint,
        severity=payload.severity,
        match_threshold=payload.match_threshold,
        created_by=user.get("user_id") if isinstance(user, dict) else None,
        last_seen_at=now_utc(),
        last_rssi=fingerprint.rssi,
        low_battery=(not bool(battery_ok)) if battery_ok is not None else False,
        pairing_warning=pairing_warning,
    )
    doc = device.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.rf_devices.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.put("/devices/{rf_device_id}/assign")
async def assign_device(rf_device_id: str, payload: RFDeviceAssign, user=Depends(require_admin)):
    """Reassign a paired device to a different resident (or unassign with
    resident_id=None) — the fingerprint/historical events stay exactly as
    they were, only the assignment changes, so past evidence still
    reflects who the device was actually assigned to at the time."""
    dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(404, detail="RF device not found")
    room = None
    if payload.resident_id:
        r = await db.residents.find_one({"resident_id": payload.resident_id}, {"_id": 0, "room": 1})
        if not r:
            raise HTTPException(404, detail="Resident not found")
        room = r.get("room")
    await db.rf_devices.update_one(
        {"rf_device_id": rf_device_id},
        {"$set": {"resident_id": payload.resident_id, "room": room}},
    )
    doc = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
    return _iso(doc)


@router.get("/devices")
async def list_devices(user=Depends(require_admin)):
    items = await db.rf_devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for i in items:
        _iso(i)
    return items


# ---------------- Kiosk provisioning (install wizard + APK QR pairing) ----------------

import secrets as _secrets


def _public_api_url(request: Optional[object] = None) -> str:
    """Best-effort backend public URL — used inside install commands.
    Priority: PUBLIC_API_URL env var → X-Forwarded-Host (set by ingress) →
    inbound request host → placeholder."""
    env_url = os.environ.get("PUBLIC_API_URL")
    if env_url:
        return env_url.rstrip("/")
    if request is not None:
        try:
            fwd_host = request.headers.get("x-forwarded-host")
            fwd_proto = request.headers.get("x-forwarded-proto", "https")
            if fwd_host:
                return f"{fwd_proto}://{fwd_host}"
            return f"{request.url.scheme}://{request.url.netloc}"
        except Exception:
            pass
    return "https://YOUR-FACILITY.caoscare.com"


@router.get("/kiosk/{kiosk_id}/install-info")
async def kiosk_install_info(kiosk_id: str, request: Request, user=Depends(require_admin)):
    """Return everything a tablet/host needs to run the bridge daemon —
    api_url, kiosk_id, rf_secret. If no rf_secret exists yet, mint one.
    Powers the install wizard *and* the APK QR-pairing flow."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(404, detail="Kiosk not found")
    secret = kiosk.get("rf_secret")
    if not secret:
        secret = _secrets.token_urlsafe(32)
        await db.kiosks.update_one(
            {"kiosk_id": kiosk_id}, {"$set": {"rf_secret": secret}},
        )
    api_url = _public_api_url(request)
    return {
        "api_url": api_url,
        "kiosk_id": kiosk_id,
        "rf_secret": secret,
        "kiosk_name": kiosk.get("name"),
        "room": kiosk.get("room"),
        "qr_payload": json.dumps({
            "v": 1,
            "api_url": api_url,
            "kiosk_id": kiosk_id,
            "rf_secret": secret,
        }),
    }


@router.post("/kiosk/{kiosk_id}/regenerate-secret")
async def kiosk_regenerate_secret(kiosk_id: str, user=Depends(require_admin)):
    """Rotate the kiosk's rf_secret. Any running bridge using the old
    secret will start getting 401 on /api/rf/event until re-paired."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(404, detail="Kiosk not found")
    secret = _secrets.token_urlsafe(32)
    await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": {"rf_secret": secret}})
    return {"ok": True, "rf_secret": secret}


@router.get("/bridge-daemon", include_in_schema=False)
async def serve_bridge_daemon():
    """Serve /app/android-bridge/caos_rf_bridge.py so the install wizard's
    `curl` command resolves without requiring static-asset hosting setup."""
    from fastapi.responses import FileResponse
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "android-bridge", "caos_rf_bridge.py")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise HTTPException(404, detail="bridge daemon not found on server")
    return FileResponse(
        path,
        media_type="text/x-python",
        filename="caos_rf_bridge.py",
    )


@router.delete("/devices/{rf_device_id}")
async def delete_device(rf_device_id: str, user=Depends(require_admin)):
    res = await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
    if res.deleted_count == 0:
        raise HTTPException(404, detail="RF device not found")
    return {"ok": True}


@router.post("/test/{rf_device_id}")
async def test_device(rf_device_id: str, user=Depends(require_admin)):
    """Open a 5-second test capture. Admin presses the pendant; we score
    the resulting capture against the saved fingerprint and return pass/fail."""
    dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(404, detail="RF device not found")
    # Pick a kiosk in the same room if known, else any kiosk
    kiosk_q = {"room": dev.get("room")} if dev.get("room") else {}
    kiosk = await db.kiosks.find_one(kiosk_q, {"_id": 0, "kiosk_id": 1})
    if not kiosk:
        kiosk = await db.kiosks.find_one({}, {"_id": 0, "kiosk_id": 1})
    if not kiosk:
        raise HTTPException(404, detail="No kiosk available to test from")

    capture = RFCapture(
        kiosk_id=kiosk["kiosk_id"],
        requested_by=user.get("user_id") if isinstance(user, dict) else None,
        bands=[dev["fingerprint"]["frequency_hz"]],
        status="pending",
        expires_at=now_utc() + timedelta(seconds=DEFAULT_TEST_SECONDS + 2),
    )
    doc = capture.model_dump()
    doc["started_at"] = doc["started_at"].isoformat()
    doc["expires_at"] = doc["expires_at"].isoformat()
    doc["test_for"] = rf_device_id
    await db.rf_captures.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


# ---------------- Live press intake (bridge daemon) ----------------

@router.post("/event")
async def rf_event(
    payload: RFEventIn,
    x_rf_signature: Optional[str] = Header(default=None, alias="X-RF-Signature"),
):
    """Bridge → backend. Live RF event. Match against all enabled devices on
    the same frequency, fire an alert on the best match above its threshold.
    Unmatched events are still logged for diagnostic value."""
    kiosk = await db.kiosks.find_one(
        {"kiosk_id": payload.kiosk_id},
        {"_id": 0, "kiosk_id": 1, "room": 1, "rf_secret": 1, "rf_seq": 1},
    )
    if not kiosk:
        raise HTTPException(404, detail="Kiosk not found")

    # HMAC verification (when a secret is configured)
    secret = kiosk.get("rf_secret")
    if secret and x_rf_signature:
        body = payload.model_dump_json().encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_rf_signature):
            raise HTTPException(401, detail="Bad RF signature")

    # Replay prevention: monotonic sequence
    last_seq = kiosk.get("rf_seq") or 0
    if payload.sequence <= last_seq:
        raise HTTPException(409, detail="Sequence not monotonic — possible replay")
    await db.kiosks.update_one(
        {"kiosk_id": payload.kiosk_id}, {"$set": {"rf_seq": payload.sequence}},
    )

    # Match. Frequency is a RANGE, not an exact value - real transmitters
    # drift a few kHz between presses (temperature, battery voltage), and
    # since enabling "-M level" on the bridge (2026-09-06, for real RSSI
    # data) rtl_433 now reports that per-packet measured frequency instead
    # of always falling back to the nominal tuned band. An exact match here
    # would silently stop matching ANY real device the moment its measured
    # frequency drifted even 1 Hz off its stored calibration value - proven
    # live the same day this was added (a real press measured 319.509MHz
    # against a device calibrated at 319.500MHz). Tolerance is generous
    # enough for real OOK transmitter drift, tight enough that it can never
    # bridge actual different bands (315/319.5/433.92/868/915MHz are each
    # megahertz apart).
    candidates = await db.rf_devices.find(
        {
            "enabled": True,
            "fingerprint.frequency_hz": {
                "$gte": payload.fingerprint.frequency_hz - FREQ_TOLERANCE_HZ,
                "$lte": payload.fingerprint.frequency_hz + FREQ_TOLERANCE_HZ,
            },
        },
        {"_id": 0},
    ).to_list(500)
    best = None
    best_score = 0.0
    for c in candidates:
        score = hamming_similarity(
            c["fingerprint"]["bit_pattern_hex"],
            payload.fingerprint.bit_pattern_hex,
        )
        if score > best_score:
            best_score = score
            best = c

    matched = best is not None and best_score >= (best.get("match_threshold", 0.85) if best else 1.0)
    raw_event = {
        "kiosk_id": payload.kiosk_id,
        "fingerprint": payload.fingerprint.model_dump(),
        "sequence": payload.sequence,
        "matched_device_id": best["rf_device_id"] if matched else None,
        "match_score": round(best_score, 4),
        "captured_at": (payload.captured_at or now_utc()).isoformat() if isinstance(payload.captured_at, datetime) or payload.captured_at is None else payload.captured_at,
        "received_at": now_utc().isoformat(),
        "alert_id": None,
    }

    if matched:
        telemetry = {
            "last_seen_at": now_utc().isoformat(),
            "last_rssi": payload.fingerprint.rssi,
        }
        # battery_ok is real decoder-provided evidence (Interlogix-Security
        # and similar PERS protocols report it on every transmission) - was
        # captured in every event's fingerprint.decoded already but never
        # actually propagated onto the paired device record, so the admin
        # pendant list could never show a real low-battery warning even
        # though the data was right there (2026-09-06, real ask: "battery
        # life and whatever else can be derived" as pairing/device data).
        battery_ok = (payload.fingerprint.decoded or {}).get("battery_ok")
        if battery_ok is not None:
            telemetry["low_battery"] = not bool(battery_ok)
        await db.rf_devices.update_one(  # telemetry
            {"rf_device_id": best["rf_device_id"]},
            {"$set": telemetry, "$inc": {"press_count": 1}},
        )
        # Every RF press is persisted to db.rf_events unconditionally,
        # below, regardless of whether it coalesces into an already-open
        # resident event or opens a fresh one - evidence is never dropped,
        # only ACTIVATION is deduped. Map our RF severities ("help" /
        # "assist" / "emergency" / "comfort") to the tighter
        # Alert.AlertSeverity Literal which has no "help" - collapse
        # "help" -> "assist" so the alert is valid.
        sev_map = {"help": "assist", "assist": "assist", "emergency": "emergency", "comfort": "comfort"}
        alert_severity = sev_map.get(best.get("severity", "help"), "assist")
        try:
            result = await record_resident_activation(
                resident_id=best.get("resident_id"),
                room=best.get("room") or kiosk.get("room"),
                source="rf_pendant",
                device_id=best["rf_device_id"],
                rssi=payload.fingerprint.rssi,
                severity=alert_severity,
                auto_voice=True,  # Michael, 2026-08-29: a pendant press must always reach Aria hands-free, matching pendants.py/wearables.py
                message=f"RF pendant pressed: {best.get('label', 'unknown')}",
                triggered_by="rf_pendant",
                kiosk_id=payload.kiosk_id,
                source_metadata={
                    "rf_device_id": best["rf_device_id"],
                    "match_score": round(best_score, 4),
                    "rssi": payload.fingerprint.rssi,
                    "rf_severity": best.get("severity", "help"),
                },
            )
            raw_event["alert_id"] = result["alert_id"]
            press_coalesced = result["coalesced"]
        except Exception as e:
            # Best-effort. Log the cause so we know if activation recording breaks.
            import logging
            logging.getLogger(__name__).warning(f"RF activation recording failed: {e}")
            press_coalesced = False

    await db.rf_events.insert_one(raw_event)
    raw_event.pop("_id", None)
    return {
        "ok": True,
        "matched": matched,
        "score": round(best_score, 4),
        "device_id": best["rf_device_id"] if matched else None,
        "alert_id": raw_event.get("alert_id"),
        "press_coalesced": press_coalesced if matched else False,
    }


@router.get("/events")
async def list_events(limit: int = 100, user=Depends(require_admin)):
    items = await db.rf_events.find({}, {"_id": 0}).sort("received_at", -1).to_list(min(limit, 500))
    return items


# ---------------- Bridge polling endpoint ----------------

@router.get("/bridge/{kiosk_id}/pending")
async def bridge_pending(kiosk_id: str):
    """The Android bridge polls this to see if there's an active capture
    window it should run the SDR for. No auth required — but the bridge is
    expected to sign its responses (POST /listen/.../captured) with the
    kiosk's HMAC secret."""
    await mark_bridge_polled(kiosk_id)
    cap = await db.rf_captures.find_one(
        {"kiosk_id": kiosk_id, "status": {"$in": ["pending", "listening"]}},
        {"_id": 0},
        sort=[("started_at", -1)],
    )
    if not cap:
        return {"capture": None}
    # Mark as listening once the bridge picks it up
    if cap["status"] == "pending":
        await db.rf_captures.update_one(
            {"capture_id": cap["capture_id"]}, {"$set": {"status": "listening"}},
        )
        cap["status"] = "listening"
    return {"capture": _iso(cap)}
