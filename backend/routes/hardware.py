"""Hardware Devices — Blueprint [INF-004] capability-probe pipeline.

Endpoints implement the Device Class → Capability Profile → Compatibility
Probe → Hardware Receipt → Deployment Role → Blueprint Stack flow.

The actual probe RUNS on-device (Companion APK or bridge daemon). This
backend exposes:
  - the capability profile catalog (so the device knows what to probe)
  - probe submission endpoint (device posts results, backend mints receipt)
  - role-assignment endpoint (gated on a passing, non-expired receipt)
"""
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_admin, require_owner
from models import (
    HardwareDevice, HardwareDeviceCreate, HardwareReceipt, ProbeRequest,
    RoleAssignment, CapabilityProfile, ProbeResult, now_utc,
)

router = APIRouter(prefix="/hardware", tags=["hardware"])

RECEIPT_VALID_DAYS = 90

# Capability profile catalog. Every Device Class declares what it needs.
# Required capabilities must pass for a receipt to be `pass`. Optional
# capabilities are reported but don't gate the receipt.
CAPABILITY_PROFILES: dict = {
    "kiosk_tablet": {
        "required": ["far_field_mic", "speaker_quality", "wifi_ac", "persistent_power", "touchscreen"],
        "optional": ["usb_host", "bluetooth_le", "camera"],
    },
    "caos_hub": {
        "required": ["far_field_mic", "speaker_quality", "wifi_ac", "persistent_power", "touchscreen", "usb_host"],
        "optional": ["mesh_radio_subghz", "bluetooth_le", "camera", "haptic_feedback"],
    },
    "speaker_node": {
        "required": ["far_field_mic", "speaker_quality", "wifi_ac", "persistent_power"],
        "optional": ["bluetooth_le"],
    },
    "linux_bridge": {
        "required": ["wifi_ac", "persistent_power", "usb_host"],
        "optional": ["mesh_radio_subghz", "bluetooth_le"],
    },
    "wearable_gateway": {
        "required": ["wifi_ac", "battery_min_hours", "haptic_feedback"],
        "optional": ["bluetooth_le"],
    },
    "wall_terminal": {
        "required": ["touchscreen", "display_resolution_min", "wifi_ac", "persistent_power"],
        "optional": ["far_field_mic", "speaker_quality"],
    },
}

# Each Deployment Role's minimum capability set. Role assignment requires
# a passing receipt that satisfies ALL of these.
ROLE_REQUIREMENTS: dict = {
    "room_companion": ["far_field_mic", "speaker_quality", "wifi_ac", "persistent_power", "touchscreen"],
    "pendant_gateway": ["usb_host", "wifi_ac", "persistent_power"],
    "staff_pager_hub": ["bluetooth_le", "wifi_ac", "battery_min_hours"],
    "lobby_kiosk": ["touchscreen", "display_resolution_min", "persistent_power"],
    "medication_station": ["touchscreen", "camera", "far_field_mic", "persistent_power"],
}

# Each Deployment Role's auto-installed Blueprint stack. Used by the device
# on role-assign to know what services to enable.
BLUEPRINT_STACK: dict = {
    "room_companion": [
        "voice_loop_realtime", "barge_in_vad", "tv_auto_mute",
        "rest_sleep_protocol", "resident_memory_hydration",
    ],
    "pendant_gateway": [
        "rf_bridge_daemon", "rtl_433_decoder", "hmac_event_signer",
    ],
    "staff_pager_hub": [
        "alert_receipt_ws", "ptt_resident_to_staff", "task_list_view",
    ],
    "lobby_kiosk": [
        "wayfinding_display", "facility_directory", "visitor_check_in",
    ],
    "medication_station": [
        "medication_capture_camera", "voice_confirm_dispense", "audit_trail",
    ],
}


def _iso(doc: dict) -> dict:
    for k in ("created_at", "issued_at", "expires_at", "measured_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


def _sign_receipt(facility_id: str | None, payload: str) -> str:
    """Sign a receipt with a per-facility HMAC. Falls back to a process-level
    secret when no facility is set (single-tenant mode)."""
    secret = os.environ.get("RECEIPT_SIGNING_SECRET", "caos-care-dev-receipt").encode()
    if facility_id:
        secret = (secret.decode() + ":" + facility_id).encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


# ---------------- Capability profile catalog ----------------

@router.get("/profiles")
async def list_profiles(user=Depends(require_admin)):
    """Returns the capability profile per Device Class. The Companion APK
    and bridge daemon hit this on first launch to know what to probe."""
    return [
        CapabilityProfile(
            device_class=dc,
            required=p["required"],
            optional=p["optional"],
        ).model_dump() for dc, p in CAPABILITY_PROFILES.items()
    ]


@router.get("/roles")
async def list_roles(user=Depends(require_admin)):
    """Returns each Deployment Role's required capabilities + auto-installed
    Blueprint stack."""
    return [
        {
            "role": role,
            "required_capabilities": reqs,
            "blueprint_stack": BLUEPRINT_STACK.get(role, []),
        }
        for role, reqs in ROLE_REQUIREMENTS.items()
    ]


# ---------------- Devices CRUD ----------------

@router.get("/devices")
async def list_devices(user=Depends(require_admin)):
    items = await db.hardware_devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for i in items:
        _iso(i)
    return items


@router.post("/devices")
async def create_device(payload: HardwareDeviceCreate, user=Depends(require_admin)):
    d = HardwareDevice(**payload.model_dump())
    doc = d.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.hardware_devices.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.delete("/devices/{hw_id}")
async def delete_device(hw_id: str, user=Depends(require_owner)):
    res = await db.hardware_devices.delete_one({"hw_id": hw_id})
    if res.deleted_count == 0:
        raise HTTPException(404, detail="Device not found")
    return {"ok": True}


# ---------------- Probes & receipts ----------------

@router.post("/probe")
async def submit_probe(payload: ProbeRequest, user=Depends(require_admin)):
    """A device (or admin running the wizard) submits probe results.
    We score them against the Device Class's required capabilities,
    mint a HardwareReceipt, and update the device's last_receipt_status."""
    device = await db.hardware_devices.find_one({"hw_id": payload.hw_id}, {"_id": 0})
    if not device:
        raise HTTPException(404, detail="Hardware device not found")

    profile = CAPABILITY_PROFILES.get(device["device_class"], {"required": [], "optional": []})
    required = set(profile["required"])
    submitted_pass = {p.capability for p in payload.probes if p.result == "pass"}
    overall = "pass" if required.issubset(submitted_pass) else "fail"

    issued_at = now_utc()
    expires_at = issued_at + timedelta(days=RECEIPT_VALID_DAYS)
    probes_doc = []
    for p in payload.probes:
        d = p.model_dump()
        if d.get("measured_at") is None:
            d["measured_at"] = issued_at.isoformat()
        elif not isinstance(d["measured_at"], str):
            d["measured_at"] = d["measured_at"].isoformat()
        probes_doc.append(d)

    receipt = HardwareReceipt(
        hw_id=payload.hw_id,
        facility_id=device.get("facility_id"),
        device_class=device["device_class"],
        probes=[ProbeResult(**p) for p in probes_doc],
        overall=overall,
        issued_at=issued_at,
        expires_at=expires_at,
        issued_by=user.get("user_id") if isinstance(user, dict) else None,
    )
    rdoc = receipt.model_dump()
    rdoc["issued_at"] = rdoc["issued_at"].isoformat()
    rdoc["expires_at"] = rdoc["expires_at"].isoformat()
    rdoc["probes"] = probes_doc
    # Sign the canonical JSON of (hw_id, device_class, probes, expires_at)
    canon = f"{rdoc['hw_id']}|{rdoc['device_class']}|{rdoc['expires_at']}|{rdoc['overall']}"
    rdoc["signature"] = _sign_receipt(device.get("facility_id"), canon)
    await db.hardware_receipts.insert_one(rdoc)
    rdoc.pop("_id", None)

    # Reflect onto the device
    await db.hardware_devices.update_one(
        {"hw_id": payload.hw_id},
        {"$set": {
            "last_receipt_id": receipt.receipt_id,
            "last_receipt_status": overall,
        }},
    )
    return _iso(rdoc)


@router.get("/devices/{hw_id}/receipt")
async def get_current_receipt(hw_id: str, user=Depends(require_admin)):
    """Returns the most-recent receipt for a device, or 404 if never probed."""
    r = await db.hardware_receipts.find_one(
        {"hw_id": hw_id}, {"_id": 0}, sort=[("issued_at", -1)],
    )
    if not r:
        raise HTTPException(404, detail="No receipt — device has not been probed")
    return _iso(r)


@router.post("/assign-role")
async def assign_role(payload: RoleAssignment, user=Depends(require_admin)):
    """Assign a Deployment Role to a device. Gated on receipt: device must
    have a non-expired passing receipt that satisfies the role's required
    capabilities. This is the rule that enforces the Blueprint hard rule
    'No marketplace claim counts. Only a live hardware receipt proves
    deployment compatibility.'"""
    device = await db.hardware_devices.find_one({"hw_id": payload.hw_id}, {"_id": 0})
    if not device:
        raise HTTPException(404, detail="Device not found")

    receipt = await db.hardware_receipts.find_one(
        {"hw_id": payload.hw_id}, {"_id": 0}, sort=[("issued_at", -1)],
    )
    if not receipt:
        raise HTTPException(409, detail="Cannot assign role — device has no receipt. Run a compatibility probe first.")
    expires = receipt["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(409, detail="Cannot assign role — receipt is expired. Re-probe the device.")
    if receipt["overall"] != "pass":
        raise HTTPException(409, detail="Cannot assign role — receipt is FAILING. Required capabilities are missing.")

    role_required = set(ROLE_REQUIREMENTS.get(payload.deployment_role, []))
    capable = {p["capability"] for p in receipt["probes"] if p["result"] == "pass"}
    missing = role_required - capable
    if missing:
        raise HTTPException(
            409,
            detail=f"Cannot assign '{payload.deployment_role}' — missing capabilities: {sorted(missing)}",
        )

    await db.hardware_devices.update_one(
        {"hw_id": payload.hw_id},
        {"$set": {
            "deployment_role": payload.deployment_role,
            "deployment_room": payload.deployment_room,
        }},
    )
    return {
        "ok": True,
        "hw_id": payload.hw_id,
        "deployment_role": payload.deployment_role,
        "blueprint_stack": BLUEPRINT_STACK.get(payload.deployment_role, []),
    }
